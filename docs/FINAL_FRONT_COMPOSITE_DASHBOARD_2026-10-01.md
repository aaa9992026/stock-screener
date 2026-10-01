# Final front composite dashboard update — 2026-10-01

Implemented from the client’s latest handwritten dashboard sketch.

- Front page now contains a **Top 200 Stocks — Composite Final Score** dashboard before the detailed screener.
- Latest client composite layout: **Technical 30% + Fundamental 25% + Ownership 15% + Sector 20% + RS 10%**.
- Clicking a ranked stock switches the active stock and opens its price/indicator context above the ranking list.
- Ranking columns include Composite, Technical, Fundamental, Ownership, Sector, RS, EPS, PAT, Sales, Alpha, Beta and coverage.
- Missing historical factor values remain `N/A`; they are not fabricated.
- The backend `/market/top-composite` endpoint batches stored price history and returns up to 200 rows from a broad high-coverage candidate pool.
- Dashboard RS is explicitly marked provisional until the full required market-universe history is populated.
- Existing detailed filters, Ownership, Sector Analysis and live Excel / 4-year history support are preserved.
