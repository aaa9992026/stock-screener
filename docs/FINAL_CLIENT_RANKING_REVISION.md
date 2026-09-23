# Final Client Ranking Revision

This revision applies the client's last Milestone 1 ranking requests without expanding provider scope.

## Final ranking categories

The final ranking now uses only:

- Technical
- Fundamental
- Relative Strength
- Ownership

Breakout / VCP remains visible in the technical-analysis section, but it is no longer a separate final-ranking category.

## Customization

- Broad category weights remain editable and are normalized automatically.
- Technical, fundamental, and ownership parameter weights remain editable.
- A weight of 0 disables that ranking input.
- Settings are stored in the browser.

## Relative Strength

Relative Strength now supports:

- 1 week
- 2 weeks
- 1 month
- 2 months
- 3 months
- 6 months
- 1 year

The newly added 2-week weight defaults to 0 so the previously approved formula does not change unless the client chooses a value.

Each RS horizon has an independent Show/Hide control for its visible result card. The horizon weight remains separately customizable; use weight 0 to exclude a horizon from scoring.

## Indian-market data rule

No unavailable Indian fundamental or ownership data is estimated. When required data is unavailable, the final Indian ranking remains withheld instead of producing a misleading partial score.
