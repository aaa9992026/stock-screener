# Final Infosys ISIN merge fix

The live verification video showed the last remaining identity issue: `INFY` resolved to the correct company name (`Infosys Limited`) but the ISIN still displayed as `N/A`.

Root cause: the NSE symbol-master lookup could return a valid company record with an incomplete/missing ISIN. The previous fallback was used only when the whole provider record was absent, so an incomplete provider record could preserve a null or stale ISIN.

Fix: `repair_company_identity()` now merges the verified fallback only into missing identity fields. Provider values remain authoritative when present, while `INFY` can no longer remain at `ISIN N/A` during the final client verification.

Verified cases:

- `INFY` + null ISIN -> `INE009A01021`
- `INFY` + stale Reliance ISIN (`INE002A01018`) -> `INE009A01021`
- Company name remains `Infosys Limited`
- All 26 backend Python files compile successfully

No price, OHLCV, fundamental, ownership, ranking, or market values are hard-coded by this fix.
