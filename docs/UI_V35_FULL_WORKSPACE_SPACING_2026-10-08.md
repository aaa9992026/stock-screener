# UI V35 — Full workspace spacing and margin rhythm

This pass standardizes spacing across Overview, Top 200 Ranking, Filters, Backtesting, Export / Excel, and Settings without changing data, ranking, filtering, chart calculations, or backend behavior.

## Main changes

- One shared 1600px content rail with consistent desktop gutters and top/bottom page spacing.
- Overview, Top 200, and Filters use the same compact top-area vertical rhythm.
- Filters no longer stack excessive padding around headings, tabs, rule tables, actions, and qualified-stock panels.
- Filter rule tables use a controlled viewport height so each section is easier to scan without making the full page unnecessarily long.
- Backtesting cards use the same 12px section rhythm and reduced nested padding.
- Export / Excel action cards no longer rely on a forced minimum height or paragraph spacer height.
- Export workflow/detail cards use tighter, consistent inner spacing.
- Settings cards no longer use artificial 250px/310px minimum heights, removing large blank areas beneath short content.
- Settings controls, API panel, policy list, and session grid use a consistent 8–12px internal rhythm.
- Responsive gutters remain proportional on tablet and mobile.
