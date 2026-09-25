# Replacing a Data Provider

The screener separates provider-specific retrieval from database synchronization and UI logic. A future provider can therefore be replaced without rebuilding the whole application.

## Provider location

`backend/app/services/providers/`

Current adapters include Yahoo Finance, Twelve Data/BSE, SEC EDGAR, and Indian shareholding support.

## OHLCV contract

A replacement OHLCV provider should return a list of dictionaries with:

- `date`
- `open`
- `high`
- `low`
- `close`
- `volume`

Pass those rows to `sync_ohlcv(...)`; the existing PostgreSQL storage and chart endpoints can remain unchanged.

## Fundamental contract

A replacement snapshot provider should map available fields to the existing `sync_fundamental_data(...)` format, including market cap, EPS, revenue, net income, margins, ROE/ROA, ownership percentages, shares and company classification when available.

For US historical fundamentals, `sec_provider.py` demonstrates the official SEC EDGAR/XBRL implementation.

## Steps to replace a provider

1. Add a provider adapter in `backend/app/services/providers/`.
2. Keep its normalized output compatible with the existing sync service.
3. Replace the provider selection in `backend/app/api/market.py` and, if automatic refresh is required, `backend/app/services/scheduler.py`.
4. Put credentials in `.env`; never hard-code them.
5. Test one symbol with `POST /market/refresh/{symbol}`.
6. Test scheduled configuration with `POST /market/refresh-configured`.
7. Confirm `GET /market/provider-status` and the live chart/dashboard.

## Provider changes / pricing

Third-party API terms, prices, authentication and schemas are outside the application owner's control. Source-code ownership does not make third-party compatibility maintenance unlimited or free. If a provider later changes, this adapter layer is the intended place to perform the compatibility update.

## Database independence

Changing providers does not require replacing the PostgreSQL database. Existing stored history remains available, and a new adapter can continue appending/updating the same normalized records.
