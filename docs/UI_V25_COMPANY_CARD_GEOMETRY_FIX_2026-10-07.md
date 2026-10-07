# UI V25 — Company Card Geometry Fix

This patch corrects the V24 selected-company card layout regression.

- Removes inherited flex wrapping that could move the Momentum snapshot cards into a second hidden column.
- Resets inherited fixed/max-height conflicts and keeps the desktop company card aligned with the chart at 430px.
- Forces every company-card section to use the full available width.
- Keeps Price, Market Cap, EPS, Sector and Industry inside a compact two-row stat grid.
- Keeps RSI, MACD, ROC and ADX visible in one four-card row on desktop.
- Prevents clipped or partially visible cards along the right edge.
- Responsive layouts return to natural height below 1280px.
- No market-data, scoring, ranking, filter or backend logic changed.
