"""Deterministic next-session technical simulation; never uses current statements."""
from datetime import date
import math
from statistics import median
import pandas as pd


class HistoricalDataUnavailable(ValueError):
    pass


def simulate(rows, benchmark_rows, config):
    selected = config.get("components", ["technical"])
    unsupported = set(selected) - {"technical", "relative_strength"}
    if unsupported:
        raise HistoricalDataUnavailable("Point-in-time published statements/holdings are unavailable for: " + ", ".join(sorted(unsupported)) + ". Current fundamentals are never substituted.")
    if not selected:
        raise ValueError("Enable at least one strategy component")
    if len(rows) < 60:
        raise HistoricalDataUnavailable("At least 60 verified daily bars are required")
    frame = pd.DataFrame(rows).sort_values("date").drop_duplicates("date")
    for field in ("open", "high", "low", "close"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    frame = frame.dropna(subset=["open", "high", "low", "close"])
    frame = frame[(frame[["open", "high", "low", "close"]] > 0).all(axis=1)]
    frame["date"] = pd.to_datetime(frame.date).dt.date
    frame = frame[frame.date <= config["end_date"]].reset_index(drop=True)
    closes = frame.close
    # Strategy settings are explicit user inputs, not a replacement client score.
    period = config.get("ema_period", 50)
    ema = closes.ewm(span=period, adjust=False, min_periods=period).mean()
    trend = closes > ema
    lookback = config.get("rs_lookback", 63)
    benchmark = {r["date"]: r["close"] for r in benchmark_rows}
    if "relative_strength" in selected:
        matched = pd.Series([benchmark.get(day) for day in frame.date], dtype=float)
        # This is positive relative return, not the current 5,000-stock score.
        if matched.notna().sum() < lookback + 1:
            raise HistoricalDataUnavailable("Aligned historical benchmark observations are unavailable")
        rs_return = closes.pct_change(lookback, fill_method=None) - matched.pct_change(lookback, fill_method=None)
    else:
        rs_return = pd.Series(0.0, index=frame.index)
    qualifies = pd.Series(True, index=frame.index)
    if "technical" in selected:
        qualifies &= trend
    if "relative_strength" in selected:
        qualifies &= rs_return > 0
    capital = float(config["starting_capital"])
    cash, quantity, entry, high_since_entry, active_stop = capital, 0, None, None, None
    trades, curve, qualifications = [], [], []
    fee_rate = config.get("commission_bps", 0) / 10000
    slip = config.get("slippage_bps", 0) / 10000
    stop_rate = config.get("initial_stop_percent", 10) / 100
    trail_rate = config.get("trailing_stop_percent", 10) / 100
    allocation = config.get("allocation_percent", 25) / 100
    risk = config.get("risk_percent", 2) / 100
    peak, first_close, first_date = capital, None, None
    def close_trade(day, exit_price, reason):
        nonlocal cash, quantity, entry
        proceeds = quantity * exit_price
        exit_fee = proceeds * fee_rate
        cash += proceeds - exit_fee
        profit = proceeds - exit_fee - entry["entry_price"] * quantity - entry["entry_fee"]
        trade = {**entry, "exit_date": str(day), "exit_price": exit_price, "holding_days": (day - date.fromisoformat(entry["entry_date"])).days, "return_percent": profit / (entry["entry_price"] * quantity + entry["entry_fee"]) * 100, "net_profit": profit, "exit_fee": exit_fee, "highest_price_since_entry": high_since_entry, "exit_reason": reason}
        trades.append(trade)
        quantity, entry = 0, None
    for i, row in frame.iterrows():
        day = row.date
        if day < config["start_date"]:
            continue
        if first_close is None:
            first_close, first_date = float(row.close), day
        signal = bool(qualifies.iloc[i - 1]) if i else False
        if quantity:
            # The stop was set before this bar. A gap gets the opening price;
            # today's new high cannot raise a stop retroactively within the bar.
            if row.open <= active_stop:
                close_trade(day, float(row.open) * (1 - slip), "Gap through stop")
            elif not signal:
                close_trade(day, float(row.open) * (1 - slip), "Prior-close qualification ended")
            elif row.low <= active_stop:
                close_trade(day, active_stop * (1 - slip), "Stop loss")
            else:
                high_since_entry = max(high_since_entry, float(row.high))
                next_stop = high_since_entry * (1 - trail_rate)
                if config.get("ema_stop") and pd.notna(ema.iloc[i]):
                    next_stop = max(next_stop, float(ema.iloc[i]))
                active_stop = max(active_stop, next_stop)
        elif signal:
            price = float(row.open) * (1 + slip)
            equity = cash
            quantity = int(min(cash / (price * (1 + fee_rate)), equity * allocation / (price * (1 + fee_rate)), equity * risk / (price * stop_rate)))
            if quantity:
                fee = quantity * price * fee_rate
                cash -= quantity * price + fee
                active_stop = price * (1 - stop_rate)
                high_since_entry = price
                entry = {"entry_date": str(day), "signal_date": str(frame.iloc[i - 1].date), "announcement_date": None, "entry_price": price, "initial_stop_loss": active_stop, "quantity": quantity, "entry_fee": fee, "qualification": " & ".join(selected), "return_multiple": None}
                if row.low <= active_stop:
                    # Newly placed initial stop is active after opening entry.
                    close_trade(day, min(float(row.open), active_stop) * (1 - slip), "Initial stop")
                else:
                    high_since_entry = max(price, float(row.high))
                    active_stop = max(active_stop, high_since_entry * (1 - trail_rate))
        equity = cash + quantity * float(row.close)
        peak = max(peak, equity)
        curve.append({"date": str(day), "equity": equity, "cash": cash, "drawdown_percent": (equity / peak - 1) * 100, "buy_hold_percent": (float(row.close) / first_close - 1) * 100})
        if bool(qualifies.iloc[i]):
            qualifications.append({"evaluation_date": str(day), "next_session_entry": True, "technical": bool(trend.iloc[i]), "relative_return_percent": float(rs_return.iloc[i] * 100) if pd.notna(rs_return.iloc[i]) else None})
        if cash < -1e-7:
            raise AssertionError("Simulation cash invariant failed")
    if not curve:
        raise HistoricalDataUnavailable("No observations in the requested historical period")
    if quantity:
        close_trade(frame.iloc[-1].date, float(frame.iloc[-1].close) * (1 - slip), "End of test liquidation")
        curve[-1]["equity"] = cash
        curve[-1]["cash"] = cash
        curve[-1]["drawdown_percent"] = (cash / peak - 1) * 100
    ending = curve[-1]["equity"]
    days = max(1, (date.fromisoformat(curve[-1]["date"]) - first_date).days)
    wins = [t["return_percent"] for t in trades if t["net_profit"] > 0]
    losses = [t["return_percent"] for t in trades if t["net_profit"] <= 0]
    for trade in trades:
        trade["return_multiple"] = 1 + trade["return_percent"] / 100
    dated_curve = pd.Series([c["equity"] for c in curve], index=pd.to_datetime([c["date"] for c in curve]))
    annual_returns = []
    for day, value in dated_curve.items():
        target = day - pd.DateOffset(years=1)
        earlier = dated_curve[dated_curve.index <= target]
        if not earlier.empty:
            annual_returns.append((value / earlier.iloc[-1] - 1) * 100)
    benchmark_dates = [d for d in sorted(benchmark) if first_date <= d <= date.fromisoformat(curve[-1]["date"])]
    benchmark_return = (benchmark[benchmark_dates[-1]] / benchmark[benchmark_dates[0]] - 1) * 100 if len(benchmark_dates) > 1 and (benchmark_dates[0] - first_date).days <= 7 and (date.fromisoformat(curve[-1]['date']) - benchmark_dates[-1]).days <= 7 else None
    total = (ending / capital - 1) * 100
    return {"starting_capital": capital, "ending_value": ending, "net_profit": ending - capital, "total_return_percent": total, "cagr_percent": ((ending / capital) ** (365.25 / days) - 1) * 100, "max_drawdown_percent": min(c["drawdown_percent"] for c in curve), "win_rate_percent": len(wins) / len(trades) * 100 if trades else None, "average_winning_trade_percent": sum(wins) / len(wins) if wins else None, "average_losing_trade_percent": sum(losses) / len(losses) if losses else None, "trade_count": len(trades), "average_holding_days": sum(t["holding_days"] for t in trades) / len(trades) if trades else None, "median_12_month_return_percent": median(annual_returns) if annual_returns else None, "benchmark_return_percent": benchmark_return, "benchmark_excess_percent": total - benchmark_return if benchmark_return is not None else None, "buy_hold_return_percent": curve[-1]["buy_hold_percent"], "history_rows": len(curve), "actual_years": days / 365.25, "earliest_date": curve[0]["date"], "latest_date": curve[-1]["date"], "trades": trades, "equity_curve": curve, "qualifications": qualifications, "point_in_time_status": "Technical prices only; published fundamental/ownership strategy data unavailable", "universe_status": "Selected stock only; historical universe/survivorship not certified", "assumptions": {"execution": "Prior close signal, next session open; prior-bar trailing stop; conservative gap fills; end-of-test close liquidation", "commission_bps": config.get("commission_bps", 0), "slippage_bps": config.get("slippage_bps", 0), "allocation_percent": allocation * 100, "risk_percent": risk * 100, "dividends": "Excluded; provider raw OHLC used", "corporate_actions": "Yahoo split-normalized OHLC; individual corporate action ledger not available", "rs": "Positive historical relative return, not an unavailable historical 5,000-stock percentile", "reinvestment": "Available capital is reused; whole shares only"}}
