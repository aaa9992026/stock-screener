# UI V32 — Filters shared shell and width correction

This revision fixes the Filters workspace presentation only.

- Filters now uses the same 1600px content rail, 28px desktop gutters, and centered main geometry as Overview and Top 200 Ranking.
- The Filters command bar now uses the same custom market selector, search field, Search / Refresh / Export controls, and Daily / Weekly / Monthly segmented control geometry as the upper workspaces.
- Explicit SVG sizing prevents the market/search/action icons from expanding into oversized black shapes.
- Filter workspace cards, active filter table, and Universe Screener now fill the same content width instead of being constrained to the older 1480px workspace width.
- Existing filter logic, qualification rules, market data, ranking formulas, and backend behavior are unchanged.
