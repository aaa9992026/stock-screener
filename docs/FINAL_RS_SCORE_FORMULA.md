# Final Relative Strength Score Formula

Client-confirmed method:

1. Period Relative Return = Stock Return % - Benchmark Return %.
2. For each period, convert relative return to a market percentile:
   (number of stocks with lower relative return + 0.5 * number of stocks with equal relative return) * 100 / total scored stocks.
3. Final RS Score is a customizable weighted average of the period percentiles plus Sector RS Score.
4. Default weights follow the client message:
   - 1W percentile: 20%
   - 1M percentile: 20%
   - 3M percentile: 20%
   - 6M percentile: 10%
   - 12M percentile: 10%
   - Sector RS Score: 20%
5. 2W and 2M remain optional and default to 0 so they can be enabled if the client wants them later.
6. Sector RS Score is calculated from the target sector's average member RS and percentile-ranked against other represented sectors. If sector coverage is unavailable, no sector value is fabricated.

All RS weights remain editable in the frontend.
