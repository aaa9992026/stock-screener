# Milestone 2 acceptance - focused Top-200 HTTP 502 repair

**The local repair is implemented and tested, but NOT deployed. Milestone 2 remains PROVISIONAL; production reliability remains FAIL. The actual Railway root cause remains BLOCKED without private runtime evidence.** No OOM, process restart, database failure or timeout mechanism is asserted as the proven cause.

Starting application commit: `fd114426ab84aa1fc2e118ccf261f2aced7d07ec`. This pass only addresses ranking request cost, memory/query bounds, snapshot delivery and safe diagnostics. The approved layout/CSS, ranking formulas, eligible cohorts, missing-data rules and existing financial/price/portfolio history are preserved. No production deployment, settings change, direct SQL write, forced backfill or trade was performed. Existing public GET handlers may maintain normal caches/snapshots.

The complete preceding public frontend/backend acceptance matrix is archived in [prior-acceptance.md](ranking-502-fix-2026-10-16/prior-acceptance.md). Its seven 502s and other live module checks remain dated evidence; this focused pass does not rerun unrelated production workflows or relabel local tests as production success.

## Confirmed implementation problems and repairs

Both requested market routes are the same `GET /market/top-composite` implementation with `market=US` or `market=INDIA`.

Before this patch, each request selected candidates, downloaded candidate price histories, built full persisted RS reference metrics, calculated ranks, loaded financial enrichment, optionally fetched up to 20 statement histories synchronously, built the shared sector cohort, triggered background enrichment/Beta work, serialized every row into an immutable score snapshot, committed those snapshots, and returned a dictionary for FastAPI to serialize again. Concurrent HTTP calls could independently repeat that work.

Confirmed costly paths:

- `_load_persisted_ranking_enrichment` selected **every fresh market snapshot** with `.all()`, then filtered the requested candidates in Python.
- Sector calculations retained every snapshot's complete rule/metadata payload although they only need six growth observations and the sector name.
- RS fallback queried all eligible-market legacy OHLCV and discarded already-covered symbols in Python after database transfer.
- Candidate downloads used 80-symbol frames/four provider threads; statement enrichment used up to eight workers. Statement history cache had no entry bound. Provider downloads and synchronous statement work extended the ranking HTTP lifetime.
- The bounded candidate/response count did not bound the full-universe RS work or deduplicate concurrent ranking requests.

These are locally verified software/resource problems. They are **not proof of the private production failure mechanism**.

The repair introduces a completed-response delivery layer:

1. HTTP reads a matching completed response; it performs no ranking generation or full-universe calculation synchronously. One background ranking worker **per process** builds responses, with at most eight queued requests and eight cached response bodies. Identical concurrent requests share one build. Market, candidate limit, response limit and all entered weights are part of the cache fingerprint.
2. A completed response persists in a new additive `ranking_responses` table: one replaceable slot per canonical market, at most five market slots through the public route. Existing `ScoreSnapshot` records remain immutable and retained. Process-cache loss/restart can load the completed response directly.
3. Responses are fresh for **120 seconds**. A matching completed response up to **900 seconds** old can be served while refreshing, with its original timestamp/row IDs, `X-Ranking-Cache: stale` and `Age`. Older or mismatched responses are withheld. No wrong-weight or indefinitely stale snapshot is silently reused.
4. On a cold/expired cache, the API returns an explicit **503 `RANKING_WARMING`**, with `Retry-After: 5`. The existing frontend waits for this code within its existing 50/45-second request budgets. It does not poll generic 502/database-503 failures as warmup. If generation cannot finish within that budget, the existing unavailable/cached-data message remains. A cold cache is not falsely presented as an immediately available ranking.
5. Candidate enrichment reads now filter exchange/symbol in SQL. RS legacy fallback only requests uncovered eligible keys in 200-key chunks. Sector processing retains only required growth/sector inputs, preserving its full cohort and cohort ID. The full statement memory cache is capped at **512 entries**; evicting memory entries does not delete persisted financial observations.
6. Provider price batches are capped at **20 symbols/two threads**, with a 10-second per-provider timeout. Statement workers are capped at two. Statement enrichment is asynchronous; `TOP200_SYNC_ENRICH_LIMIT` no longer triggers synchronous statement calls. An individual provider timeout is not claimed to be a total build deadline.
7. Each completed response is JSON-encoded once, persisted and served as JSON bytes without FastAPI recursively re-encoding its full dictionary on every read. The existing **20-200 response-row** and **200-1,200 candidate** validation remains; free-tier candidates still cap at 220. Responses over **2 MiB** are rejected rather than silently truncated. Pagination/selection formulas were not changed to return a different ranked population.
8. Dedicated stderr diagnostics log request/cache/build/serialization/stage duration, row and byte counts, exception class, and Linux RSS when available. Query failures, response oversize and `MemoryError` are captured without SQL text, bound parameters, provider URLs, exception messages, environment values or credentials. Failed refreshes preserve the last complete response and back off for 30 seconds. Linux RSS is unavailable on this Windows host; measured local memory below is Python allocation tracing, not RSS.

The supplied uvicorn startup command runs one process by default. Coordination is process-local; this is not a distributed build lock for an independently configured multi-worker/replica deployment. Actual production worker topology and PostgreSQL query plans were not verified through private access.

## Local reproduction and measured evidence

The isolated on-disk SQLite benchmark contains **11,034 synthetic listing identities**, **9,849 compressed histories**, and **11,034 persisted financial enrichment snapshots**. It repeats recorded real AAPL/provider/benchmark inputs solely to exercise realistic cohort sizes and payload shapes. It does not represent 11,034 verified real issuers or invent production financial observations. All provider network I/O is stubbed for this benchmark. Test reference date is **2026-10-13**, not the live US/India evaluation dates.

| Measure | US before | US after | India before | India after |
|---|---:|---:|---:|---:|
| Eligible synthetic listings | 5,756 | 5,756 | 5,278 | 5,278 |
| Ready compact histories | 5,426 | 5,426 | 4,423 | 4,423 |
| Scoring reference population | 5,000 | 5,000 | 4,423 | 4,423 |
| Candidates / returned rows | 220 / 200 | 220 / 200 | 220 / 200 | 220 / 200 |
| Traced builder time, seconds | 24.60 | 26.59 | 20.70 | 21.72 |
| Peak traced Python allocations, MiB | 80.17 | **38.12** | 73.43 | **34.73** |
| Candidate enrichment loading, seconds | 0.511 | **0.052** | 0.520 | **0.049** |
| Database statements | 10 | 11 | 10 | 14 |

Full builder CPU time was **not improved** in this traced run; bounded fallback chunks add statements while preventing covered-history transfers. The benefit is lower memory and isolation from HTTP traffic. Runs were local and subject to concurrent test/host load. The final digest of symbol, exchange, Composite, RS, Fundamental, Technical, Ownership and Sector values matches **exactly before/after for both markets**.

Actual local FastAPI delivery checks on the same persisted population:

| Delivery check | US | India |
|---|---:|---:|
| Initial explicit warmup response | 503 / 66.9 ms | 503 / 15.7 ms |
| Warm HTTP response median | **4.82 ms** | **4.48 ms** |
| Warm HTTP response maximum, ten reads | 7.07 ms | 17.18 ms |
| Health database read while building | 3.70 ms | 4.05 ms |
| Persisted response read after process-cache replacement | 8.42 ms | 5.48 ms |
| Returned rows / compact JSON bytes | 200 / 660,916 | 200 / 661,523 |

Ten cold reads per market did not multiply generation: **one calculation per market**. The resulting background calculations took about **8.06/6.09 seconds** without allocation tracing; this is not a comparison against the traced before timings. Repeated warm reads retained the exact same immutable row IDs. Every returned row's composite matches its stored `ScoreSnapshot`; recreated delivery instances load byte-identical responses from SQLite. These numbers are local results, not Railway latency or a production load test. Provider delays, process RSS and Postgres behavior are excluded from these measurements.

A separate regression verifies that only **one requested candidate out of 300 snapshots** is materialized, already-covered legacy OHLCV is not queried, many custom configurations cannot create unbounded workers/queues, expired/mismatched responses are withheld, failed refreshes preserve completed data, and memory/database exceptions cannot leak the test secret strings.

## Fresh production observations - unpatched release

Only **four** public requests were sent, one per market plus two health checks, to avoid repeatedly loading Railway:

| Time UTC, October 16 | Request | Status | Seconds |
|---|---|---:|---:|
| 12:01:36.534877 | `/health` | 200 | 0.94 |
| 12:01:56.508106 | US Top-200, candidate limit 200 / response limit 20 | 200 | 19.97 |
| 12:02:02.471468 | India Top-200, candidate limit 200 / response limit 20 | 502 | 5.96 |
| 12:02:03.130155 | `/health` | 502 | 0.66 |

Client-local window: **05:01:36-05:02:03 America/Los_Angeles**. The US response contained 20 rows and still took nearly 20 seconds; this does not isolate serialization as the cause. India and subsequent health failed. Error bodies/request IDs are saved. No follow-up load test, deployment or settings change was performed. **The patch cannot be certified against production until an authorized deployment and subsequent checks.** The earlier full 200-row public verification and seven 502s remain archived, not combined into this four-request count.

## Acceptance and validation

| Requirement | Status | Evidence / remaining limit |
|---|---|---|
| Locally reproduce expensive persisted ranking work | PASS | Production-sized on-disk fixture, full RS calculations, persisted enrichment, no production data changes. Reproduced CPU/memory cost; not the actual Railway process failure. |
| Stop synchronous full-universe work in HTTP routes | PASS | Public route serves completed responses or bounded warmup. Both local market routes, cold bursts and health responsiveness tested. |
| Preserve ranking math/cohorts and immutable snapshots | PASS | Identical component digests, fixed 5,000 denominator/tie tests, retained missing values and snapshot identity/database checks. |
| Query/memory/serialization bounds and restart access | PASS | Filtered SQL, uncovered-only fallback, compact sector inputs, bounded queues/caches/payloads, restart/stale/mismatch/error cases tested. |
| Safe diagnostics | PASS | Dedicated logging enabled; database/MemoryError secrecy regressions pass. No production RSS/log trace collected. |
| Approved UI/UX | PASS | CSS/layout unchanged. Only warmup polling and structured-error handling added. Eight frontend tests and 184 replay-browser checks / 110 layouts pass, including one explicit warmup response followed by success. |
| Backend and API regression | PASS | **70 backend tests**, **113 API replay checks**, five stocks x three timeframe independent indicator replay pass. API replay polls the actual new warmup protocol, then validates real-recorded-input calculations/exports/portfolio/backtesting contracts on isolated SQLite. |
| Frontend build / lint | PASS | Build and lint pass; eight existing lint warnings and the existing large-bundle warning remain. |
| Current production ranking reliability | FAIL | Fresh limited sample: US 200 but slow; India 502, health then 502. Local patch is not deployed. |
| Actual production root cause | BLOCKED | Public evidence cannot identify the private runtime failure. No Railway credential/log request and no guessed OOM/restart explanation. |
| Production validation of local repair | BLOCKED | Deployment intentionally not performed; requires user authorization. First cache warmup can produce explicit retryable 503 and must be distinguished from generic runtime 503/502. |
| Full Milestone 2 acceptance | PROVISIONAL | Runtime acceptance remains open. Earlier historical Ownership, quarterly/industry CFO, client NPM/CFO definitions, incomplete India cohort, PIT vintages/universe data and native Excel blockers remain unchanged. |

Regression uses recorded October 14 real provider histories and explicitly isolated synthetic error/performance fixtures. No data in these tests was inserted into the production application. Native Excel and live trading were not exercised in this runtime-focused pass.

## Evidence and reproduction

- [Before persisted benchmark](ranking-502-fix-2026-10-16/local-before.json), [after benchmark and unchanged component digests](ranking-502-fix-2026-10-16/local-after.json), [actual local HTTP load/restart checks](ranking-502-fix-2026-10-16/http-load.json), [recorded benchmark provider inputs](ranking-502-fix-2026-10-16/benchmark-provider-inputs.json).
- [Four fresh public responses](ranking-502-fix-2026-10-16/public-checks.json), [regression summary](ranking-502-fix-2026-10-16/regression.json), [113-check API replay](ranking-502-fix-2026-10-16/local-api-report.json), [independent indicator replay](ranking-502-fix-2026-10-16/local-independent-indicators.json), [browser results](ranking-502-fix-2026-10-16/browser/browser-report.json).
- [Complete preceding acceptance matrix and live deployment evidence](ranking-502-fix-2026-10-16/prior-acceptance.md). Earlier local/live pass claims remain dated; this report supersedes the runtime investigation status only.

Run from repository root with backend dependencies and PYTHONPATH configured: `python -m unittest discover -s backend/tests -v`; `node --test frontend/tests/scoring.test.mjs frontend/tests/ranking.test.mjs`; `npm.cmd --prefix frontend run build`; `npm.cmd --prefix frontend run lint`; `git diff --check`. This workstation uses the existing isolated QA dependency launcher and `-X utf8`.

Portable persisted HTTP reproducer: `python backend/scripts/benchmark_top200.py`. It explicitly selects `.completion-qa/ranking-502.sqlite`, never the production database, and only clears that benchmark's completed-response cache. Recorded fixture dates must remain within the configured readiness windows or be refreshed for a later reproduction. It emits `http-load.json` with the actual measurements.

Patch handoff: the additive cache table is created by the existing startup `Base.metadata.create_all` path on an approved deployment. There are no destructive migrations. Review cold warmup, stale snapshot age and per-process worker coordination before approving deployment. No production setting or credential change is required by this patch, and none was made.

Suggested Git commit message: `Move Top 200 ranking builds off requests and bound memory use`
