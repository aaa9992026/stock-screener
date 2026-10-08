# Completion pass verification

Verified locally on October 7–8, 2026. The current visual system is preserved. These changes have not been deployed or pushed.

## Changes

- Fixed the missing pandas import that broke backtesting and the live-provider row access that broke Excel exports. Both AAPL and RELIANCE now return populated backtests and valid workbooks.
- Added a bounded, compressed RS history store and persisted batch state/retry cooldowns. Free-tier cache cleanup no longer removes this RS store. Automatic RS batches now run in free-tier mode.
- Added the approved Twelve Data BSE listing directory to company synchronization. Indian RS candidates prefer NSE and deduplicate dual listings by ISIN or ticker. Local masters contain 5,753 eligible US listings and 5,289 unique Indian listings.
- Kept the fixed 5,000 percentile denominator, exact tie formula, default weights, and weight-independent raw relative returns. Incremental comparisons use one persisted evaluation date. Incomplete scores stay explicitly provisional.
- Reduced Overview to the dashboard, three compact filter previews, and an eight-row Top 200 preview. Detailed analysis, weights, history, and SEC tools remain accessible in Ranking and the dedicated workspaces.
- Corrected missing-value formatting, stale backtest response handling, export error details, and a duplicated US ownership heading.

## Results

| Requested check | Result |
| --- | --- |
| RS 5,000-stock full real history coverage | **FAIL / pending**: 15/5,000 US and 10/5,000 India in the isolated verification database. The requested persisted incremental alternative is implemented and tested. |
| Backtesting AAPL | PASS: 5,046 observations, about 20.1 years, KPIs, equity curve, six strategy results |
| Backtesting RELIANCE | PASS: 4,953 observations, about 20.1 years, KPIs, equity curve, six strategy results |
| Excel export AAPL | PASS: workbook loaded, 5,000 history rows, formula cells retained, missing data N/A |
| Excel export RELIANCE | PASS: workbook loaded, 5,000 history rows, formula cells retained, missing data N/A |
| Excel Live Link | PASS: selected-stock IQY generated; feed and live CSV return HTTP 200 |
| Master Excel package | PASS: HTTP download and ZIP integrity; reusable workbook, bridge, requirements, and launchers present |
| Overview cleaned | PASS |
| Top 200 checked | PASS: basket, periods, weights, ascending/descending sorting, Beta beside standard deviation |
| Filters checked | PASS: all four workspaces, required columns, weights, Use toggles, qualified-table layouts |
| Settings checked | PASS: timeframe updates reflected in session state |
| Frontend build | PASS |
| Browser console errors | NONE in the exercised local browser session |

17 backend regression tests pass. 32 backend HTTP checks return 200. Browser verification includes 51 assertions and 126 layout cases across both stocks and widths 320, 390, 768, 1366, 1440, 1600, and 1920; no document overflow or tested control overlap was detected.

## Evidence and limits

- [Real-history and workbook report](live-data-report.json): provider observations were downloaded from Yahoo, then reused for deterministic local endpoint/workbook checks. Workbooks were loaded with openpyxl; Microsoft Excel's native UI and formula recalculation were not exercised.
- [Real incremental report](incremental-report.json): actual provider batches in an isolated local database. US ready coverage increased 10 → 15; India increased 6 → 10. One unsupported BSE symbol produced a persisted cooldown; other symbols continued. No production database writes were made.
- [HTTP report](api-report.json): revised backend routes using recorded real stock and benchmark history. Auxiliary delivery/comparison metadata remained unavailable.
- [Browser report](browser-report.json): production frontend build with replayed responses from those backend HTTP checks. Auxiliary fundamentals, ownership history, SEC, and classification responses were missing-data fixtures; this does not certify live upstream coverage for those providers. The ranking replay contained the two tested stocks, not a real 200-stock population.
- PNGs in this folder show all pages, desktop/mobile layouts, filter tabs, RS progress, indicator baskets, Overview previews, and backtest charts/results.
- [Regression suite](../../backend/tests/test_completion.py): explicit synthetic observations test formulas, a complete 5,000-stock cohort, persistence, retries, missing fields, and provider errors. Synthetic observations are confined to tests and never enter production data.

Run the retained regression suite from the repository root with the backend dependencies installed:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
cd frontend
npm run build
npm run lint
```

Existing nonblocking warnings remain: Vite's large bundle warning, nine lint warnings, and dependency/deprecation warnings in the QA Python environment. Deployment and continued scheduled real-history evaluation are still needed before certifying a fully populated 5,000-stock universe.

Provider references: [Yahoo history API](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html) and [Twelve Data symbol discovery](https://support.twelvedata.com/en/articles/5620513-how-to-find-all-available-symbols-at-twelve-data).
