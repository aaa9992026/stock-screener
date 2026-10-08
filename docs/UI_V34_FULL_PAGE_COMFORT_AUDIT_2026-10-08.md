# UI V34 — Full-page comfort audit

This pass standardizes typography, visual weight, and color intensity across all six primary workspaces: Overview, Top 200 Ranking, Filters, Backtesting, Export / Excel, and Settings.

## Changes

- Replaced the brittle Inter/Arial fallback with a Windows-friendly Segoe UI system stack while preserving Inter when available.
- Raised micro-copy that had fallen to 6.5–10px into a more readable 10–12px range where space permits.
- Standardized page titles, section titles, field labels, table headers, table cells, buttons, badges, and helper text.
- Reduced excessive 800/900-weight usage so labels no longer look heavy while secondary text remains readable.
- Softened high-saturation blue/green/orange/violet accents. Strong color is now reserved for primary actions, selected state, and small semantic indicators.
- Standardized neutral text, borders, surfaces, focus rings, status colors, and card shadows.
- Applied the same command-bar typography to Overview, Top 200 Ranking, and Filters.
- Harmonized score cards between Overview and Top 200 Ranking.
- Improved company card, chart helper text, filter previews, ranking tables, Top-200 indicator controls, filter tables, backtesting cards/tables, Excel cards, and Settings cards.
- Added a common Recharts text treatment so technical charts are readable without dominating the page.
- Preserved all existing application logic, data rules, formulas, APIs, and page widths.
