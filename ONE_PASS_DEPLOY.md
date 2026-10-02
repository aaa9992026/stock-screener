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
