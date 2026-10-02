# Final selected-stock sector component fix — 2026-10-02

- Persists provider sector/industry metadata from compact Top-200 enrichment into the Company master.
- Repairs missing selected-stock classification from a fresh ranking snapshot or one bounded live metadata call.
- Reuses compact real EPS/PAT/Sales growth-history snapshots to calculate the selected stock's sector component.
- Requires at least 5 real peer observations before exposing a sector score; otherwise remains N/A rather than fabricating data.
- Recomputes selected dashboard score/coverage after the real sector component becomes available.
- Keeps free-tier OHLCV storage protection unchanged.
