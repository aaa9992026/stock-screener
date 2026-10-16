# Milestone 2 final acceptance - public deployment verification

**Overall: PROVISIONAL. The latest frontend is active and connected to the backend. Production Top-200 availability is FAIL, so this release is suitable for a scoped client review but not full Milestone 2 acceptance or a dependable ranking demonstration.** Missing historical financial/ownership data remains explicitly unavailable.

Verified release: `fd114426ab84aa1fc2e118ccf261f2aced7d07ec`. Public GitHub deployment records report successful Vercel Production deployment (11:31:45 UTC) and Railway production deployment (latest success 11:34:43 UTC). These are deployment metadata, not private runtime-log evidence. The public API still exposes scoring version `client-rs5000-fiscal-v3`, without a runtime Git SHA.

- Frontend: https://stock-screener-two-pied.vercel.app/
- Backend: https://stock-screener-production-d90e.up.railway.app
- Backend observation window: **October 16, 2026, 04:33:45-04:39:09 America/Los_Angeles / 11:33:45-11:39:09 UTC**. Live browser capture: 11:35-11:36 UTC.

The user-supplied frontend address is current: HTTP 200, Vercel last-modified 11:31:45 UTC, and its JavaScript/CSS bytes exactly match the locally tested build. Its bundled API address is the expected Railway service. A real headless-browser session reached the public frontend and received real backend responses; this is **not replayed API evidence**.

No application code, styling, database schema, deployment or production setting was changed. No forced backfill, direct SQL write, portfolio action or trade was performed. Public GET handlers may maintain their normal existing caches/snapshots. The browser's automatic Fundamental-refresh POST was intercepted and blocked before transmission by the read-only QA guard; that mutation path was not exercised. No API response was mocked.

## Current acceptance status

| Requirement | Status | Actual evidence and limits |
|---|---|---|
| Frontend deployment active/current | PASS | Public repository homepage matches the supplied URL. Successful deployment record identifies fd11442. HTML/JS/CSS return 200; asset hashes/bytes match the tested build. |
| Live frontend/backend connection | PASS | Browser Overview shows AAPL 54.9 Provisional, Fundamental 27.5 Provisional, Technical 85.1, RS 83.5 and Ownership N/A; price 342.00, ISIN US0378331005. Network responses come from the expected Railway backend. No uncaught JavaScript/console errors recorded. |
| Approved UI preserved | PASS | Application source/CSS unchanged. Six desktop workspaces and mobile Export render without document-width overflow. Screenshots retained. This is a seven-view smoke check, not a repeat of the prior 110-layout regression matrix. |
| Backend health | PASS | Initial and final `/health` return 200 with database ready. Intervening health failures are separately counted below; a ready response does not establish stability. |
| Runtime reliability | FAIL | **46 explicit backend observations: 38 HTTP 200, seven HTTP 502, one HTTP 422 caused by an invalid QA row limit.** No HTTP 503 or transport timeout occurred in this window. 502 bodies say `Application failed to respond` and include request IDs. Health/RS endpoints later recovered. |
| Private runtime root-cause diagnosis | BLOCKED | Public metadata, health/status and request IDs establish failures but not their cause. No OOM/restart/deadlock/provider explanation is asserted. No Railway credentials or private-log connection requested. |
| US RS population | PASS | **5,426 ready / 5,756 eligible**, evaluation 2026-10-14; the 5,000 target remains met. AAPL detail RS 83.46. Fresh ranking RS cannot be compared because ranking requests fail. |
| India RS population | PROVISIONAL | **4,423 ready / 5,278 deduplicated eligible**, 855 pending; evaluation 2026-10-07. Still below 5,000. No valid history reset or cooldown bypass. |
| Background processing | PASS | Persisted checkpoint advancement observed: US 11:32:38.314589 -> 11:35:13.723474 UTC, India 11:32:38.630449 -> 11:35:13.969531 UTC. Latest US batch reports 25 attempted/25 downloaded, ready count unchanged; successful downloads are not falsely counted as newly ready histories. India remains idle/cooldown. Both public schedulers report running/registered. |
| Composite calculation | PASS | Captured initial default-rule points give **54.86**, displayed 54.9; later cohort gives **55.09**. Both retain Ownership N/A and 85% component coverage. Four captured baseline dashboard composites independently reconcile; baseline diagnostics are not the client-rule score. Details below. |
| Fundamental available-input math | PASS | Fresh statement-history/Fundamental endpoints return real inputs; default rule evaluation gives 27.5. Fiscal-date and SEC growth regressions remain supported by the preceding dated audit. No new SEC-source arithmetic certification is inferred merely from endpoint availability. |
| Complete Fundamental score | BLOCKED | **38/41 enabled rules, 400/460 weight**. Missing quarterly CFO YoY, quarterly CFO QoQ and industry CFO comparison. True quarterly CFO/industry data and client confirmation of unresolved NPM/CFO scoring definitions remain needed. |
| Technical score/data | PASS | AAPL technical endpoint returns 200 and default-rule score 85.0746269 (display 85.1), all nine positive-weight rules available. NSE RELIANCE and BSE TCS Technical endpoints also return 200. Prior independent real-provider indicator arithmetic is retained as dated evidence. |
| Current Ownership / historical score | PROVISIONAL | Live current institutional/insider percentages are returned; US historical aggregate scoring remains explicitly BLOCKED. The live frontend correctly displays historical Ownership N/A; current aggregate baseline 48.92 is not substituted into it. |
| Sector Analysis | PROVISIONAL | US and India endpoints return 200. **27 populated sector observations across three responses** independently match weighted arithmetic. Statement coverage and cohort IDs evolve; scores remain provisional. Browser Sector shell rendered, but Refresh was not pressed, so an automatically populated live sector table is not claimed. |
| US and India Top-200 availability | FAIL | Both markets returned 502 on their initial and follow-up requests: four ranking failures total. Current candidate, qualified-stock and ranking-component counts are **unknown**. Prior 200 candidates/zero Final-qualified per market are historical, not a current live count. |
| Existing immutable snapshot retention | PASS | Predeployment AAPL snapshot `d50b24d11e514220ae8af798bb8bdf32` downloads after deployment. Fundamental 30, Technical 100, RS 83.46, Ownership aggregate 48.92, Sector 84.22 and Summary snapshot ID exactly match the original saved row. This proves retention/transport, not a newly generated Top-200 snapshot. |
| Fresh ranking snapshot consistency | BLOCKED | Cannot obtain a new ranking payload because the Top-200 routes fail. Existing immutable-export success does not substitute for this check. |
| Portfolio Management read path | PASS | `/portfolios` returns 200 and the real browser lists the existing portfolio without creating/editing anything. Full create/trade/equity reconciliation remains the preceding isolated-test evidence, not a production write certification. |
| 20-year backtesting | PASS | Live AAPL: **5,046 rows / 20.0548 years**, through 2026-10-15. NSE RELIANCE: **4,948 / 20.0575 years**, BSE TCS: **4,945 / 20.0575 years**, through 2026-10-16. All report verified Yahoo long history and Complete. Live browser shows the AAPL equity curve and history KPIs. |
| Point-in-time historical limitations | BLOCKED | Published statement/ownership vintages and historical eligible-universe membership remain unconfigured. Browser explicitly labels Fundamental/Ownership published history unavailable. No simulation POST was sent in this read-only pass; prior local/live 422 guard evidence remains dated. |
| Live Beta | PASS | AAPL risk endpoint returns Beta **1.064578**, 104 aligned completed-week adjusted returns, as-of 2026-10-12. Prior five-stock fresh-provider covariance checks remain dated independent validation. No current five-stock live Beta claim. |
| US/NSE/BSE company/price data | PASS | AAPL, RELIANCE and TCS dashboard/Technical/CSV/XLSX return 200 with the correct selected-stock identities. BSE TCS export honestly leaves Sector/Industry N/A. This is a three-stock market-path check, not all-universe metadata completeness or exchange-certified live quotes. |
| Live CSV/XLSX / Master package | PASS | Valid `limit=20` CSVs return at least 20 real observations for all three markets. Live XLSX sheets/identities/OHLCV rows validate. Public Master ZIP returns 200, 51,219 bytes, valid archive CRC. Initial CSV `limit=5` correctly returned 422; the corrected request succeeds. This was a harness input error, not an application outage. |
| Native Excel/xlwings execution | BLOCKED | File/HTTP validation does not certify native Excel refresh/recalculation. The prior automation-runtime limitation remains; no native Excel bridge was exercised. |
| Regression evidence | PASS | Application code is unchanged from the tested build. Prior 56 backend tests, five Node scoring tests, 113 API checks and 184 browser checks/110 layouts remain dated validation. They were not rerun or relabeled as new production tests. This pass adds live public HTTP/browser and independent response/export arithmetic checks. |
| Full Milestone 2 sign-off | PROVISIONAL | Working frontend and multiple live backend modules are reviewable; ranking availability, incomplete India RS, historical datasets/definitions and native Excel execution prevent full acceptance. |

## Composite chronology and deployment failures

Initial captured default-rule values: Fundamental **27.5**, Technical **85.07462686567165**, RS **83.46**, Ownership **N/A**, Sector **89.49** (cohort `c2504e228b2f066e467d`):

`27.5*0.30 + 85.07462686567165*0.25 + 83.46*0.25 + 89.49*0.05 = 54.85815671641791` -> **54.86**, display **54.9 Provisional**. The actual deployed browser displayed 54.9 / 27.5 / 85.1 / 83.5 / N/A.

Later successful AAPL detail used Sector **94.10**, cohort `f8d29c6f66febc53cbdf`; applying the same captured default rules gives **55.08865671641791 -> 55.09**, display 55.1. These are different timestamped cohorts, not contradictory evaluations of identical inputs. The browser screenshot is the earlier evaluation, not falsely labeled as the later value. Both calculations have only 85% component coverage, incomplete Fundamental rules and a provisional Sector input.

The earlier user-reported Fundamental 28.2 is not reproduced by the current default rule evaluation. Current aggregate ownership belongs to the simpler backend baseline, not the missing historical card. Changing data/settings or snapshot selection must preserve these source distinctions.

US Top-200 failures took **12.22** and **15.17 seconds**; India failures followed in about **0.68/0.66 seconds**. Three additional 502s affected health/status. Subsequent ready responses do not erase these failures. Request IDs, paths, timestamps and durations are saved in the summary. Public evidence establishes endpoint failure; it does **not establish a root cause**. No speculative repair, deployment or setting change was attempted.

The read-only browser saw 26 successful GET responses and one blocked automatic refresh POST, zero application JavaScript/console errors, and no horizontal overflow in seven captured views. The blocked request is deliberately recorded as `ERR_BLOCKED_BY_CLIENT.Inspector`; it is not attributed to Railway. Write flows and automatic refresh POST behavior remain outside this pass.

## Remaining data, definitions and operational blockers

Full acceptance still requires verified dated aggregate ownership history; actual quarter-duration CFO and industry CFO reference data; approved unresolved NPM/CFO allocations/period/industry comparison definitions; announcement-time financial/ownership vintages and historical eligible-universe constituents; enough eligible India histories and complete compatible sector/financial cohorts; native Excel/xlwings execution; and reliable ranking endpoint operation.

SEC and Twelve Data report configured. Kotak Neo is not configured; its key/token/base URL are needed only if that broker's India live-quote workflow is required. No new SEC/Twelve credential requirement was established, and no private Railway access is requested. The detailed dataset/definition list remains in the [preceding acceptance report](public-deployment-2026-10-16/prior-acceptance.md). Any future production deployment/settings change requires authorization.

## Evidence

- [Deployment discovery](public-deployment-2026-10-16/frontend-discovery.json), [public deployment statuses](public-deployment-2026-10-16/deployment-metadata.json), [frontend HTML/asset hashes](public-deployment-2026-10-16/frontend-http.json).
- [Live backend summary and arithmetic/export checks](public-deployment-2026-10-16/summary.json), [initial responses](public-deployment-2026-10-16/public-deployment.json), [follow-up responses](public-deployment-2026-10-16/public-followup.json), [retained snapshot response](public-deployment-2026-10-16/public-snapshot.json). Large series are compacted with length/hash/first/last.
- [Initial default-rule arithmetic](public-deployment-2026-10-16/arithmetic.json), [later cohort arithmetic](public-deployment-2026-10-16/arithmetic-latest.json), [actual live browser network/DOM evidence](public-deployment-2026-10-16/live-browser.json), [live Overview screenshot](public-deployment-2026-10-16/live-Overview-1440.png), [live mobile Export screenshot](public-deployment-2026-10-16/live-Mobile-Export-390.png).
- [Live US workbook](public-deployment-2026-10-16/AAPL-15.xlsx), [NSE workbook](public-deployment-2026-10-16/followup-RELIANCE-7.xlsx), [BSE workbook](public-deployment-2026-10-16/followup-TCS-12.xlsx), [retained immutable AAPL export](public-deployment-2026-10-16/retained-AAPL-0.xlsx), [public Master ZIP validation](public-deployment-2026-10-16/live-master-package.json).
- [Preceding acceptance report](public-deployment-2026-10-16/prior-acceptance.md), [dated local regression](final-acceptance-2026-10-16/local-regression.json). Prior observations are not current-window successes.

**Decision: ready for scoped client review, not final acceptance.** The public frontend address is active/current; the remaining live blocker is reproducible ranking/service availability, alongside the explicit external-data and native-Excel limitations. UI and production data were preserved.
