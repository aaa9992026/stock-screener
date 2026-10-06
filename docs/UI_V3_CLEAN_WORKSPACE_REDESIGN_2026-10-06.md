# UI V3 Clean Workspace Redesign — 2026-10-06

This revision changes the real React stock-screener project (not a mockup image) to a clean multi-workspace interface while preserving the existing ranking, filter, chart, screener, Excel and advanced-analysis functionality.

## Structure

- **Overview** — compact score cards, selected-stock card, candlestick chart, four quick indicator snapshots, three filter previews, and a compact Top-200 table.
- **Top 200 Ranking** — full ranking workflow with indicator controls, editable composite weights, complete ranking table and ranking detail controls.
- **Filters** — full Fundamental, Technical and Ownership filter editors, including qualified-stock lists and editable scoring inputs.
- **Universe Screener** — the complete many-stock screener, sector analysis, configurable columns, pagination and Excel export.
- **Advanced Analytics** — all existing detailed/legacy analytical sections preserved in a dedicated workspace instead of extending the Overview page indefinitely.

## UI changes

- Fixed left navigation with an active workspace state rather than jump links.
- Cleaner toolbar, score-card row, stock/chart split and consistent card alignment.
- Overview filter cards use a concise preview; full filter functions are available in the Filters workspace.
- Excel export remains directly available from the top toolbar. The Excel Live Link remains available in Advanced Analytics.
- Responsive layouts are included for desktop, tablet and mobile widths.

## Functional preservation

The redesign does not remove backend routes or calculation logic. Existing chart overlays, OHLCV hover values, indicator calculations, editable filter thresholds/weights, qualified-stock scanning, Top-200 sorting, stock-universe screener, sector analysis, Excel tools and detailed analytics remain in the project.
