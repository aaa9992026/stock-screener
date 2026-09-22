# Final client data corrections

This patch addresses the latest review points:

- ADR (20D) is calculated from daily sessions as the 20-session average of `(High-Low)/Low * 100`, even when the selected chart timeframe is weekly or monthly.
- ATR(14) uses Wilder/RMA smoothing on the selected timeframe, matching the standard TradingView ATR convention more closely.
- Relative Strength uses the requested weights: 1W 10%, 1M 30%, 2M 20%, 3M 15%, 6M 15%, 1Y 10%, relative to S&P 500 for US stocks and NIFTY 500 for Indian stocks.
- The dashboard ranking now uses the same weighted RS calculation as the Technical Screening Summary.
- Charts request about four years of daily data, five years of weekly data, and enough monthly data for long EMAs when history is available.
- Indian-stock ranking is withheld as `N/A` when fundamental or ownership categories have positive weights but the configured provider has no such data. Missing data is not silently re-normalized into a full score.
- Ownership holder tables show the provider's latest report date and reported percentage change when Yahoo exposes those fields.
- A complete FII/DII/MF/Promoter/Public historical ownership series still requires a provider that exposes that historical breakdown; values are not fabricated.
