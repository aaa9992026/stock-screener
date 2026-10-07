# UI V28 — Overview alignment correction (2026-10-07)

## Problem

After the V27 multi-pane chart correction, the Overview chart card became substantially taller than the selected-company card. Both cards began on the same line but ended on different baselines, making the hero row look broken.

## Fix

- Desktop selected-company card and chart card now share the same 430px height and baseline.
- The chart canvas flexes into the remaining card space instead of forcing a fixed 400px chart height.
- OHLCV, EMA legend, and hovered-value strips are compacted without removing data.
- Lightweight Charts now reads the real canvas height and recalculates pane heights on resize.
- Price remains the dominant pane; Volume, EPS, and RS stay on independent scales in compact synchronized panes.
- Tablet/mobile layouts keep natural stacked heights rather than forcing desktop parity.
- No scoring, ranking, provider, filtering, Excel, or backend behavior changed.
