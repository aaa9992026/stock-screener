# Final volatility / Standard Deviation / sorting patch — 2026-10-02

Client-requested framework additions:

- ATR % chart using rolling ATR divided by close.
- ADR % chart using the editable ADR lookback (default 20 sessions).
- ADR Ratio chart = current High-Low range / rolling absolute ADR.
- BB Width is explicitly shown as BB Width %.
- Top-200 Standard Deviation is displayed immediately beside Beta.
- Standard Deviation is annualized standard deviation of daily returns (%) using up to 252 daily returns.
- Top-200 sort controls now show visible Sort by and Order labels with explicit Ascending / Descending choices.
- Standard Deviation is included as a sortable field.

This remains a framework-first revision. Existing data/provider safeguards remain unchanged and missing values continue to display as N/A.
