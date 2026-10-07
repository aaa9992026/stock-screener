# UI V29 — Ranking workspace render fix (2026-10-07)

The shared premium SVG icons added for the Overview toolbar and score cards were only dimensioned inside the Overview workspace. The Top 200 Ranking workspace renders the same JSX, so browser-default SVG dimensions expanded the market/search/action glyphs and score icons, breaking the full page.

This revision:

- adds hard safety dimensions for shared toolbar and score SVGs;
- restores a compact one-row Ranking command bar on desktop;
- properly positions the market/search icons inside their controls;
- keeps Search, Refresh and Export actions at consistent sizes;
- restores the Daily / Weekly / Monthly segmented control;
- applies the premium score-card structure to Ranking so labels, values and progress bars no longer collapse together;
- keeps Overview V28 geometry and all backend/ranking/data behavior unchanged.
