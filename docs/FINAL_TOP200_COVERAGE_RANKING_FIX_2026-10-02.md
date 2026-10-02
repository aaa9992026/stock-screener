# Final Top-200 coverage/ranking fix — 2026-10-02

- Provisional composite no longer renormalizes missing categories away.
- Missing Fundamental/Sector remain N/A and earn no weight instead of inflating low-coverage rows.
- A 55% coverage row is capped at 55 provisional points, so incomplete rows cannot dominate the top of the table.
- First 20 leading candidates are enriched synchronously (bounded max 30); remaining candidates warm in smaller background batches and persist in `ranking_snapshots`.
- No provider data is fabricated. Genuine unavailable statement/sector data remains N/A.
