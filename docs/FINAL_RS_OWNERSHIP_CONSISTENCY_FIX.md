# Final RS / Ownership Consistency Fix

This patch closes two consistency issues found during the final Milestone 1 review.

## Relative Strength
- The Technical Summary now returns the verified RS chart series from the same benchmark data used to calculate the RS rating.
- The frontend uses that server-verified RS series instead of independently reconstructing it from a second benchmark request.
- If verified benchmark overlap is insufficient, RS is shown as N/A and is excluded from the displayed ranking score/coverage instead of leaving a stale/default RS score in the ranking.
- The RS benchmark history request was expanded to 5 years so the chart and 1Y weighted period have sufficient overlap where available.

## Ownership Change
- US holder-table `pctChange` is labeled `Provider Change`.
- The UI explicitly states that Yahoo `pctChange` is the provider-reported proportional change in the holder's share position; it is not a quarter-over-quarter ownership-percentage-point change.
- Indian quarterly ownership history keeps `QoQ pp Change`, because those fields are calculated as percentage-point changes between quarters.
