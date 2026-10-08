# Logic consistency verification — October 8, 2026

The approved UI is preserved. These are local code changes and local verification results; this pass has not been deployed or pushed.

## Results

| Requirement | Result / evidence |
| --- | --- |
| 52-week logic | PASS. Daily, Weekly, and Monthly use the same trailing 365-calendar-day daily highs/lows and latest daily price. Positive distance below high and positive distance above low are used consistently. |
| Timeframe semantics | PASS. Period indicators use active bars. Summary ADR is explicitly daily; basket ADR is explicitly active-timeframe. ROC(20) is not called approximately one month. |
| Monthly EMA before display slicing | PASS. AAPL EMA100/200: 177.42 / 111.59; LITE EMA100: 212.60; RELIANCE EMA100/200: 1086.57 / 743.94. LITE EMA150/200 remain N/A because its listing history is insufficient. |
| BB Width formula and display | PASS. Summary, series, and explanatory text use `(Upper Band - Lower Band) / Middle Band * 100`. |
| Top 200 versus selected-stock scores | PASS using the requested snapshot approach. Ranking rows have immutable snapshot IDs, timestamps, and `client-rs5000-v2` versions. Opening a row retains its component scores across pages. Live chart/filter inputs are labeled separately; Use live scores returns to live rule evaluation. |
| RS universe | IN PROGRESS. Real persisted coverage: US 41/5,000; India 31/5,000. Rankings and detail use the same market cohort, fixed denominator, and period percentile formula. No completion is claimed. |
| AAPL backtest | PASS: 5,046 rows; 20.05 years. |
| RELIANCE backtest | PASS: 4,952 rows; 20.05 years. |
| LITE backtest | PASS: 2,820 rows; 11.21 years, explicitly partial against a requested 20 years. |
| AAPL and RELIANCE Excel exports | PASS: workbooks load; selected symbol, exchange, latest price, and EPS match recorded real provider inputs. Formula cells are preserved. |
| Excel Live Connection / Master package | PASS: selected-stock IQY downloads and CSV feeds; package downloads and ZIP integrity; the same reusable workbook/bridge is preserved. |
| BSE | PASS for TCS: search, OHLCV, charts, indicators, available fundamentals, ranking snapshot, backtest, and Excel export. |
| ISIN / issuer metadata | PASS: AAPL `US0378331005`, LITE `US55024U1097`, RELIANCE `INE002A01018`, TCS `INE467B01029`. BSE ISIN is copied from the verified NSE master only when both the ticker and normalized issuer name match. |
| Composite formula | PASS: Fundamental 30%, Technical 25%, RS 25%, Ownership 15%, Sector 5%. Edited weights normalize against the entered total. Missing categories earn no points and do not inflate the provisional composite by renormalizing only available categories. |
| Fabricated provider observations | NO. Missing rule inputs remain N/A; incomplete coverage remains provisional. |
| Frontend build / backend tests | PASS. See validation below. |
| Console errors | NONE in the final browser run. |

## Fixes and behavior

- Removed the frontend's timeframe-dependent 260-bar low calculation. The backend now returns both distances and their daily reference values.
- Removed the six-year provider cap for monthly calculation history. Chart responses expose full calculation history separately from the visible window; EMA and indicator calculations use that history before selecting plotted bars.
- Fixed a short-history fallback that discarded fresh merged observations when a listing could not reach the requested row target. Daily price, reference date, and both 52-week distances now match exactly across Daily, Weekly, and Monthly for all four recorded stocks.
- Replaced Top 200's bounded-candidate RS percentile with the shared persisted 5,000-stock cohort calculation. Dual-listed BSE targets use their own real returns against that same deduplicated cohort without being counted twice.
- Saved compact immutable scoring snapshots. Snapshot exports identify their source and populate the corresponding scoring cells. Live price history and snapshot prices are identified separately. Snapshots are retained for 24 hours; an expired snapshot export returns a useful refresh instruction.
- Reused the Filters rule evaluation for live score cards, eliminating a second technical rule subset. Final scores are withheld when required inputs, rule coverage, or the RS universe are incomplete.
- Calculated backtest signals with real warm-up history before slicing the requested test horizon. Buy-and-hold returns and the final curve point were independently checked against the provider closes.
- Kept missing volume out of scoring averages and chart values instead of treating it as verified zero volume. Weekly/monthly volume stays N/A if any constituent daily volume is missing. Fixed stale chart-request logging and same-stock row reopening.
- Distinguished EPS (TTM), quarterly chart EPS, and EPS/PAT/Sales ranking scores. BSE now defaults to the verified TCS listing; INFY supplied no usable history during this provider run.
- Automatic RS evaluation continues in bounded batches, defaulting to 25 symbols per market every five minutes. Existing environment overrides remain supported. Compressed observations, comparison dates, cooldowns, and batch checkpoints survive restarts and OHLCV cache cleanup.

## Evidence and scope

- [Provider report](provider-report.json): new real Yahoo OHLCV, metadata, and actual persisted background batches in an isolated local database. Unsupported provider symbols remain pending with retry cooldowns.
- [API report](api-report.json): 81 successful HTTP checks on the revised backend using those recorded real observations, real statement history, and recorded real benchmark history. Checks include independent 52-week calculations, EMA arithmetic, BB width agreement, composite arithmetic, backtest return arithmetic, and workbook values.
- [Browser report](browser-report.json): 134 passing checks, 252 layout cases without overflow/overlap failures, and no console errors. The production frontend uses revised backend response replay; four stocks, all six pages, seven widths from 320 to 1920, monthly EMA checks, opened-row snapshot card comparisons, weights, sorting, filter controls, Settings, and downloads. A separate missing-volume regression removes that field from recorded rows and verifies N/A. The browser also uses explicit missing-data fixtures for auxiliary upstreams that were not recorded, including SEC and Indian historical ownership/delivery. This does not certify those live upstream integrations or every universe stock.
- PNGs in this directory show the four-stock matrix, mobile layouts, monthly indicators, snapshots, RS progress, and populated equity curves/results.
- [Regression tests](../../backend/tests/test_completion.py): 22 passing tests, including short-history fresh merges and missing volume across all three timeframes, plus synthetic formula/cohort/error cases isolated to tests. Synthetic observations never enter production data.

Excel files were loaded and inspected with openpyxl; native Excel recalculation and live xlwings execution were not exercised. The master package was checked for download/integrity and its existing workflow was preserved.

Run from the repository root with backend dependencies installed:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
cd frontend
npm run build
npm run lint
```

Production build, Python compilation, and `git diff --check` pass. Lint passes with eight existing nonblocking warnings. The large-bundle build warning and dependency deprecation warnings remain. Deployment and continued real background evaluation are needed before declaring the 5,000-stock universe complete.

Provider history parameters follow the [official yfinance history API](https://ranaroussi.github.io/yfinance/reference/yfinance.price_history.html).
