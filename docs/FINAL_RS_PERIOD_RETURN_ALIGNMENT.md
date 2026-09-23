# Final RS period-return alignment

The client confirmed that each Relative Strength period begins with:

`Relative Return = Stock Return % - Benchmark Return %`

The lookback anchor is a true calendar period (1W, 2W, 1M, 2M, 3M, 6M, 1Y). If that calendar anchor falls on a weekend or market holiday, the calculation now uses the **first available trading session on or after the anchor date** for both the stock and benchmark. Previously the code used the session on or before the anchor, which could lengthen the period and create values such as the disputed AAPL 1M result.

The API now also returns `anchor_date` and `benchmark_start_date` inside each RS period metric to make the calculation auditable.
