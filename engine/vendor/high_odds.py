#!/usr/bin/env python3
"""Verify, publish and settle Predict2u's High Odds code board.

Public labels never expose an import source. Candidate sources are the house
research slips, approved local exports, and SportyBet's public featured hub.
Only decoded SportyBet football shares without double chance are accepted.
Other rule failures remain high-risk signals, not a publishing filter.
"""
from __future__ import annotations
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

REPO = Path(sys.argv[1] if len(sys.argv) > 1 else (__import__('os').environ.get('REPO_DIR','/workspace/Predict2u')))
FEED = Path((__import__('os').environ.get('FEED_DIR','/workspace/predict2u-feed')))
RESEARCH = Path((__import__('os').environ.get('RESEARCH_DIR','/workspace/predict2u-research')))
EXPORTS = Path((__import__('os').environ.get('INBOX_PARENT', (__import__('os').environ.get('ENGINE_DIR','')+'/inbox') if __import__('os').environ.get('ENGINE_DIR') else '/workspace/picks_export')))
OUT = REPO / 'high_odds.json'
CACHE = FEED / 'high-odds-cache.json'
BOOK_CACHE = FEED / 'high-odds-books.json'
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
SETTLE_ONLY = '--settle-only' in sys.argv
sys.path.insert(0, str(RESEARCH))
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
HEADERS = ['-A', UA, '-H', 'Accept: application/json, text/plain, */*', '-H', 'Accept-Language: en-GB,en;q=0.9', '-H', 'Referer: https://www.sportybet.com/gh/']


def get_json(url, timeout=25):
    r = subprocess.run(['curl', '-sS', '--max-time', str(timeout), *HEADERS, url], capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError('request failed')
    return json.loads(r.stdout)


def load(path, default):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return default


def save(path, data, pretty=True):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1 if pretty else None, separators=None if pretty else (',', ':')) + ('\n' if pretty else ''))


def iso_ms(ms):
    if not ms:
        return None
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def code_key(book, code):
    return f'{book}:{str(code).upper()}'


def leg_fingerprint(legs):
    raw = [(x.get('eventId'), str(x.get('marketId')), x.get('specifier') or '', str(x.get('outcomeId'))) for x in legs]
    return hashlib.sha256(json.dumps(sorted(raw)).encode()).hexdigest()[:20]


def original_index(raw_legs):
    out = {}
    for p in raw_legs or []:
        if p.get('match') and p.get('selection'):
            out[('match', str(p['match']).lower().replace(' vs ', ' v '), str(p['selection']).lower())] = p
        key = (p.get('eventId'), str(p.get('marketId')), p.get('specifier') or '', str(p.get('outcomeId')))
        if key[0]:
            out[key] = p
    return out


def decode(code):
    d = get_json(f'https://www.sportybet.com/api/gh/orders/share/{code}')
    if d.get('bizCode') != 10000 or not isinstance(d.get('data'), dict):
        raise RuntimeError('share unavailable')
    return d['data']


def decoded_legs(data, original=None):
    original = original_index(original)
    selections = {(s.get('eventId'), str(s.get('marketId')), s.get('specifier') or '', str(s.get('outcomeId'))) for s in (data.get('ticket') or {}).get('selections') or []}
    legs = []
    for o in data.get('outcomes') or []:
        if o.get('sport', {}).get('id') != 'sr:sport:1':
            continue
        for m in o.get('markets') or []:
            for oc in m.get('outcomes') or []:
                key = (o.get('eventId'), str(m.get('id')), m.get('specifier') or '', str(oc.get('id')))
                if selections and key not in selections:
                    continue
                start = iso_ms(o.get('estimateStartTime'))
                stamp = dt.datetime.fromisoformat(start.replace('Z', '+00:00')) if start else NOW
                cat = o.get('sport', {}).get('category') or {}
                league = ' - '.join(x for x in (cat.get('name'), (cat.get('tournament') or {}).get('name')) if x)
                old = original.get(key) or original.get(('match', f"{o.get('homeTeamName')} v {o.get('awayTeamName')}".lower(), str(oc.get('desc')).lower())) or {}
                status = o.get('matchStatus') or 'Not start'
                winning = oc.get('isWinning')
                if status in ('Cancelled', 'Postponed', 'Abandoned') or oc.get('refundFactor') not in (None, 0, 0.0):
                    result = 'void'
                elif status == 'Ended' and winning is not None:
                    result = 'won' if winning == 1 else 'lost'
                else:
                    result = 'pending'
                live_odds = float(oc.get('odds') or 0)
                booked_odds = float(old.get('odds') or 0) or live_odds or None
                legs.append(dict(
                    eventId=o.get('eventId'), marketId=str(m.get('id')), specifier=m.get('specifier') or '', outcomeId=str(oc.get('id')),
                    date=stamp.date().isoformat(), ko=stamp.strftime('%H:%M'), kickoff=start,
                    league=league, match=f"{o.get('homeTeamName')} v {o.get('awayTeamName')}",
                    market=m.get('desc'), selection=oc.get('desc'), odds=booked_odds, liveOdds=live_odds or None,
                    result=result, matchStatus=status, score=o.get('setScore') or None, played=o.get('playedSeconds'),
                    table=old.get('table'), x12=old.get('x12'), case=old.get('case'), leagueFavRate=old.get('leagueFavRate'), rate=old.get('rate'),
                ))
    return legs


def risk_score(slip):
    """Run the real shared rules and strict gates; publish failures as risk evidence."""
    try:
        import matchup_rules as mr
        if any(mr.is_double_chance(p) for p in slip.get('legs') or []):
            return 100, 'Unscored', [], 'HARD VETO: double chance legs cannot be verified or published'
    except Exception as e:
        return 100, 'Unscored', [], f'rule engine unavailable: {e}'
    flags = []
    with cf.ThreadPoolExecutor(8) as ex:
        def one(p):
            q = dict(p)
            try:
                mr.enrich(q)
            except Exception:
                pass
            try:
                ok, cls, why = mr.check(q)
            except Exception as e:
                ok, cls, why = False, 'error', str(e)
            try:
                strict = mr.strict(q)
            except Exception as e:
                strict = f'gate error: {e}'
            reasons = []
            if not ok:
                reasons.append(why)
            if strict:
                reasons.append(strict)
            return dict(match=q.get('match'), selection=q.get('selection'), matchup=cls, passed=not reasons, reasons=reasons), q
        checked = list(ex.map(one, slip.get('legs') or []))
    for i, (r, enriched) in enumerate(checked):
        slip['legs'][i].update({k: v for k, v in enriched.items() if k in ('table', 'x12', 'case', 'leagueFavRate') and v})
        slip['legs'][i]['risk'] = 'review' if r['passed'] else 'flagged'
        if not r['passed']:
            flags.append(r)
    n = max(1, len(slip.get('legs') or []))
    failed = len(flags)
    odds = float(slip.get('odds') or 25)
    score = min(100, round(40 + 35 * failed / n + 10 * math.log10(max(1, odds) / 25 + 1) + min(10, n / 3)))
    rating = 'Elevated' if score < 55 else 'High' if score < 72 else 'Very high' if score < 88 else 'Extreme'
    return score, rating, flags, None


def settle_slip(s, data=None):
    try:
        data = data or decode(s['code'])
        legs = decoded_legs(data, s.get('legs'))
        if not legs or len(legs) != len((data.get('ticket') or {}).get('selections') or legs):
            raise RuntimeError('incomplete decoded legs')
        s['verifiedAt'] = NOW.isoformat(timespec='seconds').replace('+00:00', 'Z')
        s['verification'] = 'Verified by Predict2u'
        s['legs'] = legs
        s['fingerprint'] = leg_fingerprint(legs)
        s['decodeError'] = None
    except Exception as e:
        s['decodeError'] = str(e)
        # Last verified data is retained temporarily; it is never represented as freshly verified.
        legs = s.get('legs') or []
    results = [(x.get('result') or 'pending').lower() for x in legs]
    s['hit'] = results.count('won')
    s['lostLegs'] = results.count('lost')
    s['total'] = len(legs)
    s['status'] = 'lost' if 'lost' in results else 'won' if results and all(x in ('won', 'void') for x in results) else 'pending'
    s['settledAt'] = NOW.isoformat(timespec='seconds').replace('+00:00', 'Z') if s['status'] != 'pending' else None
    s['live'] = any(x.get('matchStatus') not in (None, 'Not start', 'Ended', 'Cancelled', 'Postponed', 'Abandoned') for x in legs)
    starts = [x.get('kickoff') for x in legs if x.get('kickoff')]
    s['lastKickoff'] = max(starts) if starts else None
    return s


def house_candidates():
    out = []
    for path in sorted(RESEARCH.glob('*.json')):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}\.json', path.name):
            continue
        if path.stem < TODAY:
            continue
        d = load(path, {})
        for s in d.get('slips') or []:
            if s.get('earlier') or float(s.get('totalOdds') or 0) < 25:
                continue
            code = (s.get('codes') or {}).get('sportybet')
            if code and s.get('legs'):
                out.append(dict(code=code, name=s.get('name') or 'House High Odds', odds=s.get('totalOdds'), date=path.stem, original=s['legs'], origin='strategy'))
    return out


def export_candidates():
    out = []
    # Only today's approved exports. SMAGPF is explicitly ignored by the standing site rules.
    for path in sorted(EXPORTS.glob(f'*/{TODAY}.json')):
        if path.parent.name.lower() == 'smagpf':
            continue
        d = load(path, {})
        for s in d.get('slips') or []:
            if s.get('code') and s.get('legs'):
                odds = s.get('odds') or s.get('totalOdds')
                if not odds:
                    odds = math.prod(float(x.get('odds') or 1) for x in s['legs'])
                if float(odds) >= 25:
                    out.append(dict(code=s['code'], name=s.get('name') or s.get('build') or 'Verified High Odds', odds=round(float(odds), 2), date=TODAY, original=s['legs'], origin='code-hub'))
    return out


def hub_candidates(limit=12):
    # Twelve fresh candidates per sync; already-published codes remain in the ledger.
    out = []
    for page in range(1, 5):
        try:
            d = get_json(f'https://www.sportybet.com/api/gh/orders/bookingCode/featured?pageNum={page}&pageSize=20')
        except Exception:
            break
        for c in d.get('data') or []:
            if len(c.get('shareCodeDetail') or []) < 2:
                continue
            odds = math.prod(float(x.get('odds') or 1) for x in c.get('shareCodeDetail') or [])
            if odds >= 25:
                out.append(dict(code=c['shareCode'], name='High Odds Selection', odds=round(odds, 2), date=TODAY, original=c.get('shareCodeDetail'), origin='code-hub'))
        if len(out) >= limit:
            break
    return out[:limit]


def clean_name(name):
    name = re.sub(r'^\d{4}-\d{2}-\d{2}(?:/[a-z0-9_ -]+)?\s*/\s*', '', str(name or ''), flags=re.I)
    name = re.sub(r'\s*\((?:All|Main|Aggressive|Short|record).*?\)\s*', ' ', name, flags=re.I).strip(' /-')
    return (name or 'Verified High Odds')[:80]


def normalize_candidate(c, data):
    legs = decoded_legs(data, c.get('original'))
    if not legs or len(legs) != len((data.get('ticket') or {}).get('selections') or []):
        raise RuntimeError('incomplete decoded legs')
    starts = [dt.datetime.fromisoformat(x['kickoff'].replace('Z', '+00:00')) for x in legs if x.get('kickoff')]
    if not starts or max(starts) < NOW or max(starts) > NOW + dt.timedelta(days=4):
        raise RuntimeError('expired or outside four-day window')
    calculated = math.prod(float(x.get('odds') or 0) for x in legs if float(x.get('odds') or 0) > 0)
    decoded_total = float((data.get('ticket') or {}).get('displayTotalOdds') or calculated)
    total = float(c.get('odds') or decoded_total)
    # Prefer booked export prices; use the decoded ticket total when it is available.
    if total <= 0 or (not c.get('original') and decoded_total > 0):
        total = decoded_total
    return dict(code=str(c['code']).upper(), bookmaker='SportyBet', book='sportybet', name=clean_name(c.get('name')),
                date=c.get('date') or TODAY, odds=round(total, 2), decodedOdds=round(decoded_total, 2),
                share=f"https://www.sportybet.com/gh/?shareCode={c['code']}", legs=legs,
                verifiedAt=NOW.isoformat(timespec='seconds').replace('+00:00', 'Z'), verification='Verified by Predict2u',
                origin=c.get('origin') or 'code-hub', fingerprint=leg_fingerprint(legs), replacementOf=c.get('replacementOf'))


def book_other_sites(slips, cache):
    """Reuse exact-leg public bookings; create missing codes without login.

    Import book_home without its executable booking body, as the existing Hot
    Picks pipeline does. Every result records actual booked legs and odds.
    """
    import ast
    sys.path.insert(0, str(RESEARCH))
    sys.path.insert(0, '/workspace')
    src = (RESEARCH / 'book_home.py').read_text()
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))]
    keep += [n for n in tree.body if isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id in ('MU', 'BU', 'FCU', 'MAXL') for t in n.targets)]
    ns = {'__name__': 'p2u_high_odds_books'}
    exec(compile(ast.Module(body=keep, type_ignores=[]), 'book_home_functions', 'exec'), ns)
    import bp_book
    entries = cache.get('entries') or {}
    wanted = []
    for s in slips:
        if s.get('decodeError') or not s.get('legs'):
            continue
        s.pop('bookingPending', None)
        s.setdefault('codes', {})['sportybet'] = dict(code=s['code'], legs=s.get('total'), odds=s.get('odds'), link=s.get('share'))
        fp = s.get('fingerprint') or leg_fingerprint(s['legs'])
        entry = entries.setdefault(s['code'], {})
        for book in ('msport', 'betika', 'footballcom', 'betpawa'):
            old = entry.get(book)
            if old and old.get('fingerprint') == fp and old.get('code'):
                s['codes'][book] = {k: v for k, v in old.items() if k != 'fingerprint'}
            else:
                wanted.append((s, book, fp))
    # Limit concurrent API work: BetPawa event search is comparatively expensive.
    def one(job):
        s, book, fp = job
        try:
            if book == 'msport':
                r = ns['mbook'](s['legs'])
                if r: r = dict(code=r['msport'], legs=r['legs'], odds=r['totalOdds'], link=r['link'])
            elif book == 'betika':
                r = ns['bkbook'](s['legs'])
                if r: r = dict(code=r['betika'], legs=r['legs'], odds=r['totalOdds'], link=r['link'])
            elif book == 'footballcom':
                r = ns['fc_book'](s['legs'])
                if r: r = dict(code=r['code'], legs=r['legs'], odds=r['totalOdds'], link=f"https://www.football.com/gh/?shareCode={r['code']}")
            else:
                r = bp_book.book(s['legs'])
                if r: r = dict(code=r['code'], legs=r['legs'], odds=r['totalOdds'], link=r['link'])
            return s['code'], book, fp, r
        except Exception as e:
            return s['code'], book, fp, dict(pending=str(e)[:80])
    with cf.ThreadPoolExecutor(4) as ex:
        for code, book, fp, result in ex.map(one, wanted):
            if result and result.get('code'):
                result['fingerprint'] = fp
                entries.setdefault(code, {})[book] = result
                next(s for s in slips if s['code'] == code)['codes'][book] = {k: v for k, v in result.items() if k != 'fingerprint'}
                print('booked', code, book, result['code'], result['legs'], result['odds'])
            else:
                next(s for s in slips if s['code'] == code).setdefault('bookingPending', {})[book] = 'No accepted legs'
    # Betway cannot be produced by the no-login API pipeline. Overlay exact hand-booked codes only.
    betway = load(FEED / 'betway_codes.json', {})
    for s in slips:
        e = (betway.get('bySlip') or {}).get(s['code'])
        if e and betway.get('date') == TODAY:
            s['codes']['betway'] = dict(code=e['code'], legs=e.get('picks'), odds=e.get('odds'), link=f"https://www.betway.com.gh/sport/soccer?bookingCode={e['code']}", note=e.get('note'))
        else:
            s.setdefault('bookingPending', {})['betway'] = 'Pending browser booking'
    cache['entries'] = entries
    save(BOOK_CACHE, cache, pretty=False)


def build_og(doc):
    try:
        from PIL import Image, ImageDraw, ImageFont
        W, H = 1200, 630
        im = Image.new('RGB', (W, H), '#07120f')
        px = im.load()
        for y in range(H):
            for x in range(W):
                glow = max(0, 1 - math.hypot(x - 980, y - 70) / 720)
                px[x, y] = (int(7 + 22 * glow), int(18 + 66 * glow), int(15 + 40 * glow))
        dr = ImageDraw.Draw(im)
        font = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
        bold = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
        F = lambda n, b=False: ImageFont.truetype(bold if b else font, n)
        dr.rounded_rectangle((54, 48, 1146, 582), radius=38, outline='#22c77a', width=3, fill='#0b1c17')
        dr.text((94, 82), 'PREDICT2U', font=F(40, True), fill='#58e69b')
        dr.rounded_rectangle((865, 78, 1095, 130), radius=24, fill='#b4232d')
        dr.text((895, 91), 'HIGH RISK', font=F(25, True), fill='white')
        dr.text((94, 190), 'HIGH ODDS', font=F(88, True), fill='#f5f8f6')
        dr.text((98, 298), 'Verified codes. Live progress. Settled results.', font=F(31), fill='#b8c9c0')
        active = doc.get('slips') or []
        top = max((float(s.get('odds') or 0) for s in active), default=0)
        dr.text((98, 390), f"{len(active)} codes to watch", font=F(38, True), fill='#ffd166')
        dr.text((98, 449), f"Top odds {top:,.2f}", font=F(32), fill='#f5f8f6')
        dr.text((98, 526), 'High odds, high risk. Stake small.  |  predict2u.com', font=F(25), fill='#ffb4a8')
        im.save(REPO / 'og-high-odds.png', optimize=True)
    except Exception as e:
        print('OG image:', e)


def update_meta(doc):
    p = REPO / 'high-odds' / 'index.html'
    if not p.exists():
        return
    s = p.read_text()
    active = doc.get('slips') or []
    top = max((float(x.get('odds') or 0) for x in active), default=0)
    desc = f"{len(active)} verified high odds codes, live progress and settled results on Predict2u. Top odds {top:,.2f}. High risk — stake small."
    s = re.sub(r'<meta name="description" content="[^"]*"', f'<meta name="description" content="{desc}"', s)
    s = re.sub(r'<meta property="og:description" content="[^"]*"', f'<meta property="og:description" content="{desc}"', s)
    s = re.sub(r'<meta name="twitter:description" content="[^"]*"', f'<meta name="twitter:description" content="{desc}"', s)
    p.write_text(s)


def mr_is_double_chance(leg):
    sys.path.insert(0, str(RESEARCH))
    import matchup_rules as mr
    return mr.is_double_chance(leg)


def rebook_dc_free_existing(existing, previous_replacements=None):
    """Replace old DC-containing shares with newly booked non-DC tickets.

    A share code is immutable, so removing a leg requires a fresh SportyBet
    booking. Only upcoming non-DC legs are carried over. If the remaining
    ticket cannot reach the High Odds 25+ threshold, it is dropped.
    """
    sys.path.insert(0, '/workspace')
    from sb_share_helper17 import book
    out = list(previous_replacements or [])
    for old in existing.values():
        legs = old.get('legs') or []
        if not any(mr_is_double_chance(p) for p in legs):
            continue
        kept = []
        for p in legs:
            if mr_is_double_chance(p) or p.get('matchStatus') not in (None, 'Not start'):
                continue
            start = p.get('kickoff')
            try:
                if start and dt.datetime.fromisoformat(start.replace('Z', '+00:00')) <= NOW:
                    continue
            except Exception:
                pass
            kept.append(p)
        odds = math.prod(float(p.get('odds') or 1) for p in kept)
        if not kept or odds < 25:
            print('drop DC high-odds code', old.get('code'), 'no 25+ DC-free replacement')
            continue
        code, status = book(kept)
        if not code or status != 'ok':
            print('drop DC high-odds code', old.get('code'), 'rebook failed', status)
            continue
        print('rebook DC-free high odds', old.get('code'), '->', code, len(kept), round(odds, 2))
        out.append(dict(code=code, name=old.get('name') or 'Verified High Odds', odds=round(odds, 2),
                        date=TODAY, original=kept, origin=old.get('origin') or 'code-hub', replacementOf=old.get('code')))
    return out


def main():
    old = load(OUT, {})
    existing = {code_key('sportybet', s['code']): s for s in (old.get('slips') or []) + (old.get('history') or []) if s.get('code')}
    cache = load(CACHE, {})
    ledger_replacements = []
    for r in cache.get('dcReplacements') or []:
        if r.get('code') not in existing:
            ledger_replacements.append(dict(code=r['code'], name='Verified High Odds', date=r.get('date') or TODAY, original=None, origin='code-hub', replacementOf=r.get('replacementOf')))
    previous_replacements = [dict(code=s['code'], name=s.get('name'), odds=s.get('odds'), date=s.get('date') or TODAY, original=s.get('legs'), origin=s.get('origin'), replacementOf=s.get('replacementOf')) for s in existing.values() if s.get('replacementOf')]
    candidates = [] if SETTLE_ONLY else rebook_dc_free_existing(existing, previous_replacements + ledger_replacements) + house_candidates() + export_candidates() + hub_candidates()
    by_code = {code_key('sportybet', c['code']): c for c in candidates}
    decode_codes = sorted(set(existing) | set(by_code))
    raw_cache = cache.get('shares') or {}
    def cached_decode(key):
        code = key.split(':', 1)[1]
        try:
            data = decode(code)
            return key, data, None
        except Exception as e:
            return key, raw_cache.get(code), str(e)
    decoded = {}
    with cf.ThreadPoolExecutor(8) as ex:
        for key, data, error in ex.map(cached_decode, decode_codes):
            decoded[key] = data
            if data:
                raw_cache[key.split(':', 1)[1]] = data
    # Existing entries are settled on every run, including the nightly results routine.
    refreshed = {}
    for key, s in existing.items():
        s = settle_slip(dict(s), decoded.get(key))
        # Hard veto applies to active and historical High Odds codes too.
        # Remove the whole old share: editing its JSON would misrepresent the booked ticket.
        if any(mr_is_double_chance(p) for p in s.get('legs') or []):
            print('drop DC high-odds code', s.get('code'))
            continue
        if key in by_code and s.get('decodeError') is None:
            s['verification'] = 'Verified by Predict2u'
        if not s.get('riskRating') and s.get('legs'):
            score, rating, flags, err = risk_score(s)
            s.update(riskScore=score, riskRating=rating, riskFlags=flags, riskError=err)
        refreshed[key] = s
    added = 0
    for key, c in by_code.items():
        if key in refreshed:
            continue
        try:
            if not decoded.get(key):
                continue
            s = normalize_candidate(c, decoded[key])
            if any(mr_is_double_chance(p) for p in s.get('legs') or []):
                raise RuntimeError('HARD VETO: double chance leg')
            s = settle_slip(s, decoded[key])
            # Same legs under another code count as the same selection.
            if not c.get('replacementOf') and any(x.get('fingerprint') == s['fingerprint'] for x in refreshed.values()):
                continue
            s['status'] = 'pending'
            s['addedAt'] = NOW.isoformat(timespec='seconds').replace('+00:00', 'Z')
            score, rating, flags, err = risk_score(s)
            s.update(riskScore=score, riskRating=rating, riskFlags=flags, riskError=err)
            refreshed[key] = s
            added += 1
        except Exception as e:
            print('skip', c['code'], e)
    pinned = {'D2BEMV', 'AE1S9M', 'AMNN1X', 'BQCUCP', 'E51P68', 'DZBHA7'}
    house = {c['code'] for c in house_candidates()}
    replacement_pairs = {s.get('replacementOf'): s['code'] for s in refreshed.values() if s.get('replacementOf')}
    hub_count = 0
    active, history = [], []
    ordered = sorted(refreshed.values(), key=lambda s: (0 if s['code'] in pinned else 1 if s['code'] in house else 2, s.get('addedAt') or ''))
    for s in ordered:
        s['shareUrl'] = f"https://predict2u.com/high-odds/#{s['code']}"
        if s['code'] in replacement_pairs and s['code'] != replacement_pairs[s['code']]:
            # The source hub can independently offer an identical ticket; keep one public card.
            print('dedupe replacement duplicate', s['code'], 'of', replacement_pairs[s['code']])
            continue
        if s.get('status') in ('won', 'lost'):
            history.append(s)
        elif (s.get('date') or '') >= TODAY and s.get('lastKickoff') and dt.datetime.fromisoformat(s['lastKickoff'].replace('Z', '+00:00')) >= NOW:
            if s['code'] not in pinned and s['code'] not in house and not s.get('replacementOf'):
                hub_count += 1
                if hub_count > 12:
                    continue
            s['origin'] = 'strategy' if s['code'] in house else 'code-hub'
            s.pop('bookingPending', None)
            active.append(s)
        elif s.get('status') in ('won', 'lost'):
            history.append(s)
    active.sort(key=lambda s: (0 if s['code'] in pinned else 1 if s['code'] in house else 2, s.get('date') or '', -(s.get('odds') or 0)))
    history.sort(key=lambda s: (s.get('settledAt') or s.get('date') or ''), reverse=True)
    won = sum(s['status'] == 'won' for s in history)
    lost = sum(s['status'] == 'lost' for s in history)
    doc = dict(label='High Odds — higher risk', updatedAt=NOW.isoformat(timespec='seconds').replace('+00:00', 'Z'),
               slips=active, history=history[:90], record=dict(won=won, lost=lost, settled=won + lost, pending=len(active), winRate=round(100 * won / (won + lost), 1) if won + lost else None))
    save(OUT, doc)
    replacement_ledger = [dict(replacementOf=s.get('replacementOf'), code=s['code'], date=s.get('date') or TODAY) for s in refreshed.values() if s.get('replacementOf')]
    known_rep = {(r['replacementOf'], r['code']) for r in replacement_ledger}
    replacement_ledger += [r for r in (cache.get('dcReplacements') or []) if (r.get('replacementOf'), r.get('code')) not in known_rep]
    save(CACHE, dict(updatedAt=doc['updatedAt'], shares=raw_cache, dcReplacements=replacement_ledger), pretty=False)
    books_cache = load(BOOK_CACHE, {})
    # Restore the immutable booking map onto settled proofs without creating new codes.
    for s in history:
        s.setdefault('codes', {})['sportybet'] = dict(code=s['code'], legs=s.get('total'), odds=s.get('odds'), link=s.get('share'))
        for book, result in (books_cache.get('entries') or {}).get(s['code'], {}).items():
            if result.get('fingerprint') == s.get('fingerprint') and result.get('code'):
                s['codes'][book] = {k: v for k, v in result.items() if k != 'fingerprint'}
        e = (load(FEED / 'betway_codes.json', {}).get('bySlip') or {}).get(s['code'])
        if e:
            s['codes']['betway'] = dict(code=e['code'], legs=e.get('picks'), odds=e.get('odds'), link=f"https://www.betway.com.gh/sport/soccer?bookingCode={e['code']}")
    if not SETTLE_ONLY:
        book_other_sites(active, books_cache)
    # Persist the new per-bookmaker codes and refresh the social card after booking.
    save(OUT, doc)
    build_og(doc)
    # Keep each High Odds slip's downloadable/share-preview image in the existing card pipeline.
    try:
        share_src = (FEED / 'share_cards.py').read_text().replace('\nmain()\n', '\n')
        share_mod = {'__name__': 'p2u_high_share_cards'}
        exec(compile(share_src, str(FEED / 'share_cards.py'), 'exec'), share_mod)
        seen = set()
        for slip in active + history:
            code = share_mod['codes'](slip).get('sportybet')
            if code and code not in seen:
                seen.add(code)
                share_mod['card'](slip, 'high', TODAY)
    except Exception as e:
        print('High Odds share images:', e)
    update_meta(doc)
    print(f"high odds: {len(active)} active ({added} added), {len(history)} settled; record {won}W/{lost}L")
    for s in active:
        print(s['code'], s['status'], f"{s.get('hit',0)}/{s.get('total',0)}", s.get('riskRating'), s.get('riskScore'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
