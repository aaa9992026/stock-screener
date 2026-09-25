# Data Providers

## Provider map

| Data | Primary source | Authentication | Notes |
|---|---|---|---|
| US/NSE OHLCV | Yahoo Finance via yfinance | No project API key | Stored in PostgreSQL |
| BSE OHLCV | Twelve Data | `TWELVE_DATA_API_KEY` | Uses BSE MIC `XBOM` |
| US official filings/XBRL fundamentals | SEC EDGAR | No API key; identifying `SEC_USER_AGENT` required | Companyfacts + submissions JSON |
| US company universe | Nasdaq Trader Symbol Directory | None | Search/company sync |
| NSE company universe | NSE public equity list | None | Search/company sync |
| Indian shareholding history | Configured public shareholding provider | Provider-dependent | Missing categories are never estimated |

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

## Failure behavior

If a provider changes its endpoint, authentication, response format, pricing, or stops providing data, the adapter must be updated/replaced. The application should show a provider error/stale state rather than fabricate data. The PostgreSQL data model and frontend do not need to be replaced when a compatible provider adapter is changed.
