# Milestone 2 — One-Pass Final Audit (2026-10-01)

This cumulative package uses the client's latest handwritten dashboard and ranking notes as the active reference.

## Exact fundamental mapping
- EPS: 11 handwritten rules, weights total 100.
- PAT: same 11-rule structure as EPS, weights total 100.
- Sales: same 11-rule structure as EPS, weights total 100.
- NPM: all six visible handwritten formulas are represented.
- NPM rules whose point weights are not legible in the supplied note remain editable at weight 0 rather than being guessed.
- CFO scoring is disabled at weight 0 until an exact client scoring rule/point allocation is confirmed; raw provider CFO values remain available.
- Missing provider history remains N/A and is not fabricated.

## Dashboard
- Top 200 composite dashboard follows the latest client weighting: Technical 30%, Fundamental 25%, Ownership 15%, Sector 20%, RS 10%.
- A Final composite score is displayed only when all positively weighted categories are available.
- When data is incomplete, the dashboard may show a clearly marked Provisional score instead of presenting it as final.
- Selected-stock price chart is shown above the ranking list.

## Excel/Python
- One reusable master Excel workbook is connected to Python/xlwings.
- The same workbook can be used for different symbols; separate workbooks per stock are not required.
- The workflow requests up to 5 years of history, supporting indicators that need at least 4 years when the provider supplies that history.

## Package checks
- Backend Python compilation passed.
- Backend source contains 26 Python files.
- Frontend JSX/JavaScript syntax check passed with TypeScript `allowJs` / `jsx preserve` / `noResolve`.
- Exact fundamental configuration contains 45 rows: EPS 11, PAT 11, Sales 11, NPM 6, CFO 2, Other 4.
- No real `.env`, local database, `node_modules`, build, or cache folders are included in the distribution.
