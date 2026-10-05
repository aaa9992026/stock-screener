# Stock Screener

Full-stack US / NSE / BSE stock screener built with React, FastAPI and PostgreSQL.

## Current scope

This source combines the accepted Milestone 1 work with the Milestone 2 continuation for Modules 4–8 and the remaining client fixes.

Key capabilities include:

- US, NSE and BSE market support.
- Daily / Weekly / Monthly OHLCV and timeframe-aware technical calculations.
- PostgreSQL historical storage and refresh/update behavior.
- Candlestick chart, EMA 20/30/50/100/150/200, SMA, RSI, Bollinger, ATR/ADR, VCP/breakout analysis and volatility trends.
- US fundamentals and extended quarterly/annual history.
- Ownership/shareholding layouts for US and Indian markets without fabricating unavailable categories.
- Relative Strength vs S&P 500 / NIFTY 500, Sector RS and the client-requested 5,000-stock percentile denominator.
- Weight-independent raw Relative Return; editable weights affect only Final RS Score.
- SEC EDGAR official US filing metadata and XBRL/companyfacts integration.
- Configurable automatic market-data refresh without CSV uploads.
- One reusable **Master Excel + Python (xlwings)** package: the same workbook is used for every stock, so no per-stock Excel files are created.
- The Python bridge reads the selected exchange/symbol from Excel, requests up to 20 years of verified daily provider data for backtesting, calculates technical indicators locally, and updates the same workbook in place without storing that long history in Railway.
- Provider status, stale/error handling and provider-replacement documentation.

## Stack

- React + Vite
- FastAPI
- PostgreSQL + SQLAlchemy
- yfinance
- Twelve Data for BSE/XBOM
- SEC EDGAR JSON/XBRL
- APScheduler

## Documentation

- `docs/SETUP.md`
- `docs/DATA_PROVIDERS.md`
- `docs/PROVIDER_REPLACEMENT.md`
- `docs/MILESTONE1_STATUS.md`
- `docs/MILESTONE2_STATUS.md`

## Run locally

Backend:

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\Activate.ps1
pip install -r requirements.txt
# Copy .env.example to .env and set your own values
uvicorn app.main:app --reload
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Swagger is available at `http://127.0.0.1:8000/docs` when the backend is running.


## Milestone 2 ranking + Excel

Latest client handwritten formulas are documented in `docs/MILESTONE2_HANDWRITTEN_RANKING_SYSTEM.md`.

Useful endpoints:

- `GET /market/ranking-spec` — machine-readable client composite/sector formulas.
- `GET /market/excel-feed/{symbol}?exchange=NSE` — refreshable JSON source used by the master xlwings workbook.
- `GET /market/excel-export/{symbol}?exchange=NSE` — legacy editable per-stock snapshot endpoint (kept for compatibility; not the recommended client workflow).
- `GET /market/provider-status` — configured provider status, including SEC/Twelve Data/Kotak Neo readiness.

Kotak Neo is kept separate as an Indian-market source. Do not commit client API keys/tokens to Git.


### Master Excel + Python (recommended client workflow)

Download `frontend/public/StockScreener_Master_Excel_Python.zip` from the deployed site or use the **Master Excel + Python** button. The package contains:

- `StockScreener_Master.xlsx` — one reusable workbook for all stocks.
- `excel_bridge.py` — xlwings Python bridge.
- `INSTALL_MASTER_EXCEL.bat` — one-time package installer.
- `START_MASTER_EXCEL.bat` — one-click updater for the selected stock.

In the workbook, change **Control → Exchange / Symbol**, then run `START_MASTER_EXCEL.bat`. Python fetches the selected stock's history and rewrites the same workbook's History, Indicators, Fundamentals and Ownership sheets. It does not create another workbook.

The Python bridge calculates SMA/EMA 20/50/200, RSI14, ATR14/ATR%, ROC14, Bollinger width, +DI/-DI/ADX/DI spread, volume ratio, 52-week levels and 1W/1M/3M/6M/1Y returns. Missing provider values remain blank/N/A.

### Universe screener / Excel export

The Milestone 2 UI includes a many-stock screener with Popular, Fundamentals, Technicals and Relative Comparison tabs. It uses stored provider/database values and supports configurable columns plus filtered Excel export.

- `GET /market/screener` — paginated filtered stock table.
- `GET /market/screener-export` — download the full filtered result as an Excel workbook.

## Final screener data-availability update

The universe screener now applies an equity-only US filter at query time, automatically cleans legacy warrants/units/ETFs/SPAC rows, shows real-data coverage, prioritizes rows with the most available verified data, and incrementally enriches missing fundamentals/ownership in bounded background batches. No missing values are fabricated. Use **Fill Missing Data** for an additional bounded refresh of the selected market and **Export Excel** to export the current filtered universe.

## 2026-10-01 exact handwritten formula revision

The Fundamental Filters tab now implements the client's exact 11-rule EPS composite and the same 11-rule structure for PAT and Sales. All six visible NPM formulas are represented; any point weight that is not legible in the supplied page remains editable and defaults to zero rather than being guessed. Quarterly YoY values are calculated for prior quarters as required. Incomplete Top-200 composite rows are explicitly marked Provisional instead of being presented as Final.

## 2026-10-02: interactive Master Excel workflow

The website's **Master Excel + Python** download now contains one reusable workbook. Change the Exchange/Symbol in `Control`, run `START_MASTER_EXCEL.bat`, and the same workbook refreshes 5-year history, indicators, signals/backtests, fundamentals/ownership, and dashboard charts. The Top-200 web dashboard also includes ascending/descending sorting.

## 2026-10-02 latest client feedback patch

- Restored the client's fixed **5,000-stock** RS percentile denominator.
- RS scoring remains: period Relative Return = Stock Return - Benchmark Return; period percentile = `(lower + 0.5*equal)*100/5000`; Final RS = 1W 30% + 1M 25% + 3M 20% + 6M 15% + 1Y 10%. 2W/2M/Sector are optional with 0% defaults.
- Restored client composite defaults to **Fundamental 30% + Technical 25% + RS 25% + Ownership 15% + Sector 5%** and bumped browser storage versions so stale saved weights cannot override them.
- A stale stored OHLCV cache can no longer freeze the chart at an old date. Stored history older than seven days is refreshed/merged with live provider rows, allowing 2024/2025/2026 data to appear when supplied by the provider.
- Both composite and RS weight controls remain editable in the frontend.

## 2026-10-02 framework-first client revision

Per the latest client direction, the Top-200 page is now arranged for framework review before another data/scoring pass:

- Selected stock opens a real candlestick chart directly in the Top-200 workflow.
- Price overlays: RS price line, quarterly EPS line, Bollinger Bands, EMA 10/20/34/50/100/150/200, and volume.
- Chart dates use `DD/MM/YYYY`.
- Indicator charts are directly below the candlestick chart.
- MACD and Signal use different colors; ADX, +DI and -DI each use different colors.
- Indicator basket can be enabled/disabled and periods are editable.
- Framework includes RSI, MACD, ROC, ADX/+DI/-DI, DI Spread, ATR, BB Width, Volume Ratio, Volume Contraction, Volume Dry-Up, RS and a Delivery % slot.
- Delivery % is intentionally a framework slot until the next data stage because the client explicitly asked not to spend time on data yet.
- Clicking a row in the Top-200 table moves back to the framework chart for that stock.


### Final client framework metrics
The client framework now includes ATR%, ADR%, ADR Ratio, BB Width%, and a Top-200 Standard Deviation column beside Beta. Top-200 sort order is explicitly selectable as ascending or descending, including Standard Deviation.

## 2026-10-02 final fundamental-filter / RS / EMA polish

- Fundamental filter table now labels each rule result as **RS Score** and keeps compare sign, threshold/value, weight and enable/disable editable.
- EPS, PAT, Sales, NPM, CFO and the additional ROE/ROCE/share filters remain grouped exactly as the client's handwritten framework.
- An explicit **Fundamental Score** is shown below the rule table together with the subgroup RS scores.
- A **Stocks Qualifying the Fundamental Criteria** table is placed directly below the Fundamental Score. It only lists rows with 100/100 Fundamental Score and complete rule coverage; missing provider history never counts as a pass.
- Indicator RS is now a bounded **0–100 RS Score** and cannot exceed 100. The separate price-chart RS overlay remains the requested stock/benchmark price-relative line.
- The candlestick section now shows a clear color key beside the EMA names for EMA 10/20/34/50/100/150/200.

## EMA legend readability update (2026-10-02)

- EMA 10/20/34/50/100/150/200 now each show a larger matching-color line swatch.
- Each EMA name is printed in the exact same color as its chart line.
- Every EMA has its own bordered badge and the legend is placed directly above the chart for fast identification.


## Latest client UI fix — standalone Fundamental Filters

The Fundamental Filters framework is now displayed as its own always-visible section before the Stock Universe Screener. It includes per-rule RS score, editable compare/value/weight/use controls, the Fundamental Score strip, and the qualifying-stock list directly below.

## UI alignment polish
- Top-200 Market selector now uses the same labeled control layout as Sort by and Order.
- Market / Sort by / Order / Refresh controls are bottom-aligned for a clean single-row desktop layout.

## Latest CFO framework completion

- Completed the CFO fundamental group with 7 visible filters: quarterly YoY, quarterly QoQ, annual YoY, 3-year expansion, industry comparison, YoY acceleration, and cash flow per share.
- Each CFO rule has editable compare/target/weight/use controls and contributes to the CFO RS score when data is available.
- Missing provider values remain N/A rather than being fabricated.

## Fundamental Qualified Stocks live-filter fix (2026-10-02)

The qualified-stock list now recalculates from the currently enabled Fundamental Filters and their current compare signs / thresholds instead of using a stale aggregate score. Per-rule real provider values are returned with Top-200 rows, and older persisted ranking snapshots remain compatible for latest EPS/PAT/Sales YoY rules while the remaining rule-value cache refreshes. Missing provider values remain N/A and never count as a pass.


## 2026-10-05 client ranking-framework corrections

This build adds the latest client-requested ranking-system corrections:

- Technical Filters now follow the same table structure as Fundamental Filters: Filter Name, Compare, Value/Target, Actual Value, Weight, RS Score, Use.
- Added requested technical framework rows for Price/EMA, 52-week distances, RS, ROC, ADX, RSI, BB Width %, ATR %, RVOL, 10-day average volume, volume dry-up/contraction, DI spread and pivot breakout.
- Technical Score and a qualified-stock list are shown directly below the Technical Filters.
- Ownership Filters are shown as a separate section with Ownership Score and qualified-stock list. Missing US historical ownership series are explicitly N/A rather than fabricated.
- Fundamental qualified-stock columns now mirror the currently enabled Fundamental filters. Sort By / Order controls were moved directly above this filtered list.
- Candlestick framework now displays OHLCV (including Volume).
- RS Score remains a dedicated 0–100 indicator chart.
- RS percentile calculation now follows the latest client formula: [lower + (same - 1)/2] / (total - 1) × 100.
- Any unconfirmed handwritten definition/threshold is left disabled/N/A or editable instead of guessed.
