# Milestone 2 — Client Handwritten Ranking System

This document records the formulas and filters supplied in the latest handwritten notes. The implementation follows one strict data rule: **provider values are used when available; missing or unclear values remain N/A and are never fabricated.**

## 1. Overall composite score

The latest handwritten formula is:

```text
Composite RS Score =
(Fundamental RS Score × 0.30)
+ (Technical RS Score × 0.25)
+ (RS Score × 0.25)
+ (Ownership Score × 0.15)
+ (Sector RS Score × 0.05)
```

Default weights therefore are:

- Fundamental: 30%
- Technical: 25%
- Relative Strength: 25%
- Ownership: 15%
- Sector: 5%

The frontend keeps these weights editable. A missing component is reported through metric coverage instead of inventing a score.

## 2. Sector ranking system

The sector-ranking note specifies these component weights:

- EPS growth: 30%
- PAT growth: 25%
- Sales growth: 20%
- Growth acceleration: 15%
- Growth breadth: 5%
- Acceleration breadth: 5%

The note also says to use the **median stock growth** for a sector rather than the average.

### Growth breadth

```text
Growth Breadth = (Sales Breadth + PAT Breadth + EPS Breadth) / 3
```

The worked example in the note uses 75, 68 and 72 and produces 71.7.

### Acceleration breadth

```text
Acceleration Breadth =
(EPS acceleration breadth × 0.35)
+ (PAT acceleration breadth × 0.35)
+ (Sales acceleration breadth × 0.30)
```

### Sector composite

```text
Sector RS Score =
(EPS RS Score × 0.30)
+ (PAT RS Score × 0.25)
+ (Sales RS Score × 0.20)
+ (Growth Acceleration RS Score × 0.15)
+ (Growth Breadth × 0.05)
+ (Acceleration Breadth × 0.05)
```

The raw formula is implemented as a configuration contract. The final live sector component should only be enabled when enough real peer fundamental-history data exists to calculate the requested breadth/acceleration metrics.

## 3. Technical ranking filters

The new technical note groups filters into:

- Trend: price/EMA position and EMA slope over short, medium and long term.
- Strength: composite RS, 52-week-high recency, ADX, DI spread, sector RS and RS acceleration/slope.
- Momentum: ROC level/slope and recent ROC acceleration.
- Participation: delivery %, short/medium volume averages and related volume participation.
- Volatility: ATR%, ATR contraction and Bollinger-band width contraction.
- Base formation: 90-period range, ATR/base contraction, volume contraction and VCP-style tightening.

The API now exposes these as `client_technical_filters` from `/market/technical-summary/{symbol}`. The note does not clearly assign a point value to every filter, so unclear point allocations remain editable/unscored until confirmed.

## 4. Fundamental / NPM / CFO / ownership notes

The supplied pages contain multiple EPS/PAT/Sales, NPM/CFO and ownership tests, including quarterly YoY/QoQ growth, growth acceleration, annual growth, promoter/FII/DII/MF history and pledge/insider rules.

Many thresholds are readable and remain represented by the existing editable handwritten-factor configuration. A few handwritten point allocations are not fully legible; those must not be guessed. They remain configurable until the client confirms the exact point values.

## 5. Excel connection

Two endpoints are included:

```text
GET /market/excel-feed/{symbol}?exchange=US
GET /market/excel-export/{symbol}?exchange=US
```

`excel-feed` is designed for Excel Power Query. In Excel use **Data → Get Data → From Web** and enter the endpoint URL. Refreshing the query requests current stored provider data again, so no CSV upload is needed.

`excel-export` downloads an editable `.xlsx` snapshot containing OHLCV, snapshots, the overall composite formula and sector-ranking formula sheets. The client can add more formulas without modifying the web application.

## 6. Kotak Neo

Kotak Neo is treated as an **Indian-stock-only** provider. The project now contains environment placeholders/status reporting for the client credentials, but no credential is hardcoded. Live quote/auth integration should be activated only after the client provides the required Kotak Neo account/API values and it is tested against the current provider flow.
