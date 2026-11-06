# Predict2u autonomous engine

This package lets the daily pipeline run on GitHub Actions even when the assistant is offline.

## What it does

1. **Collect** — pull upcoming fixtures from the public SportyBet GH factsCenter API, then run the house favourites/buckets engine (`vendor/fav_engine.py` + `vendor/run.py`). Extra picks can be dropped into `engine/inbox/` as JSON (teammate bots cannot be invoked from cron). SMAGPF files are ignored. Bot and tipster names are stripped.
2. **Gate** — `vendor/matchup_rules.py`: no double chance anywhere; skip top-5 v top-5 and bottom-3 v bottom-3; mismatch → GG / Over 1.5; middle → GG only; even → no Over 1.5 / Over 2.5; Over 1.5 or Under 3.5 above 1.30 needs strong stats; no leg above 1.60 without extreme stats. Optional `newrules.py` / `gate31.py` live in `engine/gates/` (report mode by default; set `P2U_STRICT_GATES=enforce` to drop failures).
3. **Book** — public no-login share APIs: SportyBet, Football.com, MSport, Betika, BetPawa. Betway needs a login and is skipped.
4. **Publish** — rebuild `picks.json` / `home-picks.json`, prune expired codes, optionally lock premium codes, settle High Odds.
5. **Settle** — grade every pending pick on the published JSON files as won, lost, or void.

## Schedule (Africa/Accra = UTC+0)

| Workflow | Cron (UTC) | Job |
|---|---|---|
| `engine-daily.yml` | `0 23 * * *` (11:00 PM) | collect + book + publish |
| `engine-settle.yml` | `45 1 * * *` (1:45 AM) and `15 */2 * * *` | settle + prune |

Scheduled jobs only commit when they run on `main`. Pull requests run the unit tests and a `--dry-run` collect is **not** forced (network-heavy); tests are local.

## Secrets the user must add

| Secret | Required? | Why |
|---|---|---|
| `P2U_LOCK_KEY` | Yes, before the daily job commits banker/hot codes | Hex AES key that matches the existing `predict2u-feed/private/lock.key`. Without it the job will still generate files but must not publish unlocked premium codes. Do not put the key in chat. |
| Betway login | No | Betway is skipped in this engine. To add it later, store credentials as repo secrets (never in the tree) and wire them yourself. |

Existing repo secrets already used by other workflows (`API_FOOTBALL_KEY`, Telegram, Supabase, etc.) are not required for this engine. Booking uses public share endpoints and does not need passwords.

## Local commands

```bash
python -m engine.pipeline collect --dry-run
python -m engine.pipeline daily --dry-run
python -m engine.pipeline settle
python -m pytest engine/tests -q
```

## Pick sources (no bot calls)

The house engine reads:

- SportyBet upcoming events: `https://www.sportybet.com/api/gh/factsCenter/pcUpcomingEvents`
- SportyBet event markets: `https://www.sportybet.com/api/gh/factsCenter/event`
- Sportradar stats hosted for SportyBet: `https://stats.fn.sportradar.com/sportybet/en/Europe:Berlin/gismo/`
- Historical closing odds CSVs in `engine/data/` for a few leagues (football-data.co.uk extracts already used by the research engine)

That is the same public data the box research pipeline already used, rather than calling other assistants.
