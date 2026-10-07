# UI V27 — chart correctness / multi-pane market chart

The Overview stock chart now separates metrics by unit instead of forcing them onto one price axis.

- Main pane: candlesticks, EMA 10/20/34/50/100/150/200 and Bollinger Bands.
- Volume: dedicated synchronized pane.
- Quarterly EPS: dedicated synchronized pane using the actual EPS/share scale.
- RS: dedicated synchronized pane using the raw `Stock Price / Benchmark Price` ratio.
- The previous RS rebasing-to-stock-price behavior was removed because it made the plotted last-value label look like a stock price while the hover value showed a ratio.
- EPS quarter dates are never snapped backward to an earlier candle; each new quarterly value starts on the first chart candle on or after its period date.
- EMA and Bollinger last-value labels are hidden from the right edge to prevent the price scale from becoming a stack of overlapping colored tags. Hover values and the EMA legend remain available above the chart.
- The shared time axis remains DD/MM/YYYY and all panes follow the same crosshair/time range.

No backend ranking, screener, ownership, filter, Excel, or market-data endpoint logic was changed.
