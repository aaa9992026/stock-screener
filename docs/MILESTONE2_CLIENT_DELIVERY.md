# Milestone 2 client delivery

**Available for scoped client review; final acceptance remains open.**

Public Vercel and Railway deployment metadata identify commit `d1d631e`. The frontend and expected backend connection are active. US/NSE/BSE search, sampled stock details, Technical/Fundamental provider inputs, Sector Analysis, portfolio listing, technical backtesting, Beta and CSV/XLSX downloads work in the current public checks. No UI redesign, direct database mutation or deployment was performed.

The critical unresolved issue is production Top-200 availability: both markets returned 502 during this sample, with intervening health failures. The actual Railway process failure cause remains BLOCKED with available public diagnostics. Deployment success does not prove this is resolved.

The local patch removes candidate price downloads and statement/Beta crawls from ranking generation, uses dated persisted observations, and replaces repeated RS candle scans with binary lookup. Missing or stale inputs remain N/A; final scores remain provisional where required. No ranking formula or approved frontend was changed. This patch has not been committed, pushed or deployed by this pass.

Validation: **73 backend tests, 8 frontend tests, 113 API replay checks**, independent indicator checks for five stocks across three timeframes, lint and build pass. Local production-sized persisted ranking builds return 200 provisional rows for each market, retain immutable snapshot IDs and complete in 5.34/4.51 seconds with approximately 4 ms cached reads. These are local measurements, not production reliability certification.

Remaining limitations: India RS has 4,423 of the required 5,000 ready histories; complete historical aggregate Ownership, some quarter-duration/industry CFO data, exact client NPM/CFO definitions, complete sector/financial coverage and point-in-time vintages/universe membership remain unavailable. Technical 20-year backtests do not certify historical Fundamental/Ownership simulations. Native Excel automation remains unverified; downloaded workbooks parse correctly. Ranking prices now disclose their stored observation date and may differ from live selected-stock charts. Missing ranking Beta/history stays N/A until verified inputs exist. No fabricated market data or scores were introduced.

The full module-by-module status and timestamped evidence are in [MILESTONE2_FINAL_ACCEPTANCE.md](MILESTONE2_FINAL_ACCEPTANCE.md).

## Prepare the commit locally

Run from the repository root. These commands stage only this stabilization pass and its evidence; they do not push or deploy.

```powershell
git add README.md backend/app/api/market.py backend/app/services/ranking_delivery.py backend/app/services/risk_metrics.py backend/scripts/benchmark_top200.py backend/tests/test_completion.py docs/MILESTONE2_FINAL_ACCEPTANCE.md docs/MILESTONE2_CLIENT_DELIVERY.md docs/final-delivery-2026-10-16
git commit -m "Stabilize Top 200 builds with persisted prices and faster RS lookup"
```

## Deployment instructions - only after explicit approval

1. Review the commit and acceptance limitations. Obtain approval before pushing `main`, because the existing GitHub integrations can automatically deploy both services. No push/deployment has been performed here.
2. After approval, push the reviewed commit to `main` using the existing GitHub/Railway/Vercel deployment pipeline. Retain the current Railway service, PostgreSQL volume/database and all environment settings. No database reset, reseed, cleanup, forced history refresh or destructive migration is required. The additive ranking-response table was already part of the deployed starting release; this pass changes no schema.
3. Check the public deployment status identifies the new commit. The backend patch invalidates old response fingerprints naturally; old source records and immutable snapshots remain intact. Frontend source is unchanged, so no frontend configuration or UI migration is needed.
4. Run the single bounded automatic public smoke command below. It performs GETs only, polls only explicit ranking warmup, stops costly checks if health fails, checks both ranking markets and weighted composites, and records evidence. It exits nonzero for missing rankings, unexpected HTTP errors or composite mismatches. It does not certify external-data completeness; inspect the automated report and refresh the acceptance matrix accordingly. No client-by-client endpoint testing is required.

```powershell
python docs/final-delivery-2026-10-16/verify_public.py
```

5. Do not declare the release accepted unless both rankings become usable and runtime checks remain healthy. If generic 502s persist, stop repeated probes and retain FAIL for reliability / BLOCKED for the unproven private root cause. Any production rollback/settings change requires approval; rollback the application release through the existing pipeline without restoring/deleting the database or discarding financial/portfolio records.

Local verification commands, if needed before the approved release:

```powershell
python -m unittest discover -s backend/tests -v
node --test frontend/tests/scoring.test.mjs frontend/tests/ranking.test.mjs
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run build
python backend/scripts/benchmark_top200.py
git diff --check
```

Backend commands require the existing backend dependencies. The benchmark uses only its isolated `.completion-qa/ranking-502.sqlite` database and recorded dates; it is not a Railway load test.
