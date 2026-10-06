# Ranking System correction — 2026-10-06

Scope: Ranking System review corrections only.

## Corrected

- Live OHLCV merge prevents compact DB history from hiding newer provider sessions.
- Dynamic chart hover values: OHLCV, all requested EMAs, Bollinger bands, EPS, and price/benchmark RS.
- Latest candle restored when the crosshair leaves the chart.
- Wilder/RMA RSI, ATR, +DI/-DI and ADX calculations.
- Bollinger Width standardized to `(Upper-Lower)/Middle*100`.
- Technical compare selectors work for dynamic relationship filters; EMA-34 target is numeric when available.
- Complete-universe fast path for supported EPS/PAT/Sales growth filters, with eligible-equity intersection.
- Automatic polling while complex full-universe histories are still warming.
- Refreshable Excel `.iqy` live-link for the selected symbol.

## Scope boundary

Sector Analysis, Portfolio Management, and the separate 20-year Backtesting milestone part are not marked complete in this correction build.
