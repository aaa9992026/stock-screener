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
        return number if np.isfinite(number) else None
    except Exception:
        return None


def _growth(current, previous):
    if current is None or previous in (None, 0):
        return None
    return ((float(current) - float(previous)) / abs(float(previous))) * 100.0


def _stateful_position(buy_condition: pd.Series, sell_condition: pd.Series) -> pd.Series:
    """Long/cash position: enter on buy, exit on sell, otherwise keep prior state."""
    state = 0.0
    out = []
    for buy, sell in zip(buy_condition.fillna(False), sell_condition.fillna(False)):
        if bool(buy):
            state = 1.0
        elif bool(sell):
            state = 0.0
        out.append(state)
    return pd.Series(out, index=buy_condition.index, dtype=float)


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate chart indicators, signals and a simple long/cash backtest locally."""
    df = df.copy().sort_values("Date").reset_index(drop=True)
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    for n in (20, 50, 200):
        df[f"SMA{n}"] = close.rolling(n, min_periods=n).mean()
        df[f"EMA{n}"] = close.ewm(span=n, adjust=False, min_periods=n).mean()

    # RSI 14 (Wilder-style smoothing)
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    avg_loss = loss.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df["RSI14"] = 100 - (100 / (1 + rs))

    # True range / ATR
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    df["ATR14"] = atr
    df["ATR %"] = (atr / close.replace(0, np.nan)) * 100

    # ROC
    df["ROC14 %"] = close.pct_change(14) * 100

    # MACD 12/26/9
    ema12 = close.ewm(span=12, adjust=False, min_periods=26).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    df["MACD"] = ema12 - ema26
    df["MACD Signal"] = df["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    df["MACD Hist"] = df["MACD"] - df["MACD Signal"]

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
    df["+DI14"] = plus_di
    df["-DI14"] = minus_di
    df["ADX14"] = dx.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
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

    for label, periods in [("1W", 5), ("1M", 21), ("3M", 63), ("6M", 126), ("1Y", 252)]:
        df[f"Return {label} %"] = close.pct_change(periods) * 100

    # Signals matching the reference Excel workflow.
    df["SMA Signal"] = np.where(close > df["SMA50"], "Buy", "Sell")
    df["ROC Signal"] = np.where(df["ROC14 %"] > 0, "Buy", "Sell")
    df["MACD Signal State"] = np.where(df["MACD"] > df["MACD Signal"], "Buy", "Sell")
    df["RSI Signal"] = np.where(df["RSI14"] < 30, "Buy", np.where(df["RSI14"] > 70, "Sell", "Hold"))
    df["BOLL Signal"] = np.where(close < df["BB Lower"], "Buy", np.where(close > df["BB Upper"], "Sell", "Hold"))

    # Long/cash positions for simple strategy comparison.
    sma_pos = (close > df["SMA50"]).astype(float)
    roc_pos = (df["ROC14 %"] > 0).astype(float)
    macd_pos = (df["MACD"] > df["MACD Signal"]).astype(float)
    rsi_pos = _stateful_position(df["RSI14"] < 30, df["RSI14"] > 70)
    boll_pos = _stateful_position(close < df["BB Lower"], close > df["BB Upper"])
    vote_count = sma_pos + roc_pos + macd_pos + rsi_pos + boll_pos
    combined_pos = (vote_count >= 3).astype(float)
    df["Combined Signal"] = np.where(combined_pos > 0, "Buy", "Sell")
    df["Position"] = combined_pos

    daily_ret = close.pct_change().fillna(0.0)
    df["Daily Return %"] = daily_ret * 100
    strategy_ret = combined_pos.shift(1).fillna(0.0) * daily_ret
    df["Strategy Return %"] = strategy_ret * 100
    df["Buy&Hold Cum %"] = ((1 + daily_ret).cumprod() - 1) * 100
    df["Strategy Cum %"] = ((1 + strategy_ret).cumprod() - 1) * 100

    # Keep positions for per-indicator backtests in attrs, avoiding extra workbook columns.
    df.attrs["positions"] = {
        "SMA": sma_pos, "ROC": roc_pos, "MACD": macd_pos, "RSI": rsi_pos,
        "BOLL": boll_pos, "Combined": combined_pos,
    }
    return df


def build_backtest(calc: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    daily_ret = calc["Close"].pct_change().fillna(0.0)
    positions = calc.attrs.get("positions") or {}
    out = pd.DataFrame({"Date": calc["Date"]})
    out["Buy & Hold"] = (1 + daily_ret).cumprod() - 1
    summary = {}
    buy_hold_total = float(out["Buy & Hold"].iloc[-1]) if len(out) else 0.0

    last_signal_lookup = {
        "SMA": calc["SMA Signal"].iloc[-1],
        "ROC": calc["ROC Signal"].iloc[-1],
        "MACD": calc["MACD Signal State"].iloc[-1],
        "RSI": calc["RSI Signal"].iloc[-1],
        "BOLL": calc["BOLL Signal"].iloc[-1],
        "Combined": calc["Combined Signal"].iloc[-1],
    }

    for name in ["SMA", "ROC", "MACD", "RSI", "BOLL", "Combined"]:
        pos = positions.get(name, pd.Series(0.0, index=calc.index))
        strat_ret = pos.shift(1).fillna(0.0) * daily_ret
        cum = (1 + strat_ret).cumprod() - 1
        out[name] = cum
        total = float(cum.iloc[-1]) if len(cum) else 0.0
        summary[name] = {
            "last_signal": str(last_signal_lookup.get(name, "N/A")),
            "strategy_return": total,
            "buy_hold": buy_hold_total,
            "value_added": total - buy_hold_total,
            "status": "Pass" if total >= buy_hold_total else "Fail",
        }
    return out, summary


def _set_status(book, text: str, ok: bool = True):
    try:
        sheet = book.sheets["Control"]
        sheet.range("A12").value = text
        sheet.range("B9").value = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
        sheet.range("A12:H14").color = (240, 253, 244) if ok else (254, 242, 242)
        sheet.range("A12:H14").font.color = (22, 101, 52) if ok else (185, 28, 28)
    except Exception:
        pass


def _write_matrix(sheet, start_cell: str, matrix):
    if matrix is None or len(matrix) == 0:
        return
    sheet.range(start_cell).value = matrix




def _direct_yahoo_payload(symbol: str, exchange: str, limit: int):
    """Fallback used only when the deployed API is unreachable.

    It keeps the client's one-workbook workflow usable by reading the same
    Yahoo Finance source directly from Python. No synthetic values are added.
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("Backend API is unavailable and yfinance fallback is not installed. Run INSTALL_MASTER_EXCEL.bat once.") from exc

    exchange = str(exchange or "US").upper()
    symbol = str(symbol or "").upper()
    provider_symbol = symbol
    if exchange == "NSE":
        provider_symbol = f"{symbol}.NS"
    elif exchange == "BSE":
        provider_symbol = f"{symbol}.BO"
    elif exchange == "US":
        provider_symbol = symbol.replace(".", "-").replace("/", "-")

    ticker = yf.Ticker(provider_symbol)
    hist = ticker.history(period="5y", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        raise RuntimeError(f"Yahoo Finance returned no daily history for {exchange}:{symbol}.")

    rows = []
    for dt, row in hist.tail(limit).iterrows():
        def num(name):
            value = row.get(name)
            try:
                value = float(value)
                return value if np.isfinite(value) else None
            except Exception:
                return None
        close = num("Close")
        if close is None or close <= 0:
            continue
        rows.append({
            "date": pd.Timestamp(dt).date().isoformat(),
            "open": num("Open"), "high": num("High"), "low": num("Low"),
            "close": close, "volume": num("Volume"),
        })

    try:
        info = ticker.info or {}
    except Exception:
        info = {}
    isin = info.get("isin")
    if not isin:
        try:
            raw_isin = getattr(ticker, "isin", None)
            if callable(raw_isin):
                raw_isin = raw_isin()
            if raw_isin and str(raw_isin).strip() not in {"-", "None", "nan"}:
                isin = str(raw_isin).strip()
        except Exception:
            isin = None

    earliest = rows[0]["date"] if rows else None
    latest = rows[-1]["date"] if rows else None
    requirement_met = False
    if earliest:
        try:
            requirement_met = pd.Timestamp(earliest).date() <= (pd.Timestamp.now().date() - pd.Timedelta(days=366 * 4))
        except Exception:
            requirement_met = False

    return {
        "symbol": symbol,
        "exchange": exchange,
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "history": {
            "earliest_date": earliest,
            "latest_date": latest,
            "stored_rows": len(rows),
            "required_years": 4,
            "requested_years": 5,
            "requirement_met": bool(requirement_met),
            "backfill_attempted": True,
            "warning": "Loaded directly from Yahoo Finance because the deployed API was unavailable.",
        },
        "company": {
            "name": info.get("longName") or info.get("shortName") or symbol,
            "isin": isin,
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        },
        "fundamental_snapshot": {
            "market_cap": info.get("marketCap"),
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
        },
        "ownership_snapshot": {
            "insider_percent": info.get("heldPercentInsiders"),
            "institution_percent": info.get("heldPercentInstitutions"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
        },
        "ohlcv": rows,
    }


def _reset_chart_series(chart, book, title: str, series_defs, y_min=None, y_max=None, percent_axis=False):
    """Rebind an existing Dashboard chart to exact Date/value series.

    This prevents Excel from reinterpreting every date/row as a separate series
    after a data refresh and forces missing SMA warm-up values to plot as gaps.
    """
    try:
        api = chart.api[1]
        api.HasTitle = True
        api.ChartTitle.Text = title
        api.DisplayBlanksAs = 1  # xlNotPlotted: gaps, never artificial zero-lines
        collection = api.SeriesCollection()
        while collection.Count:
            collection.Item(1).Delete()
        for name, sheet_name, category_range, value_range in series_defs:
            series = collection.NewSeries()
            series.Name = name
            series.XValues = book.sheets[sheet_name].range(category_range).api
            series.Values = book.sheets[sheet_name].range(value_range).api
        api.HasLegend = True
        try:
            api.Legend.Position = -4107  # bottom
        except Exception:
            pass
        try:
            axis = api.Axes(2)
            if y_min is not None:
                axis.MinimumScaleIsAuto = False
                axis.MinimumScale = float(y_min)
            else:
                axis.MinimumScaleIsAuto = True
            if y_max is not None:
                axis.MaximumScaleIsAuto = False
                axis.MaximumScale = float(y_max)
            else:
                axis.MaximumScaleIsAuto = True
            if percent_axis:
                axis.TickLabels.NumberFormat = "0%"
        except Exception:
            pass
    except Exception:
        # Chart repair is presentation-only; never fail the data refresh for it.
        pass


def _refresh_dashboard_charts(book, row_count: int):
    try:
        ds = book.sheets["Dashboard"]
        charts = list(ds.charts)
        if len(charts) < 4 or row_count < 2:
            return
        last = row_count + 1
        date_rng = f"A2:A{last}"
        _reset_chart_series(charts[0], book, "Price + SMA50 + SMA200", [
            ("Close", "History", date_rng, f"E2:E{last}"),
            ("SMA50", "History", date_rng, f"H2:H{last}"),
            ("SMA200", "History", date_rng, f"I2:I{last}"),
        ])
        _reset_chart_series(charts[1], book, "MACD", [
            ("MACD", "History", date_rng, f"Q2:Q{last}"),
            ("Signal", "History", date_rng, f"R2:R{last}"),
        ])
        _reset_chart_series(charts[2], book, "RSI 14", [
            ("RSI14", "History", date_rng, f"M2:M{last}"),
        ], y_min=0, y_max=100)
        _reset_chart_series(charts[3], book, "Backtest: Buy & Hold vs Combined", [
            ("Buy & Hold", "Backtest", date_rng, f"B2:B{last}"),
            ("Combined", "Backtest", date_rng, f"H2:H{last}"),
        ], percent_axis=True)
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
        # Reuse the exact workbook if it is already open.
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
            book = app.books.open(str(workbook_path), update_links=False, read_only=False)

        app.visible = visible
        app.display_alerts = False
        app.screen_updating = False
        control = book.sheets["Control"]
        api_base = str(control.range("B4").value or "").strip().rstrip("/")
        exchange = str(control.range("B5").value or "US").strip().upper()
        symbol = str(control.range("B6").value or "").strip().upper()
        limit = int(_safe_number(control.range("B8").value) or 1500)
        limit = max(1000, min(limit, 5000))

        if not api_base:
            raise ValueError("Control!B4 API Base URL is empty.")
        if exchange not in {"US", "NSE", "BSE"}:
            raise ValueError("Control!B5 Exchange must be US, NSE or BSE.")
        if not symbol:
            raise ValueError("Control!B6 Symbol is empty.")

        _set_status(book, f"Refreshing latest provider data for {exchange}:{symbol} …", True)
        app.screen_updating = True

        # Best-effort latest-data refresh first. The Excel feed then backfills long history.
        refresh_warning = None
        try:
            rr = requests.post(f"{api_base}/market/refresh/{symbol}", params={"exchange": exchange}, timeout=180)
            if rr.status_code >= 400:
                refresh_warning = f"Latest refresh returned HTTP {rr.status_code}; continuing with verified stored data."
        except Exception as exc:
            refresh_warning = f"Latest refresh unavailable ({exc}); continuing with verified stored data."

        api_warning = None
        try:
            response = requests.get(
                f"{api_base}/market/excel-feed/{symbol}",
                params={"exchange": exchange, "limit": limit},
                timeout=90,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            api_warning = f"Deployed API unavailable ({exc}); Excel used direct Yahoo Finance fallback."
            payload = _direct_yahoo_payload(symbol, exchange, limit)
        rows = payload.get("ohlcv") or []
        if not rows:
            raise RuntimeError(f"No verified OHLCV rows returned for {exchange}:{symbol}.")

        raw = pd.DataFrame(rows).rename(columns={
            "date": "Date", "open": "Open", "high": "High", "low": "Low", "close": "Close", "volume": "Volume"
        })
        raw["Date"] = pd.to_datetime(raw["Date"], errors="coerce")
        raw = raw.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
        if len(raw) > limit:
            raw = raw.tail(limit).reset_index(drop=True)
        calc = calculate_indicators(raw)
        backtest, test_summary = build_backtest(calc)

        output_cols = [
            "Date","Open","High","Low","Close","Volume",
            "SMA20","SMA50","SMA200","EMA20","EMA50","EMA200","RSI14",
            "ATR14","ATR %","ROC14 %","MACD","MACD Signal","MACD Hist",
            "BB Mid","BB Upper","BB Lower","BB Width %","+DI14","-DI14","ADX14","DI Spread",
            "Volume Avg20","Volume Ratio","52W High","52W Low","Dist 52W High %","Dist 52W Low %",
            "Return 1W %","Return 1M %","Return 3M %","Return 6M %","Return 1Y %",
            "SMA Signal","ROC Signal","MACD Signal State","RSI Signal","BOLL Signal","Combined Signal",
            "Position","Daily Return %","Strategy Return %","Buy&Hold Cum %","Strategy Cum %",
        ]
        calc_out = calc[output_cols].where(pd.notna(calc[output_cols]), None)

        # HISTORY
        hs = book.sheets["History"]
        hs.range("A2:AW5001").clear_contents()
        hs.range("A2").options(index=False, header=False).value = calc_out.values.tolist()
        hs.range(f"A2:A{len(calc_out)+1}").number_format = "yyyy-mm-dd"
        hs.range(f"B2:E{len(calc_out)+1}").number_format = "0.00"
        hs.range(f"F2:F{len(calc_out)+1}").number_format = "#,##0"
        hs.range(f"G2:AW{len(calc_out)+1}").number_format = "0.00"

        # BACKTEST
        bs = book.sheets["Backtest"]
        bs.range("A2:H5001").clear_contents()
        backtest_values = backtest.where(pd.notna(backtest), None).values.tolist()
        bs.range("A2").options(index=False, header=False).value = backtest_values
        bs.range(f"A2:A{len(backtest)+1}").number_format = "yyyy-mm-dd"
        bs.range(f"B2:H{len(backtest)+1}").number_format = "0.00%"

        # INDICATORS
        latest = calc.iloc[-1]
        signal_map = {
            "SMA20": latest.get("SMA Signal"), "SMA50": latest.get("SMA Signal"), "SMA200": latest.get("SMA Signal"),
            "EMA20": "Ready", "EMA50": "Ready", "EMA200": "Ready",
            "RSI14": latest.get("RSI Signal"), "ROC14": latest.get("ROC Signal"),
            "MACD": latest.get("MACD Signal State"), "MACD Signal": latest.get("MACD Signal State"), "MACD Hist": latest.get("MACD Signal State"),
            "BB Width": latest.get("BOLL Signal"), "+DI14": "Ready", "-DI14": "Ready", "ADX14": "Ready", "DI Spread": "Ready",
            "Volume Ratio": "Ready", "52W High": "Ready", "52W Low": "Ready",
        }
        indicator_map = [
            ("SMA20","SMA20"),("SMA50","SMA50"),("SMA200","SMA200"),("EMA20","EMA20"),("EMA50","EMA50"),("EMA200","EMA200"),
            ("RSI14","RSI14"),("ATR14","ATR14"),("ATR %","ATR %"),("ROC14","ROC14 %"),("MACD","MACD"),("MACD Signal","MACD Signal"),
            ("MACD Hist","MACD Hist"),("BB Width","BB Width %"),("+DI14","+DI14"),("-DI14","-DI14"),("ADX14","ADX14"),("DI Spread","DI Spread"),
            ("Volume Ratio","Volume Ratio"),("52W High","52W High"),("52W Low","52W Low"),("Distance From 52W High","Dist 52W High %"),
            ("Distance From 52W Low","Dist 52W Low %"),("Return 1W","Return 1W %"),("Return 1M","Return 1M %"),("Return 3M","Return 3M %"),
            ("Return 6M","Return 6M %"),("Return 1Y","Return 1Y %"),
        ]
        ind_rows = []
        for display, col in indicator_map:
            value = _safe_number(latest.get(col))
            note = "" if value is not None else "Insufficient history/provider value"
            ind_rows.append([value, signal_map.get(display, "Ready" if value is not None else "N/A"), "Ready" if value is not None else "N/A", note])
        ins = book.sheets["Indicators"]
        ins.range("B4:B31").value = [[r[0]] for r in ind_rows]
        ins.range("D4:D31").value = [[r[1]] for r in ind_rows]
        ins.range("E4:E31").value = [[r[2]] for r in ind_rows]
        ins.range("F4:F31").value = [[r[3]] for r in ind_rows]
        ins.range("B4:B31").number_format = "0.00"

        # FUNDAMENTALS / OWNERSHIP
        fundamental = payload.get("fundamental_snapshot") or {}
        fs = book.sheets["Fundamentals"]
        fs.range("B4:B10").value = [[v] for v in [
            fundamental.get("market_cap"), fundamental.get("trailing_eps"), fundamental.get("forward_eps"),
            fundamental.get("revenue"), fundamental.get("net_income"), fundamental.get("profit_margin"), fundamental.get("return_on_equity"),
        ]]
        fs.range("B4").number_format = "#,##0"
        fs.range("B5:B6").number_format = "0.00"
        fs.range("B7:B8").number_format = "#,##0"
        fs.range("B9:B10").number_format = "0.00%"
        ownership = payload.get("ownership_snapshot") or {}
        osheet = book.sheets["Ownership"]
        osheet.range("B4:B7").value = [[v] for v in [
            ownership.get("insider_percent"), ownership.get("institution_percent"), ownership.get("shares_outstanding"), ownership.get("float_shares"),
        ]]
        osheet.range("B4:B5").number_format = "0.00%"
        osheet.range("B6:B7").number_format = "#,##0"

        # DASHBOARD SUMMARY
        ds = book.sheets["Dashboard"]
        for idx, name in enumerate(["SMA", "ROC", "MACD", "RSI", "BOLL"], start=2):
            info = test_summary[name]
            ds.cells(5, idx).value = info["last_signal"]
            ds.cells(6, idx).value = info["strategy_return"]
            ds.cells(7, idx).value = info["buy_hold"]
            ds.cells(8, idx).value = info["value_added"]
            ds.cells(9, idx).value = info["status"]
        ds.range("B6:F8").number_format = "0.0%"

        company = payload.get("company") or {}
        ds.range("I5:I10").value = [[v] for v in [
            company.get("name") or symbol, symbol, exchange, company.get("isin") or "N/A",
            _safe_number(latest.get("Close")), latest.get("Date").strftime("%Y-%m-%d") if pd.notna(latest.get("Date")) else "N/A",
        ]]
        ds.range("I9").number_format = "0.00"

        # Rebind chart series after every refresh. This fixes the Excel issue where
        # dates could appear as dozens of legend series and blank SMA warm-up
        # periods were plotted as zero/diagonal lines.
        _refresh_dashboard_charts(book, len(calc))
        try:
            for ch, title in zip(list(ds.charts), [
                f"{symbol} Price + SMA50 + SMA200", f"{symbol} MACD", f"{symbol} RSI 14", f"{symbol} Backtest: Buy & Hold vs Combined"
            ]):
                api = ch.api[1]
                api.HasTitle = True
                api.ChartTitle.Text = title
        except Exception:
            pass

        try:
            app.calculate()
        except Exception:
            pass

        history = payload.get("history") or {}
        warn_parts = [x for x in [refresh_warning, api_warning, history.get("warning")] if x]
        warning_text = " | ".join(warn_parts)
        status_message = (
            f"Updated {exchange}:{symbol} — {company.get('name') or symbol} | "
            f"{len(calc)} daily rows | {calc['Date'].min().date()} to {calc['Date'].max().date()} | "
            f"4-year history {'OK' if history.get('requirement_met') else 'PARTIAL'}"
        )
        if warning_text:
            status_message += f" | {warning_text}"
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
        if created_app and book is None and app is not None:
            try:
                app.quit()
            except Exception:
                pass


def main():
    parser = argparse.ArgumentParser(description="Refresh the single StockScreener master workbook in place.")
    parser.add_argument("--workbook", default=None, help="Optional path to StockScreener_Master.xlsx")
    parser.add_argument("--hidden", action="store_true", help="Run Excel hidden (automation/tests only).")
    args = parser.parse_args()
    message = update_workbook(args.workbook, visible=not args.hidden)
    print(message)


if __name__ == "__main__":
    main()
