# Final Relative Strength Percentile Method

Relative Strength now follows the client's clarified two-stage method:

1. For each enabled horizon (1W, 2W, 1M, 2M, 3M, 6M, 1Y):
   - Stock Return % = `(latest close / period-start close - 1) * 100`
   - Benchmark Return % = `(latest benchmark / period-start benchmark - 1) * 100`
   - Relative Return % = `Stock Return % - Benchmark Return %`
2. Period relative returns are combined using the client-configurable horizon weights.
3. The weighted relative return is ranked across the stored market universe using:
   - `Percentile = (count lower + 0.5 * count equal) * 100 / total scored stocks`
4. The percentile is used as the 0-100 Relative Strength score.

Calendar-aware lookbacks are used for week/month/year horizons rather than fixed trading-day approximations, reducing date-alignment discrepancies.

The RS line chart remains a rebased stock/benchmark ratio for visualization only and is not the scoring formula.
