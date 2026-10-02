# Final master Excel + Python workflow — 2026-10-02

This update replaces the earlier blank/static master workbook behavior with one reusable Excel analysis workbook.

## Client workflow

1. Extract the Excel package.
2. Run `INSTALL_MASTER_EXCEL.bat` once.
3. Open `StockScreener_Master.xlsx` and enable editing if Excel asks.
4. In **Control**, choose Exchange and enter a Symbol.
5. Save the workbook and run `START_MASTER_EXCEL.bat`.
6. The same workbook is refreshed in place. No per-stock workbooks are created.

## Refreshes together

- 5-year daily OHLCV target (>=4 years required by client)
- SMA/EMA, RSI, ATR, ROC, MACD, Bollinger, ADX/DMI, volume and 52-week metrics
- Buy/Sell/Hold signal columns
- Long/cash backtests for SMA, ROC, MACD, RSI, Bollinger and combined signal
- Fundamentals and ownership snapshots
- Dashboard summary
- Price/SMA chart
- MACD chart
- RSI chart
- Buy & Hold vs Combined backtest chart

The updater first attempts the deployed `/market/refresh/{symbol}` route and then uses `/market/excel-feed/{symbol}` for long verified history. Provider failures fall back to verified stored data; no values are fabricated.

## Web dashboard sorting

The Top-200 dashboard now exposes both **Sort by** and **Ascending / Descending** controls for composite and component columns.
