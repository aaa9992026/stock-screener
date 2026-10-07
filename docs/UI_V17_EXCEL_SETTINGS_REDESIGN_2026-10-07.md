# UI V17 — Excel + Settings Workspace Redesign

This revision replaces the sparse utility pages with functional dashboard workspaces while preserving the existing export and data behavior.

## Export / Excel
- Premium workspace header with current stock context.
- Three functional action cards: current-stock XLSX, refreshable Excel live link, and Master Excel + Python.
- Existing download handlers are reused; no export workflow was removed.
- Added a compact 3-step Master workbook workflow and a current data-link panel.
- Export status / success messages now appear directly in the workspace.

## Settings
- Replaced read-only status boxes with a functional preferences workspace.
- Market selector is wired to the existing exchange state.
- Daily / Weekly / Monthly selector is wired to the existing timeframe state.
- Refresh Market Data reuses the existing refresh handler.
- Reset Defaults restores US + Daily only; it does not delete ranking/filter settings.
- Added backend/API connection card with copy action, current stock/company context, freshness status, and last-updated value.
- Added data-quality policy and session summary cards.

## Design
- Larger readable typography (no 8px utility-page body text).
- Balanced 2-column / 3-card layouts with responsive breakpoints.
- Consistent card radii, spacing, shadows, and status treatments with the rest of the product UI.
