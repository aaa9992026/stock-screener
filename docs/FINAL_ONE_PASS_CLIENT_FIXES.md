# Final one-pass client fixes

This build consolidates the latest Milestone 1 corrections and hardens the areas repeatedly raised during client review.

## Data correctness / availability
- US fundamental history now merges Yahoo Finance statements with official SEC companyfacts field-by-field.
- SEC financial-statement values take precedence when present; Yahoo fills remaining gaps.
- Quarter-duration facts reported in 10-K filings are retained, improving Q4 coverage.
- Quarterly and annual growth/CAGR values are recomputed after the merge.
- Missing values are never invented.

## ADR / ATR
- ADR(20D) = average absolute daily range (High - Low), matching the requested TradingView-style display.
- ADR %(20D) remains available separately.
- ATR(14) uses Wilder/RMA on the selected timeframe.

## Relative Strength
- Separate RS chart vs S&P 500 / NIFTY 500, rebased to 100 for easy visual comparison.
- RS horizon weights are fully customizable: 1W, 1M, 2M, 3M, 6M, 1Y.
- The same RS weights feed the RS rating and dashboard ranking.

## Ranking customization
- Broad category weights remain customizable.
- The parameters inside Technical, Fundamental, Ownership and Breakout/VCP are now visible and individually weighted.
- A zero subweight disables that parameter.
- Settings persist in browser localStorage.
- Indian ranking remains withheld when required fundamental/ownership inputs are unavailable.

## Ownership
- Indian Shareholding Pattern displays quarterly Promoter, FII, DII, MF and Public values when the public source exposes them.
- Change columns are explicit quarter-over-quarter percentage-point changes.
- Missing ownership categories remain unavailable instead of being estimated.
- US holder tables retain provider report date and provider-reported position change.

## UI stability
- Fixed the India Monthly rendering crash caused by a missing percentage-change formatter.
- Existing chart overlays, long-history EMAs, colored EMA legend and candle-based volume colors are retained.
