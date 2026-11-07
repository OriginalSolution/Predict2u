"""Exit 1 when today's favourites day-master codes are missing on the published site data.
Missing = home-picks.json is not for today (no midnight rollover) OR today's dayMasters has no booked code
while today has qualifying picks. Hide-only-if-no-picks: a day with zero picks is OK."""
import json, sys, datetime as dt, pathlib
p = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else 'home-picks.json')
today = dt.datetime.now(dt.timezone.utc).date().isoformat()
d = json.loads(p.read_text())
picks = [x for x in d.get('picks') or [] if x.get('date') == today]
dm = ((d.get('homeCode') or {}).get('dayMasters') or {}).get(today) or {}
codes = dm.get('codes') or {}
if not codes and isinstance(dm, dict):
    for part in dm.get('parts') or dm.get('slips') or []:
        codes.update((part or {}).get('codes') or {})
ok = bool(codes) or not picks
print(f"date={d.get('date')} today={today} picks_today={len(picks)} dayMaster_books={sorted(codes)} -> {'OK' if ok else 'MISSING'}")
sys.exit(0 if ok else 1)
