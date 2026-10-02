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
- The Python bridge reads the selected exchange/symbol from Excel, requests up to 5 years of verified daily data (targeting at least 4 years), calculates technical indicators locally, and updates the same workbook in place.
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
