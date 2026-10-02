STOCK SCREENER — ONE MASTER EXCEL + PYTHON

IMPORTANT
---------
Extract this ZIP/folder first. Do NOT open the workbook directly from inside a ZIP.
If Excel shows Protected View or Read-Only, click Enable Editing.

FIRST-TIME SETUP
----------------
1. Keep all files together in the same folder.
2. Double-click INSTALL_MASTER_EXCEL.bat once.
3. Open StockScreener_Master.xlsx.

DAILY USE — SAME WORKBOOK FOR EVERY STOCK
-----------------------------------------
1. Open the Control sheet.
2. Choose Exchange: US / NSE / BSE.
3. Enter a Symbol: AAPL, INFY, RELIANCE, etc.
4. Save the workbook.
5. Double-click START_MASTER_EXCEL.bat.
6. The SAME workbook updates in place. No separate file is created for each stock.

WHAT UPDATES TOGETHER
---------------------
- Up to 20 years of daily OHLCV for backtesting (provider history permitting)
- SMA 20/50/200 and EMA 20/50/200
- RSI 14
- ATR 14 / ATR %
- ROC 14
- MACD 12/26/9
- Bollinger Bands / Band Width
- +DI / -DI / ADX / DI Spread
- Volume average / Volume Ratio
- 52-week High/Low and distances
- 1W / 1M / 3M / 6M / 1Y returns
- Buy/Sell/Hold signal columns
- Simple indicator strategy backtests
- Fundamental snapshot
- Ownership snapshot
- Dashboard price chart, RSI chart, MACD chart and backtest chart

DATA RULE
---------
Provider/verified data only. Missing values remain blank/N/A; nothing is fabricated.
Signals and backtests are analytical aids, not investment advice.

BACKEND-OUTAGE FALLBACK
-----------------------
The updater first uses the deployed Stock Screener API. If that API is temporarily unreachable,
Python automatically uses the same Yahoo Finance provider for up to 20-year OHLCV + current
fundamental/ownership fields, so the History, Indicators, Backtest and Dashboard sheets can still refresh.
Provider-missing values remain blank/N/A; nothing is fabricated.
