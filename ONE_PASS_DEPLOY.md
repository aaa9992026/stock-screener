# One-pass deploy — UI V5 reference match

```bash
git add .
git commit -m "Match stock screener dashboard to clean reference UI"
git push
```

After Vercel deploys, hard-refresh the browser with `Ctrl + Shift + R`.


## UI V9 Top 200 ranking correction
The Top 200 workspace is now table-first: full ranking list and controls first, selected-stock detail/chart second, with ranking settings preserved below.

## UI V12 deploy

```bash
git add .
git commit -m "Fix backtesting workspace and verified-history fallback"
git push
```
