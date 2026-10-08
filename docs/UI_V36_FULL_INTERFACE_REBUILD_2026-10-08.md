# UI V36 — Full Interface Rebuild (2026-10-08)

This revision replaces the accumulated multi-version styling layer with one coherent dashboard design system. It is a full frontend presentation rebuild while preserving the existing stock-screening, ranking, filter, chart, backtesting, Excel and provider logic.

## What changed

- Replaced the legacy 10k+ line layered stylesheet with a single clean design system.
- Standardized typography, font weights, line heights, card spacing, page gutters, borders, shadows and control sizes.
- Unified the 1600px content rail across Overview, Top 200 Ranking, Filters, Backtesting, Export / Excel and Settings.
- Rebuilt the sidebar and sticky application header with one restrained blue accent and softer status colors.
- Rebuilt the market/search/refresh/export/timeframe command bar as one consistent component across data workspaces.
- Rebuilt the five score cards with restrained category accents and a clear information hierarchy.
- Rebalanced the Overview selected-company card and stock chart into a clean two-column hero row.
- Kept the corrected multi-pane price / volume / EPS / RS chart behavior while removing unnecessary visual clutter.
- Rebuilt Top 200 detail spacing, indicator controls, indicator cards, composite weights and ranking table presentation.
- Rebuilt Filters as a focused tabbed workspace: only the selected Fundamental, Technical, Ownership or Universe section is visible.
- Normalized table density and added consistent scroll containers and sticky headers for large datasets.
- Rebuilt Backtesting, Export / Excel and Settings using the same card, typography and spacing system.
- Added responsive behavior for 1320px, 1100px, 820px and 560px breakpoints.

## Logic preservation

No ranking formulas, scoring rules, API endpoints, market-data logic, qualification logic, backtesting calculations, Excel behavior or provider rules were changed by this UI rebuild.
