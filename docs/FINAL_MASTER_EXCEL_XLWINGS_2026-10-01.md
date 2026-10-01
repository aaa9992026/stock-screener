# Final Master Excel + Python (xlwings) update — 2026-10-01

Client correction: do not create one Excel file per stock. Use one master workbook for all stocks.

## Final workflow

1. Download `StockScreener_Master_Excel_Python.zip`.
2. Run `INSTALL_MASTER_EXCEL.bat` once.
3. Open `StockScreener_Master.xlsx`.
4. In `Control`, select `US`, `NSE`, or `BSE` and enter any symbol.
5. Run `START_MASTER_EXCEL.bat`.
6. Python/xlwings updates that same workbook in place.

## Data and indicators

The bridge uses `/market/excel-feed/{symbol}` and requests up to five years of daily history, targeting at least four years when the provider can supply it. It calculates SMA/EMA 20/50/200, RSI14, ATR14/ATR%, ROC14, Bollinger bands/width, +DI/-DI/ADX/DI spread, volume average/ratio, 52-week levels, and 1W/1M/3M/6M/1Y returns. Fundamental and ownership snapshots are also written into the master workbook.

No per-stock workbook is created. Missing provider data remains blank/N/A.
