# Final handwritten-factor ranking revision

This revision removes the simplified ranking-parameter UI and exposes only the factors shown in the client's handwritten scoring sheets.

## Final ranking categories

- Technical
- Fundamental
- Relative Strength
- Ownership

Breakout/VCP stays available as technical analysis but is not a final-ranking category.

## Technical handwritten factors

- Upper BB - Lower BB (editable BB-width threshold)
- 5-day ATR% average < 20-day ATR% average
- 10-day ATR% average < 20-day ATR% average
- RSI (14) factor shown with editable 30/50/70 cutoffs
- 10-day volume average > 20-day volume average
- 20-day volume average < 40-day volume average
- Distance from 52-week high, using the handwritten 10/17/20% bands
- 20 EMA > 50 EMA
- 50 EMA > 150 EMA

The exact RSI point allocation is not fully legible in the supplied photo, so its ranking weight defaults to 0 rather than inventing a score. The cutoffs stay editable and the factor can be enabled once the client confirms the points.

## Fundamental handwritten factors

Quarterly:
- Latest quarter EPS YoY growth
- Quarterly EPS rising over the latest three quarters
- Quarterly EPS YoY trend rising
- Latest quarter PAT YoY growth
- Quarterly PAT rising over the latest three quarters
- Quarterly PAT YoY trend rising
- Quarterly net-profit-margin YoY growth
- Latest quarter Sales YoY growth
- Quarterly Sales rising over the latest three quarters

Annual:
- Latest year EPS YoY growth
- Annual EPS rising over the latest three years
- Latest year PAT YoY growth
- Annual PAT rising over the latest three years
- Latest year Sales YoY growth
- Annual Sales rising over the latest three years

All visible thresholds and factor weightages are editable and saved in the browser.

## Ownership handwritten factors

- Promoter holding change QoQ
- Promoter holding above an editable level
- Promoter holding rising
- Promoter pledge bands
- FII holding change QoQ
- FII holding rising
- DII/MF holding change QoQ
- DII/MF holding rising
- Yearly holding rising
- Insider activity (repeated buy / repeated sell)

Indian shareholding factors use the public Promoter/FII/DII/MF history when the provider exposes it. Missing pledge/insider/history fields are not estimated.

For US stocks, Yahoo institutional/mutual-fund holder data is not silently relabeled as Promoter/FII/DII data. Therefore the exact handwritten Ownership category can be unavailable, and the visible metric coverage reflects that limitation.

## Relative Strength

Relative Strength remains a separate customizable category with 1W, 2W, 1M, 2M, 3M, 6M and 1Y weights and show/hide controls.
