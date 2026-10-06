# Blank page ReferenceError hotfix — 2026-10-06

Observed browser error:

`Uncaught ReferenceError: latestEmaFromChart is not defined`

Cause: `latestEmaFromChart` was declared inside the dashboard scoring IIFE but reused by the separate technical factor evaluation block, where it was out of scope.

Fix: move the helper to the parent React component scope before both consumers. No ranking formula or chart behavior was changed by this hotfix.
