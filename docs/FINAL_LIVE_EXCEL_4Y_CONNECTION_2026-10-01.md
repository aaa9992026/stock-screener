# Final live Excel connection + 4-year history update

## Client requirement
The client clarified that a static Excel download is not useful. Excel must stay connected to the screener so **Data -> Refresh All** can request current data, and indicator creation needs **at least 4 years of daily history**.

## Implemented
- Added `GET /market/excel-live-csv/{symbol}?exchange=...&limit=1500`.
- Live Excel requests best-effort backfill of **5 calendar years** of real OHLCV data, leaving a safety margin over the 4-year minimum.
- Missing/provider-unavailable history is never fabricated; the API reports whether the 4-year requirement is met and returns verified stored rows.
- Added **Connect Excel Live** in the main search controls and ranking area.
- The button creates an Excel Internet Query (`.iqy`) that points to the live CSV URL.
- Open the `.iqy` once in desktop Excel, allow the connection, then save as a normal workbook. Later **Data -> Refresh All** updates the connected data.
- Existing snapshot export remains available only as an optional static backup.

## Excel data columns
Symbol, Exchange, Company, ISIN, Sector, Industry, Date, Open, High, Low, Close, Volume.

## Data integrity
No synthetic market/fundamental/ownership values are introduced. Provider failures fall back to verified stored data and expose partial history rather than inventing rows.
