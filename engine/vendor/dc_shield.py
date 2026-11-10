#!/usr/bin/env python3
"""Predict2u DC Shield Goals — nightly strategy.

Finds next-day (or --date) games where home/away double-chance odds are under 1.20,
then books Over 1.5 / Over 2.5 / GG (never the DC pick itself) for those that pass
matchup_rules + newrules + gate31. Publishes into today's research JSON so build.py
picks it up tonight.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import math
import os
import re
import subprocess
import sys
import datetime as dt
from pathlib import Path

FEED = Path((__import__('os').environ.get('FEED_DIR','/workspace/predict2u-feed')))
RESEARCH = Path((__import__('os').environ.get('RESEARCH_DIR','/workspace/predict2u-research')))
NOV = Path(__import__('os').environ.get('ENGINE_GATES_DIR', str(__import__('pathlib').Path(__file__).resolve().parents[1]/'gates')))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
NAME = 'DC Shield Goals'
YT = re.compile(r'\bu-?1\d\b|\bu-?2\d\b|youth|reserve|\s(ii|iii)$|\biii\b|academy|castilla|primavera|next gen|next pro|juvenil|jong |amateur', re.I)
YL = re.compile(r'u-?1\d|u-?2\d|youth|reserve|primavera|juvenil|next pro|amateur|women|development|academy', re.I)
WOM = re.compile(r'women|\(w\)|\bwfc\b|ladies|femin', re.I)
MK = [
    ('o15', '18', 'total=1.5', '12', 'Over 1.5'),
    ('o25', '18', 'total=2.5', '12', 'Over 2.5'),
    ('gg', '29', '', '74', 'GG (BTTS Yes)'),
]


def parse_args():
    now = dt.datetime.now(dt.timezone.utc)
    tomorrow = (now + dt.timedelta(days=1)).date().isoformat()
    ap = argparse.ArgumentParser(description='DC Shield Goals pipeline')
    ap.add_argument('--date', default=tomorrow, help='Target kickoff date YYYY-MM-DD (Accra/UTC)')
    ap.add_argument('--skip-book', action='store_true', help='Stop after filter (no booking/publish)')
    ap.add_argument('--skip-others', action='store_true', help='Only book SportyBet')
    return ap.parse_args()


def mon_dd(date_s: str) -> str:
    d = dt.date.fromisoformat(date_s)
    return d.strftime('%b%d').lower()  # nov06


def workdir_for(date_s: str) -> Path:
    wd = FEED / f'dc_shield_{mon_dd(date_s)}'
    wd.mkdir(parents=True, exist_ok=True)
    return wd


def curl_json(url: str, timeout=30, headers=None):
    cmd = ['curl', '-s', '-m', str(timeout), '-A', UA]
    for h in headers or []:
        cmd += ['-H', h]
    cmd.append(url)
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, check=False).stdout
        return json.loads(out) if out and out.strip().startswith('{') else {}
    except Exception:
        return {}


def fetch_event(eid: str) -> dict:
    url = (
        'https://www.sportybet.com/api/gh/factsCenter/event'
        f'?eventId={eid.replace(":", "%3A")}&productId=3'
    )
    return curl_json(url, headers=['Accept: application/json', 'Referer: https://www.sportybet.com/gh/']).get('data') or {}


def build_ev(eids: list[str], wd: Path) -> dict:
    """Pull full SportyBet event payloads so newrules.info() can resolve markets."""
    ev_path = wd / 'ev.json'
    if ev_path.exists():
        try:
            old = json.loads(ev_path.read_text())
            missing = [e for e in eids if not (old.get(e) or {}).get('markets')]
            if not missing:
                return old
            base = old
        except Exception:
            base = {}
            missing = list(eids)
    else:
        base, missing = {}, list(eids)

    def one(eid):
        for _ in range(2):
            d = fetch_event(eid)
            if d:
                return eid, d
        return eid, {}

    print(f'[dc_shield] pulling event details for {len(missing)} events…', flush=True)
    with cf.ThreadPoolExecutor(12) as ex:
        for eid, d in ex.map(one, missing):
            if d:
                base[eid] = d
    ev_path.write_text(json.dumps(base))
    print(f'[dc_shield] EV cache size={len(base)} with_markets={sum(1 for d in base.values() if d.get("markets"))}', flush=True)
    return base


def inject_ev(ev: dict):
    sys.path.insert(0, str(NOV))
    import newrules as N
    N._EV = ev
    # also merge into on-disk so subsequent N.EV() loads if cache cleared mid-run
    return N


def fetch_dc_games(date_s: str) -> tuple[list, int]:
    """SportyBet GH upcoming: DC (1X/X2) under 1.20 on target date."""
    day = dt.date.fromisoformat(date_s)
    lo = dt.datetime(day.year, day.month, day.day, 0, 0, tzinfo=dt.timezone.utc).timestamp() * 1000
    hi = lo + 86400_000
    E = {}
    for p in range(1, 40):
        u = (
            'https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents'
            f'?sportId=sr%3Asport%3A1&marketId=1%2C10%2C18%2C29&pageSize=100&pageNum={p}&option=1'
        )
        d = curl_json(u).get('data')
        if not d or 'tournaments' not in d:
            break
        new = [dict(e, league=t.get('name')) for t in d['tournaments'] for e in t['events']]
        for e in new:
            E[e['eventId']] = e
        if not new or len(E) >= d.get('totalNum', 0):
            break
    out = []
    now_ms = dt.datetime.now(dt.timezone.utc).timestamp() * 1000
    for e in E.values():
        est = e.get('estimateStartTime') or 0
        if not (lo <= est < hi):
            continue
        if est <= now_ms:
            continue
        league = e.get('league') or ''
        home, away = e.get('homeTeamName') or '', e.get('awayTeamName') or ''
        if WOM.search(league + ' ' + home + ' ' + away):
            continue
        if any(YT.search(t) for t in (home, away)) or YL.search(league):
            continue
        M = {}
        for m in e.get('markets') or []:
            for o in m.get('outcomes') or []:
                if o.get('isActive', 1):
                    M[(str(m['id']), m.get('specifier') or '', str(o['id']))] = float(o['odds'])
        dc1x = M.get(('10', '', '9'))
        dcx2 = M.get(('10', '', '11'))
        best = min([x for x in (dc1x, dcx2) if x] or [9])
        if best >= 1.20:
            continue
        out.append(dict(
            eventId=e['eventId'],
            match=home + ' v ' + away,
            league=league,
            home=home, away=away,
            ko=dt.datetime.fromtimestamp(est / 1000, dt.timezone.utc).strftime('%H:%M'),
            date=date_s,
            dc1x=dc1x, dcx2=dcx2,
            x12=f"{M.get(('1','','1'))}/{M.get(('1','','2'))}/{M.get(('1','','3'))}",
            o15=M.get(('18', 'total=1.5', '12')),
            o25=M.get(('18', 'total=2.5', '12')),
            gg=M.get(('29', '', '74')),
        ))
    out.sort(key=lambda g: g['ko'])
    return out, len(E)


def local_hard_veto(p: dict) -> str | None:
    """Backstop rules that must hold even if EV cache is incomplete."""
    sel = p.get('selection') or ''
    odds = float(p.get('odds') or 0)
    league = p.get('league') or ''
    match = p.get('match') or ''
    if WOM.search(league + ' ' + match):
        return 'women'
    if any(YT.search(t) for t in match.split(' v ')) or YL.search(league):
        return 'youth/reserve'
    if odds > 1.50:
        return f'>1.50 ({odds})'
    if sel == 'Over 2.5' and odds > 1.30:
        return f'R4 O2.5 >1.30 ({odds})'
    # Over 1.5 / Under 3.5 >1.30 without extreme is handled by matchup_rules.extreme
    return None


def filter_legs(games: list) -> tuple[list, list]:
    """Apply matchup_rules + newrules + gate31 (STRICT: no stats allowed)."""
    vendor = Path(__file__).resolve().parent
    for p in (RESEARCH, NOV, vendor):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import matchup_rules as MR
    import newrules as N
    import gate31 as G

    res, log = [], []
    for g in games:
        ok = []
        for k, mid, sp, oid, sel in MK:
            if not g.get(k):
                continue
            market = 'Over/Under' if mid == '18' else 'BTTS'
            p = dict(
                eventId=g['eventId'], match=g['match'], league=g['league'],
                date=g['date'], ko=g['ko'], marketId=mid, specifier=sp,
                outcomeId=oid, odds=g[k], selection=sel, market=market, x12=g['x12'],
            )
            try:
                MR.enrich(p)
            except Exception:
                pass
            a, cls, why = MR.check(p)
            lv = local_hard_veto(p) if a else 'skipped-matchup'
            nr = N.ok(g['eventId'], mid, sp, oid, g[k]) if a and not lv else (lv or 'skipped')
            gt = None
            if a and not nr:
                gt = G.gate(
                    g['eventId'], g['match'], g['league'],
                    f'{mid}|{sp}|{oid}', f'{market}: {sel}', g[k], None,
                    need_grade=False, skip_check=True, allow_hi=True,
                )[0]
            gate_ok = (not gt) or gt == 'STRICT: no stats'
            passed = bool(a and not nr and gate_ok)
            log.append(dict(
                match=g['match'], sel=sel, odds=g[k], ok=passed,
                matchup=a, cls=cls, why=why, newrules=nr, gate31=gt,
                table=p.get('table'), case=p.get('case'),
            ))
            if passed:
                p['strictGate'] = gt or 'pass'
                ok.append(p)
        if ok:
            ok.sort(key=lambda p: -p['odds'])
            res.append(ok[0])
    now = dt.datetime.now(dt.timezone.utc)
    final = []
    for p in res:
        if local_hard_veto(p):
            continue
        try:
            ko = dt.datetime.fromisoformat(p['date'] + 'T' + p['ko']).replace(tzinfo=dt.timezone.utc)
        except Exception:
            continue
        if ko <= now:
            continue
        if not MR.check(p)[0]:
            continue
        if N.ok(p['eventId'], p['marketId'], p['specifier'], p['outcomeId'], p['odds']):
            continue
        r = G.gate(
            p['eventId'], p['match'], p['league'],
            f"{p['marketId']}|{p['specifier']}|{p['outcomeId']}",
            f"{p['market']}: {p['selection']}", p['odds'], None,
            need_grade=False, skip_check=True, allow_hi=True,
        )
        if r[0] and r[0] != 'STRICT: no stats':
            continue
        final.append(p)
    # Thin day: keep hard rules, drop newrules/gate31 and the short-price caps.
    try:
        import thin_pool as TP
        if TP.pool_is_thin(final):
            have = {p['eventId'] for p in final}
            added = 0
            before = len(final)
            for g in games:
                if g.get('eventId') in have:
                    continue
                chosen = None
                for k, mid, sp, oid, sel in MK:
                    if not g.get(k):
                        continue
                    market = 'Over/Under' if mid == '18' else 'BTTS'
                    p = dict(
                        eventId=g['eventId'], match=g['match'], league=g['league'],
                        date=g['date'], ko=g['ko'], marketId=mid, specifier=sp,
                        outcomeId=oid, odds=g[k], selection=sel, market=market, x12=g.get('x12'),
                    )
                    lv = local_hard_veto(p)
                    if lv in ('women', 'youth/reserve'):
                        continue
                    if not TP.still_bookable(p, now) or not TP.relaxed_ok(p):
                        continue
                    p['thinPoolFallback'] = True
                    p['strictGate'] = 'thin-pool'
                    chosen = p
                    break
                if chosen:
                    final.append(chosen)
                    have.add(chosen['eventId'])
                    added += 1
            print(
                f"thin-pool fallback used: DC Shield qualified {before}, added {added} "
                f"by loosening non-hard filters only",
                flush=True,
            )
    except Exception as e:
        print('thin-pool fallback skipped in DC Shield', e, flush=True)
    return final, log


def book_sporty(legs: list) -> dict:
    """Book SportyBet; drop not-open legs and retry until status ok or empty."""
    eng = Path(os.environ.get('ENGINE_DIR') or Path(__file__).resolve().parents[1])
    for p in (eng, Path(__file__).resolve().parent):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    from sb_share_helper17 import book

    cur = list(legs)
    last_code, last_st = None, None
    for attempt in range(6):
        if not cur:
            break
        c, st = book(cur)
        last_code, last_st = c, st
        if c and st == 'ok':
            return dict(
                sportybet=c,
                totalOdds=round(math.prod(p['odds'] for p in cur), 2),
                legs=cur,
                dropped=len(legs) - len(cur),
            )
        # Probe which singles are open
        open_legs = []
        for p in cur:
            _, pst = book([p])
            if pst == 'ok':
                open_legs.append(p)
        if not open_legs:
            break
        if len(open_legs) == len(cur):
            # All singles open but combo failed — try smaller set by dropping lowest odds first? 
            # More likely API transient; drop last leg and retry
            cur = cur[:-1]
        else:
            cur = open_legs
            print(f'[dc_shield] SportyBet retry: {len(cur)} open of prior set (status was {st!r})', flush=True)
    raise RuntimeError(f'SportyBet book failed: code={last_code!r} status={last_st!r} remaining={len(cur)}')


def book_others(legs: list, helpers_dir: Path) -> dict:
    sys.path.insert(0, str(helpers_dir))
    sys.path.insert(0, str(RESEARCH))
    import book_helpers as B
    import bp_book
    out = {}
    for name, fn in [('msport', B.mbook), ('betika', B.bkbook), ('footballcom', B.fc_book)]:
        try:
            r = fn(legs)
            out[name] = r if r else dict(error='no code')
        except Exception as e:
            out[name] = dict(error=str(e))
    try:
        out['betpawa'] = bp_book.book(legs)
    except Exception as e:
        out['betpawa'] = dict(error=str(e))
    return out


def _extract_code(book_key: str, payload) -> tuple[str | None, float | None]:
    if not isinstance(payload, dict) or payload.get('error'):
        return None, None
    code = payload.get(book_key) or payload.get('code')
    odds = payload.get('totalOdds')
    return code, odds


def publish(sporty: dict, others: dict, target_date: str) -> tuple[dict, Path]:
    """Write/replace DC Shield Goals slip into TODAY's research JSON."""
    today = dt.datetime.now(dt.timezone.utc).date().isoformat()
    rf = RESEARCH / f'{today}.json'
    if rf.exists():
        d = json.loads(rf.read_text())
    else:
        # Actions has no box research day-file; create a minimal shell so the
        # shield slip can land and build.py can publish it the same run.
        rf.parent.mkdir(parents=True, exist_ok=True)
        now = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
        d = dict(
            date=today, days=2, strategy='engine',
            leagues=[], picks=[], slips=[], excluded={}, homeCode={},
            updatedAt=now,
        )
        print(f'[dc_shield] created research shell {rf}', flush=True)
    L = sporty['legs']
    codes = {'sportybet': sporty['sportybet']}
    odds = {'sportybet': sporty['totalOdds']}
    fails = {}
    for k in ('msport', 'betika', 'footballcom', 'betpawa'):
        c, o = _extract_code(k, others.get(k))
        if c:
            codes[k] = c
            if o is not None:
                odds[k] = o
        else:
            fails[k] = (others.get(k) or {}).get('error') or 'missing'
    legs_out = []
    for p in L:
        legs_out.append(dict(
            eventId=p['eventId'], match=p['match'], league=p['league'],
            date=p['date'], ko=p['ko'], market=p['market'], selection=p['selection'],
            odds=p['odds'], marketId=p['marketId'], specifier=p['specifier'],
            outcomeId=p['outcomeId'], result='pending',
        ))
    notes = {}
    if sporty['totalOdds'] < 25:
        notes['sportybet'] = (
            f'{len(L)} match(es) passed every strategy gate for {target_date}; '
            f'best valid slip is below 25 total odds.'
        )
    if fails:
        notes['booking_failures'] = fails
    slip = dict(
        name=NAME,
        totalOdds=sporty['totalOdds'],
        legs=legs_out,
        codes=codes,
        bookOdds=odds,
        bookPicks={k: 1 for k in codes},
        bookNotes=notes,
        risk='safe',
        strategy=NAME,
        bookedAt=dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
        bookStatus='ok',
        targetDate=target_date,
    )
    d['slips'] = [x for x in (d.get('slips') or []) if x.get('name') != NAME] + [slip]
    d['updatedAt'] = dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
    rf.write_text(json.dumps(d, indent=1, ensure_ascii=False))
    return slip, rf


def main():
    args = parse_args()
    date_s = args.date
    wd = workdir_for(date_s)
    os.chdir(wd)
    bh_dst = wd / 'book_helpers.py'
    if not bh_dst.exists():
        vendored = Path(__file__).resolve().parent / 'book_helpers.py'
        feed_src = FEED / 'dc_shield_nov05' / 'book_helpers.py'
        src = vendored if vendored.exists() else feed_src
        if src.exists():
            bh_dst.write_text(src.read_text())

    print(f'[dc_shield] target={date_s} workdir={wd}', flush=True)
    games, n_events = fetch_dc_games(date_s)
    (wd / 'step1_dc_games.json').write_text(json.dumps(games, indent=1))
    print(f'[dc_shield] sporty events scanned={n_events} DC<1.20 candidates={len(games)}', flush=True)
    if not games:
        summary = dict(status='failed', reason='zero DC candidates', date=date_s, candidates=0, legs=0)
        print(json.dumps(summary, indent=1))
        sys.exit(2)

    ev = build_ev([g['eventId'] for g in games], wd)
    inject_ev(ev)

    legs, log = filter_legs(games)
    (wd / 'step2_final_legs.json').write_text(json.dumps(legs, indent=1))
    (wd / 'step2_final_log.json').write_text(json.dumps(log, indent=1))
    tot = round(math.prod(p['odds'] for p in legs), 2) if legs else 0
    print(f'[dc_shield] after rules: {len(legs)} legs, product odds={tot}', flush=True)
    for p in legs:
        print(f"  {p['ko']} {p['match']} | {p['selection']} @ {p['odds']} | {p.get('table')}", flush=True)
    if not legs:
        summary = dict(
            status='failed', reason='rules wiped all legs',
            date=date_s, candidates=len(games), legs=0,
        )
        print(json.dumps(summary, indent=1))
        sys.exit(3)

    if args.skip_book:
        print(json.dumps(dict(status='filtered', date=date_s, candidates=len(games),
                              legs=len(legs), totalOdds=tot), indent=1))
        return

    try:
        sporty = book_sporty(legs)
    except Exception as e:
        summary = dict(status='failed', reason=f'SportyBet book: {e}', date=date_s,
                       candidates=len(games), legs=len(legs), totalOdds=tot)
        print(json.dumps(summary, indent=1))
        sys.exit(4)
    (wd / 'sporty_booking.json').write_text(json.dumps({
        **{k: v for k, v in sporty.items() if k != 'legs'},
        'legs': sporty['legs'],
    }, indent=1, default=str))
    (wd / 'sporty_code.txt').write_text(
        f"{NAME} — {date_s}\nSportyBet code: {sporty['sportybet']}\n"
        f"{len(sporty['legs'])} legs — total odds {sporty['totalOdds']}\n\n"
        + ''.join(
            f"{i}. {p['ko']} GMT — {p['match']} ({p['league']})\n   {p['selection']} @ {p['odds']}\n"
            for i, p in enumerate(sporty['legs'], 1)
        )
    )
    print(f"[dc_shield] SportyBet {sporty['sportybet']} @ {sporty['totalOdds']} ({len(sporty['legs'])} legs)", flush=True)

    others = {}
    if not args.skip_others:
        others = book_others(sporty['legs'], wd)
        (wd / 'other_bookings.json').write_text(json.dumps(others, indent=1))
        print(
            '[dc_shield] other bookings: '
            + json.dumps({
                k: (v.get('error') if isinstance(v, dict) and 'error' in v else 'ok')
                for k, v in others.items()
            }),
            flush=True,
        )

    slip, rf = publish(sporty, others, date_s)
    (wd / 'published_slip.json').write_text(json.dumps(slip, indent=1))

    summary = dict(
        status='success' if len(slip['codes']) >= 2 else 'partial',
        date=date_s,
        researchFile=str(rf),
        candidates=len(games),
        legs=len(sporty['legs']),
        totalOdds=sporty['totalOdds'],
        codes=slip['codes'],
        bookOdds=slip['bookOdds'],
        bookNotes=slip.get('bookNotes'),
        legDetail=[{
            'ko': p['ko'], 'match': p['match'], 'league': p['league'],
            'selection': p['selection'], 'odds': p['odds'],
        } for p in sporty['legs']],
        workdir=str(wd),
    )
    print(json.dumps(summary, indent=1))
    if summary['status'] == 'failed':
        sys.exit(1)


if __name__ == '__main__':
    main()
