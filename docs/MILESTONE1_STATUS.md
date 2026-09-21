# Milestone 1 Status (Modules 1-4)

## Added in this package

- Dashboard 0-100 rule-based score with Buy / Watch / Sell signal.
- Sector and industry display with ranking among peers that currently have sufficient stored data.
- Technical screening summary:
  - RS percentile within the currently stored symbol universe
  - EMA 20 / 30 / 50 / 100 / 150 / 200 and alignment status
  - 20-day average volume and current volume ratio
  - ADR (20-day)
  - breakout status
  - VCP contraction heuristic
  - simple price-pattern status
- Fundamental history additions:
  - ROA
  - ROCE
  - free cash flow
  - 5-year CAGR when six valid annual endpoints are supplied by the provider
- Ownership detail:
  - institutional holders
  - mutual-fund holders
  - insider transactions
  - provider limitation message where verified categories are unavailable
- Provider warnings are shown in the UI instead of silently fabricating unavailable benchmark/ownership data.

## Provider-dependent limitations

- The configured Indian benchmark source does not currently return usable NIFTY 500 history, so the application shows an explicit warning rather than a fake line.
- Yahoo does not expose a verified FII/DII/promoter-change breakdown in the same structured form for all Indian symbols. Those values are not estimated.
- 5-year CAGR requires six annual endpoints. When the provider returns fewer, the UI shows `Unavailable`.
- Sector/industry and their rankings become more complete as stock fundamentals/classification data is populated for additional peers.

## Validation performed

- Python source files compile successfully with `py_compile`.
- Frontend JSX structural delimiter/tag checks passed manually.
- A full Vite build could not be executed in the Linux sandbox because the uploaded Windows `node_modules` native Rolldown binding is platform-specific. Install frontend dependencies on the deployment environment (`npm install`/`npm ci`) before building.


## Final transparency patch
- Sector/industry ranks are hidden until at least 5 scored peers are available; small universes are labeled insufficient instead of showing misleading 1/1 ranks.
- RS Rating is hidden until at least 20 symbols have sufficient stored history.
- The benchmark overlay is rebased to the stock's first overlapping price so relative performance is comparable while retaining true candlestick prices.
- Missing 5-year CAGR remains explicitly unavailable when the provider does not supply six valid annual endpoints; no values are estimated.
- Indian FII/DII/promoter-change data remains provider-limited and is labeled accordingly.
