from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests

WORKBOOK_NAME = "StockScreener_Master.xlsx"


def _safe_number(value: Any):
    try:
        if value is None or value == "":
            return None
        number = float(value)
        if np.isfinite(number):
            return number
    except Exception:
        pass
    return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate technical indicators locally in Python from verified OHLCV rows."""
    df = df.copy().sort_values("Date").reset_index(drop=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # Moving averages
    for n in (20, 50, 200):
        df[f"SMA{n}"] = close.rolling(n, min_periods=n).mean()
        df[f"EMA{n}"] = close.ewm(span=n, adjust=False, min_periods=n).mean()

    # RSI 14 (Wilder-style exponential smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))

    # True range / ATR
    prev_close = close.shift(1)
    tr = pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["ATR14"] = atr
    df["ATR %"] = (atr / close.replace(0, np.nan)) * 100

    # ROC
    df["ROC14 %"] = close.pct_change(14) * 100

    # Bollinger Bands 20, 2 stdev
    bb_mid = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std(ddof=0)
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std
    df["BB Mid"] = bb_mid
    df["BB Upper"] = bb_upper
    df["BB Lower"] = bb_lower
    df["BB Width %"] = ((bb_upper - bb_lower) / bb_mid.replace(0, np.nan)) * 100

    # DMI / ADX 14
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = pd.Series(np.where((up_move > down_move) & (up_move > 0), up_move, 0.0), index=df.index)
    minus_dm = pd.Series(np.where((down_move > up_move) & (down_move > 0), down_move, 0.0), index=df.index)
    tr_smoothed = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / tr_smoothed.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean() / tr_smoothed.replace(0, np.nan)
    dx = ((plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)) * 100
    adx = dx.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["+DI14"] = plus_di
    df["-DI14"] = minus_di
    df["ADX14"] = adx
    df["DI Spread"] = plus_di - minus_di

    # Volume / 52-week context
    vol_avg20 = volume.rolling(20, min_periods=20).mean()
    df["Volume Avg20"] = vol_avg20
    df["Volume Ratio"] = volume / vol_avg20.replace(0, np.nan)
    high_52w = high.rolling(252, min_periods=20).max()
    low_52w = low.rolling(252, min_periods=20).min()
    df["52W High"] = high_52w
    df["52W Low"] = low_52w
    df["Dist 52W High %"] = ((close / high_52w.replace(0, np.nan)) - 1) * 100
    df["Dist 52W Low %"] = ((close / low_52w.replace(0, np.nan)) - 1) * 100

    # Standard trading-day return windows
    for label, periods in [("1W", 5), ("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252)]:
        df[f"Return {label} %"] = close.pct_change(periods) * 100

    return df


def _indicator_status(name: str, value: Any) -> tuple[str, str]:
    n = _safe_number(value)
    if n is None:
        return "N/A", "Insufficient history"
    if name == "RSI14":
        return ("High" if n >= 70 else "Low" if n <= 30 else "Normal"), ""
    if name == "ADX14":
        return ("Strong trend" if n >= 25 else "Weak trend"), ""
    if name == "DI Spread":
        return ("Positive" if n > 0 else "Negative" if n < 0 else "Neutral"), ""
    if name == "Volume Ratio":
        return ("Above avg" if n >= 1 else "Below avg"), ""
    return "Ready", ""


def _set_status(book, text: str, ok: bool = True):
    try:
        sheet = book.sheets["Control"]
        sheet.range("A12").value = text
        sheet.range("B9").value = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.range("A12:H14").color = (240, 253, 244) if ok else (254, 242, 242)
        sheet.range("A12:H14").font.color = (22, 101, 52) if ok else (185, 28, 28)
    except Exception:
        pass


def update_workbook(workbook_path: str | Path | None = None, visible: bool = True):
    try:
        import xlwings as xw
    except ImportError as exc:
        raise RuntimeError("xlwings is not installed. Run INSTALL_MASTER_EXCEL.bat once.") from exc

    workbook_path = Path(workbook_path or Path(__file__).resolve().parent / WORKBOOK_NAME).resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(f"Workbook not found: {workbook_path}")

    app = None
    book = None
    created_app = False
    try:
        # Reuse the workbook if the client already has the master file open.
        # Otherwise open it in a new visible Excel instance.
        for candidate_app in list(xw.apps):
            for candidate_book in list(candidate_app.books):
                try:
                    if Path(candidate_book.fullname).resolve() == workbook_path:
                        app = candidate_app
                        book = candidate_book
                        break
                except Exception:
                    continue
            if book is not None:
                break

        if book is None:
            app = xw.App(visible=visible, add_book=False)
            created_app = True
            book = app.books.open(str(workbook_path))

        app.visible = visible
        app.display_alerts = False
        app.screen_updating = False
        control = book.sheets["Control"]
        api_base = str(control.range("B4").value or "").strip().rstrip("/")
        exchange = str(control.range("B5").value or "NSE").strip().upper()
        symbol = str(control.range("B6").value or "").strip().upper()
        limit = int(_safe_number(control.range("B8").value) or 1500)
        limit = max(1000, min(limit, 5000))

        if not api_base:
            raise ValueError("Control!B4 API Base URL is empty.")
        if exchange not in {"US", "NSE", "BSE"}:
            raise ValueError("Control!B5 Exchange must be US, NSE or BSE.")
        if not symbol:
            raise ValueError("Control!B6 Symbol is empty.")

        _set_status(book, f"Updating {exchange}:{symbol} …", True)
        app.screen_updating = True

        url = f"{api_base}/market/excel-feed/{symbol}"
        response = requests.get(url, params={"exchange": exchange, "limit": limit}, timeout=180)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("ohlcv") or []
        if not rows:
            raise RuntimeError(f"No verified OHLCV rows returned for {exchange}:{symbol}.")

        raw = pd.DataFrame(rows).rename(columns={
            "date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
        })
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
        raw = raw.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
        calc = calculate_indicators(raw)

        output_cols = [
            "Date","Open","High","Low","Close","Volume",
            "SMA20","SMA50","SMA200","EMA20","EMA50","EMA200","RSI14",
            "ATR14","ATR %","ROC14 %","BB Mid","BB Upper","BB Lower","BB Width %",
            "+DI14","-DI14","ADX14","DI Spread","Volume Avg20","Volume Ratio",
            "52W High","52W Low","Dist 52W High %","Dist 52W Low %",
            "Return 1W %","Return 1M %","Return 3M %","Return 6M %","Return 1Y %",
        ]
        calc = calc[output_cols]

        hist_sheet = book.sheets["History"]
        hist_sheet.range("A2:AI5000").clear_contents()
        hist_sheet.range("A2").options(index=False, header=False).value = calc.where(pd.notna(calc), None).values.tolist()
        hist_sheet.range(f"A2:A{len(calc)+1}").number_format = "yyyy-mm-dd"
        hist_sheet.range(f"B2:E{len(calc)+1}").number_format = "0.00"
        hist_sheet.range(f"F2:F{len(calc)+1}").number_format = "#,##0"
        hist_sheet.range(f"G2:AI{len(calc)+1}").number_format = "0.00"

        latest = calc.iloc[-1]
        indicator_map = [
            ("SMA20", "SMA20"), ("SMA50", "SMA50"), ("SMA200", "SMA200"),
            ("EMA20", "EMA20"), ("EMA50", "EMA50"), ("EMA200", "EMA200"),
            ("RSI14", "RSI14"), ("ATR14", "ATR14"), ("ATR %", "ATR %"),
            ("ROC14", "ROC14 %"), ("BB Width", "BB Width %"),
            ("+DI14", "+DI14"), ("-DI14", "-DI14"), ("ADX14", "ADX14"), ("DI Spread", "DI Spread"),
            ("Volume Ratio", "Volume Ratio"), ("52W High", "52W High"), ("52W Low", "52W Low"),
            ("Distance From 52W High", "Dist 52W High %"), ("Distance From 52W Low", "Dist 52W Low %"),
            ("Return 1W", "Return 1W %"), ("Return 1M", "Return 1M %"),
            ("Return 3M", "Return 3M %"), ("Return 6M", "Return 6M %"), ("Return 1Y", "Return 1Y %"),
        ]
        ind_sheet = book.sheets["Indicators"]
        indicator_rows = []
        for display, col in indicator_map:
            value = _safe_number(latest.get(col))
            status, note = _indicator_status(display if display != "ROC14" else "ROC14", value)
            indicator_rows.append([value, status, note])
        ind_sheet.range("B4:B28").value = [[row[0]] for row in indicator_rows]
        ind_sheet.range("E4:E28").value = [[row[1]] for row in indicator_rows]
        ind_sheet.range("F4:F28").value = [[row[2]] for row in indicator_rows]
        ind_sheet.range("B4:B28").number_format = "0.00"

        fundamental = payload.get("fundamental_snapshot") or {}
        fund_values = [
            fundamental.get("market_cap"), fundamental.get("trailing_eps"), fundamental.get("forward_eps"),
            fundamental.get("revenue"), fundamental.get("net_income"), fundamental.get("profit_margin"),
            fundamental.get("return_on_equity"),
        ]
        book.sheets["Fundamentals"].range("B4:B10").value = [[v] for v in fund_values]

        ownership = payload.get("ownership_snapshot") or {}
        own_values = [
            ownership.get("insider_percent"), ownership.get("institution_percent"),
            ownership.get("shares_outstanding"), ownership.get("float_shares"),
        ]
        book.sheets["Ownership"].range("B4:B7").value = [[v] for v in own_values]

        company = payload.get("company") or {}
        history = payload.get("history") or {}
        status_message = (
            f"Updated {exchange}:{symbol} — {company.get('name') or symbol} | "
            f"{len(calc)} daily rows | {calc['Date'].min().date()} to {calc['Date'].max().date()} | "
            f"4-year history {'OK' if history.get('requirement_met') else 'PARTIAL'}"
        )
        _set_status(book, status_message, bool(history.get("requirement_met")))
        book.save()
        app.screen_updating = True
        return status_message
    except Exception as exc:
        if book is not None:
            _set_status(book, f"Update failed: {exc}", False)
            try:
                book.save()
            except Exception:
                pass
        raise
    finally:
        if app is not None:
            try:
                app.screen_updating = True
                app.display_alerts = True
            except Exception:
                pass
        # Keep the workbook/Excel open after a successful update. If a new app
        # was created but opening the workbook failed, close only that empty app.
        if created_app and book is None and app is not None:
            try:
                app.quit()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Update the single StockScreener master Excel workbook in place.")
    parser.add_argument("--workbook", default=None, help="Optional path to StockScreener_Master.xlsx")
    parser.add_argument("--hidden", action="store_true", help="Run Excel hidden (mainly for automation/tests).")
    args = parser.parse_args()
    message = update_workbook(args.workbook, visible=not args.hidden)
    print(message)


if __name__ == "__main__":
    main()
