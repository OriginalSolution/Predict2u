# Predict2u — hand-off note

Last updated: 14 Nov 2026 (Africa/Accra, UTC+0 — every time in this file is GMT/Accra = UTC).
Written so a person or bot who knows nothing about the project can pick it up.

> **This repository is PUBLIC.** Never commit a password, API key, token, card number, bank detail or
> company registration/tax number. Secrets are listed below by **name** and **where they live** only.
> Personal details that are not here are in **the owner's vault** (Grok Bot vault of the owner, Riddim Boss).

---

## 1. What Predict2u is

- **predict2u.com** — a football tips site: daily bankers, picks, high-odds slips, Hot Picks, favourites by
  league, results/record. Visitors copy **booking codes** (shared bet slips) for SportyBet, Football.com,
  MSport, Betika and BetPawa (Ghana). It is a **tips site, not a gaming/betting operator**: it never takes bets.
- Hosted on **GitHub Pages** from `main` of `OriginalSolution/Predict2u` (root `/`, custom domain via `CNAME`
  = `predict2u.com`). Every commit to `main` deploys (`pages-build-deployment`).
- Content is produced by the **engine** (`engine/`, Python) running in **GitHub Actions** on a fixed daily
  schedule. It collects fixtures, applies the rules (`engine/RULES.md`), books codes on the bookmakers' public
  no-login share endpoints, publishes JSON files the site reads, and settles results.
- Owner: **Riddim Boss** (time zone Africa/Accra).

### Current state (14 Nov 2026)
- Site up, all data feeds fresh, **free mode ON** (every code free to visitors).
- Engine books and publishes on its own every day. A **booking watchdog** catches up missed or failed
  booking jobs, so no assistant or human is needed (PR #30).
- Payments: relay is live with **Paystack TEST keys** (Medit USA LTD). Paystack **activation for the Predict2u
  business (2091346) is pending review**. Paystack asked for "Registered Business" plus a Gaming Commission
  letter, and the owner replied on 14 Nov that Predict2u is a tips site, not gaming. The paywall stays off
  until Paystack is approved and on live keys.
- Open health items: see §9.

---

## 2. Standing rules from the owner (follow these)

1. **Codes stay free until Paystack is approved AND the relay is on live keys** ("Keep Predict2u codes free
   until Paystack is live"). Don't publish locked slips. Don't flip free mode off without the owner's yes.
2. **Booking is autonomous.** Booking jobs, reruns and catch-ups need **no approval**, but **never
   double-book** (check published data and gates first; the watchdog already does this).
3. **Merge Predict2u PRs without asking** ("Dont ask me again to merge something always merge").
4. **Payments need the owner's explicit yes in chat:** spending money, Paystack authorization, switching
   payments to live, turning off free mode. An agent's approval never counts, only the owner's own words.
5. `high_odds.json` must stay **compact one-line JSON**.
6. Never reveal secret values; give names and storage paths only.
7. Don't re-enable the hand-disabled workflows (§5.4) unless the owner says so.
8. Payment reports go **only** to `meditusa2023@gmail.com`.

---

## 3. Repositories (GitHub org/account `OriginalSolution`, formerly `riddimbossy-prog`)

| Repo | Visibility | Default branch | What it is | Deploy |
|---|---|---|---|---|
| [`Predict2u`](https://github.com/OriginalSolution/Predict2u) | **PUBLIC** | `main` | Site (static HTML/JS/JSON) + engine (`engine/`) + all workflows | GitHub Pages from `main` → https://predict2u.com |
| [`p2u-relay`](https://github.com/OriginalSolution/p2u-relay) | PUBLIC | `main` | Node payment/unlock relay (`server.js`, `persist.js`, `render.yaml`, admin page) | Render web service, auto-deploy on commit to `main` |
| [`Predict2u-live`](https://github.com/OriginalSolution/Predict2u-live) | PUBLIC | `main` | Live-scores redesign (Vite/TS app: purple match cards, board, bankers, public proof). Has no relay URL and no workflows | Not deployed by any workflow; no Pages site |

Other branches in `Predict2u` (`cursor/*`, `engine/*`, `feature/*`, `fix/*`, `nerdytips-strategies`,
`selfheal-watchdog`, `handoff-doc`) are old work branches; their PRs are merged except **PR #1**
("Add market profile intelligence to Team Intelligence", open since Aug 2026, never merged).

**PRs #9, #10, #11:** the owner's earlier rule said "don't merge #9/#10/#11 without his yes". On GitHub all
three already show as **MERGED** (#9 nightly clearing of unusable codes, #10 daily publish KeyError fix,
#11 rebase-autostash fix for the refresh workflows). Nothing to do; don't revert them without the owner's yes.

Recent PRs worth reading for context: #16 (paywall for >25 odds), #18 (on-time ticker and gates), #21 (health
check), #25 (free mode), #26 (new relay URL), #27 (favourites restore), #28 (night jobs and ticker reload),
#29 (Hot Picks fix), #30 (booking watchdog and monitor).

---

## 4. How the site gets its data

The site reads these files from the repo root (written only by the engine):

| File | Content | Written by |
|---|---|---|
| `home-picks.json` | Home page: picks, slips, `homeCode` (home code + `dayMasters` = favourites day-master codes for today/tomorrow), favourites by league | daily, shield, morning, fav-leagues, strategies, settle |
| `picks.json`, `picks-history.json`, `record.json` | Picks and track record | daily, settle |
| `high_odds.json` (**one line**) | High odds / Bets For The Day / master / GG / NYSM / NT slips | strategies, morning, GG, NYSM, NT, strategy-master |
| `hot-picks.json` | Hot Picks (SportyBet Code Hub scan), M1/M2, Safest | daily (Hot Picks), m1m2, Hot Picks catch-up |
| `fav-leagues.json` | Favourites-by-league backup used by `engine/fav_guard.py` | fav-leagues |
| `fixtures.js`, `sportybet-odds.js`, `current-data.js` | Fixtures and odds | sportybet-odds |
| `news-hub.json`, `live-scores.json` | News hub and live scores snapshot | engine-refresh |
| `dead-codes.json`, `health.json` | Codes hidden because they no longer load; health status | health check |
| `locked.enc.json` | Encrypted store of premium codes (paid mode only) | engine (`engine/premium.py`) |

### Booking
- `engine/bookers.py` posts to the bookmakers' **public no-login share endpoints**: **SportyBet**, **Football.com**
  (same platform, reuses the SportyBet code), **MSport**, **Betika**, **BetPawa** (`engine/bp_book.py`).
  **Betway is skipped** (needs a logged-in account). No bookmaker passwords are used.
- Since PR #30 each call retries network failures with backoff, and a book that is down gets one try per call
  (circuit breaker).
- **NYSM** books SportyBet only and only slips with combined odds ≥ 25, so an NYSM run that books nothing is normal.
  GG and NT can also legitimately book nothing on a day with no qualifying games.

### Free / paid switch
- `p2u-free-mode.js`: `window.P2U_FREE_CODES = true;` = free mode (now). The engine reads the same line
  (`engine/premium.py free_mode()`). `false` = paywall (`p2u-paywall-v3xx.js` via the relay) and engine sealing
  of codes with odds > 25 come back. Keep the exact format `P2U_FREE_CODES = true;`.

---

## 5. GitHub Actions (all in `Predict2u/.github/workflows/`)

### 5.1 The on-time scheduler (ticker)
GitHub's own cron on this repo runs hours late or drops runs. So **`engine-ticker.yml`** runs
`.github/scripts/p2u_ticker.py`, which stays alive about 5h40m, checks the clock every minute, dispatches each
workflow at its slot (`SCHEDULE` list in that file, 15-minute grace), and then dispatches its own successor.
- It re-reads `SCHEDULE` from `main` whenever `main` moves, so a schedule edit takes effect within a minute.
- A ticker started on newer ticker code cancels the older one with no gap. Same-code tickers hand over within 4 min.
- Its own cron `7,37 * * * *` only restarts the chain if it breaks. The watchdog also restarts it.
- Each booking workflow still has its own GitHub cron as a late fallback.

**Run-once gates** — `.github/scripts/p2u_gate.py --at HH:MM --job <job>`: a run is skipped when, inside the slot
window (6h before to 18h after), an older run is still in flight or its real job already **succeeded**. A failed
run never blocks a retry. Manual `workflow_dispatch` with `force: true` (or `dry_run: true`) bypasses the gate.

**Push** — `.github/scripts/p2u_push.sh main`: 5 attempts of fetch, `rebase --autostash` and push, with backoff.
After a rebase, `home-picks.json` is re-merged section by section (`p2u_merge_live.py`) so one job's stale copy
can't wipe sections another job published.

**fav_guard** — `engine/fav_guard.py` restores the favourites-by-league section from `fav-leagues.json` or git
history if any job emptied it. It runs after every engine job and never books.

### 5.2 Daily schedule (ticker slots, GMT = Accra)

| Time | Workflow | Books? | What |
|---|---|---|---|
| 06:00 | `engine-fav-leagues.yml` | yes | Favourites by league: stats and day-master codes for today and tomorrow |
| 06:00 | `engine-strategy-master.yml` | yes | Code of the Day from the night's strategy codes |
| 07:00 | `engine-morning.yml` | yes | SportyBet stats markets, one 1.20–1.60 pick per match, plus master slip |
| 07:30 | `engine-health.yml` | heal only | Post-run check of night/morning jobs |
| 18:00 | `engine-health.yml` | no | **Preflight**: compile/import every module, dry-run every strategy for tomorrow in a no-write sandbox, site checks |
| 21:00 | `engine-shield.yml` | yes | DC Shield Goals and AH −1 scan |
| 21:45 | `engine-m1m2.yml` | yes | M1/M2 and Safest market (Hot page) |
| 22:00 | `engine-daily.yml` | yes | Daily collect, book, publish (home code, slips, **Hot Picks**, high odds, three strategies, Verzzify, daily master) |
| 22:30 | `engine-strategies.yml` | yes | Three-strategy High Odds and Verzzify Edge Banker |
| 23:10 | `engine-gg.yml` | yes | GG / BTTS-Yes for the next Accra day (SportyBet) |
| 23:15 | `engine-health.yml` | heal only | Post-run check of the evening booking jobs |
| 23:30 | `engine-nysm.yml` | yes | NYSM decision tree v2 (SportyBet, odds ≥ 25 only) |
| 23:50 | `engine-nt-tomorrow.yml` | yes | NerdyTips Tomorrow (trust 5.0+, Agree only) |
| 01:45, every 2h at :15 | `engine-settle.yml` | no | Settle all codes, prune, rebuild record |
| every 3h at :19 | `sportybet-odds.yml` | no | SportyBet markets, odds, fixtures |
| hourly at :25 | `engine-refresh.yml` | no | News hub and live-scores snapshot |
| 06:15, 14:15, 22:15 | `engine-self-heal.yml` | no | Sync BUILD_VERSION/sw cache, share pages; reruns Site Quality checks; opens issue if still red |
| :10 and :40 hourly | `daymasters-guard.yml` | no | If today's favourites day-master codes are missing, dispatches the watchdog |
| :05 and :35 hourly | `engine-watchdog.yml` | catch-up | Booking watchdog (§5.3) |
| 01:17, 07:17, 13:17, 19:17 | `monitor.yml` | no | Self-healing monitor (§5.3) |
| 00:15 / 00:30 / 00:45 / 00:50 | `daily-picks-email`, `results-email`, `tracker-email`, `post-social` | no | Daily emails (`MAIL_*`) and Telegram post |
| Sun 18:00 | `weekly-digest.yml` | no | Weekly digest email (Resend + Supabase) |

Not scheduled: `engine-hot-picks.yml` (Hot Picks alone; dispatched by the watchdog), `engine-tests.yml` (unit tests
and pyflakes on PRs/pushes touching `engine/**`), `site-quality.yml` (PR/push site checks), `publish-image.yml`,
`odds-api-refresh.yml`.

### 5.3 Self-healing (runs with no assistant and no credits)
- **Booking watchdog** — `engine-watchdog.yml` + `.github/scripts/p2u_watchdog.py`
  ([workflow](https://github.com/OriginalSolution/Predict2u/actions/workflows/engine-watchdog.yml)).
  - **Triggers:** ticker at :05/:35, four GitHub crons, and the end of every booking workflow and of the ticker
    (`workflow_run`).
  - **What it checks:** for each product (favourites, Code of the Day, morning, shield, M1/M2, daily, Hot Picks,
    strategies, GG, NYSM, NT) it looks at the latest slot that is at least 20 min old and still bookable.
  - **What it does:** if a run is going, it waits. If the codes are published, it does nothing. Otherwise it
    re-dispatches the job, waiting 10/30/60 min between tries, max 3 tries per slot.
  - **No double booking:** if a run succeeded but its codes are missing, it is re-run with `force=true` at most
    once. Products that can legitimately book nothing (GG, NYSM, NT, shield, M1/M2, strategies, master) are only
    re-run when no run succeeded.
  - **Also:** restarts a dead ticker and re-enables engine workflows that GitHub disabled for 60-day inactivity
    (never hand-disabled ones). If it gives up, it opens one issue `[watchdog] Booking catch-up needs attention`
    (label `monitor`).
- **Monitor** — `monitor.yml` + `.github/monitor/` (`monitor.py`, `monitor_lib.py`, `checks.json`, `README.md`)
  ([workflow](https://github.com/OriginalSolution/Predict2u/actions/workflows/monitor.yml)).
  - **Checks:** predict2u.com, the high-odds page, the free-mode switch, the relay `/health`, feed freshness
    (`home-picks.json`, `hot-picks.json`, `high_odds.json`, `picks.json` ≤ 30h; `fixtures.js`,
    `sportybet-odds.js` ≤ 8h) and the HTTPS certificate.
  - **Issues:** one `monitor` issue per failing check, closed automatically when the check passes again.
  - **Safe fixes only:** a stale feed dispatches the watchdog. The relay redeploys only if the
    `RENDER_DEPLOY_HOOK` secret exists. Payment emails go to meditusa2023@gmail.com only if `GMAIL_APP_PASSWORD`
    exists.
  - **Never:** merges PRs, re-enables workflows, touches payments or free mode.
- **Health check** — `engine-health.yml` + `engine/health.py` (18:00 preflight; 23:15 and 07:30 post-run).
  It keeps one rolling issue (**#22**) and self-heals safe things: restarts the ticker, reruns refresh jobs,
  hides dead codes, restores favourites. Telegram alerts work only if `TELEGRAM_ALERT_CHAT_ID` is set (it is not).

### 5.4 Disabled workflows (disabled by hand — leave them off unless the owner says so)
`live-scores.yml` (Live Scores), `news-sync.yml` (Football News Sync), `future-fixtures.yml` (Fast All Games),
`fixture-snapshot.yml` (Fast Fixture Snapshot), plus `auto-picks-learning.yml`, `probe-markets.yml`, `probe-sot.yml`,
`settle-slips.yml`, `update-data.yml`, `update-scores.yml`. Their outside services are gone or replaced by the engine.

---

## 6. Services and accounts

| Service | What | Account / login | Notes |
|---|---|---|---|
| GitHub | All repos, Pages, Actions | `OriginalSolution` (same account as old `riddimbossy-prog`) | Box `gh` CLI is logged in; token in `/home/box/.config/gh/hosts.yml` (box only) |
| GitHub Pages | predict2u.com hosting | same | Source `main` `/`; CNAME `predict2u.com` |
| Domain predict2u.com | DNS → GitHub Pages | Registrar/login: **unknown** (not in repo or memory) | Renewal date **unknown** |
| Render | Relay web service `p2u-relay` | Render workspace `tea-dbr591uc6qcc73crvc2g`; login in **the owner's vault** | Service `srv-dbr5cqt9fdbs73db28k0`, URL https://p2u-relay-c0mn.onrender.com, Frankfurt, plan **Starter**, auto-deploy on commit to `p2u-relay` `main`, created 13 Nov 2026. `render.yaml` also defines Key Value `p2u-relay-kv` (free). **Old `p2u-relay.onrender.com` is retired** (site repointed in PR #26) |
| Paystack (Medit USA LTD) | Card/MoMo payments for unlocks | Medit USA LTD Paystack account; login in **the owner's vault** | Relay runs on its **TEST** keys (`pay:true` in `/health`) |
| Paystack (Predict2u, business 2091346) | Predict2u's own activation | account mail: `predict2u@gmail.com` | **Pending review**; see §1 |
| Supabase project `tjbkkhirnwfensqzuvzn` | Community features: profiles, slips, follows, tails, leaderboard, user ranks, reports, avatars (`community.js`, `slip.js`, `board.html`, `cloud-config.js`), the weekly digest and the disabled news sync | Org / owner login: **unknown** (not determinable from the repo) | Browser uses the public publishable key (in `cloud-config.js`); server key is the `SUPABASE_SECRET_KEY` repo secret. SQL migrations in `supabase/` |
| Bookmakers | SportyBet, Football.com, MSport, Betika, BetPawa | none (public no-login share endpoints) | Betway skipped |
| Gmail `predict2u@gmail.com` | Paystack account mail; relay `ADMIN_EMAIL` | password in **the owner's vault** | Watched daily for Paystack review emails |
| Gmail `meditusa2023@gmail.com` | **Back channel**: the owner emails with subject starting `Predict2u fix`; payment reports go here | password in **the owner's vault** | Daily routine reads it and replies in the thread |
| Telegram | Code posts (`post-social.yml`, engine publish) | bot token in repo secrets | |
| Resend | Weekly digest email | API key in repo secrets | |
| The Odds API / API-Football / stats API | Older data feeds (mostly the disabled workflows; `odds-api-refresh.yml`) | keys in repo secrets | |

### Costs and renewals (known)
- GitHub Actions/Pages: free (public repo).
- Render `p2u-relay` web service: **Starter** plan (Render's list price is about $7/month; billing date unknown).
  Key Value `p2u-relay-kv`: free plan.
- Supabase: plan and cost **unknown**.
- Domain predict2u.com: cost and renewal **unknown**.
- Paystack: no fixed fee known; per-transaction fees once live.
- Any purchase needs the owner's yes in chat (card details are in the owner's vault; never put them here).

---

## 7. Secrets and environment variable names (values are NEVER in this repo)

### GitHub repo secrets — `OriginalSolution/Predict2u` (Settings → Secrets and variables → Actions)
`P2U_LOCK_KEY` (AES key that seals premium codes; must match the relay's `LOCK_KEY`), `TELEGRAM_BOT_TOKEN`,
`TELEGRAM_CHAT_ID`, `MAIL_USERNAME`, `MAIL_PASSWORD` (daily emails), `RESEND_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SECRET_KEY`, `NEWS_SYNC_SECRET`, `PUSH_DISPATCH_SECRET`, `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`,
`VAPID_SUBJECT` (web push), `ODDS_API_KEY`, `API_FOOTBALL_KEY`, `STATS_API_KEY`, `API_KEY`,
`AUTO_LEARNING_POLICY_B64`, and tuning values `DAYS_BACK`, `DAYS_FWD`, `H2H`, `LEAGUES`, `MAX_LEAGUES`,
`MAX_PROBES`, `ODDS`, `REQUEST_BUDGET`, `SEASON`, `SLEEP_MS`.
**Not set yet (optional):** `TELEGRAM_ALERT_CHAT_ID` (health alerts), `TELEGRAM_CHANNEL`, `RENDER_DEPLOY_HOOK`
(monitor can redeploy the relay), `GMAIL_APP_PASSWORD` (monitor payment emails). As of 14 Nov the last two
did not appear in the repo's secret list, so those monitor fixes are inactive until they are added.
`p2u-relay` and `Predict2u-live` have no GitHub secrets.

### Relay environment (Render dashboard → p2u-relay → Environment)
`ADMIN_EMAIL` (= predict2u@gmail.com), `ADMIN_PASSWORD`, `ADMIN_PASSWORD_SHA256`, `LOCK_KEY`, `LOCKED_URL`,
`PAYSTACK_SECRET_KEY`, `PAYSTACK_PUBLIC_KEY`, `REDIS_URL` (from `p2u-relay-kv`), `PORT`.
Backup copy of the relay env on the box: `/home/box/secrets/render-env-backup-2026-11-13/p2u-relay.env`.

### Files on the owner's box (shared Grok Bot machine; not in git)
- `/home/box/secrets/nsaabo-paystack/PAYSTACK_PUBLIC_KEY` and `PAYSTACK_SECRET_KEY`: the Medit USA LTD Paystack
  **test** keys the relay uses.
- `/home/box/secrets/medit-usa-ltd/`: Medit USA LTD company material.
- `/home/box/secrets/render-env-backup-2026-11-13/`: Render env backups.
- Logins (GitHub, Render, Paystack, Gmail, Supabase, card): **saved in the Grok Bot vault** of the owner.

---

## 8. The Grok routine (outside git)

**"Predict2u daily self-check"** — a Grok Bot routine, about **08:30 Accra daily** (after the 07:00 morning job and
07:30 health check). It:
- checks the site, Actions, relay, watchdog and monitor, and fixes breakages with a merged PR;
- reads `meditusa2023@gmail.com` for emails with a subject starting **`Predict2u fix`**, fixes the problem and
  replies in that thread;
- watches `predict2u@gmail.com` for Paystack review emails on the "Activation Request for Predict2u (2091346)"
  thread (read-only; never replies to Paystack);
- emails the owner **only about payments**, from and to `meditusa2023@gmail.com`;
- may rerun booking jobs (no approval needed, no double booking), but asks the owner in chat before any payment
  step (spending, Paystack authorization, going live, ending free mode).

The engine does **not** depend on this routine: booking and self-healing all run in GitHub Actions (§5.3).

---

## 9. Open issues, gaps and pending decisions

- **Issue #22**: rolling health-check issue. On 14 Nov 18:00 it listed: `/league/slovakia-2-liga.html` returns 503;
  dry runs of `engine.pipeline daily`, `shield` and `settle` hit `TypeError: 'int' object is not iterable` (they
  continue, but this should be traced); 6 dead codes hidden.
- **Issue #8**: old "Self-heal could not clear Site Quality (2026-11-09)", still open. Close it once Site Quality is
  green (the owner asked to close it only when he says so).
- **`monitor` issues**: none open as of 14 Nov (opened/closed automatically).
- **PR #1**: open since Aug 2026, unreviewed.
- **Known gaps:**
  - ESPN news feed is empty (news hub shows no ESPN items).
  - NerdyTips Tomorrow for 13 Nov failed and was never booked (too late now).
  - Two 8 Nov locked codes (`banker-20261108`, `medium-20261108`) were lost; no saved code exists, so they stay hidden.
  - Ad scripts (Adsterra / Monetag): the owner hasn't decided yet; don't add or remove without his yes.
  - `RENDER_DEPLOY_HOOK` and `GMAIL_APP_PASSWORD` secrets aren't set or verified.
  - `TELEGRAM_ALERT_CHAT_ID` isn't set (add only if the owner asks).
- **Pending decisions (owner):** switching to paid mode after Paystack approval and live keys; ad scripts.

---

## 10. How to…

### Run the tests locally
```bash
git clone https://github.com/OriginalSolution/Predict2u.git && cd Predict2u
python3 -m venv .venv && . .venv/bin/activate
pip install pytest pyflakes pyyaml pillow cryptography
python -m pytest engine/tests -q          # ~210 tests, no network
python -m engine.check_rules              # rule self-check
python -m pyflakes engine .github/scripts # no undefined names
```
Dry-run an engine job (no booking, no commit): `python -m engine.pipeline daily --dry-run` (also `shield`,
`morning`, `fav`, `hot`). Watchdog dry run: `P2U_WATCHDOG_DRY=1 GH_TOKEN=$(gh auth token) python3 .github/scripts/p2u_watchdog.py`.
Monitor locally: `cd .github/monitor && python3 monitor.py` (no token = no issues touched).

### Run / trigger workflows
- GitHub → Actions → pick the workflow → **Run workflow** (or `gh workflow run <file>.yml -R OriginalSolution/Predict2u --ref main`).
- Booking workflows accept `dry_run` and `force`. The gate skips a slot that already succeeded; use
  `-f force=true` only when you've checked the codes are **not** published (otherwise you double-book).
  Simplest safe path: `gh workflow run engine-watchdog.yml` — it decides what (if anything) to re-run.
- Hot Picks alone: `gh workflow run engine-hot-picks.yml`.
- Restart the scheduler: `gh workflow run engine-ticker.yml` (the watchdog does this automatically).
- Change a slot: edit `SCHEDULE` in `.github/scripts/p2u_ticker.py` and merge. The live ticker picks it up within a minute.
  Keep each booking workflow's gate `--at` time equal to its slot (a test checks this).

### Deploy
- **Site:** merge to `main` → GitHub Pages deploys automatically. When you change site JS/CSS, bump
  `BUILD_VERSION.txt`, `sw.js` and the `?v=` query strings (the self-heal job keeps them in sync). PR checks:
  `engine-tests.yml` (pytest, check_rules, pyflakes) and `site-quality.yml`.
- **Relay:** commit to `OriginalSolution/p2u-relay` `main` → Render auto-deploys `srv-dbr5cqt9fdbs73db28k0`.
  Env vars are changed in the Render dashboard (never in git). Health: `curl https://p2u-relay-c0mn.onrender.com/health`
  should return `{"ok":true,...,"pay":true}`.

### Switch to paid mode (ONLY with the owner's yes, after Paystack approval and LIVE keys)
1. Put the **live** `PAYSTACK_SECRET_KEY` / `PAYSTACK_PUBLIC_KEY` on the Render relay (dashboard → Environment) and
   confirm `/health` shows `pay:true`. Do a real test payment with the owner.
2. Make sure the relay `LOCK_KEY` equals the repo secret `P2U_LOCK_KEY` (both set; values never shown).
3. In `p2u-free-mode.js` set `window.P2U_FREE_CODES = false;` (keep the format), bump the cache version, open a PR, merge.
4. The next engine runs flag and seal codes with odds > 25 (`engine/premium.py`, `lock_codes.py`), and the
   paywall (GHS 50 per product per day: banker / medium / hot) sells them via the relay.
5. To go back to free: set it to `true` again.

---

## 11. Quick health checklist for a new owner/bot
1. https://predict2u.com loads; feeds are fresh (run `monitor.yml` or look at its last run).
2. Actions: `engine-ticker.yml` has a run **in progress**; `engine-watchdog.yml` runs every ~30 min and is green.
3. Issue #22 (health) and any `monitor` / `[watchdog]` issues.
4. `curl https://p2u-relay-c0mn.onrender.com/health` → `ok:true`.
5. `p2u-free-mode.js` still `true` unless the owner switched to paid.
