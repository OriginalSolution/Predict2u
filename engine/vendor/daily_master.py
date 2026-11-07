#!/usr/bin/env python3
"""Daily master code: publish the day's master SportyBet code UNCHANGED as Code of the Day,
in Hot Picks and on High Odds, always labelled HIGH RISK, and settle it.

Records: engine/data/daily-master/YYYY-MM-DD.json (code, legs, totalOdds, link, legList, uncertainLegs).
Run after every rebuild of home-picks / hot-picks / high_odds (box sync and Actions):
    python3 engine/vendor/daily_master.py REPO
No source names are stored or published. Never called "fully verified" while any leg is uncertain.
"""
import json, os, sys, glob, datetime as dt
REPO = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('REPO_DIR', '/workspace/Predict2u')
DIR = os.path.join(REPO, 'engine', 'data', 'daily-master')
NOW = dt.datetime.now(dt.timezone.utc)
TODAY = NOW.date().isoformat()
SB = 'https://www.sportybet.com/gh/?shareCode={}'


def load(p, d=None):
    try: return json.load(open(p))
    except Exception: return d


def save(p, d, pretty=False):
    json.dump(d, open(p, 'w'), ensure_ascii=False, **({'indent': 1} if pretty else {'separators': (',', ':')}))


def settle(rec):
    """Settle legs with the High Odds settler (decodes the share code for live results)."""
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    try:
        import high_odds as HO
        s = dict(code=rec['code'], legs=rec['legList'])
        HO.settle_slip(s)
        if not s.get('decodeError') and s.get('legs'):
            rec['legList'] = s['legs']
        rec['decodeError'] = s.get('decodeError')
    except Exception as e:
        rec['decodeError'] = str(e)
    res = [(x.get('result') or 'pending').lower() for x in rec['legList']]
    rec['hit'], rec['lostLegs'], rec['total'] = res.count('won'), res.count('lost'), len(res)
    rec['status'] = 'lost' if 'lost' in res else 'won' if res and all(r in ('won', 'void') for r in res) else 'pending'
    if rec['status'] != 'pending' and not rec.get('settledAt'):
        rec['settledAt'] = NOW.isoformat(timespec='seconds').replace('+00:00', 'Z')
    return rec


def verification(rec):
    u = int(rec.get('uncertainLegs') or 0)
    return f"Not fully verified — {u} leg{'s' if u != 1 else ''} status uncertain" if u else 'Checked by Predict2u'


def main():
    recs = []
    for f in sorted(glob.glob(os.path.join(DIR, '????-??-??.json'))):
        r = load(f)
        if not r or not r.get('code'): continue
        if r.get('status') in (None, 'pending') or r['date'] >= TODAY:
            settle(r)
            try:
                import split_codes as SC
                SC.ensure_parts(r, 'legList', base_name=r['code'])
            except Exception as e:
                print('daily master split failed:', e)
            save(f, r, pretty=True)
        recs.append(r)
    if not recs:
        # Fallback: rebuild today's record from gate_exempt when date files
        # are missing (e.g. older checkouts before daily-master was tracked).
        ge = load(os.path.join(REPO, 'engine', 'gate_exempt.json'), {}) or {}
        for e in (ge.get('entries') or []):
            if not e or e.get('date') != TODAY or not e.get('code'):
                continue
            # Prefer regenerating from an existing High Odds / home slip copy.
            ho = load(os.path.join(REPO, 'high_odds.json'), {}) or {}
            src = next((s for s in (ho.get('slips') or []) + (ho.get('history') or []) if s.get('code') == e['code']), None)
            if not src:
                print('daily master: none (gate_exempt', e['code'], 'has no slip copy)'); continue
            r = dict(code=e['code'], date=e['date'], legs=e.get('nLegs') or len(src.get('legs') or []),
                     totalOdds=e.get('odds') or src.get('odds'), link=e.get('share') or src.get('share'),
                     name=f"Daily master · {e['date']}", riskLabel='HIGH RISK',
                     uncertainLegs=src.get('uncertainLegs') or 0, note=e.get('warning') or src.get('warning'),
                     bookedAt=src.get('bookedAt'), legList=src.get('legs') or [], status=src.get('status') or 'pending',
                     parts=src.get('parts'), partsDropped=src.get('partsDropped'))
            os.makedirs(DIR, exist_ok=True)
            save(os.path.join(DIR, f"{e['date']}.json"), r, pretty=True)
            settle(r)
            try:
                import split_codes as SC
                SC.ensure_parts(r, 'legList', base_name=r['code'])
            except Exception as ex:
                print('daily master split failed:', ex)
            save(os.path.join(DIR, f"{e['date']}.json"), r, pretty=True)
            recs.append(r)
        if not recs:
            print('daily master: none'); return
    cur = [r for r in recs if r['date'] == TODAY]
    note_of = lambda r: r.get('note') or 'HIGH RISK accumulator.'
    # High Odds: active today, settled ones move to history (engine record).
    ho_p = os.path.join(REPO, 'high_odds.json'); ho = load(ho_p, {}) or {}
    for r in recs:
        slip = dict(code=r['code'], bookmaker='SportyBet', book='sportybet', name=f"{r['name']} · HIGH RISK", date=r['date'],
                    odds=r['totalOdds'], share=r['link'], legs=r['legList'], verification=verification(r), origin='daily-master',
                    hit=r.get('hit', 0), lostLegs=r.get('lostLegs', 0), total=r.get('total', r['legs']), status=r.get('status', 'pending'),
                    settledAt=r.get('settledAt'), riskRating='HIGH', riskLabel='HIGH RISK', highRisk=True, warning=note_of(r),
                    shareUrl=f"https://predict2u.com/high-odds/#{r['code']}",
                    codes={'sportybet': dict(code=r['code'], legs=r['legs'], odds=r['totalOdds'], link=r['link'])},
                    parts=r.get('parts'), partsDropped=r.get('partsDropped'), lastKickoff=max((x.get('kickoff') or '') for x in r['legList']) or None)
        for k in ('slips', 'history'):
            ho[k] = [s for s in (ho.get(k) or []) if s.get('code') != r['code']]
        (ho.setdefault('slips', []).insert(0, slip) if slip['status'] == 'pending' else ho.setdefault('history', []).insert(0, slip))
    # High-Odds-only masters (engine/data/ho-masters): published on High Odds only, in parts, HIGH RISK, settled per leg.
    HD = os.path.join(REPO, 'engine', 'data', 'ho-masters')
    for f in sorted(glob.glob(os.path.join(HD, '*.json'))):
        r = load(f)
        if not r or not r.get('parts'): continue
        if r.get('status') in (None, 'pending'):
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            try:
                import high_odds as HO
                for pt in r['parts']:
                    c = ((pt.get('codes') or {}).get('sportybet') or [{}])[0].get('code')
                    if not c: continue
                    sl = dict(code=c, legs=[x for x in r['legList'] if x['eventId'] in set(pt['events'])]); HO.settle_slip(sl)
                    if not sl.get('decodeError'):
                        res = {x['eventId']: x for x in sl['legs']}
                        r['legList'] = [res.get(x['eventId'], x) for x in r['legList']]
            except Exception as e: print('ho master settle failed', e)
            import split_codes as SC; SC.settle_parts(r['legList'], r['parts'])
            res = [(x.get('result') or 'pending').lower() for x in r['legList']]
            r['hit'], r['total'] = res.count('won'), len(res)
            r['status'] = 'lost' if 'lost' in res else 'won' if res and all(x in ('won', 'void') for x in res) else 'pending'
            save(f, r, pretty=True)
        for i, pt in enumerate(r['parts']):
            cs = {b: dict(code=L[0]['code'], legs=L[0]['legs'], odds=L[0]['totalOdds'], link=L[0]['link']) for b, L in (pt.get('codes') or {}).items() if L}
            if 'sportybet' not in cs: continue
            sc = cs['sportybet']['code']; ev = set(pt['events']); pl = [x for x in r['legList'] if x['eventId'] in ev]
            pr = [(x.get('result') or 'pending').lower() for x in pl]
            st = 'lost' if 'lost' in pr else 'won' if pr and all(x in ('won', 'void') for x in pr) else 'pending'
            slip = dict(code=sc, bookmaker='SportyBet', book='sportybet', name=pt.get('label') or f"{r['name']} · part {i + 1}/{len(r['parts'])} · HIGH RISK", date=r['date'],
                        odds=pt['totalOdds'], share=cs['sportybet']['link'], legs=pl, verification=r.get('verification'), origin='ho-master',
                        hit=pr.count('won'), lostLegs=pr.count('lost'), total=len(pl), status=st, riskRating='HIGH', riskLabel='HIGH RISK', highRisk=True,
                        shareUrl=f"https://predict2u.com/high-odds/#{sc}", codes=cs, lastKickoff=max((x.get('kickoff') or '') for x in pl) or None,
                        settledAt=NOW.isoformat(timespec='seconds').replace('+00:00', 'Z') if st != 'pending' else None)
            for k in ('slips', 'history'):
                ho[k] = [x for x in (ho.get(k) or []) if x.get('code') != sc]
            (ho.setdefault('slips', []).append(slip) if st == 'pending' else ho.setdefault('history', []).insert(0, slip))
    H = ho.get('history') or []; won = sum(s.get('status') == 'won' for s in H); lost = sum(s.get('status') == 'lost' for s in H)
    ho['record'] = dict(won=won, lost=lost, settled=won + lost, pending=len(ho.get('slips') or []), winRate=round(100 * won / (won + lost), 1) if won + lost else None)
    save(ho_p, ho)
    hot_p = os.path.join(REPO, 'hot-picks.json'); hot = load(hot_p)
    hp_p = os.path.join(REPO, 'home-picks.json'); hp = load(hp_p)
    for r in cur:
        chip = [dict(code=r['code'], totalOdds=r['totalOdds'], legs=r['legs'], link=r['link'])]
        if hot is not None:
            hot['slips'] = [s for s in (hot.get('slips') or []) if not s.get('dailyMaster')]
            hot['slips'].insert(0, dict(name=r['name'], legs=r['legs'], totalOdds=r['totalOdds'], codes={'sportybet': chip}, highRisk=True,
                                        riskLabel='HIGH RISK', dailyMaster=True, warning=note_of(r) + ' ' + verification(r) + '.', status=r.get('status'), parts=r.get('parts')))
        if hp is not None:
            hp['slips'] = [s for s in (hp.get('slips') or []) if not s.get('dailyMaster')]
            hp['slips'].insert(0, dict(name='Main · ' + r['name'], totalOdds=r['totalOdds'], legs=r['legList'], codes={'sportybet': r['code']},
                                       bookPicks={'sportybet': r['legs']}, dailyMaster=True, highRisk=True, riskLabel='HIGH RISK',
                                       warning=note_of(r), verification=verification(r), status=r.get('status'), parts=r.get('parts')))
    if not cur:  # yesterday's master must not stay as Code of the Day
        for d in (hot, hp):
            if d is not None: d['slips'] = [s for s in (d.get('slips') or []) if not s.get('dailyMaster')]
    if hot is not None: save(hot_p, hot)
    if hp is not None: save(hp_p, hp)
    print('daily master:', [(r['code'], r['date'], r.get('status'), f"{r.get('hit',0)}/{r.get('total')}") for r in recs])


if __name__ == '__main__':
    main()
