"""No-login bookmaker helpers used by DC Shield (and other nightlies).

Vendored for GitHub Actions — does not depend on /workspace/predict2u-feed.
"""
from __future__ import annotations
import json, math, subprocess

MU = 'https://www.msport.com/api/gh/orders/real-sports/order/share'
BU = 'https://api.betika.com.gh/v2/share/'
FCU = 'https://www.football.com/api/gh/orders/share'


def mcall(m, url, body=None):
    c = ['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0 Chrome/120',
         '-H', 'Content-Type: application/json', '-H', 'operid: 3', '-X', m, url]
    if body:
        c += ['-d', json.dumps(body)]
    try:
        return json.loads(subprocess.run(c, capture_output=True, text=True).stdout)
    except Exception:
        return {}


def msel(p):
    return {
        'eventId': p['eventId'],
        'marketId': str(p.get('marketId', '')),
        'specifier': p.get('specifier') or '',
        'outcomeId': str(p.get('outcomeId', '')),
    }


def mbook(L):
    ok = [p for p in L if p.get('marketId') and p.get('outcomeId')
          and mcall('POST', MU, {'selections': [msel(p)]}).get('bizCode') == 10000]
    if not ok:
        return None
    r = mcall('POST', MU, {'selections': [msel(p) for p in ok]})
    if r.get('bizCode') != 10000:
        return None
    code = r['data']['shareCode']
    b = mcall('GET', MU + '/' + code)
    B = (b.get('data') or {}).get('bettableBetSlip') or []
    tot = round(math.prod(float(x['outcome']['odds']) for x in B), 2) if B else None
    return dict(
        msport=code, totalOdds=tot, legs=len(B) or len(ok), of=len(L),
        matches=[p['eventId'] for p in ok],
        link=f'https://www.msport.com/gh/sports/share?shareCode={code}',
    )


def bcall(m, url, body=None):
    c = ['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0 Chrome/120',
         '-H', 'Content-Type: application/json', '-X', m, url]
    if body:
        c += ['-d', json.dumps(body)]
    try:
        return json.loads(subprocess.run(c, capture_output=True, text=True).stdout)
    except Exception:
        return {}


def bsel(p):
    return {
        'odd_key': '', 'outcome_id': str(p.get('outcomeId', '')),
        'special_bet_value': p.get('specifier') or '',
        'parent_match_id': p['eventId'].split(':')[-1],
        'sub_type_id': str(p.get('marketId', '')),
        'has_parent': None, 'parent_code': None,
    }


def bkbook(L):
    L = [p for p in L if p.get('marketId') and p.get('outcomeId')]
    if not L:
        return None
    r = bcall('POST', BU + 'encode', {
        'profile_id': 0, 'bet_id': None, 'token': None,
        'src': 'MOBILE_WEB', 'product_type': 'PREMATCH',
        'betslip': [bsel(p) for p in L],
    })
    code = r.get('code')
    if not code:
        return None
    dd = bcall('GET', BU + 'decode?code=' + code + '&src=MOBILE_WEB').get('data') or []
    V = [x for x in dd if str(x.get('valid')) == '1']
    if not V:
        return None
    tot = round(math.prod(float(x['odd_value']) for x in V), 2)
    ids = {'sr:match:' + x['parent_match_id'] for x in V}
    return dict(
        betika=code, totalOdds=tot, legs=len(V), of=len(L),
        link=f'https://betika.com/en-gh/share/{code}', matches=sorted(ids),
    )


def fcall(m, url, body=None):
    c = ['curl', '-s', '-m', '30', '-A', 'Mozilla/5.0 Chrome/120',
         '-H', 'Content-Type: application/json', '-H', 'Accept: application/json',
         '-X', m, url]
    if body:
        c += ['-d', json.dumps(body)]
    try:
        return json.loads(subprocess.run(c, capture_output=True, text=True).stdout)
    except Exception:
        return {}


def fsel(p):
    return {
        'eventId': p['eventId'],
        'marketId': str(p.get('marketId', '')),
        'specifier': p.get('specifier') or None,
        'outcomeId': str(p.get('outcomeId', '')),
    }


def fc_book(L):
    L = [p for p in L if p.get('marketId') and p.get('outcomeId')]
    if not L:
        return None
    r = fcall('POST', FCU, {'selections': [fsel(p) for p in L]})
    if r.get('bizCode') != 10000:
        L = [p for p in L if fcall('POST', FCU, {'selections': [fsel(p)]}).get('bizCode') == 10000]
        if not L:
            return None
        r = fcall('POST', FCU, {'selections': [fsel(p) for p in L]})
        if r.get('bizCode') != 10000:
            return None
    code = r['data']['shareCode']
    O = (fcall('GET', FCU + '/' + code).get('data') or {}).get('outcomes') or []
    od = []
    for o in O:
        if o.get('matchStatus') != 'Not start':
            continue
        for mk in o.get('markets') or []:
            for oc in mk.get('outcomes') or []:
                od.append(float(oc['odds']))
    tot = round(math.prod(od), 2) if od else round(math.prod(p['odds'] for p in L), 2)
    return dict(
        code=code, totalOdds=tot, legs=len(od) or len(L),
        matches=[o['eventId'] for o in O] or [p['eventId'] for p in L],
    )


def bp_try(L):
    try:
        import bp_book
        return bp_book.book(L)
    except Exception:
        return None
