# Milestone 1 – Final Client Changes

Implemented from the client's final handwritten notes/screenshots:

- Main chart: OHLC readout, EMA 20/30/50/100/150/200 overlays, Bollinger Bands, volume, 50-period average volume, quarterly EPS points/line, and US/India relative-strength line.
- Relative strength line: stock price divided by S&P 500 (`^GSPC`) for US stocks or NIFTY 500 (`^CRSLDX`) for Indian stocks. The line is visually rebased only to share the stock-price pane; its direction is driven by the stock/index ratio.
- RS rating: uses relative returns for 1/2/3/4 weeks and 2/3/6/12 months. Each horizon is centered at 50 for benchmark-equivalent performance and averaged into a transparent 0–100 score.
- Breakout: pivot = highest high of the prior 20 sessions (~4 weeks). Confirmed breakout requires close above pivot by 0.3%, volume at least 1.5x the 20-day average, close above open, and close in the upper half of the day's range.
- Breakout diagnostics: breakout-strength score, gap %, 52-week-high distance, pivot, ATR(14), ATR%, Bollinger Band width, and 20-day range.
- VCP: requires successive 20-session price-depth contractions and ATR% contractions. This is a transparent heuristic based on the client's contraction formulas.
- Fundamental history UI: up to 8 quarterly rows, up to 5 annual rows, plus quarterly Sales/EPS/PAT trend charts.
- ROE / ROA / ROCE: calculated from financial statements using average balance-sheet denominators:
  - ROE = Net income / average stockholders' equity
  - ROA = Net income / average total assets
  - ROCE = EBIT / average (total assets - current liabilities)
- Fundamental refresh now refreshes live provider data before falling back to a stored snapshot, reducing stale/null fundamental cards.
- Historical market refresh begins from 2000 where the provider has data, allowing long-period EMA calculations on weekly/monthly charts when the stock has enough history.

## Provider-dependent limitations

- Yahoo frequently exposes only about 5 quarterly financial columns. The UI is ready for 8 quarters, but it never fabricates missing quarters.
- Five-year CAGR requires six valid annual endpoints. It remains unavailable when the provider does not expose enough usable annual history.
- Indian FII/DII/promoter/public historical shareholding percentages are not available from the currently configured providers. The application does not hard-code the illustrative values from the client's handwritten example.
- Macrotrends can be used as a manual validation/reference source for US fundamentals, but this build does not rely on fragile website scraping as a production API.


## Fundamental-history accuracy update
- US history now keeps Yahoo Finance as the primary source and falls back to the official SEC Company Facts API when Yahoo exposes too few statement periods.
- This fallback is intended to supply up to 8 quarterly periods and 6 annual endpoints (5-year CAGR requires six endpoints).
- ROE is calculated as net income / period-end stockholders' equity.
- ROA is calculated as net income / period-end total assets.
- ROCE is calculated as EBIT (operating income fallback) / (period-end total assets - period-end current liabilities).
- The UI reports how many requested quarterly/yearly periods are actually available and identifies the source used.
- Set `SEC_USER_AGENT` in production to a descriptive app name and contact email for SEC API etiquette.
