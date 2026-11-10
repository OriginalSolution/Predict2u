# Predict2u autonomous engine

This package lets the daily pipeline run on GitHub Actions even when the assistant is offline.

## What it does

1. **Collect** — pull upcoming fixtures from the public SportyBet GH factsCenter API, then run the house favourites/buckets engine (`vendor/fav_engine.py` + `vendor/run.py`). Extra picks can be dropped into `engine/inbox/` as JSON (teammate bots cannot be invoked from cron). SMAGPF files are ignored. Bot and tipster names are stripped.
2. **Gate** — see `RULES.md` / `config.json`. Hard vetoes: DC 12 (Home or Away) always; 1X/X2 only above 1.35; no NG (BTTS No). Skip top-5 v top-5 and bottom-3 v bottom-3; mismatch → GG / Over 1.5; middle → GG only; even → no Over 1.5 / Over 2.5; Over 1.5 or Under 3.5 above 1.30 needs strong stats; no leg above 1.60 without extreme stats; main slips 25+. Optional `newrules.py` lives in `engine/gates/` (report mode by default; set `P2U_STRICT_GATES=enforce` to drop failures). `gate31` is documented but not called until its snapshot caches can be rebuilt.
3. **Book** — public no-login share APIs: SportyBet, Football.com, MSport, Betika, BetPawa. Betway needs a login and is skipped. Strategies: house favourites, hot picks, DC Shield Goals, High Odds (Heavy Home / HIGH RISK), AH −1, plus inbox/export slips.
4. **Publish** — rebuild `picks.json` / `home-picks.json`, prune expired codes, optionally lock premium codes, rebuild High Odds, write the record/ledger, refresh share cards, and post to Telegram when those secrets exist.
5. **Settle** — grade every pending pick on the published JSON files as won, lost, or void.

## Schedule (Africa/Accra = UTC+0)

| Workflow | Cron (UTC) | Job |
|---|---|---|
| `engine-shield.yml` | `0 21 * * *` (9:00 PM) | DC Shield Goals + AH −1 scan + publish |
| `engine-strategies.yml` | `30 22 * * *` (10:30 PM) | Bets For The Day three-strategy High Odds masters + Verzzify Edge Banker |
| `engine-morning.yml` | `0 7 * * *` (7:00 AM) | SportyBet stats markets (one 1.20–1.60 pick per match) |
| `engine-daily.yml` | `0 23 * * *` (11:00 PM) | collect + book + publish (all strategies) |
| `engine-settle.yml` | `45 1 * * *` (1:45 AM) and `15 */2 * * *` | settle + prune + record |
| `engine-tests.yml` | on push/PR to `engine/**` | unit tests + `python -m engine.check_rules` |

Scheduled jobs only commit when they run on `main`. Pull requests run the unit tests and a `--dry-run` collect is **not** forced (network-heavy); tests are local.

## Secrets the user must add

| Secret | Required? | Why |
|---|---|---|
| `P2U_LOCK_KEY` | Yes, before the daily job commits banker/hot codes | Hex AES key that matches the existing `predict2u-feed/private/lock.key`. Without it the job will still generate files but must not publish unlocked premium codes. Do not put the key in chat. |
| Betway login | No | Betway is skipped in this engine. To add it later, store credentials as repo secrets (never in the tree) and wire them yourself. |
| `TELEGRAM_BOT_TOKEN` plus `TELEGRAM_CHANNEL` or `TELEGRAM_CHAT_ID` | No | Engine posts codes after publish when these are set. The existing `post-social.yml` workflow can also post. |
| `SUPABASE_URL` / `SUPABASE_SECRET_KEY` / `NEWS_SYNC_SECRET` | No for pick booking | Required by the existing `news-sync.yml` SEO/news hub workflow. |

Booking uses public share endpoints and does not need bookmaker passwords.

## Local commands

```bash
python -m engine.pipeline collect --dry-run
python -m engine.pipeline daily --dry-run
python -m engine.pipeline settle
python -m pytest engine/tests -q
python -m engine.check_rules
```

## Daily strategy jobs

- `vendor/three_strategies.py` — ASC/DESC 50-pick masters (25+25 splits) + top5-v-bottom3 screens → `engine/data/ho-masters/` → High Odds (HIGH RISK).
- `vendor/verzzify_banker.py` — Verzzify Edge Banker (>25 odds, all normal rules) → Bankers / home Main slip + `engine/inbox/p2u/`.

## Pick sources (no bot calls)

The house engine reads:

- SportyBet upcoming events: `https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents`
- SportyBet event markets: `https://www.sportybet.com/api/gh/factsCenter/event`
- Sportradar stats hosted for SportyBet: `https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/`
- Historical closing odds CSVs in `engine/data/` for a few leagues (football-data.co.uk extracts already used by the research engine)

That is the same public data the box research pipeline already used, rather than calling other assistants.

## Teammate code batches → High Odds

`python -m engine.teamcodes CODE ... --void X Y` decodes each SportyBet code, applies every rule (`combine.process`), keeps codes still at or above `min_main_slip_odds` (25, `config.json`) as their own slip and pools the rest into deduped 25+ combined slips. It books SportyBet and writes `engine/inbox/p2u/<date>.json`; `vendor/high_odds.py` then publishes those slips on High Odds (its eligibility rule is odds ≥ 25), books Football.com / MSport / Betika / BetPawa, skips duplicates by leg fingerprint, and exempts these batches from the 12-card hub cap.


## SportyBet morning markets

`python -m engine.pipeline morning` (cron 07:00 Africa/Accra) walks today's not-started SportyBet GH football, scores every modelable market with SportyBet-hosted Sportradar tables, last-x form, H2H and a Poisson model, and books one pick per match. Odds must be between 1.20 and 1.60 inclusive. Youth/reserve/women/virtual games, BTTS No and Home-or-Away double chance are skipped. Codes are published onto `home-picks.json` as `SportyBet Stats` slips (SportyBet, Football.com, MSport, Betika, BetPawa). When more than one pick qualifies, a combined master slip is also booked; if total odds are 25 or more it is marked high risk and listed on the High Odds page.
