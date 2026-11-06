#!/usr/bin/env bash
# Rebuild predict2u.com picks from bot exports and push if changed.
set -euo pipefail
exec 9>/tmp/p2u-sync.lock; flock -n 9 || { echo "previous sync still running, skipping"; exit 0; }
REPO=/workspace/Predict2u
cd "$REPO"
git pull -q --rebase origin main
# Daily research: refresh SportyBet card, run the league-favourites engine, then book every pick + slips (SportyBet, MSport, Betika)
R=/workspace/predict2u-research
DAY=$(date -u +%F)
( cd "$R" && timeout 900 python3 scan.py >/dev/null && timeout 1500 python3 run.py "$DAY" --days 2 >/dev/null && timeout 900 python3 book_home.py "$DAY" >/dev/null ) || echo "research/booking step failed"
# Book the all-picks home code once per research run (re-book when research is newer than the code)
RF=/workspace/predict2u-research/$(date -u +%F).json
if [ -e "$RF" ] && python3 -c "import json,sys;d=json.load(open('$RF'));h=d.get('homeCode') or {};sys.exit(0 if (not h.get('codes') or h.get('bookedAt','')<d.get('updatedAt','')) else 1)"; then
  python3 /workspace/predict2u-research/book_home.py "$(date -u +%F)" >/dev/null || echo "home booking failed"
fi
( cd "$R" && timeout 60 python3 risk_slips.py "$DAY" >/dev/null && timeout 900 python3 book_home.py "$DAY" >/dev/null ) || echo "risk slips step failed"
timeout 60 python3 /workspace/predict2u-feed/betway_overlay.py >/dev/null || echo "betway overlay failed"
( cd "$R" && timeout 1500 python3 hot_picks.py "$REPO/hot-picks.json" >/dev/null ) || echo "hot picks step failed"
# High Odds: verify house + code-hub shares, score risks and settle every leg.
timeout 1500 python3 /workspace/predict2u-feed/high_odds.py "$REPO" || echo "high odds step failed"
timeout 60 python3 /workspace/predict2u-feed/inject_exempt.py "$REPO" || echo "exempt inject failed"
timeout 60 python3 /workspace/predict2u-feed/prune_live.py "$REPO" || echo "prune step failed"
timeout 120 python3 /workspace/predict2u-feed/lock_codes.py "$REPO" >/dev/null || echo "lock step failed"
timeout 600 python3 /workspace/predict2u-feed/news_hub.py "$REPO" >/dev/null || echo "news hub step failed"
# Same entry point used by the after-settle results sync; --settle-only adds no new codes.
timeout 300 python3 /workspace/predict2u-feed/high_odds.py "$REPO" --settle-only || echo "high odds settle failed"
timeout 60 python3 /workspace/predict2u-feed/telegram_post.py "$REPO" --results >/dev/null || echo "telegram results skipped"
timeout 120 python3 /workspace/predict2u-feed/build_record.py "$REPO" >/dev/null || echo "record step failed"
timeout 60 python3 /workspace/predict2u-feed/telegram_post.py "$REPO" --codes >/dev/null || echo "telegram codes skipped"
timeout 600 python3 /workspace/predict2u-feed/staked_feed.py "$REPO" >/dev/null || echo "staked step failed"
# Snapshot event scores for home live-score fallback
python3 - <<'PY' || echo "live-scores snapshot failed"
import json, os, datetime as dt
REPO=os.environ.get("REPO") or "/workspace/Predict2u"
FEED="/workspace/predict2u-feed"
ev={}
try: ev=json.load(open(os.path.join(FEED,"event-cache.json")))
except Exception: pass
try: h=json.load(open(os.path.join(REPO,"home-picks.json")))
except Exception: h={"picks":[]}
out={}
for p in h.get("picks") or []:
  eid=p.get("eventId")
  if not eid: continue
  e=ev.get(eid) or {}
  out[eid]={"eventId":eid,"status":e.get("status") or ("Ended" if p.get("result") in ("won","lost") else "Not start"),"score":e.get("score") or p.get("score"),"played":e.get("played"),"home":e.get("home"),"away":e.get("away")}
json.dump({"DATA_UPDATED":dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),"events":out}, open(os.path.join(REPO,"live-scores.json"),"w"), separators=(",",":"))
print("live-scores", len(out))
PY
# SEO: static match + league pages + sitemap from home-picks
timeout 120 python3 /workspace/predict2u-feed/build_seo_pages.py "$REPO" || echo "seo pages step failed"
timeout 60 python3 /workspace/predict2u-feed/build_code_pages.py "$REPO" || echo "code pages step failed"
# Per-slip 1080x1350 share cards (share/<code>.png)
timeout 600 python3 /workspace/predict2u-feed/share_cards.py "$REPO" || echo "share cards step failed"
set +e; PRIV_DIR=/workspace/predict2u-feed/private python3 "$REPO/engine/vendor/build.py" "$REPO"; rc=$?; set -e
timeout 60 python3 /workspace/predict2u-feed/inject_exempt.py "$REPO" || echo "exempt inject failed"
timeout 60 python3 /workspace/predict2u-feed/inject_exempt.py "$REPO" || echo "exempt inject failed"
timeout 60 python3 /workspace/predict2u-feed/prune_live.py "$REPO" || echo "prune step failed"
# Pay-per-code: mask premium codes in every public file again after the rebuild
python3 /workspace/predict2u-feed/lock_codes.py "$REPO" || { echo "lock step failed - not pushing"; exit 1; }
[ $rc -eq 3 ] && ! git diff --quiet -- . && rc=0
if [ $rc -eq 3 ] && git diff --quiet -- news-hub.json share hot-picks.json staked-codes.json && [ -z "$(git ls-files --others --exclude-standard share)" ] && ! git ls-files --others --exclude-standard | grep -qx news-hub.json; then echo "no change, nothing pushed"; exit 0; fi
[ $rc -ne 0 ] && [ $rc -ne 3 ] && exit $rc
for f in high_odds.json og-high-odds.png high-odds locked.enc.json picks.json picks-history.json home-picks.json news-hub.json hot-picks.json staked-codes.json staked-index.json staked-status.json record.json live-scores.json seo-pages.json sitemap.xml robots.txt matches.html leagues.html sportybet-codes-today betway-booking-codes-today msport-booking-codes-today betika-booking-codes-today betpawa-booking-codes-today football-com-booking-codes-today; do [ -e "$f" ] && git add "$f"; done
[ -d match ] && git add -A match
[ -d league ] && git add -A league
[ -d share ] && git add -A share
[ -d s ] && git add -A s
git -c user.name="predict2u-feed" -c user.email="feed@predict2u.com" commit -q -m "Update bot picks feed $(date -u +%FT%TZ)"
git push -q origin main && echo "pushed"
