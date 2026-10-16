# Milestone 2 - final acceptance verification, October 16, 2026

**Overall: PROVISIONAL. Ready for a scoped client review of implemented features and documented gaps; NOT ready for full Milestone 2 acceptance or production sign-off.** Production availability is FAIL. The reported 54.9 can be reproduced from current default-rule inputs, but not from the particular Fundamental 28.2 / Technical 85.1 / RS 83.5 combination supplied in the request with the observed current Sector score.

Application commit: `0485cae0eb89c8a030e16d55a191d7313cbde7ca` (clean starting tree; GitHub remote HEAD matches). Public responses expose `client-rs5000-fiscal-v3`, not the deployment Git SHA. The previous ranking performance/rounding changes are now committed; this audit does not claim independent verification of an exact deployed SHA. **No application code changes were needed in this pass.**

Production: https://stock-screener-production-d90e.up.railway.app

Fresh observation window: **October 16, 2026, 04:15:56-04:23:13 America/Los_Angeles (11:15:56-11:23:13 UTC)**. Earlier evidence is explicitly dated and is not relabeled as a fresh production pass. The approved UI/UX, database schema and persistence behavior were preserved. No deployment, production settings change, forced backfill, direct database write, migration, history reset or production portfolio/trade action was performed. Existing GET handlers may maintain their normal caches and ranking snapshots. Local portfolio operations use isolated test databases.

## AAPL composite and calculation bases

Current default editable rules evaluated against captured production inputs give:

| Component | Verified value | Composite weight | Contribution |
|---|---:|---:|---:|
| Fundamental | 27.5 | 30% | 8.25 |
| Technical | 85.07462686567165 | 25% | 21.26865671641791 |
| RS | 83.46 | 25% | 20.865 |
| Historical Ownership | N/A | 15% | Unavailable; earns no points |
| Sector | 90.42 | 5% | 4.521 |

`8.25 + 21.26865671641791 + 20.865 + 4.521 = 54.90465671641791`, rounded once to **54.90**, displayed as **54.9 Provisional**. Available component weight is **85%**. Missing Ownership stays null, and the denominator is not renormalized. Fundamental is itself incomplete (38/41 enabled rules, 400/460 rule weight); Sector is provisional. A complete US RS cohort does not make this a Final composite.

The specific reported values instead give:

`28.2*0.30 + 85.1*0.25 + 83.5*0.25 + 90.42*0.05 = 55.131`, or **55.13**, displayed 55.1. Therefore **54.9 with that exact component set is not verified**. Algebraically, exact 54.90 would require Sector 85.8 using those rounded components; 85.8 is an inference, not an observed Sector value. A one-decimal displayed score also has a rounding interval. We did not access the user's browser-local settings or identify the exact historical evaluation behind Fundamental 28.2, so no cause is asserted for that difference.

The initial dashboard and US sector response both use cohort `bd2f52fa4ef9de172efa`: Technology **90.42**, **37/402** enriched constituents (9.204% statement coverage). The later immutable ranking uses cohort `29b0a85cd318835cf8a6`: Technology **84.22**, **43** qualifying peers. Different dated cohort IDs are preserved; these are not falsely compared as the same evaluation. All eight populated sector scores independently match the 30/25/20/15/5/5 weighted formula. Full-universe sector coverage remains incomplete.

Three calculation bases remain explicit:

| Basis | Fundamental | Technical | RS | Ownership | Sector | Composite |
|---|---:|---:|---:|---:|---:|---:|
| Current default editable historical rules | 27.5 | 85.0746269 | 83.46 | N/A | 90.42 | 54.90 Provisional |
| API baseline diagnostics | 100 | 100 | 83.46 | 48.92 aggregate | 90.42 | 87.72; not full client-rule acceptance |
| Saved US ranking | 30 | 100 | 83.46 | 48.92 aggregate | 84.22 | 66.41 Provisional |

Baseline diagnostics use simpler current-field checks. Ranking Fundamental uses EPS/PAT/Sales rules and excludes unresolved NPM/CFO allocations. Current ownership aggregate scoring is not historical ownership-change scoring. Saved ranking arithmetic is `9 + 25 + 20.865 + 7.338 + 4.211 = 66.414`, rounded **66.41**. All **200** returned US ranking composites match decimal HALF_UP recomputation exactly.

[Captured default-rule calculation and missing rules](final-acceptance-2026-10-16/arithmetic.json), [full US ranking snapshot](final-acceptance-2026-10-16/US-ranking-snapshot.json).

## Acceptance matrix

PASS means the stated scope was verified; it does not extend a local/replayed result to unavailable production behavior.

| Requirement | Status | Evidence and practical limit |
|---|---|---|
| Approved UI/UX preserved | PASS | Application source/CSS unchanged in this pass; rebuilt frontend passes 184 browser checks and 110 layout cases at 390/1440 pixels. Browser API responses are replayed, not a live Vercel session. |
| AAPL 54.9 arithmetic / provisional status | PASS | Fresh captured default inputs give 54.9046567 -> 54.90, with 85% component coverage and historical Ownership N/A. |
| 54.9 using exactly 28.2 / 85.1 / 83.5 / N/A and current Sector | FAIL | Current Sector 90.42 gives 55.13 from those rounded inputs. Fresh default Fundamental is 27.5, not 28.2. No score was changed to force agreement. |
| Fundamental fiscal dates and available-input math | PASS | Live SEC fiscal ends 2026-06-27 / 2025-06-28 independently yield EPS YoY 28.6624204%, PAT 27.1187164%, Sales 16.3565018%. Missing-Q4/fiscal-date/source-compatibility regressions pass. |
| Complete Fundamental acceptance | BLOCKED | Current default evaluation has 38/41 enabled inputs (400/460 weight). Missing `cfo_q_yoy_growth`, `cfo_q_qoq_growth`, `cfo_industry_compare`. True quarterly CFO and industry reference data plus confirmed NPM/CFO definitions remain required. |
| Technical calculations | PASS | Fresh raw Yahoo data independently matches production AAPL close 342.00 (2026-10-15), EMA20/50/100/150/200, RSI14 and Bollinger width. Separate five-stock x three-timeframe recorded-provider replay passes EMA/RSI/ROC/Bollinger and daily 52-week/monthly-history contracts. Default Technical score is 85.0746269. |
| Current Ownership data / aggregate baseline | PASS | Live institutional 66.348%, insider 1.648%, derived remainder 32.004%. Independent baseline `66.348*0.70 + (1.648*5)*0.30 = 48.9156` -> 48.92. Remainder is labeled derived. |
| Historical Ownership scoring | BLOCKED | Live API states historical aggregate history unavailable and historical scoring BLOCKED. All nine positively weighted US historical-rule inputs remain unavailable; holder share changes are not aggregate ownership percentage-point changes. No aggregate substitute fills the N/A card. |
| Sector arithmetic / same-cohort detail consistency | PASS | Detail and sector API both return 90.42 for the same 37-peer cohort; eight populated sector rows independently reconcile. Later ranking cohort is separately identified. |
| Complete Sector universe | PROVISIONAL | Technology has 37/402 enriched constituents in the live sector capture; 189/200 returned US ranking rows have sector scores. No full eligible-universe Sector rank is certified. |
| US RS population and detail/ranking consistency | PASS | 5,426 history-ready / 5,756 eligible; fixed scoring reference cohort 5,000, complete, evaluation 2026-10-14. AAPL detail and ranking RS both 83.46. Fixed denominator, ties, filtering and snapshot consistency tests pass. |
| India RS population | PROVISIONAL | Fresh status: 4,423 ready / 5,278 deduplicated eligible, 855 pending; NSE 2,193, BSE 2,230 ready. Evaluation 2026-10-07; target 5,000 remains unmet. No cooldown bypass or history reset. |
| US Top-200 candidates and qualified count | PASS | 220 candidates evaluated, 200 returned, **zero Final-qualified stocks** under the current acceptance gates. 129/200 returned rows have compatible Fundamental scores; provisional rows are not advertised as qualified. |
| Fresh India ranking / qualified count | BLOCKED | Ranking request closed without response after 60.66 seconds. Fresh qualified count is unknown. Prior October 15 PDT evidence returned 200 provisional candidates, zero Final-qualified; this is historical only. |
| Fully qualified 200-stock delivery | BLOCKED | Fresh US count is zero; fresh India result unavailable. Missing coverage and unresolved client definitions prevent Final qualification. |
| Immutable US ranking / Excel consistency | PASS | AAPL snapshot `d50b24d11e514220ae8af798bb8bdf32` at 11:16:45.718259 UTC downloads successfully; all five Ranking_Config components and Summary snapshot ID exactly match the captured row. |
| Background workers / persisted state | PROVISIONAL | Public RS/enrichment status initially reports running scheduler and registered jobs. Last RS checkpoints 11:13:08 UTC show zero attempted (US complete / India idle). No second successful status after the availability failure, so fresh checkpoint advancement/job completion is not certified. Prior ready history remains present. |
| Universe financial/ownership coverage | PROVISIONAL | US any-current-field Fundamental/Ownership 2,250/5,747 (39.2%); India Fundamental 2,216 and Ownership 2,214 / 7,746 listings (28.6%). Listing counts differ from deduplicated RS population; any-field coverage does not establish complete historical series. |
| Portfolio Management | PASS | Production list endpoint initially returns 200. Isolated real-history integration verifies create/buy/equity=cash+positions; unit tests cover partial sales, overselling, idempotency, exposure/cash/risk. Browser flow passes. No production trade/write or live portfolio valuation certification was performed. |
| 20-year backtesting implementation | PASS | Current-code real-provider replay returns ~20.05 years for AAPL/NVDA/RELIANCE/TCS, ~11.23 years for LITE, correctly Partial. Six baseline strategies/equity curves and trade simulation checks pass; short-listed stocks are not padded to 20 years. |
| Fresh production 20-year backtest | BLOCKED | AAPL backtest request timed out at 15.46 seconds after production availability degraded. Recorded-input integration is not a fresh live pass. |
| Point-in-time safety guard | PASS | All five local integration Fundamental-strategy requests reject with expected 422; statement/ownership current snapshots cannot qualify historical trades. Next-open, cash, fees, risk and stop regressions pass. |
| Full PIT financial/ownership/universe backtesting | BLOCKED | Published announcement-time financial vintages, dated ownership and historical eligible-universe membership are not configured. Latest production PIT probe timed out; prior live 422 is retained as dated evidence only. |
| US/NSE/BSE prices and identity | PROVISIONAL | Fresh Yahoo raw provider histories exist for all five stocks; AAPL production close/date match exactly. Fresh provider latest closes: AAPL 342.00, NVDA 217.23, LITE 869.54 (2026-10-15); RELIANCE.NS 1,211.20, TCS.BO 2,463.00 (2026-10-16 observations). Current-code three-market price/identity tests pass on recorded real inputs. Fresh app-side NSE/BSE checks were not reached after availability failed; NVDA recorded ISIN remains unavailable, not invented. No exchange-certified real-time quote claim. |
| Beta calculation with actual adjusted data | PASS | Fresh Yahoo adjusted stock/benchmark series give 104 aligned completed-week returns each; independent covariance matches current local service for all five stocks. AAPL 1.064577, NVDA 1.840223, LITE 2.121070, RELIANCE 0.885490, TCS 0.708598. |
| Live Beta completion | BLOCKED | Captured AAPL ranking Beta is null, zero observations, history pending. Fresh risk endpoint probe timed out at 15.69 seconds; calculated local values were not inserted into production or the immutable export. |
| Excel exports / package / CSV implementation | PASS | Fresh immutable US workbook passes component/identity verification. Current-code real-input integration and browser verify five-stock XLSX/CSV/IQY/package behavior; ZIP integrity passes. |
| Fresh live NSE/BSE exports | BLOCKED | Not reached after production availability failed. Previous/local export success does not certify fresh remote NSE/BSE export. |
| Native Excel / xlwings execution | BLOCKED | Native Excel refresh/recalculation bridge not executed; required Windows automation runtime remains unavailable. File/HTTP tests are not a native Excel certification. Prior report records the automation limitation. |
| Production health and HTTP reliability | FAIL | 27 completed observations: 17 HTTP 200, ten transport failures. No HTTP 502/503 response was received in this window; connection closures/timeouts are recorded separately. Initial ready health was followed by a 35.82-second ready response and failed 15/25-second probes. Prior nine 502s/one 503 remain historical unresolved evidence, not current-window counts. |
| Private runtime root-cause diagnosis | BLOCKED | Accessible public health/root/status probes fail after initial successes. These do not establish a cause. No restart/OOM/provider-lock diagnosis is asserted; no Railway credentials requested. |
| Backend/frontend/integration regression | PASS | 56 backend tests, five Node scoring tests, 113 API checks, 184 browser checks / 110 layout cases, independent indicators, fresh-provider Beta and AAPL arithmetic pass. Build/lint/diff checks pass; eight existing lint warnings and bundle-size warning remain. |
| Final Milestone 2 acceptance | PROVISIONAL | Implemented features and evidence are reviewable; availability, Final-qualified count, historical data, complete cohorts and native Excel execution prevent full sign-off. |

## Accessible runtime diagnostics

The US ranking request succeeded in **19.25 seconds**, versus 63.94 seconds in the previous audit. This is one sample, not a causal benchmark or stability certification. India ranking and a later AAPL technical request both closed without HTTP responses at **60.66 seconds**. Separate health/root/India-status probes timed out at about 15 seconds; recovery health/root probes timed out at about 25 seconds. Later AAPL risk, backtest and PIT probes also timed out. These are transport errors, not observed HTTP status codes.

The longer request loop was stopped after availability degraded to avoid repeatedly sending heavy requests. Bounded recovery probes retained the failures. The earliest 17 successful responses and workbook remain available. **The root cause is unknown from accessible evidence.** Private logs remain BLOCKED under the user's instruction; another Railway credential/log connection request is not needed for this report and will not be made. No local test reproduced the production connection failure, so no speculative software patch or production configuration change was made.

## Remaining client inputs and external dependencies

| Needed input or dependency | Why needed |
|---|---|
| Verified dated aggregate ownership history, with publication dates and market-appropriate categories | Quarterly/yearly ownership-change rules and historical ownership backtesting. Current holder lists and aggregate percentages are insufficient. US category mapping and any unresolved historical thresholds/insider-activity definition require approval. |
| Actual quarter-duration CFO histories and an industry CFO reference dataset | The three currently missing default Fundamental inputs. Cumulative YTD values cannot be presented as quarterly cash flow. |
| Final NPM/CFO scoring definitions and point allocations | Confirm percentage growth vs margin percentage-point change, comparison periods, acceleration semantics and industry median cohort/basis. Existing provisional defaults are not claimed to be client sign-off. Optional price-breadth remains disabled until its definition/input is confirmed. |
| Announcement-time financial vintages, published ownership vintages and historical eligible-universe membership | Fully point-in-time historical qualification and survivorship-aware backtests. Current snapshots must not be reused. |
| Additional eligible India histories and wider compatible financial/sector coverage | India remains below 5,000; statement cohorts are partial. This is provider coverage/background completion, not permission to invent observations or bypass cooldowns. A client source may be needed for unavailable histories. |
| Kotak Neo settings only if client requires that broker's live India quote flow | Public provider status shows Kotak not configured: `KOTAK_NEO_API_KEY`, `KOTAK_NEO_ACCESS_TOKEN`, `KOTAK_NEO_BASE_URL`. Do not send secrets into the report. Yahoo fallback works as a source; a missing Kotak setup is not a reason to fabricate quotes. |
| Native Windows automation/Excel bridge runtime | Actual xlwings refresh/recalculation validation is still required beyond generated-file checks. |

SEC EDGAR and Twelve Data BSE report configured; SEC data was actually returned. **No new SEC/Twelve credential requirement was established.** Configured status alone does not prove entitlement or a successful fresh BSE quote. No paid provider purchase or private Railway access is requested. Production recovery and any settings/deployment change require the user's authorization; no such change was made.

## Evidence and reproducibility

- [Live summary, failures, cohorts and arithmetic checks](final-acceptance-2026-10-16/summary.json); [initial requests](final-acceptance-2026-10-16/final-acceptance.json), [diagnostics](final-acceptance-2026-10-16/final-acceptance-diagnostics.json), [recovery probes](final-acceptance-2026-10-16/final-acceptance-recovery.json), [final risk/backtest/PIT probes](final-acceptance-2026-10-16/final-acceptance-final-probes.json). Large series are compacted with length/hash/first/last; the full returned US ranking is saved separately.
- [Fresh AAPL default-rule arithmetic](final-acceptance-2026-10-16/arithmetic.json), [fresh provider indicators / prices / SEC arithmetic](final-acceptance-2026-10-16/fresh-provider-arithmetic.json), [fresh adjusted-provider Beta checks](final-acceptance-2026-10-16/fresh-beta-independent.json), [adjusted provider observations](final-acceptance-2026-10-16/fresh-adjusted-provider-points.json).
- [Saved US ranking](final-acceptance-2026-10-16/US-ranking-snapshot.json), [downloaded AAPL workbook](final-acceptance-2026-10-16/AAPL-15.xlsx).
- [Local regression summary](final-acceptance-2026-10-16/local-regression.json), [113-check API replay](final-acceptance-2026-10-16/local-api-report.json), [independent indicator replay](final-acceptance-2026-10-16/local-independent-indicators.json), [browser results](final-acceptance-2026-10-16/browser/browser-report.json). Replay uses recorded October 14 real provider histories and isolated databases, with explicitly synthetic missing-input fixtures only for deterministic error tests. It is not a production browser or production trade run.
- [Previous acceptance report](final-acceptance-2026-10-16/prior-acceptance.md) preserves the prior audit and earlier native Excel limitation. Its deployment, counts and availability statements are superseded by this report; dated historical tests remain historical.

Reproduce: `python -m unittest discover -s backend/tests -v` with backend dependencies/PYTHONPATH configured; `node --test frontend/tests/scoring.test.mjs`; `npm.cmd --prefix frontend run build`; `npm.cmd --prefix frontend run lint`; `git diff --check`. This machine uses the existing isolated QA Python dependencies and `-X utf8`. No production database credential is needed for local regression.

**Review decision:** scoped client review can assess implemented workflows, reproducible calculations, immutable exports and the explicit data/definition gaps. A dependable live demonstration and final milestone sign-off must wait for production availability and the BLOCKED/PROVISIONAL acceptance items above. No missing financial or ownership observation has been fabricated into a score.
