# UI V5 Reference-Match Dashboard

This build rebuilds the actual React stock-screener dashboard to follow the supplied clean reference structure while preserving the existing ranking, filtering, chart, universe, Excel and analytics logic.

## Overview layout

- Compact left navigation: Overview, Top 200 Ranking, Filters, Backtesting, Export / Excel, Settings.
- Single horizontal market/search/action/timeframe toolbar.
- Five score cards: Composite, Fundamental, Technical, Relative Strength and Ownership.
- Balanced company-information card beside the live candlestick chart.
- Company card includes price, market cap, EPS, sector, industry and RSI/MACD/ROC/ADX snapshots.
- Chart keeps live OHLCV hover, EMA, Bollinger, EPS, RS, volume and overlay controls.
- Fundamental, Technical and Ownership previews use a compact three-column form layout; detailed filters remain in the Filters workspace.
- Compact Top-200 table includes price, change, score categories, market cap, sector and watch column.

## Functional workspaces

- Top 200 Ranking keeps the complete ranking editor and full table.
- Filters keeps detailed Fundamental/Technical/Ownership filters and also exposes the Universe Screener below them.
- Backtesting routes to the existing advanced analytics workspace.
- Export / Excel provides current-stock export, Excel Live Link and the Master Excel + Python package.
- Settings exposes deployment/data status information.

## Top-200 display data

The backend now returns latest close and one-period percentage change for Top-200 rows so the compact overview table can show real Price and Change values instead of placeholders.

Missing provider data still remains N/A; no values are fabricated.
