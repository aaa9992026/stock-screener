# Final screener empty-table fix — 2026-10-01

## Exact live symptom
The live page could show a valid eligible-stock count and coverage percentages, then immediately show:
`The stock-universe screener could not be loaded.` and an empty table.

## Root cause
The frontend loaded `/api/market/screener` successfully on mount and then unconditionally called the same endpoint again five seconds later. If that second request hit a brief Railway/startup/background-sync failure, the error handler erased the already-valid table rows while leaving the successful count/coverage metadata on screen. This produced the contradictory live state seen in the client screenshot (8,349 eligible stocks + coverage, but empty rows/error).

## Fix
- Removed the unconditional five-second second request.
- The initial screener request now retries the same request once after 900 ms only if it actually fails.
- A transient failed request no longer clears previously valid screener rows.
- Added a request sequence guard so an older request cannot overwrite a newer filter/page request.
- Added a 30-second per-request timeout so a hung network request cannot leave the UI permanently loading.

No ranking formulas, provider values, ISIN logic, market-data calculations, or existing Milestone 2 filters were changed by this patch.
