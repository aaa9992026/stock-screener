# Final Ranking Client Feedback Closeout — 2026-10-05

## Scope

This patch closes the latest review items for the **Ranking System** only. Sector Analysis, Portfolio Management, and 20-year Backtesting are not represented as completed by this patch.

## Client issue → implementation

1. **OHLCV did not change while hovering candles**  
   Compact candlestick crosshair handling now looks up the hovered bar and updates Date, Open, High, Low, Close, and Volume.

2. **RS score missing**  
   The indicator header now exposes a current 0–100 RS Score with the existing RS indicator chart retained.

3. **Sort By not available**  
   Sort By and Order controls are rendered directly above the Top-200 table and support the existing ranking fields.

4. **Excel did not follow a newly searched stock**  
   The top Excel action is now a current-stock export. The free-tier Excel feed may fetch live provider OHLCV for the requested symbol when the database has no cached history.

5. **EMA / BB / EPS / RS values missing around price chart**  
   Current-value chips were added for EMA 10/20/34/50/100/150/200, Bollinger Upper/Lower, EPS, and RS Score. Overlay series also expose last-value labels.

6. **Fundamental qualified list limited to Top 200**  
   Added `POST /market/fundamental-qualified` to evaluate active fundamental rules against the complete eligible company universe using persisted real-provider ranking snapshots. Missing histories are warmed in bounded background batches. The response includes `qualified_total`, `evaluated`, `universe_total`, `scan_remaining`, and `complete` so partial provider coverage is explicit.

7. **`Pending` ownership status was unclear**  
   Historical ownership rules with unavailable provider history now say `N/A — provider history unavailable` and are not treated as passing rules.

## Data integrity

- No fundamental or ownership value is fabricated.
- Missing rule data never passes a qualification filter.
- The full-universe scan is not capped to 50 or Top 200 rows; the response limit is up to 10,000 qualifying rows.
- Cold provider histories can require progressive warming, so the UI reports scan completeness instead of claiming a complete result prematurely.
