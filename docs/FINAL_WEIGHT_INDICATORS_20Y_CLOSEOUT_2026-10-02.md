# Final weight / indicators / 20-year backtest closeout — 2026-10-02

- Top 200 visible ranking is recalculated from the current editable composite weights and immediately re-sorted by Composite when Apply Weights is used.
- Missing categories are not renormalized away; they simply do not earn their configured weight.
- Price chart remains visible together with six technical indicator charts: RSI 14, MACD 12/26/9, ROC 14, ADX/+DI/-DI 14, ATR 14, and 20-day Volume Ratio. EMA/SMA/Bollinger remain price overlays.
- Master Excel/Python now requests up to 20 years of real provider daily history for backtesting (listing/provider history permitting), with a 5,500-row target.
- In Railway free-tier mode, long Excel/backtest history is fetched directly by the Python bridge and is not persisted to PostgreSQL, protecting the 500 MB volume.
- Missing provider values remain N/A and are never fabricated.
