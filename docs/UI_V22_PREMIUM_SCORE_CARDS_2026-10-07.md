# UI V22 — Premium Score Cards

Date: 2026-10-07

This pass redesigns the five Overview ranking cards only. Existing data logic and ranking calculations are unchanged.

## Changes
- Replaced character/emoji-style score icons with a consistent custom SVG line-icon system.
- Composite uses a ranking/star glyph.
- Fundamental uses a financial-bars glyph.
- Technical uses a trend-line glyph.
- Relative Strength uses a gauge/needle glyph.
- Ownership uses a people/shareholding glyph.
- Rebuilt card hierarchy: icon + title + short context, large score, then progress.
- Added restrained category accent colors, a thin top accent, subtle tinted background, and softer elevation.
- Improved hover feedback and responsive layout.
- Preserved the original 0–100 values and score progress behavior.

No backend, formula, market-data, chart, filter, Excel, or ranking behavior was changed.
