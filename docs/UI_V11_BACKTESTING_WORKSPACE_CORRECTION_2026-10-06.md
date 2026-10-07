# UI V11 — Backtesting workspace correction — 2026-10-06

The Backtesting navigation item previously opened the old Advanced Analytics content, so the page incorrectly displayed ranking weights and unrelated stock-detail sections.

## Corrected behavior

- Backtesting now opens a dedicated **20-Year Backtesting** workspace.
- Ranking weight settings no longer appear on the Backtesting page.
- The page uses the selected market/symbol from the global search toolbar.
- History target is selectable: 5 / 10 / 15 / 20 years.
- The backend requests verified provider OHLCV directly for the requested history range and does not persist the long series to the small Railway database.
- Missing history is reported as **Partial** instead of being fabricated.
- Backtest strategies match the existing Master Excel methodology:
  - SMA50 long/cash
  - ROC14 long/cash
  - MACD 12/26/9 long/cash
  - RSI14 stateful entry below 30 / exit above 70
  - Bollinger 20/2 stateful entry below lower band / exit above upper band
  - Combined majority vote (3 of 5)
- Results include Strategy Return, Buy & Hold, Value Added, CAGR, Max Drawdown, entries/trades, current signal, and Pass/Fail vs Buy & Hold.
- Equity curve compares Buy & Hold vs Combined.

No synthetic price history is generated.
