# Milestone 2 Status — Modules 4–8 + Remaining Fixes

This is the cumulative Milestone 2 continuation build. It preserves all accepted Milestone 1 work and carries the client scope forward through Modules 4–8.

## Included in this Milestone 2 build

- Existing Modules 4–8 screener functionality is preserved in one cumulative codebase rather than separate patches.
- Relative Strength formula audit and correction:
  - raw Stock Return, Benchmark Return and Relative Return do not depend on editable score weights;
  - stock percentile denominator is fixed at 5,000 as requested;
  - editable weights affect only Final RS Score;
  - default score mix is 1W 30%, 1M 25%, 3M 20%, 6M 15%, 1Y 10%; 2W/2M/Sector default to 0%;
  - the frontend displays the exact active formula for review.
- SEC EDGAR integration for US stocks:
  - official SEC ticker/CIK mapping;
  - SEC XBRL companyfacts for fundamental history;
  - recent 10-K, 10-Q, 8-K, Forms 3/4/5 and SC 13D/13G filing metadata;
  - direct EDGAR filing links;
  - 12 quarterly and 7 annual periods where SEC data is available.
- Automatic data update support without CSV upload:
  - configured symbols refresh through the existing provider adapters;
  - schedule controlled by `AUTO_REFRESH_SYMBOLS` and `AUTO_REFRESH_HOURS`;
  - `POST /market/refresh-configured` provides an immediate test/demo refresh.
- Provider status endpoint and provider-replacement documentation.
- Existing ownership, timeframe, volatility, EMA, fundamental-history, sector RS, VCP, delivery and handwritten-layout fixes remain included.

## Data integrity rules

- Missing provider data is shown as unavailable; it is never fabricated.
- SEC EDGAR is used for official US filings/XBRL fundamentals, not stock-price OHLCV.
- US Promoter/FII/DII rows remain N/A because those are Indian-market classifications.
- API/provider failures return explicit error/stale states rather than silently presenting old data as current.
