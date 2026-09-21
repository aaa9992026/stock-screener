# Final Milestone 1 combined correction

This patch combines the client's latest requests with the data-integrity fix identified during final verification.

## Annual SEC history integrity
- Annual SEC facts are accepted only from true 10-K fiscal-year (`fp=FY`) records.
- Quarterly/YTD facts can no longer be mistaken for separate annual years.
- 3-year and 5-year CAGR are recalculated from true annual endpoints.
- ROE, ROA and ROCE use the documented period-end formulas already shown in the UI.

## Pivot, VCP and breakout
- VCP still requires successive contraction in both price depth and ATR%.
- When VCP is detected, the **final contraction high** is the pivot.
- Otherwise, the recent consolidation high is used as a fallback pivot.
- Near Pivot: close is between 95% and 102% of pivot.
- Confirmed breakout: close > pivot by 0.3%, close > open, close in upper half of range, and volume >= 1.4x the 50-period average.
- Breakout Strength remains a transparent 0-100 multi-condition score.

## Chart controls
The user can independently show/hide:
- EMA 20/30/50/100/150/200
- SMA 20/50
- Bollinger Bands
- Volume + 50-period average volume
- Quarterly EPS
- Relative Strength vs broad-market benchmark

## Custom ranking weights
The dashboard includes editable weights for:
- Technical
- Fundamental
- Relative Strength
- Ownership
- Breakout / VCP

The weights do not need to total 100; the backend normalizes them. The chosen values are saved in the browser with localStorage. This lets the client decide the weighting without code changes.


## Trading-date integrity
- Daily OHLCV sync now rejects Saturday/Sunday rows for US, NSE, and BSE stocks.
- Refresh also removes any previously stored weekend bars for the refreshed symbol.
