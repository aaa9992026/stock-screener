# Final client feedback patch — 2026-10-02

This patch addresses the three review items from the latest client screenshots.

## 1. Correct RS formula

The client formula is restored exactly as previously supplied:

- Stock Return % = `((Current Close / Period Open) - 1) * 100`
- Benchmark Return % = `((Current Benchmark Close / Benchmark Period Open) - 1) * 100`
- Relative Return % = `Stock Return % - Benchmark Return %`
- Relative Return is independent of editable score weights.
- Period Percentile = `((stocks below + 0.5 * stocks equal) * 100) / 5000`
- Final RS Score = `1W*30% + 1M*25% + 3M*20% + 6M*15% + 1Y*10%` using each period percentile.
- 2W, 2M and Sector RS remain optional with default weight 0.

The fixed percentile denominator is 5,000 stocks.

## 2. Current chart data

A stale stored OHLCV cache can no longer stop the chart at an old date merely because it has enough rows. Free-tier bounded reads now take the newest database rows (the prior `ASC + LIMIT` path could accidentally return the oldest rows). If the resulting stored series is older than seven days, the API fetches live provider history and merges it by trading date, with live rows taking precedence. This specifically prevents the Sep-2023 freeze reported by the client and allows 2024/2025/2026 provider data to appear when available.

## 3. Editable composite weights

The client composite defaults are restored to:

- Fundamental 30%
- Technical 25%
- Relative Strength 25%
- Ownership 15%
- Sector 5%

All five frontend fields remain directly editable. The browser storage version is bumped so stale saved values such as the previously displayed 35/20/10/15/20 set cannot override the corrected defaults after deployment.
