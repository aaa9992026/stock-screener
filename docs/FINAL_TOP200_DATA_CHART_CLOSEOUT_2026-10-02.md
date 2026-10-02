# Final Top-200 Data + Chart Closeout — 2026-10-02

This cumulative patch addresses the latest client screenshots without expanding the scoring rules beyond the confirmed notes.

## Top-200 live refresh
- Replaced the large synchronous cold enrichment path with a small synchronous batch plus background batches.
- Added `ranking_snapshots`, a compact persisted cache of provider metadata and derived ranking scores only. It does **not** store OHLCV history.
- Persisted enrichment survives Railway restarts and avoids repeating the same statement fetches on every request.
- Fundamental/EPS/PAT/Sales continue to use the confirmed 11-rule handwritten growth logic and real provider history only.
- Sector uses real enriched sector metadata and bounded real-history peer calculations; it remains explicitly provisional on free tier.
- Alpha/Beta use exact S&P 500 / NIFTY 500 benchmark series, with a fast live path and the existing exact-benchmark fallbacks.
- Missing provider values remain `N/A`; nothing is fabricated.

## Client dashboard layout
- Ascending / Descending remains clearly visible beside Sort By.
- Price chart now visibly includes EMA/SMA/Bollinger overlays in the dashboard card.
- An RSI-14 indicator chart is displayed directly below the price chart so price + indicator charts are visible together, matching the client's note.

## Railway 500 MB safety
- Multi-million-row universe OHLCV backfills remain disabled in `FREE_TIER_MODE`.
- The new ranking snapshot table is tiny compared with OHLCV and is intended to remain well within the existing 500 MB volume.
