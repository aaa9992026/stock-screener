# Final Fundamental Filter / RS / EMA Polish — 2026-10-02

Client-requested framework corrections implemented in this package:

1. Fundamental filters retain editable compare sign, threshold/value, weight, and enable/disable controls.
2. Rule result column is named **RS Score**.
3. EPS, PAT, Sales, NPM, CFO, ROE, ROCE, cash-flow/share and share-count framework rows remain visible in the client grouping.
4. Overall **Fundamental Score** is displayed below the filter table after the subgroup RS scores.
5. A qualifying-stock table follows the score section. It only marks a row qualified when the current stored score is 100/100 and fundamental rule coverage is complete.
6. The indicator RS line is converted to a bounded 0–100 percentile-style score, with a fixed 0–100 axis, so it cannot cross 100.
7. The price-chart RS overlay remains a separate stock-price / benchmark-price relative line as requested by the chart framework.
8. EMA 10, 20, 34, 50, 100, 150 and 200 have a visible color legend using the same colors as the plotted lines.

Data policy is unchanged: missing provider values remain N/A and are never fabricated.
