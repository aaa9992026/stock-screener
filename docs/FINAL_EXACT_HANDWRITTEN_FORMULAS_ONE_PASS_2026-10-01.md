> **Superseding note:** This document is the final formula map for this package and supersedes earlier simplified “trend rising” fundamental-filter descriptions.

# Final exact handwritten formulas — one-pass revision — 2026-10-01

This revision replaces the simplified "trend rising" rows with the formulas that are actually visible in the client's handwritten pages. Unclear point weights are **not guessed**; they remain editable and default to zero so they cannot silently affect the score.

## EPS composite — 100 visible points

1. Latest quarter EPS growth (YoY) > 20% — 10
2. Latest Q EPS YoY - prior Q EPS YoY > 20% — 10
3. Prior Q EPS YoY - second-prior Q EPS YoY > 20% — 10
4. Latest Q EPS YoY - average(prior Q YoY, second-prior Q YoY) > 20% — 10
5. Latest quarter EPS growth (QoQ) > 20% — 10
6. Prior-quarter EPS growth (QoQ) > 20% — 10
7. Second-prior-quarter EPS growth (QoQ) > 20% — 10
8. Latest Q EPS QoQ - average(prior Q QoQ, second-prior Q QoQ) > 20% — 5
9. Latest annual EPS growth (YoY) > 20% — 10
10. Latest annual EPS YoY - prior annual EPS YoY > 20% — 5
11. Latest annual EPS YoY - average(prior annual YoY, second-prior annual YoY) > 20% — 10

PAT and Sales use the same 11-rule structure exactly as the note says: **"Same for PAT, Sales"**.

## NPM rules visible in the supplied page

1. Latest quarter NPM growth (YoY) > 20% — visible weight 20
2. Latest quarter NPM growth (QoQ) > 20% — visible weight 20
3. Latest annual NPM growth (YoY) > 20% — visible weight 20
4. NPM expansion = (current NPM - 3-year average NPM) / |3-year average NPM| × 100 — formula implemented; point weight not legible, therefore editable and zero by default
5. Industry comparison — above industry median = 20 points; below median = 10 points — implemented using verified stored industry peer margin data
6. Latest Q NPM YoY - prior Q NPM YoY > 20% — formula/threshold implemented; point weight not legible, therefore editable and zero by default

The page heading mentions CFO, but an exact CFO threshold/point allocation is not legible in the supplied page. CFO raw provider values remain available, but CFO scoring is disabled by default rather than guessed.

## Data integrity changes

- Quarterly YoY growth is calculated for **every quarter** with a valid year-ago comparison, not only the latest quarter. This is required for client rules 2–4.
- Missing quarterly/annual history remains N/A.
- Missing values are never estimated or fabricated.
- The selected-stock Final Composite is withheld if any positively weighted category is unavailable; an available partial calculation is labeled Provisional.
- The Top-200 table also marks incomplete composite rows Provisional instead of presenting them as Final.

## Preserved work

- Top-200 composite dashboard and client chart layout.
- Ownership filters and Sector Analysis.
- ISIN identity fixes.
- Master Excel + Python / xlwings workflow with 4+ years of data support.
- Existing technical, RS, SEC, and provider handling.
