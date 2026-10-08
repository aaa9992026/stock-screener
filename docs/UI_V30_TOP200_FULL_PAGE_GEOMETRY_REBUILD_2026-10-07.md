# UI V30 — Top 200 full-page geometry rebuild (2026-10-07)

This pass fixes the severe Top 200 Ranking layout regression visible in the V29 screenshots.

- The selected-company card no longer stretches to the full height of the indicator stack.
- Company card and stock chart share only the first row.
- The customizable indicator basket spans the full width underneath.
- The company card uses a compact vertical layout with bounded ticker mark, metadata, watchlist and stock-stat cards.
- The advanced indicator editor uses a responsive multi-column layout instead of one tall narrow column.
- The indicator charts use three columns on wide desktop, two on medium screens and one on small screens.
- Composite weights are restored to a compact five-card row instead of full-width stacked rows.
- Weight actions and explanatory note are compact and aligned.
- Existing ranking, chart, indicator, filter, Excel and backend logic is unchanged.
