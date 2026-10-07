# UI V21 — Overview Geometry Fix (2026-10-07)

This revision fixes the visual regression visible in V20 where the selected-company card was shifted downward and appeared to overlap the filter cards.

## Root cause
An older rule defined `.dashboard-selected-stock { position: sticky; top: 86px; }`. Later Overview revisions changed the card to `position: relative` but did not reset `top`, so the old 86px offset became active again.

## Fixes
- Explicitly resets the Overview company card to `top: auto`.
- Aligns company summary and stock chart to the same top edge.
- Reduces the oversized 500px hero to a compact 430px desktop row.
- Removes the large blank gap inside the company card.
- Places RSI, MACD, ROC and ADX in one contained four-column row on desktop.
- Prevents indicator cards from peeking outside the company card.
- Keeps filter cards completely below the hero row.
- Makes the chart dominant while keeping OHLCV, EMA and hover-value information readable.
- Preserves all existing scoring, filters, ranking, chart, Excel and backtesting functionality.
