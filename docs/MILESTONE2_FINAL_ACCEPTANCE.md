# Milestone 2 final stabilization acceptance - October 16, 2026

**Final acceptance: FAIL. Ready for scoped client review with disclosed limitations; not ready for unconditional final sign-off.** Both deployed Top-200 routes still returned HTTP 502. A focused local stabilization patch is ready and tested, but has not been committed, pushed or deployed by this pass. The actual private Railway failure mechanism remains BLOCKED; no OOM, restart, timeout or database failure is asserted as its proven cause.

The verified deployed commit is `d1d631e97419d4f94bbe47b8dbb3440a765413e5`. Public GitHub deployment metadata reports Railway success at 13:01:25 UTC and Vercel success at 13:00:32 UTC. The stable frontend HTML, JavaScript and CSS returned 200 at 19:16 UTC; its bundle identifies the expected Railway backend. Deployment success does not establish runtime reliability. See [deployment metadata](final-delivery-2026-10-16/deployments.json) and [frontend HTTP evidence](final-delivery-2026-10-16/frontend-live.json).

This pass preserves the approved UI source/CSS and production data. No deployment, settings change, trade, portfolio creation, POST, forced backfill, SQL mutation, database reset or destructive migration was performed against production. Public GET handlers can perform their normal cache maintenance. All test writes used isolated local databases. No Railway credentials or private logs were requested.

## Acceptance matrix

PASS means the stated, bounded behavior was verified. BLOCKED identifies unverified scope or missing inputs; it does not imply the feature was removed. Provisional data remains described as provisional even though this matrix uses only the requested PASS / FAIL / BLOCKED labels.

| Existing module / requirement | Status | Evidence and limits |
|---|---|---|
| Vercel release and public frontend assets | PASS | Stable frontend HTML/JS/CSS 200; bundled API points to the correct Railway URL; deployment metadata matches starting commit. |
| Approved UI/UX preservation | PASS | No frontend source, CSS or layout changes. Build and eight frontend tests pass. Prior browser checks remain dated evidence. |
| Fresh interactive browser retest | BLOCKED | Required browser-control Node REPL tool is unavailable in this session; HTTP/asset verification succeeded. No new interactive or console-error certification is claimed. |
| Railway deployment and health/database response | PASS | Successful public deployment metadata; initial and final health GET 200, database ready. Health failures during the same window are counted separately below. |
| Railway sustained runtime reliability | FAIL | 29 backend GET observations: 24 HTTP 200, four HTTP 502, one explicit ranking-warmup 503. Health also failed during the ranking window before recovering. |
| US Top-200 production availability | FAIL | First response 503 `RANKING_WARMING`, next read after five seconds 502. No repeated generic-502 polling. |
| India Top-200 production availability | FAIL | One read returned 502. No repeated load or forced recalculation. |
| Actual Railway 502 root cause | BLOCKED | Public bodies/request IDs confirm failure but cannot identify private process/resource/SQL failure. No guessed cause. |
| Focused local Top-200 stabilization | PASS | Persisted candidate-only prices; no candidate download or statement/Beta crawl initiated by ranking; binary date lookup; existing completed-response delivery retained. Real API, large persisted fixture and regression tests pass. This is not a production-fix certification. |
| Production validation of this new local patch | BLOCKED | No deployment authorized/performed. Requires an approved release and subsequent bounded automated verification. |
| US screener, search, company details and prices | PASS | AAPL search/detail/technical endpoints 200 with real identity and dated observations. Stored screener price date differs from selected-stock live price; not represented as a synchronized quote. |
| NSE screener, search, company details and prices | PASS | RELIANCE search/detail/technical/XLSX 200; correct company and ISIN. Only sampled paths, not every listed security. |
| BSE screener, search, company details and prices | PASS | TCS search/detail/technical/XLSX 200; correct BSE identity/ISIN. Missing export Sector/Industry correctly N/A. |
| Technical and fundamental filter implementation | PASS | Existing filter/scoring/API regressions pass on isolated inputs; public q/search filtering works across all three markets. Production qualified-scan POST was not run because it can launch provider work. |
| Full production qualified-filter coverage | BLOCKED | Full eligible financial/ownership histories are incomplete. A successful filter response is not proof of complete provider coverage or 200 qualified stocks. |
| Technical calculations and chart history | PASS | Public daily summaries succeed for all three sampled markets. Independent recorded-real-input EMA/RSI/ROC/Bollinger checks pass for five stocks x daily/weekly/monthly; insufficient monthly history stays N/A. |
| Fundamental inputs and implemented growth calculations | PASS | AAPL fundamentals/history 200, SEC companyfacts + Yahoo merged source; dated fiscal comparisons, gap handling and implemented handwritten EPS/PAT/Sales regressions pass. This does not accept unresolved NPM/CFO definitions. |
| Complete Fundamental scoring/data acceptance | BLOCKED | Quarter-duration CFO missing in sampled AAPL history; unresolved client NPM/CFO point allocations/industry comparisons and full-market compatible history coverage remain unavailable. No fabricated points. |
| Ownership current provider information | PASS | Public AAPL holder details and current summary 200; holder pctChange semantics explicitly identify position/share changes. |
| Historical aggregate Ownership scoring | BLOCKED | Aggregate dated ownership series unavailable; historical score withheld. Current institution/insider percentages are not a substitute for quarter-over-quarter aggregate ownership history. |
| US RS population target | PASS | 5,428 ready / 5,757 active; 5,000 target met, evaluation 2026-10-14. AAPL RS 83.45. Readiness count is distinct from the fixed 5,000 scoring cohort. |
| India RS population target | BLOCKED | 4,423 / 5,278 active, 855 pending; target 5,000 short by 577. NSE 2,193 ready, BSE 2,230 ready; evaluation 2026-10-07. Incomplete ranks remain provisional. |
| Background processing public diagnostics | PASS | Status reports scheduler enabled/running and persisted last batches; India latest batch three successful downloads, zero increase in ready count. Short histories are not falsely counted as ready. No private log certification. |
| Composite arithmetic and missing-category treatment | PASS | Live backend baseline AAPL components reconcile to 87.91. Decimal/half-cent, missing-value and snapshot regressions pass. Editable frontend growth-rule score is a separate calculation; see reconciliation below. |
| Sector Analysis shared cohort calculation | PASS | Public US sector endpoint 200. Technology 94.12 matches AAPL Sector component and shared cohort ID, 66 enriched / 414 constituents. |
| Complete Sector/final score qualification | BLOCKED | Sector cohort is explicitly provisional and incomplete; unresolved scoring definitions prevent final classification. Data coverage is not equivalent to final qualification. |
| Current production ranking/detail/export snapshot identity | BLOCKED | Both ranking reads failed; no fresh production snapshot could be compared. Local actual routes and persisted ScoreSnapshot/export regressions pass. |
| Production Top-200 final-qualified count | BLOCKED | No successful fresh ranking body. Local builds return 200 provisional rows per market; implementation currently withholds final qualification (`final_composite_score=None`, final-qualified count zero). Do not promise 200 fully qualified stocks. |
| Portfolio Management existing read/list | PASS | Existing portfolio list GET 200. No production create/trade/valuation requests; valuation GET can persist marks. |
| Portfolio paper-trade/accounting implementation | PASS | Isolated API create/trade/reconciliation and backend portfolio/risk regressions pass. Stops are informational; this is paper portfolio management. |
| Production portfolio write/valuation acceptance | BLOCKED | Intentionally outside production-safe read-only checks; existing records preserved. Local tests are not certification of real brokerage execution. |
| Existing technical Backtesting | PASS | Live AAPL 20-year GET 200: 5,047 bars, 20.0575 years, 2006-09-25 to 2026-10-16. Local US/NSE/BSE recorded history checks pass; younger listings correctly Partial. Strategy result 'Fail' means strategy performance, not HTTP/software failure. |
| Historical point-in-time Fundamental/Ownership backtesting | BLOCKED | Missing publication-time financial/ownership vintages and historical eligible-universe membership. Technical backtesting availability does not remove survivorship/look-ahead limitations. No new historical dataset implemented. |
| Beta calculation | PASS | Live AAPL Beta 1.064577, alpha 7.234464, 104 aligned completed-week observations, as-of 2026-10-12; adjusted Yahoo basis disclosed. Ranking now reads only existing Beta cache and otherwise N/A. |
| Excel XLSX / live CSV endpoints | PASS | AAPL CSV 200; AAPL/NSE RELIANCE/BSE TCS XLSX 200, eight sheets and 20 dated OHLCV rows each. Downloaded files parsed locally. Snapshot export identity passes local regressions; fresh production ranking identity remains separately blocked. |
| Existing Master Excel package/backend contract | PASS | Current recorded-input API replay passes package/Excel contracts; earlier public ZIP success is archived, not claimed as a new request. |
| Native Excel/xlwings refresh execution | BLOCKED | This environment did not exercise a native Excel bridge. File parsing and API success do not certify Excel automation. |
| Backend regression | PASS | Final 73 tests pass, zero failures/errors. Includes no candidate fan-out, preserved records, stale/invalid observations and original linear-vs-binary lookup equivalence. |
| Frontend regression, lint and build | PASS | Eight Node tests pass; lint/build succeed. Eight existing lint warnings and the existing large-bundle warning remain. UI unchanged. |
| API integration and independent indicator regression | PASS | 113 recorded-real-provider API replay checks; independent five-stock x three-timeframe indicator checks. Isolated SQLite; not live market coverage or a production load test. |
| Full Milestone 2 final acceptance | FAIL | Critical deployed Top-200/runtime failures persist. External-data/definition/runtime limitations above remain open. |

## Focused repair and evidence

The deployed completed-response layer was already in place. Inspection confirmed that its background build still downloaded candidate two-year price histories and launched additional statement and Beta crawls. Moving that work off the HTTP thread did not remove its process resource cost. This pass removes that confirmed ranking-triggered fan-out; it does not claim that fan-out caused the private Railway failures.

Candidate prices now stream only requested keys: chunks of 100, legacy OHLCV projected columns/yield 1,000 and compact RS payloads/yield 10. The helper merges actual dated observations, prefers compact values on duplicate dates, excludes future/weekend/invalid values and withholds price/Technical when the latest stored observation is older than 14 days. It performs no source-record writes. `latest_date` and `price_source` identify the stored basis. The compact series can have a shorter history and older quote date than a newly downloaded two-year series, so Technical/price values can change with input vintage even though scoring rules are unchanged. No missing sessions are synthesized.

Ranking reads do not start statement or Beta provider work. Existing caches are used; missing ranking statements/Beta remain N/A. `enrichment_remaining_count` still discloses missing coverage and `enrichment_in_progress` is false, rather than claiming a crawl is running. Other existing selected-stock/filter/scheduled data workflows remain intact; no new worker or backfill was added. **The exact benchmark retains its existing cache/provider fallback**, so this is not a claim that all ranking work is network-free or that a total build deadline is enforced.

RS candle-open lookup now locates the boundary with binary search over ordered dates instead of scanning hundreds of preceding observations per stock/period. A 254-case boundary/gap/fallback equivalence test compares it to the original linear lookup. Period definitions, tie handling, fixed 5,000 denominator, full reference distribution, candidate selection and score weights are unchanged. Completed-response cache fingerprint v2 prevents old price-source bodies being reused after deployment; no old snapshot or market record is deleted.

The existing single background builder per process, bounded queue/cache, 2 MiB payload cap, candidate-filtered enrichment SQL, shared sector cohort, immutable ScoreSnapshot storage, stale-age headers and explicit cold-cache 503 remain in place. Safe exception-class/stage-duration/RSS diagnostics remain enabled. The new stored-price stage uses the same safe tracing. Cross-process builds are not globally serialized; Railway Postgres/process RSS/provider latency are not reproduced by SQLite.

The isolated persisted fixture contains 11,034 synthetic listing identities, 5,426 US / 4,423 India ready histories and recorded real provider prices/statements. Synthetic identities exist only in the benchmark database, never production. The exact benchmark and risk cache are supplied by recorded/stubbed fixtures; candidate-provider access raises an error. One build per market serves the burst, 200 provisional rows return, immutable IDs remain stable, every stored row Composite matches, and new delivery instances reload byte-identical responses.

| Final local HTTP metric | US | India |
|---|---:|---:|
| Background build | 5.34 s | 4.51 s |
| Warm response median | 4.18 ms | 4.15 ms |
| Restart read | 6.10 ms | 5.70 ms |
| Response size | 671657 | 672264 |

The preceding same-fixture run exposed the repeated scan cost (US 48.89 s / India 17.81 s under concurrent local verification). Host load differed, so this is **not a controlled speedup claim**. The final measured 5.34/4.51-second build timings are local, not a guarantee against Railway 502s. See [final load results](final-delivery-2026-10-16/http-load.json) and [earlier local measurements](final-delivery-2026-10-16/http-load-before-date-lookup.json).

## Score reconciliation and production observations

Independent arithmetic on the saved provider responses confirms AAPL quarterly EPS/PAT/Sales YoY comparisons, current-summary ownership weighting, five positive Fundamental baseline fields, price-above-EMA/RSI Technical rules and Sector component weighting. This validates the implemented baseline and available growth inputs, not missing historical Ownership/CFO data.

Current AAPL backend baseline components are Fundamental 100, Technical 100, RS 83.45, current-summary Ownership 48.92 and provisional Sector 94.12. The exact weighted sum is `100*0.30 + 100*0.25 + 83.45*0.25 + 48.92*0.15 + 94.12*0.05 = 87.9065`, rounded **87.91**. The endpoint labels this the live baseline; it is not the frontend editable handwritten-growth score or a Top-200 immutable snapshot. Current Fundamental baseline positivity rules and current-summary Ownership must not be confused with the client's growth/history definitions.

The earlier user-reported editable components Fundamental 28.2, Technical 85.1, RS 83.5 and Ownership N/A produce **50.61 + 0.05*Sector** under weights 30/25/25/15/5. For example, a genuine Sector 85.0 would yield 54.86, displayed 54.9. This is arithmetic, not an assertion that the current Sector is 85.0. Current live Sector is 94.12; the older 54.9 cannot be certified as today's immutable ranking result because the public ranking endpoints failed. Missing Ownership earns no points and stays N/A, never renormalized into a fabricated higher score. Full/final classification stays withheld while definition/cohort/history requirements remain unresolved. Earlier browser-derived reconciliation is archived and is not relabeled current.

Public response evidence records request times, status, duration, safe headers/request IDs, score inputs, dated prices, cohort counts and provider limitations. The 503 is explicit application warmup, distinct from four generic Railway 502s. Two 502s affected rankings and two affected intervening health checks. Later stock modules recovered; this does not prove stable service. The search screener's AAPL stored price was 330.32 dated October 1, while selected-stock Technical returned 341.62 dated October 16. Dated stored ranking inputs must not be described as synchronized live quotes.

## Remaining external inputs and boundaries

- Client-approved exact NPM/CFO point allocations, period/industry comparison definitions; actual quarter-duration CFO and industry CFO reference inputs where unavailable.
- Verified dated aggregate ownership history with category definitions, not individual-holder changes or current ownership snapshots.
- Sufficient eligible India histories to meet 5,000 (577 additional ready histories needed in this sample), and complete compatible statement/sector constituent coverage. Short newly listed histories cannot be invented or made ready by changing the requirement.
- Publication-time financial/ownership vintages and historical eligible-universe constituents for point-in-time fundamental simulations. No historical dataset implementation is part of this final pass.
- Provider entitlement/source data only where these histories are not available from existing public sources; no new credential is asserted necessary for already-working sampled endpoints. No Railway credentials requested.
- Native Excel/xlwings runtime verification. Public XLSX/CSV contract validation is complete within the stated scope.
- Approved deployment and automated public recheck of this patch. Private Railway evidence would be required to establish the actual platform failure cause if public diagnostics remain insufficient; that diagnosis is BLOCKED under the user's access boundary, without asking for access.

## Evidence and delivery

- [Independent production Fundamental/Technical/Ownership/Sector arithmetic](final-delivery-2026-10-16/production-arithmetic.json); [Public backend observations and response/export arithmetic](final-delivery-2026-10-16/public-evidence.json); [frontend HTML/assets](final-delivery-2026-10-16/frontend-live.json); [deployment metadata](final-delivery-2026-10-16/deployments.json).
- [Final 73 backend test results](final-delivery-2026-10-16/backend-tests.txt); [113 API replay checks](final-delivery-2026-10-16/local-api-report.json); [independent indicators](final-delivery-2026-10-16/local-independent-indicators.json); [local production-sized load/snapshot checks](final-delivery-2026-10-16/http-load.json).
- [AAPL workbook](final-delivery-2026-10-16/AAPL-28.xlsx), [NSE RELIANCE workbook](final-delivery-2026-10-16/RELIANCE-21.xlsx), [BSE TCS workbook](final-delivery-2026-10-16/TCS-25.xlsx); workbook sheet/identity/row summaries and SHA-256 hashes are in public evidence.
- [Preceding report](final-delivery-2026-10-16/prior-acceptance.md) and [earlier full live/browser matrix](ranking-502-fix-2026-10-16/prior-acceptance.md) remain dated evidence; they are superseded by this report's current status.
- [Client delivery summary and authorized-release instructions](MILESTONE2_CLIENT_DELIVERY.md).

Fresh browser limitation: the installed [browser skill](C:/Users/USER/.codex/plugins/cache/openai-bundled/browser/26.1007.21434/skills/control-in-app-browser/SKILL.md) states: "Only the Node REPL `js` tool (`mcp__node_repl__js`) can be used to control the selected browser." That tool is unavailable here, so no alternate browser automation was used and no fresh interactive-browser pass is claimed. Existing approved UI files were preserved.

Reproduce with configured backend dependencies from repo root: `python -m unittest discover -s backend/tests -v`; `python backend/scripts/benchmark_top200.py`; `node --test frontend/tests/scoring.test.mjs frontend/tests/ranking.test.mjs`; `npm.cmd --prefix frontend run lint`; `npm.cmd --prefix frontend run build`; `git diff --check`. The benchmark selects only its isolated local database and expects recorded dates within the readiness window. This workstation used its existing isolated dependency launcher. API replay uses the existing recorded provider fixtures, not production mutations.
