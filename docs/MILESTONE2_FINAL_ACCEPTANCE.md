# Milestone 2 acceptance — AAPL production scoring investigation

**Milestone 2 remains provisional and is not fully accepted.** This audit started from clean workspace commit `607ac46`, after the previous fixes were committed. Production exposes scoring version `client-rs5000-v2`; it does not expose its Git SHA. The new corrections below are local, tested and **not deployed**. The approved layout/CSS is unchanged.

Fresh production observations began **2026-10-16 02:51 UTC / October 15 PDT**. Sixteen production requests produced fifteen HTTP 200 responses and one expected HTTP 422. No 502 occurred in this sample. This is an observation window, not a long-running Railway stability certification. Production was not directly connected to for SQL writes, destructively migrated or subjected to forced backfills. Existing GET handlers maintained their normal caches/ranking snapshots; no production portfolios or trades were modified.

## AAPL: why the displayed scores differ

The user-reported live cards reconcile using the default composite weights:

`28.2 × 30% + 85.1 × 25% + 83.5 × 25% = 50.61`, displayed as **50.6 Provisional**.

Ownership and Sector are unavailable in that evaluation. They remain N/A in the component data; the provisional composite retains their weights in the full denominator and earns no contribution from those unavailable categories. It is not renormalized to the 80% of available categories.

Fresh captured inputs evaluated with the checked-in default editable rules produced **Fundamental 27.5, Technical 85.0746269, RS 83.46, Ownership N/A, Sector N/A**, giving **50.38 Provisional**. The earlier 28.2 value is user-reported, not falsely relabeled as reproduced from this later capture. Editable settings and changing statement/peer inputs can change the result; the user's browser-local settings were not accessed.

Three distinct scoring bases existed and remain explicitly distinguished:

| Basis | Fundamental | Technical | RS | Ownership | Sector | Composite |
|---|---:|---:|---:|---:|---:|---:|
| Live editable client-rule evaluation, fresh captured default settings | 27.5 | 85.0746269 | 83.46 | N/A | N/A | 50.38 Provisional |
| Backend baseline dashboard diagnostics | 100 | 100 | 83.46 | 48.9 | N/A | 83.2 Provisional |
| Captured US ranking snapshot | 40 | 100 | 83.46 | 48.9 | 68.39 | 68.62 Provisional |

Backend baseline scores use simple current-field/EMA checks. Ranking fundamental scores use the EPS/PAT/Sales framework, while live editable rules additionally evaluate enabled NPM/CFO inputs. The ranking ownership value is a current institutional/insider aggregate model, not the historical ownership-change model used by the live US rules. These rows are not interchangeable observations of one formula. Ranking selection continues to use its immutable, dated components; returning to live scores selects current editable rules. No current aggregate was substituted for historical ownership merely to fill the N/A card.

## Findings and corrections

**Ownership — historical input dependency plus confirmed refresh faults.** Production returns verified current ownership of **66.326% institutional / 1.648% insider**. The transparent residual is 32.026% public/retail; it is not a reported historical series. Ten institutional and ten mutual-fund holder records do not establish dated aggregate quarterly/yearly ownership. US ownership score remains N/A because the required historical aggregate observations and some thresholds are unavailable. The API now explicitly reports that historical aggregate scoring is blocked, and the existing score-card tooltip explains the reason.

Two persistence/worker defects were fixed: partial fundamental refreshes could erase valid existing fundamental/ownership values with None, and a stock with complete current fundamentals but missing ownership was excluded from the enrichment queue. Refreshes now preserve prior observations when a field is omitted, retain verified zero, and include ownership-only gaps in the bounded queue. An attempt timestamp is recorded even when a valid response contains no new ownership values, preserving cooldown behavior. Retained prior fields are not certified as freshly observed merely because another field refreshed.

**Fundamental — missing CFO inputs and a confirmed SEC date bug.** In the fresh default live evaluation **38 of 41 enabled inputs** were available, representing **400 of 460 rule weight**. Missing inputs were `cfo_q_yoy_growth`, `cfo_q_qoq_growth`, and `cfo_industry_compare`. The merged history contains 12 quarterly and seven annual rows, but only one non-null quarterly CFO observation in this capture. Having 12 rows does not imply 12 usable CFO periods. Missing rules remain unavailable and the observed-rule score remains provisional.

The deployed SEC provider calculated growth by row offset. Its AAPL series omits Q4, so latest PAT YoY was incorrectly reported as **20.21%** using the wrong comparison period. Independently, **(29,789 / 23,434 − 1) × 100 = 27.1187164%**, comparing fiscal ends 2026-06-27 / 2025-06-28. This is fixed locally by fiscal-date matching in the SEC provider and the ranking metric scorer. Missing quarters cannot shift YoY/QoQ or acceleration lookbacks. The captured raw SEC series falls to **85% rule coverage** under the corrected scorer; its old complete-looking coverage was incorrect. The richer merged history yields an EPS/PAT/Sales ranking bundle of **30.0 with 100% coverage of those three groups**, rather than the captured old ranking 40.0. This is a local recomputation of captured data, not a claim that production already displays 30.0 or that all NPM/CFO definitions are accepted.

Detail and ranking enrichment now share the same verified SEC-plus-Yahoo statement policy, with SEC fallback on US provider failure. Fiscal-end matching replaces calendar-quarter bucketing so an official July 1 / normalized June 30 period is not duplicated. Official fiscal-end dates are preserved when matched. The frontend also matches fiscal slots before NPM/CFO comparisons. SEC quarter-duration CFO/capex facts are now exposed when genuinely reported; cumulative YTD cash flow is not relabeled as a quarter, and unavailable current-quarter values remain N/A.

**Sector — confirmed cohort inconsistency.** Production US sector analysis returned Technology **75.51**, based on 80 enriched constituents out of 387 classified Technology listings. AAPL's dashboard sector was N/A with four qualifying fresh peers, while its bounded ranking cohort produced **68.39**. These were three different peer sets. Local code now uses one compatible, fresh, deduplicated stored-market statement cohort for sector analysis, selected-stock detail and Top 200, with the same five-constituent minimum and explicit `sector_cohort_id`. Applying a display filter no longer changes the reference sector percentiles. A shared cohort ID allows comparisons to distinguish arithmetic disagreement from a genuinely updated background cohort. All sector values remain provisional; full eligible constituent coverage is not certified.

**Snapshot compatibility and presentation.** Corrected inputs carry `financial_calculation_version: fiscal-date-v3`; immutable score snapshots identify `client-rs5000-fiscal-v3`. Old enrichment calculations are not reused as corrected calculations. They are retained in storage and refreshed through existing bounded enrichment, without resetting RS/price history or rewriting old score snapshots. The frontend session-cache namespace is also versioned. Scores may temporarily be N/A while compatible statement snapshots warm. Formula tooltips now expose component contributions, missing categories, available rule weight and missing rule names. The technical ROC20 editor now reads the actual `roc_20_period_percent` API field. Client weights/thresholds are unchanged.

## Current acceptance status

| Requirement | Result | Evidence / remaining limit |
|---|---|---|
| Composite arithmetic | PASS | User's displayed 50.6 reconciles to 50.61 using rounded reported inputs; fresh-default 50.38 and ranking 68.62 independently reconcile. Missing component values stay N/A. |
| Current AAPL ownership data | PASS | Verified current institutional/insider percentages and holder tables returned live. |
| Historical ownership scoring | BLOCKED | Dated aggregate history and complete confirmed historical rule definitions are unavailable. Current percentages and holder-share changes are not substituted. |
| Fundamental chronology / ranking source consistency | FAIL | Confirmed deployed SEC row-offset bug and divergent source paths. Corrections and cache-version safeguards pass locally; deployment and bounded re-enrichment are pending. |
| Complete Fundamental acceptance | BLOCKED | Latest-quarter CFO comparisons / industry CFO median remain unavailable in this capture, and unconfirmed NPM/CFO definitions remain provisional. Full EPS/PAT/Sales bundle coverage is not full Fundamental acceptance. |
| Sector score consistency | FAIL | Three deployed peer sets produce different AAPL sector outcomes. Shared cohort / filter-invariance fixes pass locally; production verification awaits deployment and compatible snapshot warmup. |
| Sector endpoint availability | PASS | US sector endpoint returned HTTP 200 with 12 groups; this supersedes the earlier failed request for availability only. It does not certify complete sector coverage. |
| US RS cohort | PASS | **5,426 ready / 5,756 eligible**, evaluation **2026-10-14**; ranking uses 5,000 scored stocks. AAPL detail and ranking both **83.46**. |
| India RS cohort | PROVISIONAL | **4,421 ready / 5,277 deduplicated eligible**, evaluation **2026-10-07**; 856 pending/cooldown listings. NSE 2,192 ready; BSE 2,229 ready. No cooldown was bypassed or valid history reset. |
| Background jobs | PASS | Live RS and fundamental status report running scheduler, registered jobs and next-run times. India completed a recent six-symbol batch but its short histories did not increase readiness; successful downloads are not falsely counted as ready. |
| Top 200 / snapshot integrity | PASS | Live US returned **200 candidates, zero final-qualified rows**. AAPL saved snapshot components exactly match its live downloaded Excel snapshot. RS and weighted composite independently match. This validates storage/transport consistency, not correctness of the old SEC-derived input. |
| Fully qualified Top 200 | BLOCKED | No verified final-qualified 200-stock list. Sector/fundamental/ownership completeness and client definitions remain unresolved. |
| Universe current-field coverage | PROVISIONAL | US fundamental/ownership 2,186 / 5,747 listings (38.0% each); India fundamental 2,152 / 7,745 (27.8%), ownership 2,150 / 7,745 (27.8%). Counts mean any current field, not complete history, and India listing counts include dual listings. |
| SEC connection | PASS | Production SEC credentials work; filings/companyfacts returned. The growth interpretation bug is tracked separately above. No additional SEC credential is needed for this diagnosis. |
| Technical math / weekly Beta | PASS | Retained independent indicator/Beta regressions and new ROC20 wiring fix. Current-code replay checks five stocks × three timeframes against recorded real provider inputs. No new live Beta arithmetic certification is claimed in this focused audit. |
| Paper portfolios / selected-stock backtests | PASS | Existing ledger, stop-order, next-open, idempotency, cash/fee/risk tests and current five-stock API replay pass. This audit did not place production paper trades. |
| Full point-in-time fundamental/ownership/universe backtesting | BLOCKED | Fresh live fundamental-strategy request returns the expected HTTP 422. Announcement-time statement vintages, published ownership history and historical eligible-universe constituents are not configured. |
| Excel snapshot / Master package | PASS | Live AAPL snapshot workbook matches all five saved ranking components and snapshot ID; local five-stock workbook/CSV/ZIP and browser download checks pass. Snapshot identity does not certify faulty old source arithmetic. |
| Native Excel / xlwings execution | BLOCKED | Excel is installed; native refresh/recalculation/bridge execution was not re-certified. Required Windows automation runtime remains unavailable. |
| Railway request sample | PASS | Sixteen sequential checks: fifteen HTTP 200 and the expected PIT-blocking 422; repeated health ready, no 502 in this window. |
| Long-running Railway memory / logs | BLOCKED | No authenticated deployment/log session is available; public HTTP observations cannot certify worker RSS/restart history. |
| Local regression / frontend validation | PASS | **53 backend tests, four Node scoring tests, 113 API replay checks, 184 browser checks / 110 layout cases** pass. Five stocks, mobile 390 / desktop 1440 pixels; no console/layout failures. Build and lint pass; eight existing lint warnings and existing bundle-size warning remain. |
| New production release | BLOCKED | New fixes are uncommitted/unpushed/undeployed. Explicit deployment permission and authenticated Railway runtime access are not present. |

## Evidence and remaining handoff

- [Fresh production responses](scoring-audit-2026-10-15/live-api.json), [counts / SEC correction / snapshot checks](scoring-audit-2026-10-15/summary.json), [independent frontend and ranking arithmetic](scoring-audit-2026-10-15/arithmetic.json).
- [Downloaded immutable production snapshot](scoring-audit-2026-10-15/AAPL-production-ranking-snapshot.xlsx).
- [Current-code API replay](scoring-audit-2026-10-15/local-api-report.json), [independent indicator replay](scoring-audit-2026-10-15/local-independent-indicators.json), [browser results](scoring-audit-2026-10-15/browser/browser-report.json). Replay uses recorded October 14 real provider data; it is separate from the fresh production audit. Fixtures invented for deterministic tests are confined to test files.
- Previous dated [weekly Beta arithmetic](milestone2-validation/beta-independent.json), [additional indicator arithmetic](production-fix-2026-10-15/local-additional-arithmetic.json) and [prior acceptance report](scoring-audit-2026-10-15/prior-acceptance.md) remain historical evidence, not fresh production certifications.

Reproduce regression with `python -m unittest discover -s backend/tests -v`, `node --test frontend/tests/scoring.test.mjs`, `npm.cmd --prefix frontend run build`, `npm.cmd --prefix frontend run lint`, and `git diff --check`. This machine used the existing isolated QA Python environment. New `test_scoring_pipeline.py` covers missing Q4, actual fiscal-end matching, shared statement policy, version compatibility, shared sector cohorts, partial refresh preservation, ownership-only queue gaps, current-vs-historical ownership and quarter-vs-YTD CFO.

Essential remaining data dependencies are verified dated aggregate ownership history, latest-quarter cash-flow coverage and industry CFO medians, PIT financial/ownership/universe vintages, complete sector/India RS coverage, and confirmation of still-unresolved client scoring definitions. No new paid provider, invented contact identity, fabricated market value or guessed client weight was introduced.

Native Windows automation follows the [Computer Use skill](C:/Users/USER/.codex/plugins/cache/openai-bundled/computer-use/26.903.71938/skills/computer-use/SKILL.md): “Use `node_repl` JavaScript for all Computer Use actions.” That runtime is unavailable, so file/HTTP checks do not replace native Excel acceptance.

Release prerequisite: **authorize an authenticated Railway deployment session with runtime-log access**. Deploy the reviewed patch without destructive migrations, retain all RS/price/portfolio history and old immutable score snapshots, let the existing bounded enrichment regenerate fiscal-v3 calculations, then verify matching sector cohort IDs and statement provenance across detail/sector/ranking. Recheck health, worker RSS/logs, AAPL composite contributions, US/India RS, snapshot export, and PIT rejection. No production endpoint inspection is delegated to the user.

Suggested commit message: `Fix fiscal-period scoring and unify sector cohorts while preserving ownership coverage`
