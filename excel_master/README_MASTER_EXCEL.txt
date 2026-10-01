STOCK SCREENER — ONE MASTER EXCEL + PYTHON (XLWINGS)

Purpose
-------
Use ONE workbook for all stocks. No separate Excel file is created per stock.

First-time setup
----------------
1. Keep all files in this folder.
2. Double-click INSTALL_MASTER_EXCEL.bat once.
3. Open StockScreener_Master.xlsx.

Daily use
---------
1. In the Control sheet choose Exchange (US / NSE / BSE).
2. Enter the stock Symbol, e.g. INFY, RELIANCE, AAPL.
3. Save the workbook if Excel asks.
4. Double-click START_MASTER_EXCEL.bat.
5. The same workbook is updated in place and stays open.

What Python updates
-------------------
- Up to 5 years of daily OHLCV (targeting at least 4 years for indicators)
- SMA 20/50/200 and EMA 20/50/200
- RSI 14
- ATR 14 and ATR %
- ROC 14
- Bollinger Bands / Band Width
- +DI / -DI / ADX / DI Spread
- Volume 20-day average and Volume Ratio
- 52-week High/Low and distances
- 1W / 1M / 3M / 6M / 1Y returns
- Fundamental snapshot
- Ownership snapshot

API
---
The default API URL is in Control!B4. If the deployment domain changes, update that cell once.

Data rule
---------
Only returned/provider data is used. Missing values remain blank/N/A; they are not fabricated.
