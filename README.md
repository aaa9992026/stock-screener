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
