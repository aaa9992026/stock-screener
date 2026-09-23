# Final RS handwritten reference

Implemented the latest client-provided handwritten RS scoring reference.

- Period relative performance = stock return % - benchmark/index return %.
- Each period is converted to the client percentile: `(lower + 0.5 * equal) * 100 / total`.
- Default final RS score: `1W*0.30 + 1M*0.25 + 3M*0.20 + 6M*0.15 + 12M*0.10`.
- 2W and 2M remain optional customizable periods with default weight 0.
- Sector RS remains informational only and is excluded from the final RS score under this latest reference.
- Existing saved legacy RS weights are migrated to the new defaults when they exactly match the prior default formula.
