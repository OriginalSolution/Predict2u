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
    if not recs: print('daily master: none'); return
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
