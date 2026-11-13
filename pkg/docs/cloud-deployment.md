# Telegram worker with Cloudflare D1

The worker runs in GitHub Actions on weekdays in two Jakarta-time windows:

- 08:20–13:05 WIB
- 13:20–16:00 WIB

GitHub provides the Python runner. A small authenticated Cloudflare Worker proxy gives Python access to D1. D1, rather than GitHub artifacts or a checked-in database file, holds the durable signal queue, scan cache, and alert history.

## Free-plan limits and accuracy

D1 Free currently includes up to 500 MB per database, 5 million rows read per day, and 100,000 rows written per day across the account. It stops accepting queries for the day if read/write quotas are exceeded. The local SQLite file is about 60 MB and contains about 302,000 `shared_records`, so copying the entire file is not a suitable initial free-tier import.

The cloud seed imports the latest 21 price dates and selected small tables required by the scanner. Run `seed_d1.py` without `--apply` first to inspect the row count. The script refuses to seed over 30,000 source rows. D1 also counts index writes, so watch **D1 → Metrics → Row Metrics** after the initial import and keep the first run separate from the market session.

The Cloudflare Worker Cron free tier has a very small CPU budget per invocation, while the Python scanner downloads and evaluates a large ticker universe. GitHub Actions is therefore used as the compute runner. Scheduled jobs may start late; this is not a guaranteed real-time alert service.

GitHub Actions standard runners are free for public repositories. Private repositories use the account's included quota and can incur charges when exceeded. These windows use about 7 hours 25 minutes on each weekday, around 150–165 runner-hours in a typical month. For a strictly zero-cost setup, the repository must remain public. Source code and workflow will be public, but GitHub Secrets and D1 data remain private. Do not commit credentials or private research datasets.

## Create the D1 database and proxy

Install Node.js, then from the repository root run:

```powershell
npx wrangler login
npx wrangler d1 create idx-screener-state
```

`cloud/wrangler.toml` is configured for the existing `idx-screener-state` database. If you create a different database, update its name and ID in that file. Initialize the remote D1 schema:

```powershell
npx wrangler d1 execute idx-screener-state --remote --file=cloud/d1/schema.sql
```

Create a long random proxy secret and save it in a password manager. Put it in the Worker's secret store:

```powershell
npx wrangler secret put D1_PROXY_TOKEN --config cloud/wrangler.toml
```

Deploy the proxy:

```powershell
npx wrangler deploy --config cloud/wrangler.toml
```

The Worker URL is the D1 proxy base URL. The proxy accepts only authenticated POST requests under `/api/`; keep `D1_PROXY_TOKEN` private.

## Seed the initial data

First inspect how much of the local data will be copied. Replace the URL and token with the deployed Worker URL and the same secret:

```powershell
$env:SCREENER_D1_API_URL = "https://your-worker.your-subdomain.workers.dev"
$env:SCREENER_D1_API_TOKEN = "your-long-random-secret"
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" pkg/tools/seed_d1.py
```

If the plan is within the free daily write budget, run it with `--apply`. It only seeds a new empty D1 database:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" pkg/tools/seed_d1.py --apply
```

The selected source data includes 21 recent price snapshots for top-gainer ranking, the latest daily metadata, fundamental cache, current-day alert history, and no local secrets or backtest results. The local SQLite database itself remains ignored by Git.

## Configure GitHub Actions secrets

In GitHub, open **Settings → Secrets and variables → Actions → New repository secret**. Add:

- `SCREENER_D1_API_URL` — the deployed Worker URL, without `/api/query` at the end
- `SCREENER_D1_API_TOKEN` — the same random token set as `D1_PROXY_TOKEN`
- `TELEGRAM_TOKEN`
- `TELEGRAM_CHAT_ID`

Enable GitHub Actions. The workflow cron schedules use UTC: `01:20 UTC` is `08:20 WIB`, and `06:20 UTC` is `13:20 WIB`. GitHub can delay or disable schedule events, so check Actions after setup.

## Source/data hygiene

The repository `.gitignore` excludes local `.env` files, `screener.db`, imported files under `pkg/data`, backups, caches, generated signal files, and `hasil_backtest*` directories. It keeps Python backtest source files. Use `git check-ignore -v <path>` before staging a new local dataset.

If the local PC/server also runs, set `SCREENER_TELEGRAM_WORKER=0` in its `.env` so it does not send from a separate local database. The local dashboard still uses local SQLite; syncing the dashboard itself with D1 is a separate change.

Yahoo Finance data is delayed and unofficial for IDX. Use a verified exchange feed for time-sensitive decisions.
