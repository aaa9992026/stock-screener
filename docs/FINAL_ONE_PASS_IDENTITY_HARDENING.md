# Final one-pass identity hardening

This cumulative package includes the previously audited Milestone 2 code plus the final INFY identity correction and stale-UI protection observed during live verification.

## Exact issue fixed

When the user changed from one ticker to another, the frontend could temporarily or indefinitely retain the previous ticker's company name/ISIN if an auxiliary identity request failed or returned incomplete identity fields. Separately, an old database row could pair `INFY` with Reliance metadata.

## Final behavior

- NSE exact-ticker searches repair identity from the official NSE symbol master, with a verified identity-only fallback for the final client test symbols if NSE is temporarily unreachable.
- `INFY` is repaired to `Infosys Limited` / `INE009A01021`.
- The dashboard repairs NSE identity before reading the company row.
- Fundamental refresh/read paths repair NSE identity as well.
- The frontend never carries a previous ticker's company name or ISIN into a newly selected symbol.
- If an identity request is unavailable, the UI shows the current ticker with `ISIN N/A` instead of displaying another company's identity.

## Local verification performed

- 26 backend Python files compile successfully.
- A stale database row (`INFY` + Reliance name/ISIN) was repaired to `Infosys Limited` / `INE009A01021` using the final repair path.
- Cross-symbol frontend identity fallbacks using the previous company's name/ISIN were removed.

Use this package cumulatively. Do not apply older patches afterward.
