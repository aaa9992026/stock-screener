# UI V24 — Premium selected-company card

The Overview selected-company card has been rebuilt to remove the generic black single-letter mark and the decorative/fake-looking mini sparklines.

Changes:
- New neutral market identity mark with a compact trend glyph, ticker, and live-market status dot.
- Clearer company hierarchy with Selected company eyebrow, company name, live badge, ticker/exchange/industry/ISIN metadata, and a proper SVG watchlist action.
- Price, Market Cap, EPS, Sector and Industry are now individual information tiles rather than a dense table block.
- RSI, MACD, ROC and ADX use compact value cards with real values and simple semantic accents; fake sparkline decoration is removed.
- The card no longer stretches to the full chart height, eliminating the large empty white area beneath its content.
- Responsive behavior is preserved and no market-data/scoring logic was changed.
