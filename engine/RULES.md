# Predict2u engine rules (single source of truth)

Machine-readable mirror: `engine/config.json`. CI (`python -m engine.check_rules`) fails if code drifts from these numbers or vetoes.

All times below are Africa/Accra (UTC+0).

## Hard vetoes

- Never publish or book **DC 12** (Home or Away) at any price.
- Never publish or book **1X or X2** (Home or Draw / Draw or Away, including DC combo markets) when priced **above 1.35**. **1X/X2 at 1.35 or below is allowed.**
- Never publish or book **NG** (BTTS No / GG No). BTTS Yes / GG is allowed when other gates pass.
- Never print tipster or bot names on the public site.
- Ignore SMAGPF as a pick source.
- Main slips must stay at **25+** combined odds.
- Inbox / imported bot codes **under 25 are combined, never dropped** for being short. Decode (if needed), drop started games, drop vetoed DC (12, or 1X/X2 above 1.35) and NG, apply matchup rules and the odds caps, keep one market per game, then pack surviving legs into one or more 25+ slips and rebook them. Leftover legs that cannot form another 25+ slip are merged into the last slip so they still get booked.

- No single leg above **1.60** without extreme stats (each side last-10 hit ≥ 90% from 8+ games, H2H ≥ 80% from 4+, league rate ≥ 80%).
- Over 1.5 or Under 3.5 above **1.30** needs strong stats (team last-10 ≥ 80% from 8+, H2H ≥ 75% from 4+, league rate ≥ 80%).

## Matchup classes

On leagues with 10+ teams:

- Skip both-teams top 5, and both-teams bottom 3.
- **Mismatch** (large table gap and a short favourite ≤ 1.70): no straight win. Use GG / Over 1.5 (or team Over 0.5 when the 1.60 cap blocks Over 1.5).
- **Middle**: GG only, plus home/away team Over 0.5.
- **Even** (favourite longer than 1.80): no Over 1.5 / Over 2.5.

## Strategies the engine runs

| Strategy | How it runs | Schedule |
|---|---|---|
| House favourites / buckets | `vendor/fav_engine.py` + `vendor/run.py` + `vendor/book_home.py` | Daily 23:00 |
| Hot picks | `vendor/hot_picks.py` — hub scrape + per-market/team slips; also builds **sectionMasters** (one 25+ master slip per Hot page section: Hot matches, Hot by market, Trending markets, Hot teams, Most-backed teams), booked on every no-login bookmaker and shown in the Hot carousel | Daily 23:00 |
| DC Shield Goals | `vendor/dc_shield.py` — finds next-day games whose DC price is under 1.20, then books Over 1.5 / Over 2.5 / GG (**never the DC pick**) | 21:00 and again inside the 23:00 book step |
| High Odds (incl. Heavy Home + HIGH RISK labels) | `vendor/high_odds.py` full rebuild (house slips, approved inbox/export slips, SportyBet featured hub). Risk scoring can mark a slip HIGH RISK / Heavy Home. Settling also runs `--settle-only`. | Daily 23:00 + settle jobs |
| AH −1 | `vendor/ah_minus_one.py` — SportyBet AH −1 in **1.20–1.90** (win prices nearby often 1.15–1.55). AH below 1.50 maps to Over 2.5 / team 3+ / Over 3.5; 1.50–1.90 maps to team 2+ or to-win if the matchup gate allows. Women/youth/reserves skipped. | Daily 23:00 |
| Inbox / Betting Strategies exports | JSON dropped in `engine/inbox/` (and `INBOX_PARENT/*/YYYY-MM-DD.json`), including a `shareCodes` list. Names stripped. SMAGPF ignored. Short codes are combined to 25+ (`engine/combine.py`), not dropped. | Daily collect |
| Settling, pruning, record/ledger | `engine/settle_codes.py`, `vendor/prune_live.py`, `vendor/build_record.py` | 01:45 and every two hours at :15 |
| Share cards | `vendor/share_cards.py` | After publish |
| SEO / news hub | Existing `news-sync.yml` (needs Supabase secrets). Not reimplemented inside `engine/`. | That workflow’s schedule |
| Telegram | `vendor/telegram_post.py` after publish **if** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHANNEL` (or `TELEGRAM_CHAT_ID`) are set. The older `post-social.yml` workflow can also post. | After publish |
| Premium lock | `vendor/lock_codes.py` when `P2U_LOCK_KEY` is present | After publish |

## Bookmakers

No-login public share APIs only: SportyBet, football.com, MSport, Betika, BetPawa.

Booking deep-link formats (Open / chip hrefs must load the code, not a 404 or bare homepage):

- SportyBet: `https://www.sportybet.com/gh/?shareCode={code}`
- MSport: `https://www.msport.com/gh/?shareCode={code}` (not `/gh/sports/share`)
- Betika: `https://betika.com/en-gh/share/{code}`
- football.com: `https://www.football.com/gh/?shareCode={code}`
- BetPawa: `https://www.betpawa.com.gh/share-betslip/{code}` (not `/#{code}` or bare `/`)
- Betway (when booked): `https://www.betway.com.gh/sport/soccer?bookingCode={code}`


**Betway is skipped** until a login secret exists. Do not store Betway passwords in the tree.

## Gates

`vendor/matchup_rules.py` is always enforced.

Optional `engine/gates/newrules.py` runs in `P2U_STRICT_GATES=report` (default) or `enforce`.

`gate31.py` from the Nov 5 box snapshot is **not** portable: it needs `rules31`, `flowrules`, `rulebook`, and several dated JSON caches (`graded31.json`, `sbcombo31.json`, `mgst31.json`, `fx31dc.json`, league thresholds). CI cannot rebuild those caches from public APIs today, so the engine does not call `gate31` until those inputs are regenerated. Matchup rules cover the standing vetoes.

## Self-update

1. Edit **this file** and `engine/config.json` together.
2. `python -m engine.check_rules` (also run by `engine-tests.yml`) must pass.
3. Land the change through a pull request.
