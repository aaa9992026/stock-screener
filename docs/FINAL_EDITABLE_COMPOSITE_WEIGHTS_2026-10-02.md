# Editable Top-200 Composite Weights — 2026-10-02

The client-facing Top 200 Composite Dashboard now exposes editable top-level weights for:

- Technical
- Fundamental
- Ownership
- Sector
- Relative Strength (RS)

Default values remain 30 / 25 / 15 / 20 / 10.

## Behavior

- Values are editable directly on the front dashboard.
- `Apply Weights` persists the current values in browser local storage and reloads the Top 200 ranking using them.
- The backend receives all five weights and normalizes any non-negative entered combination to 100% while preserving relative proportions.
- A zero total is rejected; at least one weight must be greater than zero.
- `Reset 30/25/15/20/10` restores the client default.
- The existing lower Milestone 2 Ranking Weight Settings uses the same shared values; applying there also refreshes the Top 200 ranking.
- Missing score categories remain N/A/Provisional under the existing verified-data rules.
