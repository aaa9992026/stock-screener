# Final Top 200 data-coverage closeout — 2026-10-02

- Keeps Railway free-tier OHLCV persistence disabled so the 500 MB volume does not refill.
- Live-enriches a bounded Top-200 candidate set with real provider metadata and historical statements.
- Calculates the client's confirmed 11 handwritten growth rules separately for EPS, PAT and Sales.
- Missing historical rule inputs are skipped rather than treated as zero; each group carries real-rule coverage metadata.
- Fundamental display score is a provisional coverage-weighted combination of confirmed EPS/PAT/Sales rules only. Ambiguous NPM/CFO point allocations are not invented.
- Sector score uses the documented 30/25/20/15/5/5 structure on real bounded-peer historical growth, acceleration and breadth data and remains explicitly provisional until the full universe is available.
- Alpha/Beta use real daily returns versus S&P 500 (US) or NIFTY 500 (India), with no large database writes.
- Provider metadata fills missing sector/industry/fundamental/ownership fields only when the stored value is absent.
- Final composite remains Provisional on free-tier bounded data; missing provider values still remain N/A.
