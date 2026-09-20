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