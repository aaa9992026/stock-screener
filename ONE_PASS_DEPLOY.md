# Demo-1 Milestone 2 — One-Pass Deployment

Use this package only. Do not apply older ZIPs/patches afterward.

## 1) Railway backend
Deploy the `backend` folder.

Required Railway variables:
- `DATABASE_URL` = Railway PostgreSQL connection string
- `SEC_USER_AGENT` = `StockScreener/2.0 your-real-email@example.com`

Recommended variables are listed in `backend/.env.example`.

The backend now boots its HTTP process immediately, initializes the DB/schema in the background, retries temporary DB reconnects, validates pooled connections, and delays heavy background jobs so cold-start dashboard requests are not starved.

Verification:
- `/` -> `status: ok`
- `/health` -> `database: ready`

## 2) Vercel frontend
Deploy the `frontend` folder.

The frontend talks directly to the current Railway backend by default:
`https://stock-screener-production-d90e.up.railway.app`

If Railway ever creates a different domain, set one Vercel environment variable instead of editing code:
`VITE_API_BASE_URL=https://YOUR-NEW-RAILWAY-DOMAIN`

The frontend waits for backend DB readiness on cold starts, retries critical requests, and preserves the last verified chart/Top-200 result during a temporary reconnect rather than blanking the screen.

## 3) Excel
From the web app download `Master Excel + Python` once, or use `excel_master/StockScreener_Master_Excel_Python.zip`.

Extract the ZIP first. Run `INSTALL_MASTER_EXCEL.bat` once, then use the same workbook for every stock. `START_MASTER_EXCEL.bat` updates data, indicators, signals/backtests and charts in place.

If the deployed API is temporarily unavailable, the Excel updater automatically falls back to Yahoo Finance directly for verified 5-year OHLCV plus current fundamental/ownership fields. Missing provider fields stay blank/N/A.

## Git
```bash
git add .
git commit -m "Stabilize final Milestone 2 deployment and Excel refresh"
git push
```

## Free Railway 500 MB mode (2026-10-02)
This build defaults to `FREE_TIER_MODE=1` so no paid PostgreSQL upgrade is required.
On startup it checks the rebuildable `ohlcv` cache. If that relation is already oversized,
it truncates only `ohlcv` to reclaim volume. Company, fundamental and ownership records are preserved.
Charts, indicators and the Top-200 candidate technical/RS calculations use live provider data without
repopulating the full-universe OHLCV cache. Full 4-5 year Excel history is also fetched live by the
master Excel/Python workflow.

## Top 200 missing-data closeout
The free-tier Top 200 endpoint now live-enriches the strongest bounded candidate set with real provider statement history and metadata without writing multi-year OHLCV back to PostgreSQL. It calculates the confirmed 11-rule EPS/PAT/Sales growth scores, fills sector metadata where the provider supplies it, computes a provisional sector growth score from the bounded peer set, and calculates Alpha/Beta from real daily returns versus S&P 500/NIFTY 500. Missing provider values remain N/A. `TOP200_LIVE_ENRICH_LIMIT` defaults to 50 to keep Railway requests bounded; increase only if the deployment has enough request time/CPU.
