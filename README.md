# Stock Screener

A full-stack stock screener for US and Indian markets.

## Milestone 1 Features

- US and NSE market data
- BSE provider error/stale handling
- Daily / Weekly / Monthly OHLCV
- PostgreSQL historical storage
- Automatic data refresh
- Company search/autocomplete
- Automatic NSE + US company-list sync
- US fundamentals
- US ownership data
- Provider adapter architecture
- Stale/error warnings
- React dashboard
- FastAPI backend

## Tech Stack

- React + Vite
- FastAPI
- PostgreSQL
- SQLAlchemy
- yfinance
- Recharts
- APScheduler

## Documentation

See:

- `docs/SETUP.md`
- `docs/DATA_PROVIDERS.md`
- `docs/PROVIDER_REPLACEMENT.md`

## Run

Backend:

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload

## Milestone 1 dashboard additions

- Rule-based 0-100 dashboard score with Buy/Watch/Sell signal.
- Sector and industry classification/ranking when peer data is populated.
- Extended technical screening: EMA 20/30/50/100/150/200 alignment, RS percentile within the stored universe, 20-day average volume, volume ratio, ADR, breakout status, VCP heuristic and pattern status.
- Extended fundamental history: ROA, ROCE, free cash flow and 5-year CAGR when the provider supplies enough annual periods.
- Ownership detail panels for institutional holders, mutual funds and insider transactions where Yahoo exposes them. Verified FII/DII/promoter-change fields are intentionally not estimated when the configured provider does not expose them.

- Final RSI(14) handwritten scoring: >50 = 5 points, 40-50 = 4, 30-40 = 3, below 30 = 2; thresholds and points remain editable and the factor can be enabled/disabled.
