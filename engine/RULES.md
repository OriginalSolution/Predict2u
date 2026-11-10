# Predict2u engine rules (single source of truth)

Machine-readable mirror: `engine/config.json`. CI (`python -m engine.check_rules`) fails if code drifts from these numbers or vetoes.

All times below are Africa/Accra (UTC+0).

## Hard vetoes

- Never publish or book **DC 12** (Home or Away) at any price.
- Never publish or book **1X or X2** (Home or Draw / Draw or Away, including DC combo markets) when priced **above 1.35**. **1X/X2 at 1.35 or below is allowed.**
- Never publish or book **NG** (BTTS No / GG No). BTTS Yes / GG is allowed when other gates pass.
- **Obscure leagues → goals only:** competitions outside the major/well-known allowlist in `config.json` → `major_leagues.patterns` (top European leagues + their 2nd tiers, UEFA/FIFA/continental club comps, major domestic cups, MLS, Brasileiro, Argentina Primera, Saudi Pro League, Ghana Premier League, other named majors) may only use **goals markets**: Over/Under totals (including team totals) and GG/BTTS Yes. **NG remains banned.** 1X2, DC, handicap, win-to-nil, and similar non-goals markets in obscure leagues are swapped to the best stats-supported goals market or dropped. The **daily master** (`gateExempt` / Code of the Day) is the only exception.
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
| House favourites / buckets | `vendor/fav_engine.py` + `vendor/run.py` + `vendor/book_home.py` — also builds **dayMasters** (Today / Tomorrow favourites slips for the Home "How favourites perform by league" section), booked on every no-login bookmaker (`--day-masters-only` for a fast rebook) | Daily 22:00 UTC (10:00 PM Africa/Accra) |
| Hot picks | `vendor/hot_picks.py` — hub scrape + per-market/team slips; also builds **sectionMasters** (one 25+ master slip per Hot page section: Hot matches, Hot by market, Trending markets, Hot teams, Most-backed teams), booked on every no-login bookmaker and shown in the Hot carousel | Daily 22:00 UTC |
| DC Shield Goals | `vendor/dc_shield.py` — finds next-day games whose DC price is under 1.20, then books Over 1.5 / Over 2.5 / GG (**never the DC pick**) | 21:00 and again inside the 22:00 book step |
| High Odds (incl. Heavy Home + HIGH RISK labels) | `vendor/high_odds.py` full rebuild (house slips, approved inbox/export slips, SportyBet featured hub). Risk scoring can mark a slip HIGH RISK / Heavy Home. Settling also runs `--settle-only`. | Daily 22:00 UTC + settle jobs |
| AH −1 | `vendor/ah_minus_one.py` — SportyBet AH −1 in **1.20–1.90** (win prices nearby often 1.15–1.55). AH below 1.50 maps to Over 2.5 / team 3+ / Over 3.5; 1.50–1.90 maps to team 2+ or to-win if the matchup gate allows. Women/youth/reserves skipped. | Daily 22:00 UTC |
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

## Day masters persistence
- Favourites day-master codes (homeCode.dayMasters) are built only by engine/vendor/book_home.py; the box sync.sh calls the engine copies (no box-only book_home).
- Midnight UTC rollover: today's master must exist for the new date; .github/workflows/daymasters-guard.yml checks every 30 min (engine/daymasters_check.py) and dispatches engine-daily to rebook when missing. Hidden only when the day has no picks.

## 50-leg split
- Any code over 50 legs is auto-split (engine/vendor/split_codes.py) into balanced kickoff-ordered parts of <= 50 legs, each booked on SportyBet, Football.com, MSport, Betika, BetPawa (no Betway). Kicked-off legs are left out; legs a bookmaker does not offer are listed per part. Parts settle from the parent legs on every settle run. Empty bookmaker sections are hidden.


## Bets For The Day three-strategy set (High Odds, HIGH RISK)
Daily job: `engine/vendor/three_strategies.py` → `engine/data/ho-masters/`.
- O2.5 when ≥2 of: price 1.20–1.40; 1H O1.5 <2.00; league avg goals/match >2.5 (n≥20).
- Top-3 or won-last-3: win ≤1.45 else DNB. Bottom-3 or winless-last-3: DC against (never DC 12).
- Top flights only for 2&3; no top5-v-top5 / bottom3-v-bottom3. One pick/match; DC > win/DNB; O2.5 with 3/3 beats result, 2/3 loses to result.
- ASC = 50 lowest odds, DESC = 50 highest, each split 25+25. Drop started. No padding.
- Screens: top5-v-bottom3 weaker to-score >1.70; stronger AH −1 <1.90.
- Never NG, never DC 12. Published HIGH RISK, no guarantees. Settled via daily_master.

## Verzzify Edge Banker (Bankers page, odds >25)
Daily job: `engine/vendor/verzzify_banker.py`.
- Banker band 1.12–1.45 from house research + settled history (site band hit-rate n≥20 beats implied by ≥3pp, else league fav rate ≥78% with sample ≥50).
- ALL normal Predict2u rules (matchup_rules / hard vetoes / obscure goals-only / ≤50 legs).
- Pack until combined odds first exceeds 25; refuse to pad. Booked on every no-login bookmaker.

## Prune unusable codes from live sections
`vendor/prune_live.py` runs at the start of the daily job, again after publish (including after `daily_master.py`, which used to put kicked-off High Odds parts back on the active list), and after every settle. It removes a code from Home, Hot, High Odds active slips, Bankers/picks and dayMasters as soon as it is no longer bookable:

- settled (won/lost/void/push), or every leg settled
- every known kickoff has passed (still marked `pending` is not an excuse)
- slip date is before today and no leg is still upcoming
- the bookmaker share is dead (`decodeError` / `shareDead`)
- a leg breaks a hard rule (NG, DC 12, 1X/X2 above 1.35, obscure non-goals)

A slip with a future leg stays. Formally settled High Odds slips move to `history` as won/lost. Pending slips that can no longer be booked move to `history` as `expired` (not counted as a win or a loss). History, record, picks-history, the code ledger and settled `/s/` pages keep results. Expired share pages do not offer the old booking code.

The nightly publish is GitHub Actions `engine-daily.yml` at 22:00 UTC, which is 10:00 PM Africa/Accra. It does not depend on a chat bot. Settle (01:45 and every two hours) drops a code as soon as it becomes unusable, without waiting for 10 PM.

## Thin-pool fallback
`vendor/thin_pool.py` (`select`) is the only place non-hard filters may loosen, and only when the day's qualified pool has fewer than 6 bookable legs. It logs `thin-pool fallback used`. Callers: `run.py` (fav-engine near misses in `near.json`), `hot_picks.py` (backing floor 15 → 8, then matchup allow-lists), `dc_shield.py` (newrules / gate31 / short-price caps). A day that already has 6+ qualified legs does not loosen anything.

Loosened only on a thin day: matchup allow-lists, the extreme-stats bar, favourite sample floors (70%/n≥20/60% support → 60%/n≥12/50%), hot backing floor, DC Shield strict gates.

Never loosened: NG, DC 12, 1X/X2 above 1.35, obscure leagues limited to goals markets, and the 50-leg split.


## NerdyTips / Betting Strategies modules (candidates → existing pipeline)
Daily (engine-strategies.yml): `vendor/nerdytips_strategies.py` writes inbox picks.
- **2+ Streak** — SportyBet market 60010 YES <1.40 → book Win / team 2+ / O2.5
- **Team Win <1.50** — win-only legs strictly below 1.50
- **Draw rules** — draw>3.50 unbalanced → O1.5; draw<3.10 balanced → U3.5; draw>4.00 balanced → GG
- **Heavy Home Favourites** — Home AH −1.0 in 1.20–1.90 (filter) → Home Win / O2.5 / Home 2+
- **Team Total O2.5** — team O2.5 <2.00 → Win / team 2+ / O2.5
- **Exclusive O2.5 Club** — U3.5 >1.50 and one team O1.5 <1.60 → O2.5
- **BetMines Premium All Trends** — both teams support; price/league/H2H/form/table (needs `engine/data/betmines_trends.json`)
Candidates then pass standing Predict2u rules (no NG, no DC 12, 1X/X2 ≤1.35, obscure goals-only, combine 25+, ≤50 split, all bookmakers). No padding.

## Optional global gates (DISABLED by default)
`engine/gates/optional_gates.py` + `config.json` → `optional_gates`. Master `enabled: false`.
Proposed gates (all off — several conflict with standing user rules): SportyBet-GH-only, min 25 odds on every code, GG benched, Riddim-Edge legs <1.50, max 2 codes per event, force top5vtop5/bottom3vbottom3 drop, max 25 tips/code, per-league history. Do **not** enable without an explicit user decision.

## Records / settlement lifecycle
After settle: `prune_live.py` removes settled, expired and kicked-off tips from live Home/Hot/Bankers/High Odds/dayMasters/ho-masters/daily-master.
Before drop, slips are archived into `engine/data/code-ledger.json` (never delete history).
`build_record.py` rebuilds `record.json` from that ledger **plus** staked-codes + high_odds history so the Records page shows won/lost and per-leg results even on GitHub Actions (where the old box-only feed ledger is absent).
