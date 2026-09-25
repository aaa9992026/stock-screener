# Stock Screener Setup

## Requirements

- Python 3
- Node.js / npm
- PostgreSQL

## Backend

1. `cd backend`
2. `python -m venv venv`
3. Windows: `venv\Scripts\Activate.ps1`
4. `pip install -r requirements.txt`
5. Create PostgreSQL database `stock_screener`.
6. Copy `.env.example` to `.env` and set your own values.
7. `uvicorn app.main:app --reload`

Backend API: `http://127.0.0.1:8000`
Swagger: `http://127.0.0.1:8000/docs`

### Required / optional environment variables

- `DATABASE_URL` — required.
- `TWELVE_DATA_API_KEY` — required for the Twelve Data BSE provider.
- `SEC_USER_AGENT` — required for SEC EDGAR requests; use your own contact email. SEC does not require an API key.
- `AUTO_REFRESH_SYMBOLS` — optional automatic refresh list, e.g. `US:AAPL,NSE:RELIANCE,BSE:INFY`.
- `AUTO_REFRESH_HOURS` — refresh interval, minimum 1 hour; default 6.

## Frontend

1. `cd frontend`
2. `npm install`
3. `npm run dev`

Frontend: `http://localhost:5173`

## Initial company sync

Use Swagger:

`POST /companies/sync/all`

## Automatic-update demonstration

Configure at least one symbol in `AUTO_REFRESH_SYMBOLS`, restart the backend, then run:

`POST /market/refresh-configured`

The response reports records received/added/updated. No CSV upload is involved. Verify the same stock with:

`GET /market/chart/{symbol}?exchange=US&timeframe=daily`

## SEC EDGAR demonstration

For a US ticker such as AAPL:

`GET /market/sec-edgar/AAPL?exchange=US&filings_limit=12`

The response contains the SEC CIK, recent filing metadata, EDGAR filing links and SEC companyfacts-based fundamental history where available.
