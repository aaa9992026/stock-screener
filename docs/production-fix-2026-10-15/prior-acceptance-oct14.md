# Milestone 2 acceptance — October 14, 2026

**Milestone 2 is not fully accepted.** The implementation and local verification below preserve the approved UI. The full RS population, complete financial/ownership coverage, point-in-time universe backtesting, native Excel execution, and acceptance of a deployed new release remain outstanding. No production push, deployment, or production database mutation was performed.

## Acceptance matrix

PASS means the stated implemented scope was exercised locally. Recorded-provider API tests and browser response replay are not production acceptance tests. BLOCKED includes an implemented framework whose required data or integration cannot be verified here.

| Requirement | Result | Evidence |
|---|---|---|
| Fundamental Ranking | BLOCKED | Exact EPS/PAT/Sales 11-rule framework retained; fiscal-date matching and missing-quarter tests pass. Complete quarterly history, industry history, and unconfirmed NPM/CFO weights remain unavailable; no weights were guessed. |
| Technical Ranking | PASS | EMA, RSI, ROC, BB, 52-week metrics, volume missing-data and full-history tests; independent real calculations across five stocks × three timeframes. Unspecified client factors stay disabled/N/A. |
| Ownership Ranking | BLOCKED | Current verified categories remain available; unavailable US historical ownership and Indian published shareholding history cannot satisfy historical change rules. |
| RS 0–100 | PASS | Fixed 5,000 denominator, tie handling, zero/one/incomplete/full cohort tests and weight independence. Small incomplete scores are genuine provisional percentiles, not raw price ratios. |
| 5,000-stock universe | PROVISIONAL | Local scored observations: **US 66/5,000; India 49/5,000**, comparison date 2026-10-06. Eligible masters: US 5,753; deduplicated India 5,289. Real bounded batches and persisted cooldown/checkpoints exercised. |
| Composite Score | PASS | Default 30/25/25/15/5 and edited weights; ranking snapshot/detail/export component agreement. Missing inputs prevent a Final score; available partial categories are labeled Provisional. |
| Top 200 Ranking | BLOCKED | Snapshot workflow, components, sorting, standard deviation beside weekly Beta and ranking CSV implemented. This run returned **108 real provisional candidates**, not a verified complete 200-stock qualified list. |
| 2-year Weekly Beta | PASS | Five real stocks, 104 aligned weekly returns each; independent covariance/variance agrees within 0.000001. Adjusted prices and completed weeks; no undated daily substitution. |
| Sector Analysis | BLOCKED | Accessible workspace, median growth, acceleration, breadth, momentum, relative return, leadership, market separation and constituent coverage implemented. Only partial real statement/price coverage is populated; final sector acceptance is withheld. |
| Portfolio Management | PASS | Persisted **paper** portfolios; verified closing-price trades, costs, cash, weighted cost, partial sales, realized/unrealized P&L, observed equity, concentration/exposure/risk limits, currency isolation and idempotency. No broker holdings or sample positions are created in production. |
| 20-year Backtesting | PASS | Selected-stock technical simulation and legacy comparisons, genuine history, next-session entry, initial/trailing/EMA stops, gaps, costs, whole-share sizing, trade results, qualifications, equity/drawdown and performance metrics. History ranges below. |
| Point-in-time Backtesting | BLOCKED | Fundamental/ownership strategies return HTTP 422 with the missing-data reason. No current financial snapshot is used for historical selection. Historical eligible-universe vintages, announcement-time statements and published ownership vintages are not configured; survivorship is not certified. |
| SEC EDGAR | BLOCKED | Existing official CIK, filings, companyfacts and retry flow preserved; added shared conservative request pacing. `SEC_USER_AGENT` is absent in this environment; live SEC acceptance was not performed. Missing-credential behavior is tested. |
| US Data | PASS | Fresh actual AAPL, NVDA and LITE prices, metadata, available statements and adjusted Beta observations. NVDA ISIN was not returned by the provider and remains N/A. |
| NSE Data | PASS | RELIANCE real history, metadata, fundamentals, indicators, ranking snapshot and export. Unsupported ownership fields remain N/A. |
| BSE Data | PASS | TCS real history, available fundamentals, metadata, ranking snapshot, backtest and export. Matching verified issuer ISIN retained. No universal BSE field coverage is claimed. |
| Excel Current Stock | PASS | All five provider-backed XLSX files loaded; symbol, exchange, price and EPS checked; editable formulas and missing-data values preserved. |
| Excel Live Connection | BLOCKED | IQY selection and HTTP CSV/feed pass locally; native Microsoft Excel Refresh All was not exercised. |
| Master Excel + Python | BLOCKED | Reusable workbook, bridge and ZIP download/integrity preserved; Excel is installed, but this session does not expose the required Windows Computer Use node_repl/@oai/sky runtime; native Excel/xlwings execution was not exercised or simulated as acceptance. |
| Frontend Build | PASS | `npm.cmd --prefix frontend run build`; lint passes with eight existing nonblocking warnings; bundle-size warning remains. |
| Backend Tests | PASS | 36 tests, 0 failures, including schema compatibility and reconnection/readiness checks. |
| Deployment Readiness | BLOCKED | New code compiles and migration/readiness tests pass; existing Railway `/health` returned HTTP 200 with `database: ready`. Both existing production RS-status requests subsequently returned **HTTP 502**. This does not establish the crash cause or validate the new release, Railway build logs, PostgreSQL migration or Vercel production behavior; logs/access are required. Deployment is not authorized. |

## Implemented corrections and modules

- Corrected Beta to date-aligned two-year weekly adjusted returns. Ranking warms missing Beta data in a bounded background thread and exposes N/A while pending.
- Corrected active ROC(20) from the obsolete 21-bar monthly approximation to 20 actual bars. Preserved true daily trailing-one-year 52-week metrics and monthly EMA calculation before display slicing.
- Corrected financial comparisons to match actual fiscal dates. Missing quarters cannot shift YoY/QoQ windows or acceleration inputs.
- Historical relative-price percentile charts are labeled as a stock's own history; they are explicitly separate from the client universe RS score. Removed the obsolete undated daily Beta implementation.
- Sector growth uses the approved medians and component weights. Missing breadth components no longer inflate sector scores, and US/India sector cohorts are separate.
- Added dedicated Sector and Portfolio workspaces without changing the existing design system. Added detailed trade simulation within Backtesting and CSV exports for ranking, sectors, trades and historical qualifying dates.
- Portfolio trades are explicitly paper records, with database row locking, request idempotency, ordered ledger events and cash/risk checks. Recorded stops are informational; they do not place or automatically execute broker orders.
- Backtest decisions use prior-close signals and next-session opens. A trailing stop derived from today's high cannot execute retroactively during the same bar. Fundamental/ownership historical selection is blocked without published vintages.
- RS scoring now requires the same minimum real-history readiness as the progress counter; a short-history IPO cannot produce a false complete cohort simply because calendar-candle return fields are present.
- RS retries now use persisted exponential cooldowns capped at 72 hours. Successful retrieval resets retries; missing/short histories never count as a completed cohort.
- Idle/complete RS checkpoints now strip prior batch diagnostics instead of recursively embedding them in both before/after snapshots. Status reads cap legacy diagnostic payloads, and evaluation-date reads defer that payload. A 20-cycle regression verifies bounded serialization while retaining genuine cohort observations.
- Database interruptions restart initialization instead of leaving health permanently degraded. Unready application endpoints return retryable 503 responses. Startup remains asynchronous; no full 5,000-stock scan occurs before health.
- Removed unconditional “Data Fresh” claims. The UI identifies provider response receipt and the actual price observation date; partial category scores are labeled Provisional.

## Observed history and independent arithmetic

| Stock | Legacy comparison rows | Actual years | Trade simulation rows | Trades | 2Y weekly Beta |
|---|---:|---:|---:|---:|---:|
| US:AAPL | 5,045 | 20.06 | 5,026 | 190 | 1.064578 |
| US:NVDA | 5,045 | 20.06 | 5,026 | 270 | 1.840223 |
| US:LITE | 2,823 | 11.23 | 2,823 | 204 | 2.121070 |
| NSE:RELIANCE | 4,947 | 20.06 | 4,931 | 228 | 0.885490 |
| BSE:TCS | 4,944 | 20.06 | 4,924 | 221 | 0.708597 |

Different row counts reflect the legacy approximate 20-year horizon and the selected trade simulation date range. LITE's short listed history remains explicitly partial. Actual tested history ranges: AAPL/NVDA 2006-09-22–2026-10-13; LITE 2015-07-23–2026-10-13; RELIANCE/TCS 2006-09-22–2026-10-14. Provider timestamps and financial-period counts are retained in the evidence files.

Independent EMA/RSI/ROC/BB checks use full calculation rows and a maximum absolute tolerance of 0.005001 for two-decimal API fields. Beta tolerance is 0.000001. Backtest ledger totals, CAGR, next-session dates, end equity and drawdown reconcile; unit fixtures are confined to tests. Simulations assume long/cash positions, explicit commission/slippage, whole shares, price-only returns and end-of-test liquidation. Quarterly EPS chart annotations use fiscal period dates, not verified release-time vintages, and are not historical trade-selection evidence. Raw Yahoo OHLC is split-normalized; dividends and a separate corporate-action ledger are not modeled. Paper trades use verified closes, whereas historical simulation executes next opens; those execution assumptions are disclosed.

## Evidence and commands

- [Provider observations](milestone2-validation/provider-report.json): fresh real provider fetches, available statements and weekly-risk outputs.
- [Independent indicators](milestone2-validation/independent-indicators.json), [independent Beta](milestone2-validation/beta-independent.json).
- [API checks](milestone2-validation/api-report.json): 113 successful checks using recorded real market/statement/benchmark inputs; unsupported historical strategies also checked for HTTP 422. QA paper transactions occur only in an isolated SQLite database.
- [RS background batches](milestone2-validation/rs-backfill.json): actual bounded provider downloads, failures and retained checkpoints. Counts in the acceptance table include subsequent persistence of the five selected stocks.
- [Browser verification](milestone2-validation/browser-report.json): **184 passing interaction checks, 385 layout cases, no layout failures and no console errors**; production frontend against revised backend response replay. Auxiliary unrecorded SEC/ownership/delivery responses are explicit missing-data fixtures. This is local integration evidence, not production acceptance.
- [Production RS status](milestone2-validation/production-rs-status.json): both market requests returned 502; no production backfill was triggered. [Earlier health observation](milestone2-validation/deployment-health.json) returned HTTP 200 with a ready database.
- [Final local RS status](milestone2-validation/rs-final-status.json): 66 US and 49 India histories ready. The scoring cohort is now gated by the same readiness criteria, preventing short-history false completion.
- Regression suites: `backend/tests/test_completion.py`, `test_milestone2.py`, `test_readiness.py`.

Standard environment commands:

```powershell
$env:PYTHONPATH = "backend"
python -m unittest discover -s backend/tests -v
python -m compileall -q backend/app
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend run lint
git diff --check
```

This machine used its embedded Python 3.13 with the existing isolated QA dependency directory and `.completion-qa/run_python.py` to run those backend suites. Workbooks were read and structurally validated; native Excel recalculation and xlwings were not exercised.

## Actions required to unblock acceptance

1. Confirm unreadable/unspecified client weights and definitions; provide provider coverage for the enabled financial and historical ownership rules. Existing zero/disabled settings remain unchanged until confirmed.
2. Supply a genuine SEC application/contact User-Agent, then validate filings/companyfacts against live official endpoints. No contact identity is invented.
3. Configure a licensed or otherwise verified historical dataset with announcement/availability dates, statement vintages, published ownership and dated eligible-universe constituents. Only then can full point-in-time fundamental/ownership/universe strategy acceptance proceed.
4. Continue the deployed persistent RS batches until 5,000 usable eligible observations per market exist on one comparison date; then validate final rankings and sector coverage. Do not substitute the local 66/49 count for a production count.
5. Run native Excel live refresh and the reusable xlwings bridge in the client environment or restore the Computer Use runtime; check formula recalculation, selected symbol changes and reconciliation.
6. Authorize deployment and provide deployment/log access for the new release; validate the PostgreSQL upgrade, scheduler, Railway health, memory and Vercel API configuration.

## Deployment instructions — prepared, not executed

The existing production RS status endpoints returned 502 during read-only checks; preserve logs and inspect the current release before deploying. The recursive diagnostic risk is fixed locally, but its relationship to these production failures is not established.

Use backend root `backend`, Python 3.13, `pip install -r requirements.txt`, and the existing `uvicorn app.main:app --host 0.0.0.0 --port $PORT` command. Use one web worker with the in-process scheduler. Set external `DATABASE_URL` and provider settings without committing secrets. Startup creates additive portfolio tables and adds `rs_histories.retry_count` idempotently; retain the existing portfolio/RS/snapshot tables during OHLCV compaction. Verify `/health` reports `database: ready` and unready API requests recover from 503.

Retain `FREE_TIER_MODE=1` on constrained storage. RS evaluation stays in bounded batches; `RS_BACKFILL_BATCH_SIZE=25` and a five-minute interval are supported, with environment overrides honored. Monitor actual cohort progress and provider cooldowns. Configure Vercel root `frontend`, its existing build/output settings, and `VITE_API_BASE_URL` for the authorized backend. Re-run the five-stock matrix after deployment.

Suggested Git commit message: `Implement Milestone 2 analytics, paper portfolios and verified trade backtesting`

Provider behavior references: [yfinance history implementation](https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/history.py) and [SEC automated-access rate controls](https://www.sec.gov/filergroup/announcements-old/new-rate-control-limits).

Native Windows automation follows the [Computer Use skill](C:/Users/USER/.codex/plugins/cache/openai-bundled/computer-use/26.903.71938/skills/computer-use/SKILL.md) and its [guidance](C:/Users/USER/.codex/plugins/cache/openai-bundled/computer-use/26.903.71938/docs/guidance.md): “Use `node_repl` JavaScript for all Computer Use actions.” That runtime is not callable in this turn; no alternative Windows UI automation was attempted.
