# Data Providers

## Provider map

| Data | Primary / planned source | Authentication | Notes |
|---|---|---|---|
| Indian stock market data (Milestone 2) | Kotak Neo (planned live provider after client credentials are validated) | Client-owned Kotak Neo credentials/token | Indian stocks only; kept separate from US sources |
| NSE historical OHLCV fallback | Yahoo Finance via yfinance | No project API key | Stored in PostgreSQL; can remain fallback while Kotak integration is activated |
| BSE historical OHLCV fallback | Twelve Data | `TWELVE_DATA_API_KEY` | Uses BSE MIC `XBOM` |
| US OHLCV / market fallback | Yahoo Finance via yfinance | No project API key | Stored in PostgreSQL |
| US official filings/XBRL fundamentals | SEC EDGAR | No API key; identifying `SEC_USER_AGENT` required | Companyfacts + submissions JSON |
| US company universe | Nasdaq Trader Symbol Directory | None | Search/company sync |
| NSE company universe | NSE public equity list | None | Search/company sync |
| Indian shareholding history | Screener.in public Shareholding Pattern table | No project API key | Missing categories are never estimated |

## Kotak Neo

The client confirmed that the purchased Kotak Neo API access is **for Indian stocks only**. The codebase therefore keeps Indian and US providers separate.

Environment placeholders are included but no client secret is committed:

```text
KOTAK_NEO_API_KEY=
KOTAK_NEO_ACCESS_TOKEN=
KOTAK_NEO_BASE_URL=
```

The current provider status endpoint reports whether credentials are present and whether the base URL + access token required for live quote calls are configured. Final live authentication/symbol mapping must be tested with the client's actual account before Kotak Neo becomes the active Indian provider.

## SEC EDGAR

The backend uses official SEC JSON endpoints instead of scraping rendered HTML:

- SEC company ticker/CIK mapping
- SEC XBRL companyfacts
- SEC submissions metadata for recent filings

Endpoint in this project:

`GET /market/sec-edgar/{symbol}?exchange=US&filings_limit=12`

The SEC requires an identifying User-Agent containing a contact email:

`SEC_USER_AGENT=StockScreener/2.0 your-email@example.com`

No personal developer API key or server is required for SEC EDGAR.

## Automatic updates

Manual CSV uploads are not required. Configure symbols in the deployment owner's `.env`:

`AUTO_REFRESH_SYMBOLS=US:AAPL,NSE:RELIANCE,BSE:INFY`

`AUTO_REFRESH_HOURS=6`

The background scheduler refreshes those symbols automatically. For a final-milestone demonstration, the same job can be triggered immediately with:

`POST /market/refresh-configured`

Provider configuration can be inspected without making third-party network calls:

`GET /market/provider-status`

## Excel connection

The latest client notes ask for an Excel connection so additional formulas can be applied outside the web UI.

- `GET /market/excel-feed/{symbol}?exchange=NSE` — JSON feed suitable for Excel Power Query / From Web refresh.
- `GET /market/excel-export/{symbol}?exchange=NSE` — editable `.xlsx` snapshot with OHLCV and ranking formula sheets.

## Failure behavior

If a provider changes its endpoint, authentication, response format, pricing, or stops providing data, the adapter must be updated/replaced. The application should show a provider error/stale state rather than fabricate data. The PostgreSQL data model and frontend do not need to be replaced when a compatible provider adapter is changed.
