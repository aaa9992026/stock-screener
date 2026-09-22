# Milestone 1 — consolidated client fixes

This build consolidates the client's final Milestone-1 review items into one package.

## Technical / chart
- Candlestick chart with EMA 20/30/50/100/150/200, SMA 20/50, Bollinger Bands, volume + 50-period average, quarterly EPS overlay, and RS benchmark overlay.
- Distinct EMA colors and green/red volume bars.
- Daily chart requests roughly 4 years of trading history so EMA 150/200 can be visible when provider history exists.
- ATR(14) uses Wilder/RMA on the selected timeframe.
- ADR(20D) is the 20-session average absolute `High-Low`, matching the client's TradingView-style ADR display; ADR% remains separately available.
- Relative Strength uses the client formula: 1W 10% + 1M 30% + 2M 20% + 3M 15% + 6M 15% + 1Y 10% versus S&P 500 (US) or NIFTY 500 (India).
- Breakout / near-pivot / VCP / gap / BB-width / ATR% / distance-from-52W-high metrics remain visible.

## Ranking
- US ranking weights remain configurable and normalized automatically.
- NSE/BSE ranking is intentionally withheld as N/A when required fundamental/ownership inputs are missing; editable Indian ranking weights are hidden rather than presenting a misleading score.

## Fundamentals
- US snapshot and historical tables include corrected ROE/ROA/ROCE methodology, cash-flow values, 3Y/5Y CAGR where supported, quarterly/annual trends, and SEC fallback history where available.
- Missing provider data is shown as unavailable rather than estimated.

## Ownership
- US holder tables show report date and reported position change when Yahoo exposes them.
- NSE/BSE now has a dedicated quarterly shareholding-history fallback using Screener.in's public Shareholding Pattern table.
- The Indian table shows Promoter, FII, DII, Mutual Funds when separately exposed, Public, and quarter-over-quarter changes.
- A category not separately exposed by the public source is shown as unavailable; it is never fabricated from another category.

## Reliability
- NaN/Infinity values are sanitized before JSON responses.
- Third-party ownership-provider failures return a clean unavailable state rather than breaking the whole dashboard.
- Weekend-dated legacy bars are filtered from calculations and chart output.
