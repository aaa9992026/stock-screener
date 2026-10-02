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

The Excel updater now fetches up to 20 years of verified Yahoo Finance OHLCV directly for backtesting while using the deployed API for compact snapshots when available. Missing provider fields stay blank/N/A.

## Git
```bash
git add .
git commit -m "Add fundamental RS filters bounded RS score and EMA color legend"
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


## Final Top-200 coverage/timeout closeout (2026-10-02)
- Added a tiny `ranking_snapshots` table that persists only derived ranking scores and provider metadata, never OHLCV history. This is designed for the 500 MB Railway volume.
- Top-200 requests now reuse persisted enrichment after restarts and synchronously fetch only a small cold batch; remaining candidates are enriched in background batches and saved for the next refresh.
- This removes the previous 50-stock synchronous statement crawl that could exceed the browser/Railway timeout and force the frontend to show an older cached dashboard.
- Alpha/Beta first use a fast exact S&P 500 / NIFTY 500 live benchmark fetch, with the existing exact-benchmark fallback chain retained.
- Dashboard now shows the price chart and an RSI indicator chart together, while Ascending/Descending remains clearly visible beside the sort selector.
- Missing real provider values still remain N/A; no financial values are fabricated.

## Selected-stock Sector N/A closeout (2026-10-02)
The selected-stock dashboard now persists/reuses real sector metadata from the compact ranking cache and calculates the Sector component from real EPS/PAT/Sales peer-history metrics when at least 5 peer observations are available. It does not substitute price RS or fabricated sector values.

## 2026-10-02 client closeout update
- Top 200 ranking now recalculates locally from the currently entered composite weights and immediately reorders by Composite; Apply Weights also refreshes the backend with the same weights.
- Price chart remains visible together with the full indicator set: RSI, MACD, ROC, ADX/+DI/-DI, ATR and Volume Ratio; EMA/SMA/Bollinger remain price overlays.
- Master Excel backtesting now requests up to 20 years of real Yahoo provider history directly from Python, so the long history is not stored in the 500 MB Railway PostgreSQL volume.
- Control workbook target updated to 20 years / 5,500 rows. Younger listings correctly show partial history rather than fabricated rows.

## Latest client feedback patch (2026-10-02)
After deployment, hard-refresh the Vercel site once. This build bumps the saved-weight versions and restores the client's exact defaults/formula. It also detects stale OHLCV caches and merges current live provider rows so charts are not allowed to stop at an old stored date merely because the cache has enough rows.

## Framework-first UI revision (2026-10-02)
The current client-review target is the framework, not another data correction pass. The Top-200 workflow now opens a candlestick chart with RS/EPS/Bollinger/EMA 10-20-34-50-100-150-200/volume overlays, followed immediately by customizable indicator charts. Dates display as DD/MM/YYYY. MACD/Signal and ADX/+DI/-DI are visually separated with distinct colors. Additional handwritten basket slots (DI Spread, BB Width, volume contraction/dry-up, RS and Delivery %) are represented in the framework; Delivery % remains an explicit provider-data slot for the next stage.


## Final volatility/sorting patch (2026-10-02)
- Added ATR %, ADR %, ADR Ratio, and explicit BB Width % framework charts beneath the candlestick chart.
- ATR/ADR periods are editable; ADR Ratio is current daily range divided by rolling ADR.
- Top-200 now exposes Standard Deviation directly beside Beta. The value is annualized standard deviation of daily returns (%) over up to 252 sessions.
- Sort controls are visibly labeled **Sort by** and **Order**, with explicit Ascending/Descending choices; Standard Deviation is also sortable.


## Final fundamental framework polish (2026-10-02)
- Fundamental rules show editable compare/value/weight/on-off controls and an RS Score column.
- Fundamental Score is displayed immediately below the filter table, followed by the qualifying-stock list.
- Qualifying rows require Fundamental Score 100/100 plus complete rule coverage; missing data is never converted into a pass.
- Indicator RS is bounded to 0–100 and the RS chart axis is fixed at 0–100.
- EMA 10/20/34/50/100/150/200 now have a visible color legend with each EMA name.
