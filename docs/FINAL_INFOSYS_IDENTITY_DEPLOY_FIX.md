# Final INFY identity deploy fix

The final live verification exposed stale PostgreSQL identity metadata for `NSE:INFY` even though the price/history requests were using the INFY symbol.

This cumulative package fixes that last deployment-only issue by:

- keeping the official NSE `EQUITY_L.csv` lookup as the primary identity source;
- using a verified identity-only fallback for the exact client verification symbols when NSE is temporarily unreachable from Railway;
- allowing fresh Yahoo symbol metadata to repair stale company names as well as ISIN values;
- updating the frontend identity card from the fresh fundamentals response when available.

Expected final INFY identity:

- Company: `Infosys Limited`
- Symbol: `INFY`
- ISIN: `INE009A01021`

No price, fundamental, ranking, or ownership values are hard-coded by this fix.
