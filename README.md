> **New here? Read [HANDOFF.md](HANDOFF.md)** — full hand-off note: what Predict2u is, repos, workflows, services, secrets (names only), rules and how to run/deploy.

# Predict2U Final Week-Fixture Replacement Pack v239

This pack contains only the final files required for the seven-day fixture pipeline.

## Replace at repository root

- `fetch-data.js`
- `write-config.js`
- `verify-week-data.js`
- `package.json`
- `queue-push-events.js`
- `config.example.txt`

## Replace inside `.github/workflows/`

- `future-fixtures.yml`
- `live-scores.yml`

## Required secret value

Set the existing `DAYS_FWD` repository secret value to `6`.

Do not upload a real `config.txt` containing API keys, and do not remove `data.js` or `community.js`.
