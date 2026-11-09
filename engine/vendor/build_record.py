#!/usr/bin/env python3
"""Build public Track record (record.json) from settled booking codes.

Sources (merged, never delete history):
  1) FEED_DIR/code-ledger.json (box legacy)
  2) ENGINE_DIR/code-ledger.json
  3) RESEARCH_DIR/code-ledger.json  (engine/data — persisted on Actions)
  4) REPO/staked-codes.json
  5) REPO/high_odds.json  (active + history)
  6) Fully settled slips still lingering in home-picks / picks / hot-picks

Writes RESEARCH_DIR/code-ledger.json so GitHub Actions keep a durable ledger.
"""
from __future__ import annotations
import json, os, sys, datetime as dt
from collections import defaultdict
from pathlib import Path

FEED = Path(os.environ.get('FEED_DIR') or '/workspace/predict2u-feed')
REPO = Path(sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('REPO_DIR') or '/workspace/Predict2u'))
ENGINE = Path(os.environ.get('ENGINE_DIR') or (REPO / 'engine'))
RESEARCH = Path(os.environ.get('RESEARCH_DIR') or (ENGINE / 'data'))
STAKE = 10.0

SETTLED = frozenset({'won', 'lost'})


def _read_json(path: Path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def _leg_results(legs):
    return [(l.get('result') or 'pending').lower() for l in (legs or []) if isinstance(l, dict)]


def _derive_status(entry: dict) -> str:
    st = (entry.get('status') or '').lower()
    if st in SETTLED:
        return st
    legs = entry.get('legs') or []
    results = _leg_results(legs)
    if results and all(r in ('won', 'lost', 'void', 'push') for r in results):
        if 'lost' in results:
            return 'lost'
        if any(r == 'won' for r in results) or all(r in ('void', 'push') for r in results):
            return 'won' if any(r == 'won' for r in results) else 'void'
    return st or 'pending'


def _key(book, code):
    book = (book or 'sportybet').lower().replace('.com', 'com')
    code = str(code or '').strip().upper()
    if not code:
        return None
    return f'{book}:{code}'


def _norm_entry(raw: dict, default_book='sportybet') -> dict | None:
    if not isinstance(raw, dict):
        return None
    code = raw.get('code')
    if not code and isinstance(raw.get('codes'), dict):
        code = raw['codes'].get('sportybet') or next(iter(raw['codes'].values()), None)
        if isinstance(code, list):
            code = (code[0].get('code') if code and isinstance(code[0], dict) else code[0]) if code else None
    book = raw.get('book') or raw.get('bookmaker') or default_book
    if isinstance(book, dict):
        book = book.get('id') or book.get('name') or default_book
    k = _key(book, code)
    if not k:
        return None
    legs = raw.get('legs') or raw.get('legList') or []
    status = _derive_status({**raw, 'legs': legs})
    odds = raw.get('odds') or raw.get('totalOdds') or raw.get('total')
    try:
        odds = float(odds) if odds is not None else None
    except Exception:
        odds = None
    hit = raw.get('hit')
    if hit is None and legs:
        hit = sum(1 for l in legs if isinstance(l, dict) and (l.get('result') or '').lower() == 'won')
    return {
        'code': str(code).upper(),
        'book': str(book).lower(),
        'date': str(raw.get('date') or '')[:10] or None,
        'name': raw.get('name') or raw.get('label') or raw.get('title') or 'Slip',
        'kind': raw.get('kind') or raw.get('risk') or 'slip',
        'odds': odds,
        'firstSeen': raw.get('firstSeen') or raw.get('bookedAt') or raw.get('settledAt'),
        'legs': legs,
        'hit': hit,
        'total': raw.get('total') or len(legs),
        'status': status if status != 'void' else 'lost',  # void slips count as lost for ROI tables
        'settled': raw.get('settled') or raw.get('settledAt'),
        'risk': raw.get('risk') or raw.get('riskLabel'),
    }


def _ingest_map(acc: dict, entries):
    for raw in entries or []:
        e = _norm_entry(raw) if not (isinstance(raw, tuple) and len(raw) == 2) else None
        if isinstance(raw, tuple):
            continue
        if e is None and isinstance(raw, dict):
            e = _norm_entry(raw)
        if not e:
            continue
        k = _key(e['book'], e['code'])
        prev = acc.get(k)
        if not prev:
            acc[k] = e
            continue
        # Prefer richer / more settled copy
        prev_st = prev.get('status')
        new_st = e.get('status')
        if prev_st not in SETTLED and new_st in SETTLED:
            acc[k] = e
        elif (len(e.get('legs') or []) >= len(prev.get('legs') or [])
              and (e.get('odds') or 0) >= (prev.get('odds') or 0)):
            # keep settled status if previous had it
            if prev_st in SETTLED and new_st not in SETTLED:
                e = dict(e); e['status'] = prev_st
            acc[k] = e


def harvest_sources() -> dict:
    acc: dict = {}

    # 1–3) existing ledgers
    for path in (
        FEED / 'code-ledger.json',
        ENGINE / 'code-ledger.json',
        RESEARCH / 'code-ledger.json',
        REPO / 'code-ledger.json',
    ):
        data = _read_json(path)
        if isinstance(data, dict):
            _ingest_map(acc, data.values())
        elif isinstance(data, list):
            _ingest_map(acc, data)

    # 4) staked-codes
    sc = _read_json(REPO / 'staked-codes.json')
    if isinstance(sc, dict):
        codes = sc.get('codes')
        if isinstance(codes, dict):
            _ingest_map(acc, codes.values())
        elif isinstance(codes, list):
            _ingest_map(acc, codes)

    # 5) high_odds active + history
    ho = _read_json(REPO / 'high_odds.json')
    if isinstance(ho, dict):
        _ingest_map(acc, ho.get('history') or [])
        _ingest_map(acc, ho.get('slips') or [])

    # 6) live section files — only fully settled slips (in case prune has not run yet)
    for name in ('home-picks.json', 'picks.json', 'hot-picks.json'):
        doc = _read_json(REPO / name)
        if not isinstance(doc, dict):
            continue
        for s in doc.get('slips') or []:
            if not isinstance(s, dict):
                continue
            st = _derive_status(s)
            if st in SETTLED:
                # expand per-book codes when present
                codes = s.get('codes')
                if isinstance(codes, dict) and codes:
                    for book, code in codes.items():
                        if isinstance(code, list):
                            code = (code[0].get('code') if code and isinstance(code[0], dict) else code[0]) if code else None
                        if not code:
                            continue
                        ent = dict(s)
                        ent['book'] = book
                        ent['code'] = code
                        ent['status'] = st
                        _ingest_map(acc, [ent])
                else:
                    ent = dict(s)
                    ent['status'] = st
                    _ingest_map(acc, [ent])

    return acc


def persist_ledger(acc: dict) -> Path:
    RESEARCH.mkdir(parents=True, exist_ok=True)
    path = RESEARCH / 'code-ledger.json'
    # Keep a compact but complete ledger for Actions
    body = json.dumps(acc, ensure_ascii=False, separators=(',', ':'))
    old = path.read_text() if path.exists() else None
    if old != body:
        path.write_text(body)
    return path


def slip_type(e):
    name = (e.get('name') or '').lower()
    kind = (e.get('kind') or 'slip').lower()
    if 'safe slip' in name or e.get('risk') == 'safe': return 'safe'
    if 'medium slip' in name or e.get('risk') == 'medium': return 'medium'
    if kind == 'banker' or 'banker' in name: return 'banker'
    if kind == 'alt' or 'alternative' in name or 'steady' in name: return 'alternative'
    if kind == 'market': return 'market'
    if kind == 'all' or 'all-picks' in name: return 'all-picks'
    if kind == 'hot' or 'hot' in name: return 'hot'
    if 'high risk' in name or e.get('risk') in ('high', 'HIGH RISK'): return 'high-odds'
    return kind or 'slip'


def market_of(e):
    name = e.get('name') or ''
    if e.get('kind') == 'market':
        return name.split(' (')[0].strip() or 'Market'
    legs = e.get('legs') or []
    if not legs: return 'Other'
    sels = [str(l.get('selection') or '') for l in legs]
    def bucket(s):
        sl = s.lower()
        if sl.startswith('over '): return 'Over ' + s.split(' ', 1)[1] if ' ' in s else 'Over'
        if sl.startswith('under '): return 'Under ' + s.split(' ', 1)[1] if ' ' in s else 'Under'
        if ' or draw' in sl or ' or ' in sl: return 'Double chance'
        if sl in ('draw', 'x'): return 'Draw'
        if 'btts' in sl or 'both teams' in sl or sl in ('gg', 'yes', 'no'): return 'BTTS'
        return 'Match result / other'
    from collections import Counter
    c = Counter(bucket(s) for s in sels)
    return c.most_common(1)[0][0]


def roi_block(rows):
    n = len(rows)
    if not n: return dict(n=0, won=0, lost=0, winRate=None, staked=0, returned=0, profit=0, roi=None)
    won = sum(1 for r in rows if r['status'] == 'won')
    lost = n - won
    staked = STAKE * n
    returned = sum(STAKE * float(r.get('odds') or 0) for r in rows if r['status'] == 'won')
    profit = round(returned - staked, 2)
    return dict(
        n=n, won=won, lost=lost,
        winRate=round(100.0 * won / n, 1),
        stake=STAKE, staked=round(staked, 2), returned=round(returned, 2),
        profit=profit, roi=round(100.0 * profit / staked, 1) if staked else None,
    )


def streak(sorted_rows):
    cur = best_w = best_l = 0
    cur_kind = None
    seq = 0
    for r in sorted_rows:
        st = r['status']
        if st == cur_kind: seq += 1
        else: cur_kind = st; seq = 1
        if st == 'won': best_w = max(best_w, seq)
        if st == 'lost': best_l = max(best_l, seq)
    cur_st = sorted_rows[-1]['status'] if sorted_rows else None
    cur_n = 0
    for r in reversed(sorted_rows):
        if r['status'] != cur_st: break
        cur_n += 1
    return dict(current=cur_st, currentLen=cur_n, bestWin=best_w, bestLoss=best_l)


def build():
    acc = harvest_sources()
    ledger_path = persist_ledger(acc)
    codes = list(acc.values())
    settled = [e for e in codes if e.get('status') in SETTLED]
    pending = sum(1 for e in codes if e.get('status') == 'pending')

    distinct = {}
    for e in settled:
        key = (e.get('date'), e.get('name'), e.get('total') or len(e.get('legs') or []))
        if key not in distinct or e.get('book') == 'sportybet':
            distinct[key] = e
    distinct_rows = list(distinct.values())

    by_type = defaultdict(list)
    by_book = defaultdict(list)
    by_market = defaultdict(list)
    by_day = defaultdict(list)
    for e in settled:
        by_type[slip_type(e)].append(e)
        by_book[e.get('book') or 'unknown'].append(e)
        by_market[market_of(e)].append(e)
        by_day[e.get('date') or 'unknown'].append(e)

    d_type = defaultdict(list); d_day = defaultdict(list)
    for e in distinct_rows:
        d_type[slip_type(e)].append(e)
        d_day[e.get('date') or 'unknown'].append(e)

    chrono = sorted(distinct_rows, key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''))
    recent = sorted(settled, key=lambda e: (e.get('date') or '', e.get('firstSeen') or ''), reverse=True)

    picks = {}
    for e in codes:
        for l in e.get('legs') or []:
            r = (l.get('result') or '').lower()
            if r not in ('won', 'lost'): continue
            k = (e.get('date'), l.get('match'), l.get('selection'))
            picks[k] = r
    pw = sum(1 for r in picks.values() if r == 'won')
    pl = sum(1 for r in picks.values() if r == 'lost')

    def pack(groups):
        out = []
        for k, rows in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            b = roi_block(rows); b['key'] = k; out.append(b)
        return out

    overall = roi_block(distinct_rows)
    overall_codes = roi_block(settled)

    out = dict(
        DATA_UPDATED=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        stakeCurrency='GHS',
        flatStake=STAKE,
        note='Figures use only settled booking codes from our published slips. Pending codes are excluded. ROI assumes a flat GH₵10 stake on every settled code (no cash-out). The same slip booked on several sites is counted once in the headline, and once per site in the by-site table.',
        overall=dict(
            **overall,
            pending=pending,
            codesSettled=overall_codes['n'],
            codesWon=overall_codes['won'],
            codesLost=overall_codes['lost'],
        ),
        streak=streak(chrono),
        byType=pack(d_type),
        bySite=pack(by_book),
        byMarket=pack(by_market),
        byDay=[{**roi_block(by_day[d]), 'key': d} for d in sorted(by_day.keys(), reverse=True)],
        picks=dict(settled=pw + pl, won=pw, lost=pl, winRate=round(100.0 * pw / (pw + pl), 1) if (pw + pl) else None),
        recent=[dict(
            code=e.get('code'), book=e.get('book'), date=e.get('date'), name=e.get('name'),
            kind=slip_type(e), odds=e.get('odds'), status=e.get('status'),
            hit=e.get('hit'), total=e.get('total'),
            profit=round(STAKE * float(e['odds']) - STAKE, 2) if e.get('status') == 'won' and e.get('odds') else -STAKE,
            legs=[{
                'match': l.get('match'), 'selection': l.get('selection'),
                'odds': l.get('odds'), 'result': l.get('result'), 'score': l.get('score'),
            } for l in (e.get('legs') or []) if isinstance(l, dict)][:40],
        ) for e in recent[:40]],
        ledgerPath=str(ledger_path.relative_to(REPO)) if str(ledger_path).startswith(str(REPO)) else str(ledger_path),
    )
    path = REPO / 'record.json'
    body = json.dumps(out, indent=1, ensure_ascii=False)
    old = path.read_text() if path.exists() else None
    changed = old != body
    if changed:
        path.write_text(body)
    print('record', 'wrote' if changed else 'unchanged', 'settled_slips', overall['n'],
          'winRate', overall['winRate'], 'roi', overall['roi'], 'pending', pending,
          'ledger', len(acc), '->', ledger_path)
    return changed


if __name__ == '__main__':
    build()
