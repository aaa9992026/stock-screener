# Final client live fix — 2026-10-01

This patch addresses the three issues reported from the live deployment: an empty/zero-stock universe, missing ISIN refresh behavior, and repeated stale/empty market-data states.

## Fixes

- Stock Universe Screener now recovers company rows from verified OHLCV/fundamental/ownership data already stored in PostgreSQL if the external company-master sync has not completed yet.
- NSE and US company-master synchronization now run independently; one provider outage cannot leave both markets empty.
- Company-master sync starts within seconds of backend startup, and the frontend retries the universe once after initial deployment startup.
- A newly refreshed ticker is inserted/updated in the Company table immediately so it appears in the universe screener.
- Successful fundamental refreshes create missing Company rows and persist provider name/ISIN/sector/industry metadata.
- Manual market refresh now requests only a small overlap after the latest stored bar instead of downloading history from 2000 on every click, reducing provider throttling/rate-limit failures.
- The chart endpoint performs one real-provider recovery refresh when no stored bars exist, so a clean deployment does not immediately show a stale/empty page.
- Refresh response returns company name and ISIN so the frontend updates identity immediately.
- Filter area is explicitly labeled **Filters**, and a **Ranking Filters ↓** shortcut jumps to the Milestone 2 technical/fundamental/ownership filter tables.
- Existing INFY identity hardening remains intact: Infosys Limited / INE009A01021.

## Verification performed

- Python compile check passed for all backend modules.
- Local database recovery test: stored AAPL OHLCV with an empty company table -> universe automatically repopulated and screener returned AAPL.
- Incremental-refresh test: an existing symbol refresh used a recent overlap date, not `2000-01-01`.
- Identity/ISIN test: AAPL refresh persisted Apple Inc. / US0378331005.
- Empty-chart recovery test: INFY with no prior OHLCV automatically fetched provider data and retained Infosys Limited / INE009A01021 even when the NSE identity endpoint was simulated unavailable.
