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

## Latest handwritten ranking update

- Overall client composite updated to Fundamental 30% + Technical 25% + RS 25% + Ownership 15% + Sector 5%.
- Sector-ranking formula captured: EPS 30%, PAT 25%, Sales 20%, Growth Acceleration 15%, Growth Breadth 5%, Acceleration Breadth 5%.
- Technical Summary now exposes the additional trend/strength/momentum/participation/volatility/base-formation filter inputs from the latest notes.
- Excel Power Query feed and editable workbook export added.
- Kotak Neo is registered as the planned Indian-stock-only provider; credentials remain external to source control.
- Ambiguous handwritten point values are not guessed.

## Deployment recheck fixes

- Migrates stale browser-saved ranking weights to the current 100% Milestone 2 default: Fundamental 30%, Technical 25%, RS 25%, Ownership 15%, Sector 5%.
- Migrates stale RS period weights to the current client default and removes old Sector-RS 20% carry-over.
- Fixes the Participation panel so delivery data never renders as `[object Object]`; true NSE delivery percentages are formatted as Day/Week/Month, otherwise N/A.
- Industry/Sector return rows now exclude the selected stock and require at least five real stored peers. If peer history is insufficient, N/A is shown instead of repeating the stock's own return.
- RS output now exposes the number of actually scored stocks against the client-required 5,000 denominator and labels incomplete-universe results as provisional.
- SEC EDGAR failures are now visible in the UI instead of being silently hidden; missing `SEC_USER_AGENT` is reported explicitly and no substitute SEC values are invented.
