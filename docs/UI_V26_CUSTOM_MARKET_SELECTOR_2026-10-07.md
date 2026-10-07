# UI V26 — Custom Market Selector

Date: 2026-10-07

## Problem fixed

The Overview market selector was still the browser-native `<select>` control. When BSE was selected, the long `BSE India (Limited)` label was clipped in the field, while the opened option list used the browser's default styling and did not match the rest of the dashboard.

## Changes

- Replaced the Overview native market dropdown with a custom, accessible market picker.
- Selected labels are concise: **US Market**, **NSE India**, and **BSE India**.
- BSE's limitation note is preserved inside the dropdown as **Limited data coverage** instead of being crammed into the selected label.
- Added clean market-code badges, selected-state checkmark, hover/focus styling, chevron animation, outside-click close, and Escape-key close.
- Increased the market-control desktop width so the selected market never clips.
- Preserved the existing native selector on non-Overview workspaces to avoid changing established workspace behavior.
- Market-switching logic, default symbols, backend requests, and data handling are unchanged.
