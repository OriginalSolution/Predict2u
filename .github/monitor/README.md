# Predict2u self-healing monitor

Predict2u copy of the self-healing monitor template. Config: `checks.json` (predict2u.com, the p2u relay, data feeds). Feed checks add `max_age_hours`/`time_field`/`time_regex`; `catchup: true` dispatches the booking watchdog (`.github/scripts/p2u_watchdog.py`) when a feed is stale. Workflow: `.github/workflows/monitor.yml`.


Checks your app every 3 hours on GitHub's own runners, so it keeps working with no bot credits.
It opens **one GitHub issue per problem** (label `monitor`), quietly updates it while the problem
lasts, and **closes it by itself** when the check passes again. GitHub emails the repo owner
about new issues. Payment-related checks can also send an email.

Used live by TraffiAlert GH: `TraffiAlertGH/traffialert-site` → `.github/workflows/monitor.yml`
(a richer version with payment and download checks).

## Copy it

1. Copy `.github/monitor/` and `.github/workflows/monitor.yml` into your repo (default branch:
   scheduled workflows only run from there).
2. Edit `.github/monitor/checks.json`: replace every `YOUR-...` placeholder with your URLs and
   delete checks you do not need.
3. Edit `MAIL_FROM` / `MAIL_TO` in the workflow (or leave email off).
4. Commit, then run it once: **Actions → Monitor (self-healing) → Run workflow**.

## Check options (`checks.json`)

| Field | Meaning |
|---|---|
| `name` | Shown in the summary and as the issue title `[monitor] name` |
| `url` | Address to call (HTTPS is verified) |
| `expect` | Status code, default `200` |
| `contains` | Text that must be in the answer |
| `timeout` | Seconds, default 20 (use 75 for free Render services that sleep) |
| `method` | `GET` by default |
| `headers_env` | `{ "header": "ENV_NAME" }` sends a header from a secret |
| `json_ok_field` | JSON key that must be true, e.g. `ok` |
| `redeploy_hook_env` | Env var with a deploy hook URL; POSTed when the check fails twice in a row |
| `payment` | `true` = also email when it goes down and when it is back |

`certificates`: domains whose HTTPS certificate must have 10+ days left.

## Optional secrets (Settings → Secrets and variables → Actions)

| Secret | What for |
|---|---|
| `RENDER_DEPLOY_HOOK` | Render dashboard → service → Settings → Deploy Hook. Lets the monitor redeploy a dead service. |
| `GMAIL_APP_PASSWORD` | Google Account → Security → 2-Step Verification on → App passwords → create one for "GitHub monitor". Paste the 16 letters. Used only to send alerts from `MAIL_FROM`. |
| `SUPABASE_ANON_KEY` (or any key) | Only if a check needs a header from `headers_env`. Use read-only keys only. |

Never put passwords or keys in `checks.json` or the workflow file; only secrets.

## Cost

- Public repo: free and unlimited.
- Private repo: each run bills at least 1 minute of the 2,000 free minutes a month. Every 3 hours
  is about 240 a month; every 6 hours is about 120.

## Safe auto-fixes only

The template only wakes services (second try) and calls a deploy hook. Add more fixes in
`monitor.py` only if they cannot lose data (re-run a failed job, re-ping, redeploy) - never deletes.
