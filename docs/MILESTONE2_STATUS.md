# Milestone 2 Status — Modules 4–8 + Remaining Fixes

This is the cumulative Milestone 2 continuation build. It preserves all accepted Milestone 1 work and carries the client scope forward through Modules 4–8.

## Included in this Milestone 2 build

- Existing Modules 4–8 screener functionality is preserved in one cumulative codebase rather than separate patches.
- Relative Strength formula audit and correction:
  - raw Stock Return, Benchmark Return and Relative Return do not depend on editable score weights;
  - stock percentile denominator is market-specific: 6,000 for US and 5,500 for the combined Indian NSE/BSE universe;
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
- RS output now exposes the number of actually scored stocks against the client-required market denominator (US 6,000; India 5,500) and labels incomplete-universe results as provisional.
- SEC EDGAR failures are now visible in the UI instead of being silently hidden; missing `SEC_USER_AGENT` is reported explicitly and no substitute SEC values are invented.

## Indian fundamental-filter update

- NSE/BSE now load the same fundamental snapshot and fundamental-history UI used for US stocks.
- Search and Refresh Data both refresh Indian fundamentals automatically; no CSV/manual entry is required.
- The handwritten quarterly/annual fundamental ranking factors use the same evaluation logic for US, NSE and BSE.
- Indian market-cap/revenue/net-income values are displayed with INR formatting; US values remain USD.
- Indian ownership remains sourced from the Indian shareholding provider (Promoter/FII/DII/MF/Public) rather than mapping US insider/institution categories onto Indian stocks.
- If a required Indian fundamental or ownership category is unavailable, the overall ranking is withheld instead of silently re-normalizing around missing data.
- Missing provider fields remain N/A and are never fabricated.

## Live INFY video recheck fixes

- Indian quarterly/annual money values now use INR formatting instead of hard-coded USD labels.
- Missing/null component values are no longer coerced to numeric zero in the client ranking, so score coverage reflects only real available components.
- NSE delivery endpoint parser failures are shown as a clean unavailable message rather than exposing an internal JSON parsing exception.

## Separate RS universes + automatic listing maintenance

- US RS percentile universe is fixed at 6,000 stocks.
- Indian RS percentile universe is fixed at 5,500 stocks and combines stored NSE + BSE histories.
- US and Indian stocks are never mixed into one RS percentile universe.
- Daily company-master synchronization automatically adds/reactivates newly listed symbols and marks missing symbols inactive when the provider snapshot passes safety checks. Historical rows are retained after a delisting.
- Provider-snapshot safety prevents a partial/upstream-failure response from mass-deactivating the current company universe.
- `GET /companies/universe-status` reports active/inactive symbol-master counts and the two client-defined RS targets.
- Current automatic company-master sources are Nasdaq Trader for US and the official NSE equity list for NSE. BSE remains the existing limited market until a BSE symbol-master feed is configured.

## RS universe automatic history backfill

Client-confirmed market universes are now separate:

- US percentile denominator / target: **6,000 active US stocks**.
- India percentile denominator / target: **5,500 active Indian stocks (NSE + BSE)**.

The backend now includes an incremental real-data OHLCV backfill service. It runs in small resumable batches so Railway/provider restarts or rate limits do not require restarting the whole process. Symbols that already have sufficient recent history are skipped. Empty/error responses remain pending and are retried later; no synthetic market bars are generated.

Automatic behavior:

- Company master sync runs every 24 hours.
- New listings are added/reactivated by the symbol-master sync.
- Missing/delisted symbols are marked inactive only when the incoming provider snapshot passes safety checks.
- RS history backfill then picks active stocks that do not yet have enough recent history.
- The backfill stops once the client target is met for that market and resumes automatically if the ready count later drops below the target (for example after a delisting/new listing change).

Environment controls:

```env
RS_BACKFILL_ENABLED=true
RS_BACKFILL_BATCH_SIZE=10
RS_BACKFILL_INTERVAL_MINUTES=10
```

Operational endpoints:

- `GET /companies/rs-backfill/status`
- `GET /companies/rs-backfill/status?market=INDIA`
- `GET /companies/rs-backfill/status?market=US`
- `POST /companies/rs-backfill/run?market=INDIA&batch_size=25`
- `POST /companies/rs-backfill/run?market=US&batch_size=25`
- `POST /companies/rs-backfill/run-all?batch_size=25`

The RS calculation itself now uses only **active** company rows from the selected market universe. The displayed `scored_stocks_available` count requires usable values for all default RS periods (1W, 1M, 3M, 6M and 1Y), rather than counting a stock that only has a short fragment of history.

Current provider note: the history backfill uses real Yahoo Finance/yfinance OHLCV for US/NSE/BSE symbols already present in the active company master. NSE and US symbol masters are automatically synchronized. BSE symbol-master completeness still depends on the future BSE/Kotak symbol-master integration; the system does not invent BSE listings to force the India count to 5,500.


## Symbol search / live-video correction

- The symbol input is now separate from the active selected stock. Typing a partial
  symbol no longer launches dashboard/fundamental/RS requests for each keystroke.
- Stale dashboard/fundamental/technical requests are ignored when the active
  symbol/timeframe changes, preventing an older partial-symbol response from
  overwriting the final selected stock.
- Invalid US/NSE/BSE OHLCV rows with non-finite or zero/negative OHLC values are
  filtered from API output/calculations and rejected during future sync/backfill.
- Listing-master sync no longer erases existing sector/industry enrichment when
  the upstream symbol list omits those fields.

## 2026-09-29 client handwritten layout update

- Ranking controls are now arranged as compact tables matching the latest client note: Filter name, compare sign, value/target, current value, weight, filter score and enable/disable.
- Fundamental filters are grouped into EPS, PAT, Sales, NPM, CFO and Other.
- ROE > 20 and ROCE > 30 are exposed from the latest note. Their weights remain 0 until the client confirms the exact point allocation.
- Cash-flow-per-share, outstanding-shares and float-shares rows are included but disabled/zero-weight by default because the handwritten note did not define an unambiguous threshold/weight.
- The top Composite Ranking table shows each component score, weight and weighted contribution.
- The selected stock gets a transparent Fundamental Qualification status; missing provider values remain N/A and prevent false qualification.
- Excel actions are split into Download Excel, Copy Excel Feed URL and an in-app Excel setup guide.
- Excel exports now contain `Technical_Filter_Config` and `Fundamental_Filter_Config` sheets with editable comparison/threshold/weight/enable columns and formula-driven score cells.

## 2026-09-29 one-pass deployment hardening

- Excel download no longer opens the export endpoint in a blank browser tab. The frontend now fetches the workbook through the same-origin `/api` proxy, validates the HTTP response, creates a browser Blob, and forces a named `.xlsx` download.
- The Excel backend now returns a fixed byte response with `Content-Disposition`, `Content-Length`, `Cache-Control: no-store`, and `X-Content-Type-Options: nosniff` so Vercel/Railway proxies preserve the file download reliably.
- SEC EDGAR requests now use a retrying HTTP session for transient `429/5xx` responses and official ticker/CIK files only. The unnecessary manual `Host` header was removed.
- SEC ticker lookup has an official `company_tickers_exchange.json` fallback if the primary association file is temporarily unavailable.
- SEC filings and XBRL company-facts are handled independently: if one SEC resource is temporarily unavailable, the other can still be displayed. Missing values remain empty and are never invented.
- The SEC UI shows partial-provider warnings instead of silently hiding them.
- `SEC_USER_AGENT` remains an environment variable and is not committed into source control. It should contain the application name/version and a real contact email.

## 2026-09-30 — Many-stock screener + filtered Excel export

Added the client's requested list-style stock screener for easier access and Excel workflows.

- Tabs: Popular, Fundamentals, Technicals, Relative Comparison.
- Market selector: US, India, NSE, BSE, or combined.
- Filters use stored real provider/database values only; missing values stay N/A.
- Paginated stock table with configurable columns and row action to open the selected stock in the detailed dashboard.
- Add Columns picker and page-size controls.
- `GET /market/screener` returns the filtered stock universe.
- `GET /market/screener-export` exports the complete current filtered result set (up to 10,000 rows) to `.xlsx`, not only the current single stock.
- Excel workbook includes a `Filter Summary` sheet so the exported criteria are auditable.
- Supported stored-data filters include market/sector/industry, market cap, EPS, revenue, net income, profit margin, ROE/ROA, institutional/insider holding, LTP, 52-week distance, and volume-vs-52-week-average ratio.

This does not invent unavailable growth, delivery, or ownership data. More filter families can be added as those fields become persistently stored for the full universe.

### UI polish — action buttons
- Standardized button sizing, spacing, hover/focus/disabled states across Search/Refresh, timeframe controls, ranking actions, screener actions and pagination.
- Gave Excel, copy-link, column, help and reset actions visually distinct but restrained treatments.
- Improved screener tabs, toolbar grouping and mobile touch targets.


## Final universe-quality / loading-state cleanup

- US symbol-master ingestion now excludes ETFs, warrants, units, rights, SPAC/acquisition securities, preferred/debt instruments and other obvious non-common-equity listings from the active stock universe.
- Legacy non-equity US rows are automatically marked inactive on company sync; historical rows are retained.
- RS backfill defensively skips legacy non-equity US rows even before cleanup completes.
- Company sync runs shortly after backend startup and then every 24 hours, so new listings/delistings and security-type cleanup are applied automatically.
- When a user switches symbols, the chart now shows an explicit loading state instead of a temporary red historical-data-unavailable message.

## Final universe/data-availability pass
- The normal US screener now applies the equity-only rule at query time as well as during symbol sync. Legacy warrants, units and obvious SPAC/acquisition securities cannot appear simply because an upstream sync is delayed.
- A local cleanup job deactivates legacy non-equity US rows without deleting their historical records.
- Current fundamentals/ownership are enriched automatically in bounded Yahoo-provider batches for US and Indian equities. Missing fields remain N/A until real provider data is obtained.
- Manual bounded enrichment is available at `/companies/data-backfill/run` and `/companies/data-backfill/run-all`.
- The stock-universe UI displays real-data coverage and includes a `Fill Missing Data` action.
- Default list ordering prioritizes rows with higher real-data completeness rather than N/A-heavy rows.


## 2026-09-30 ownership / ISIN / timeframe correction
- US ownership headings now use Institutional Ownership, Insider Ownership and Retail/Public Investors.
- Retail/Public is shown only when it can be transparently derived as 100% - institutional - insider; unavailable values remain N/A.
- Indian ownership keeps Promoter/FII/DII/MF/Public categories from the Indian shareholding source.
- ISIN is stored beside the company record when a real provider/listing source supplies it (official NSE list for NSE; Yahoo lookup when available for selected/enriched US/BSE symbols).
- Selected-timeframe technical calculations already use resampled daily/weekly/monthly candles; UI labels now follow the selected period for day-based client rules.
