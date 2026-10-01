# Client fundamental filter replacement — 2026-10-01

The Stock Universe Screener **Fundamentals** tab no longer shows the generic Market Cap / EPS Min / Revenue Min / Net Income Min / Profit Margin / ROE / ROA inputs.

It now exposes the client's handwritten Milestone 2 fundamental rule set directly:

- Quarterly EPS YoY growth, EPS rising, EPS YoY trend rising
- Annual EPS YoY growth, annual EPS trend rising
- Quarterly PAT YoY growth, PAT rising, PAT YoY trend rising
- Annual PAT YoY growth, annual PAT trend rising
- Quarterly Sales YoY growth, quarterly Sales trend rising
- Annual Sales YoY growth, annual Sales trend rising
- Quarterly NPM YoY growth and annual NPM rising
- Annual CFO/operating-cash-flow YoY growth
- Cash flow per share (kept editable/disabled where client rule is still ambiguous)
- ROE > configured threshold and ROCE > configured threshold
- Shares outstanding / float rules remain editable and disabled until the exact client rule is confirmed

Thresholds, compare operators, weights and enable/disable switches use the same handwritten-factor configuration as the Milestone 2 ranking engine. Missing provider history remains N/A; the UI does not fabricate values.
