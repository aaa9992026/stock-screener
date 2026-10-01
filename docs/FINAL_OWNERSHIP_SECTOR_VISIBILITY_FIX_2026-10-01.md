# Final Ownership + Sector Analysis visibility update — 2026-10-01

This update responds directly to the client review asking where the Ownership filters and Sector Analysis are shown.

## Stock Universe Screener

Dedicated filter tabs are now visible for:

- Popular
- Fundamentals
- Technicals
- Ownership
- Sector Analysis
- Relative Comparison

## Ownership

The Ownership tab exposes the real stored-provider ownership filters at universe level (institutional / insider where available), plus the client-note ownership ranking controls in a dedicated visible panel.

- US headings use Institutional Ownership, Insider Ownership, and Retail / Public Investors.
- Indian ranking rules show the handwritten Promoter / FII / DII-MF / pledge / insider factors.
- Missing provider values remain N/A and are never invented.

## Sector Analysis

A new `GET /market/sector-analysis` endpoint and frontend Sector Analysis panel expose:

- sector stock count
- current median EPS
- current median PAT / net income
- current median Sales / revenue
- the exact client sector-ranking component columns:
  - EPS Growth RS
  - PAT Growth RS
  - Sales Growth RS
  - Growth Acceleration RS
  - Growth Breadth
  - Acceleration Breadth
  - Sector RS

The client formula remains:

`EPS Growth RS 30% + PAT Growth RS 25% + Sales Growth RS 20% + Growth Acceleration RS 15% + Growth Breadth 5% + Acceleration Breadth 5%`

Sector aggregation uses median stock growth per the client note. Historical growth-ranking fields remain N/A until verified peer historical fundamentals exist; current snapshot levels are not substituted for growth and no values are fabricated.

## Verification

- 26 backend Python files: 0 compile errors.
- `App.jsx`: 0 JSX parse errors using TypeScript JSX parser.
- `main.jsx`: 0 JSX parse errors.
