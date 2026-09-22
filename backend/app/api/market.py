from app.models import OHLCV

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.providers.yahoo_provider import YahooProvider
from app.services.ohlcv_sync import sync_ohlcv
from app.services.fundamental_sync import sync_fundamental_data
from app.models import Fundamental, Ownership, Company
from app.services.providers.bse_provider import BSEProvider

import os
import math
import requests
from datetime import datetime, timedelta, date
import yfinance as yf

router = APIRouter(prefix="/market", tags=["market"])


def _json_safe(value):
    """Recursively replace non-finite numeric values with None for JSON responses."""
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    # numpy/pandas floating scalars can reach API responses after resampling.
    try:
        if value.__class__.__module__.startswith(("numpy", "pandas")):
            numeric = float(value)
            return numeric if math.isfinite(numeric) else None
    except Exception:
        pass
    return value


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _valid_trading_rows(rows, exchange: str):
    """Exclude weekend-dated stock bars from all calculations and API output.

    The DB cleanup path also removes these rows on refresh, but filtering here
    protects the UI/calculations from any legacy or provider-misaligned rows.
    """
    if exchange.upper() not in {"US", "NSE", "BSE"}:
        return list(rows)
    return [row for row in rows if row.date is not None and row.date.weekday() < 5]


def _ema(values, period):
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    value = sum(values[:period]) / period
    for price in values[period:]:
        value = ((price - value) * multiplier) + value
    return value


def _rma(values, period):
    """TradingView/Wilder moving average used by ATR and RSI-style smoothing."""
    if len(values) < period:
        return None
    value = sum(values[:period]) / period
    alpha = 1 / period
    for item in values[period:]:
        value = (alpha * item) + ((1 - alpha) * value)
    return value


def _rsi(values, period=14):
    if len(values) < period + 1:
        return None
    changes = [values[i] - values[i - 1] for i in range(1, len(values))]
    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    def rma(items):
        result = sum(items[:period]) / period
        alpha = 1 / period
        for item in items[period:]:
            result = (alpha * item) + ((1 - alpha) * result)
        return result

    avg_gain = rma(gains)
    avg_loss = rma(losses)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _weighted_rs_against_benchmark(daily_rows, exchange: str):
    """Client-specified weighted relative-strength model.

    Weights: 1W 10%, 1M 30%, 2M 20%, 3M 15%, 6M 15%, 1Y 10%.
    Each horizon is stock return relative to S&P 500 (US) or NIFTY 500 (India).
    """
    benchmark_symbol = "^GSPC" if exchange.upper() == "US" else "^CRSLDX"
    benchmark_name = "S&P 500" if exchange.upper() == "US" else "NIFTY 500"
    periods = {"1w": 5, "1m": 21, "2m": 42, "3m": 63, "6m": 126, "1y": 252}
    weights = {"1w": 10, "1m": 30, "2m": 20, "3m": 15, "6m": 15, "1y": 10}
    metrics = {}
    try:
        hist = yf.Ticker(benchmark_symbol).history(period="2y", interval="1d", auto_adjust=False)
        benchmark_by_date = {idx.date(): float(row["Close"]) for idx, row in hist.iterrows() if row.get("Close") is not None}
        aligned = [(r.date, float(r.close), benchmark_by_date.get(r.date)) for r in daily_rows if benchmark_by_date.get(r.date) is not None]
        weighted_sum = 0.0
        available_weight = 0.0
        for label, days in periods.items():
            if len(aligned) <= days:
                continue
            _, stock_now, bench_now = aligned[-1]
            _, stock_old, bench_old = aligned[-1-days]
            if not stock_old or not bench_old:
                continue
            stock_return = (stock_now / stock_old) - 1
            bench_return = (bench_now / bench_old) - 1
            if (1 + bench_return) == 0:
                continue
            relative = ((1 + stock_return) / (1 + bench_return) - 1) * 100
            weight = weights[label]
            metrics[label] = {
                "weight_percent": weight,
                "stock_return_percent": round(stock_return * 100, 2),
                "benchmark_return_percent": round(bench_return * 100, 2),
                "relative_return_percent": round(relative, 2),
            }
            weighted_sum += relative * weight
            available_weight += weight

        if available_weight <= 0:
            return None, None, metrics, benchmark_name

        weighted_relative = weighted_sum / available_weight
        rating = round(max(0, min(100, 50 + weighted_relative * 2)))
        return rating, weighted_relative, metrics, benchmark_name
    except Exception:
        return None, None, {}, benchmark_name


def _normalize_score_weights(weights=None):
    defaults = {
        "technical": 35.0,
        "fundamental": 35.0,
        "relative_strength": 15.0,
        "ownership": 10.0,
        "breakout": 5.0,
    }
    if not weights:
        return defaults

    merged = {**defaults, **{k: max(0.0, float(v)) for k, v in weights.items() if k in defaults}}
    total = sum(merged.values())
    if total <= 0:
        return defaults
    return {k: (v / total) * 100.0 for k, v in merged.items()}


def _score_symbol(db: Session, symbol: str, exchange: str, weights=None, include_components=False):
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol, OHLCV.exchange == exchange)
        .order_by(OHLCV.date.asc())
        .all()
    )
    rows = _valid_trading_rows(rows, exchange)
    fundamental = (
        db.query(Fundamental)
        .filter(Fundamental.symbol == symbol, Fundamental.exchange == exchange)
        .first()
    )
    ownership = (
        db.query(Ownership)
        .filter(Ownership.symbol == symbol, Ownership.exchange == exchange)
        .first()
    )

    components = {
        "technical": None,
        "fundamental": None,
        "relative_strength": None,
        "ownership": None,
        "breakout": None,
    }

    closes = [float(row.close) for row in rows if row.close is not None]
    highs = [float(row.high) for row in rows if row.high is not None]
    lows = [float(row.low) for row in rows if row.low is not None]
    volumes = [float(row.volume or 0) for row in rows]

    if closes:
        latest = closes[-1]
        technical_points = 0.0
        technical_possible = 0.0
        for period in [20, 50, 150, 200]:
            ema = _ema(closes, period)
            if ema is not None:
                technical_possible += 20
                if latest > ema:
                    technical_points += 20

        rsi = _rsi(closes, 14)
        if rsi is not None:
            technical_possible += 20
            if 50 <= rsi <= 70:
                technical_points += 20
            elif 40 <= rsi < 50 or 70 < rsi <= 80:
                technical_points += 10

        if technical_possible:
            components["technical"] = round((technical_points / technical_possible) * 100, 2)

        # Use the same client-specified weighted benchmark-relative RS model
        # in the dashboard score so ranking and Technical Summary stay aligned.
        rs_component, _, _, _ = _weighted_rs_against_benchmark(rows, exchange)
        if rs_component is not None:
            components["relative_strength"] = rs_component

        if len(rows) >= 50 and len(highs) == len(rows) and len(lows) == len(rows):
            pivot_rows = rows[-21:-1]
            pivot = max((float(r.high) for r in pivot_rows), default=None)
            avg_volume_50 = sum(volumes[-50:]) / 50 if len(volumes) >= 50 else None
            volume_ratio_50 = (volumes[-1] / avg_volume_50) if avg_volume_50 else 0
            recent_range = ((max(highs[-20:]) - min(lows[-20:])) / max(highs[-20:]) * 100) if max(highs[-20:]) else None
            breakout_points = 0
            if pivot is not None and latest >= pivot * 0.95:
                breakout_points += 30
            if pivot is not None and latest > pivot:
                breakout_points += 25
            if volume_ratio_50 >= 1.4:
                breakout_points += 25
            if recent_range is not None and recent_range <= 10:
                breakout_points += 20
            components["breakout"] = min(100, breakout_points)

    if fundamental:
        values = []
        checks = [
            (fundamental.trailing_eps, lambda x: x > 0),
            (fundamental.net_income, lambda x: x > 0),
            (fundamental.profit_margin, lambda x: x > 0),
            (fundamental.return_on_equity, lambda x: x >= 0.15),
            (fundamental.return_on_assets, lambda x: x >= 0.05),
        ]
        for value, check in checks:
            if value is None:
                continue
            numeric = float(value)
            values.append(100 if check(numeric) else (50 if numeric > 0 else 0))
        if values:
            components["fundamental"] = round(sum(values) / len(values), 2)

    if ownership:
        owner_scores = []
        if ownership.institution_percent is not None:
            pct = float(ownership.institution_percent)
            if pct <= 1:
                pct *= 100
            owner_scores.append(max(0, min(100, pct)))
        if ownership.insider_percent is not None:
            pct = float(ownership.insider_percent)
            if pct <= 1:
                pct *= 100
            # Moderate insider ownership is treated positively without over-rewarding concentration.
            owner_scores.append(max(0, min(100, pct * 5)))
        if owner_scores:
            components["ownership"] = round(sum(owner_scores) / len(owner_scores), 2)

    normalized_weights = _normalize_score_weights(weights)
    weighted_points = 0.0
    available_weight = 0.0
    for key, weight in normalized_weights.items():
        value = components.get(key)
        if value is None:
            continue
        weighted_points += value * weight
        available_weight += weight

    if available_weight <= 0:
        return (None, 0, components, normalized_weights) if include_components else (None, 0)

    score = round(weighted_points / available_weight)
    coverage = round(available_weight)
    result = (max(0, min(100, score)), max(0, min(100, coverage)))
    if include_components:
        return result[0], result[1], components, normalized_weights
    return result


def _rank_within(db: Session, company: Company, field: str, minimum_peers: int = 5):
    value = getattr(company, field)
    if not value:
        return {
            "available": False,
            "rank": None,
            "total": 0,
            "group": None,
            "note": "Classification data is unavailable for this stock."
        }

    peers = (
        db.query(Company)
        .filter(
            Company.exchange == company.exchange,
            getattr(Company, field) == value,
            Company.is_active == 1
        )
        .limit(100)
        .all()
    )

    scored = []
    for peer in peers:
        score, _ = _score_symbol(db, peer.symbol, peer.exchange)
        if score is not None:
            scored.append((peer.symbol, score))

    if len(scored) < minimum_peers:
        return {
            "available": False,
            "rank": None,
            "total": len(scored),
            "group": value,
            "note": f"Insufficient peer data ({len(scored)}/{minimum_peers} minimum)."
        }

    scored.sort(key=lambda item: item[1], reverse=True)
    for index, (peer_symbol, _) in enumerate(scored, start=1):
        if peer_symbol == company.symbol:
            return {
                "available": True,
                "rank": index,
                "total": len(scored),
                "group": value,
                "note": None
            }

    return {
        "available": False,
        "rank": None,
        "total": len(scored),
        "group": value,
        "note": "The selected stock does not yet have enough comparable scored peer data."
    }


def _stored_rs_rating(db: Session, symbol: str, exchange: str, minimum_universe: int = 20):
    cutoff = date.today() - timedelta(days=220)
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.exchange == exchange, OHLCV.date >= cutoff)
        .order_by(OHLCV.symbol.asc(), OHLCV.date.asc())
        .limit(50000)
        .all()
    )
    rows = _valid_trading_rows(rows, exchange)

    grouped = {}
    for row in rows:
        if row.close is None:
            continue
        grouped.setdefault(row.symbol, []).append(float(row.close))

    returns = {}
    for peer_symbol, closes in grouped.items():
        if len(closes) >= 40 and closes[0] != 0:
            returns[peer_symbol] = (closes[-1] / closes[0]) - 1

    if symbol not in returns or len(returns) < minimum_universe:
        return None, len(returns)

    target = returns[symbol]
    below_or_equal = sum(1 for value in returns.values() if value <= target)
    percentile = round((below_or_equal / len(returns)) * 99)
    return max(1, min(99, percentile)), len(returns)


@router.post("/refresh/{symbol}")
def refresh_symbol(
    symbol: str,
    exchange: str = "US",
    db: Session = Depends(get_db)
):
    try:
        provider = YahooProvider()

        if exchange.upper() == "BSE":
            provider = BSEProvider()
            rows = provider.get_ohlcv(symbol)
        else:
            provider = YahooProvider()
            rows = provider.get_ohlcv(
                symbol=symbol,
                exchange=exchange,
                start_date="2000-01-01"
            )

        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No market data returned"
            )

        result = sync_ohlcv(
            db=db,
            symbol=symbol.upper(),
            exchange=exchange.upper(),
            rows=rows
        )

        return {
            "status": "success",
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "records_received": len(rows),
            **result
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Market data refresh failed: {str(e)}"
        )

@router.get("/history/{symbol}")
def get_history(
    symbol: str,
    exchange: str = "US",
    limit: int = 260,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(OHLCV)
        .filter(
            OHLCV.symbol == symbol.upper(),
            OHLCV.exchange == exchange.upper()
        )
        .order_by(OHLCV.date.desc())
        .limit(limit)
        .all()
    )
    rows = _valid_trading_rows(rows, exchange)

    return [
        {
            "date": row.date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume
        }
        for row in rows
    ]

@router.get("/dashboard/{symbol}")
def get_dashboard_summary(
    symbol: str,
    exchange: str = "US",
    technical_weight: float = 35,
    fundamental_weight: float = 35,
    relative_strength_weight: float = 15,
    ownership_weight: float = 10,
    breakout_weight: float = 5,
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    exchange = exchange.upper()

    company = (
        db.query(Company)
        .filter(Company.symbol == symbol, Company.exchange == exchange)
        .first()
    )

    requested_weights = {
        "technical": technical_weight,
        "fundamental": fundamental_weight,
        "relative_strength": relative_strength_weight,
        "ownership": ownership_weight,
        "breakout": breakout_weight,
    }
    score, coverage, components, normalized_weights = _score_symbol(
        db, symbol, exchange, weights=requested_weights, include_components=True
    )
    if score is None:
        raise HTTPException(status_code=404, detail="Not enough data to calculate dashboard score")

    # Do not present a seemingly complete Indian-market ranking when weighted
    # fundamental/ownership categories are unavailable. This directly exposes
    # the data-coverage limitation instead of silently re-normalizing it away.
    missing_required = []
    if exchange in {"NSE", "BSE"}:
        if normalized_weights.get("fundamental", 0) > 0 and components.get("fundamental") is None:
            missing_required.append("fundamental")
        if normalized_weights.get("ownership", 0) > 0 and components.get("ownership") is None:
            missing_required.append("ownership")

    if missing_required:
        displayed_score = None
        signal = "Insufficient Data"
    else:
        displayed_score = score
        if score >= 70:
            signal = "Buy"
        elif score >= 45:
            signal = "Watch"
        else:
            signal = "Sell"

    sector_rank = _rank_within(db, company, "sector") if company and not missing_required else None
    industry_rank = _rank_within(db, company, "industry") if company and not missing_required else None

    return _json_safe({
        "symbol": symbol,
        "exchange": exchange,
        "score": displayed_score,
        "signal": signal,
        "missing_required_score_categories": missing_required,
        "score_coverage_percent": coverage,
        "score_components": components,
        "score_weights": {k: round(v, 2) for k, v in normalized_weights.items()},
        "sector": company.sector if company else None,
        "industry": company.industry if company else None,
        "sector_rank": sector_rank,
        "industry_rank": industry_rank,
        "method_note": "Overall score is weight-based. For US stocks, change the five dashboard weights to match the client's chosen model. For NSE/BSE, a score is withheld when a positively weighted fundamental or ownership category is unavailable, rather than producing a misleading partial ranking."
    })


@router.get("/ownership-details/{symbol}")
def get_ownership_details(symbol: str, exchange: str = "US"):
    try:
        provider = YahooProvider()
        return provider.get_ownership_details(symbol.upper(), exchange.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ownership details failed: {str(e)}")


@router.get("/technical-summary/{symbol}")
def get_technical_summary(
    symbol: str,
    exchange: str = "US",
    timeframe: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    exchange = exchange.upper()

    daily_rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol, OHLCV.exchange == exchange)
        .order_by(OHLCV.date.asc())
        .all()
    )
    daily_rows = _valid_trading_rows(daily_rows, exchange)
    if len(daily_rows) < 20:
        raise HTTPException(status_code=404, detail="Not enough historical data for technical summary")

    rows = daily_rows
    if timeframe != "daily":
        import pandas as pd
        from types import SimpleNamespace

        frame = pd.DataFrame([
            {
                "date": row.date,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume or 0),
            }
            for row in daily_rows
        ])
        frame["date"] = pd.to_datetime(frame["date"])
        frame["actual_date"] = frame["date"]
        frame = frame.set_index("date")
        rule = "W" if timeframe == "weekly" else "ME"
        frame = frame.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "actual_date": "last",
        }).dropna(subset=["open", "high", "low", "close"])

        rows = [
            SimpleNamespace(
                date=item.actual_date.date(),
                open=float(item.open),
                high=float(item.high),
                low=float(item.low),
                close=float(item.close),
                volume=float(item.volume or 0),
            )
            for item in frame.itertuples()
        ]

    if len(rows) < 20:
        raise HTTPException(status_code=404, detail=f"Not enough {timeframe} historical data for technical summary")

    closes = [float(row.close) for row in rows]
    highs = [float(row.high) for row in rows]
    lows = [float(row.low) for row in rows]
    opens = [float(row.open) for row in rows]
    volumes = [float(row.volume or 0) for row in rows]

    ema_periods = [20, 30, 50, 100, 150, 200]
    emas = {str(period): _ema(closes, period) for period in ema_periods}
    available_emas = [emas[str(p)] for p in ema_periods if emas[str(p)] is not None]
    ema_alignment = "Unavailable"
    if len(available_emas) == len(ema_periods):
        bullish = all(available_emas[i] > available_emas[i + 1] for i in range(len(available_emas) - 1))
        bearish = all(available_emas[i] < available_emas[i + 1] for i in range(len(available_emas) - 1))
        ema_alignment = "Bullish" if bullish else "Bearish" if bearish else "Mixed"

    avg_volume_20 = sum(volumes[-20:]) / 20
    avg_volume_50 = sum(volumes[-50:]) / 50 if len(volumes) >= 50 else None
    volume_ratio = (volumes[-1] / avg_volume_20) if avg_volume_20 else None
    volume_ratio_50 = (volumes[-1] / avg_volume_50) if avg_volume_50 else None

    # ADR is a DAILY metric even when the chart is weekly/monthly.
    # Client/TradingView reference displays ADR(20) as an absolute price range:
    # Average(High - Low, 20 daily sessions).  Keep ADR% separately for
    # normalized comparisons and volatility logic.
    adr_daily_rows = daily_rows[-20:]
    adr_abs_values = [
        float(r.high) - float(r.low)
        for r in adr_daily_rows
        if r.high is not None and r.low is not None
    ]
    adr_percent_values = [
        ((float(r.high) - float(r.low)) / float(r.low)) * 100
        for r in adr_daily_rows
        if r.high is not None and r.low not in (None, 0)
    ]
    adr_value = sum(adr_abs_values) / len(adr_abs_values) if adr_abs_values else None
    adr_percent = sum(adr_percent_values) / len(adr_percent_values) if adr_percent_values else None

    # ATR uses Wilder's RMA (the same smoothing convention used by TradingView
    # ATR), calculated on the SELECTED timeframe.
    true_ranges = []
    for i in range(len(rows)):
        prev_close = closes[i - 1] if i > 0 else closes[i]
        true_ranges.append(max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close)))
    atr14 = _rma(true_ranges, 14)
    atr_percent = (atr14 / closes[-1] * 100) if atr14 is not None and closes[-1] else None

    recent20 = closes[-20:]
    sma20 = sum(recent20) / 20
    variance20 = sum((x - sma20) ** 2 for x in recent20) / 20
    sd20 = variance20 ** 0.5
    bb_upper = sma20 + 2 * sd20
    bb_lower = sma20 - 2 * sd20
    bb_width = ((bb_upper - bb_lower) / sma20 * 100) if sma20 else None

    range20 = ((max(highs[-20:]) - min(lows[-20:])) / min(lows[-20:]) * 100) if min(lows[-20:]) else None
    periods_per_52w = 252 if timeframe == "daily" else 52 if timeframe == "weekly" else 12
    lookback_52w = min(periods_per_52w, len(rows))
    high_52w = max(highs[-lookback_52w:])
    distance_52w_high = ((high_52w - closes[-1]) / high_52w * 100) if high_52w else None

    # VCP/consolidation detection. Three successive 20-period windows are used
    # as transparent contractions. When both price depth and ATR% contract in
    # sequence, the final contraction high becomes the pivot (client-defined).
    contractions = []
    final_contraction_high = None
    if len(rows) >= 60:
        for start_i, end_i in [(-60, -40), (-40, -20), (-20, None)]:
            segment = rows[start_i:end_i]
            seg_high = max(float(r.high) for r in segment)
            seg_low = min(float(r.low) for r in segment)
            depth = ((seg_high - seg_low) / seg_high * 100) if seg_high else None
            seg_tr = []
            for j, r in enumerate(segment):
                prev = float(segment[j-1].close) if j > 0 else float(r.close)
                seg_tr.append(max(float(r.high)-float(r.low), abs(float(r.high)-prev), abs(float(r.low)-prev)))
            seg_atr = _rma(seg_tr, 14) if len(seg_tr) >= 14 else (sum(seg_tr) / len(seg_tr) if seg_tr else None)
            seg_atr_pct = (seg_atr / float(segment[-1].close) * 100) if seg_atr and segment[-1].close else None
            contractions.append({"depth_percent": depth, "atr_percent": seg_atr_pct, "high": seg_high, "low": seg_low})

    vcp_stage = "Not Detected"
    if len(contractions) == 3:
        depths = [c["depth_percent"] for c in contractions]
        atrs = [c["atr_percent"] for c in contractions]
        if all(v is not None for v in depths + atrs) and depths[1] < depths[0] and depths[2] < depths[1] and atrs[1] < atrs[0] and atrs[2] < atrs[1]:
            vcp_stage = "VCP Contraction"
            final_contraction_high = contractions[-1]["high"]

    # If a formal VCP is not detected, use the recent consolidation high as the
    # fallback pivot. Never use today's high itself as the pivot.
    consolidation_rows = rows[-21:-1] if len(rows) >= 21 else rows[:-1]
    consolidation_high = max((float(r.high) for r in consolidation_rows), default=None)
    pivot = final_contraction_high if final_contraction_high is not None else consolidation_high

    buffer = 0.003
    latest_close = closes[-1]
    latest_open = opens[-1]
    latest_midpoint = (highs[-1] + lows[-1]) / 2

    breakout_status = "Unavailable"
    breakout_strength = None
    near_pivot = False
    if pivot is not None:
        near_pivot = (pivot * 0.95) <= latest_close <= (pivot * 1.02)
        above_pivot = latest_close > pivot * (1 + buffer)
        price_confirmation = latest_close > latest_open and latest_close >= latest_midpoint
        volume_confirmation = volume_ratio_50 is not None and volume_ratio_50 >= 1.4

        if above_pivot and price_confirmation and volume_confirmation:
            breakout_status = "Confirmed Breakout"
        elif latest_close > pivot:
            breakout_status = "Potential Breakout"
        elif near_pivot:
            breakout_status = "Near Pivot"
        else:
            breakout_status = "No Breakout"

        # Client-requested 0-100 breakout-strength model.
        points = 0
        if latest_close > pivot: points += 20
        if volume_ratio_50 is not None and volume_ratio_50 >= 1.4: points += 20
        if volume_ratio_50 is not None and volume_ratio_50 >= 2.0: points += 10
        if latest_close > pivot * 1.005: points += 10
        if latest_close > pivot * 1.01: points += 10

        atr_contraction = False
        if len(contractions) >= 2:
            a = contractions[-2].get("atr_percent")
            b = contractions[-1].get("atr_percent")
            atr_contraction = a is not None and b is not None and b < a
        if atr_contraction: points += 10

        if len(rows) >= 10:
            tight_high = max(highs[-10:])
            tight_low = min(lows[-10:])
            tight_range = ((tight_high - tight_low) / tight_high * 100) if tight_high else None
            if tight_range is not None and tight_range <= 10:
                points += 10

        breakout_strength = min(100, points)

    gap_percent = None
    gap_classification = "Unavailable"
    if len(rows) >= 2 and closes[-2]:
        gap_percent = ((opens[-1] - closes[-2]) / closes[-2]) * 100
        if gap_percent >= 8:
            gap_classification = "Excessive Gap Breakout"
        elif gap_percent >= 2:
            gap_classification = "Gap Breakout"
        else:
            gap_classification = "Normal / No Material Gap"

    if breakout_status == "Confirmed Breakout":
        pattern = "Confirmed Breakout"
    elif vcp_stage == "VCP Contraction":
        pattern = "VCP / Volatility Contraction"
    elif range20 is not None and range20 <= 10:
        pattern = "Tight Consolidation"
    elif near_pivot:
        pattern = "Near Pivot"
    else:
        pattern = "None"

    rs_rating, rs_weighted_relative_return, rs_metrics, benchmark_name = _weighted_rs_against_benchmark(daily_rows, exchange)

    return _json_safe({
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "ema": {key: (round(value, 2) if value is not None else None) for key, value in emas.items()},
        "ema_alignment": ema_alignment,
        "average_volume_20": round(avg_volume_20, 2),
        "average_volume_50": round(avg_volume_50, 2) if avg_volume_50 is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "volume_ratio_50": round(volume_ratio_50, 2) if volume_ratio_50 is not None else None,
        "adr_20": round(adr_value, 2) if adr_value is not None else None,
        "adr_percent": round(adr_percent, 2) if adr_percent is not None else None,
        "atr_14": round(atr14, 2) if atr14 is not None else None,
        "atr_percent": round(atr_percent, 2) if atr_percent is not None else None,
        "bollinger_width_percent": round(bb_width, 2) if bb_width is not None else None,
        "range_20d_percent": round(range20, 2) if range20 is not None else None,
        "distance_from_52w_high_percent": round(distance_52w_high, 2) if distance_52w_high is not None else None,
        "pivot": round(pivot, 2) if pivot is not None else None,
        "breakout_status": breakout_status,
        "breakout_strength": breakout_strength,
        "gap_percent": round(gap_percent, 2) if gap_percent is not None else None,
        "gap_classification": gap_classification,
        "vcp_stage": vcp_stage,
        "vcp_contractions": [{k: (round(v, 2) if v is not None else None) for k, v in item.items()} for item in contractions],
        "pattern": pattern,
        "rs_rating": rs_rating,
        "rs_weighted_relative_return_percent": round(rs_weighted_relative_return, 2) if rs_weighted_relative_return is not None else None,
        "rs_benchmark": benchmark_name,
        "rs_periods": rs_metrics,
        "rs_note": "Client formula: weighted relative return = 1W×10% + 1M×30% + 2M×20% + 3M×15% + 6M×15% + 1Y×10%, where each return is stock performance relative to the broad-market benchmark. The displayed 0-100 RS rating maps benchmark-equivalent performance to 50.",
        "criteria_note": f"Metrics use the selected {timeframe} timeframe. For a detected VCP, Pivot = highest high of the final contraction; otherwise it is the recent consolidation high. Near Pivot = 95%-102% of pivot. Confirmed breakout requires close > pivot by 0.3%, volume >= 1.4x 50-period average, close > open, and close in the upper half of the period's range. VCP requires successive price-depth and ATR% contractions."
    })


@router.get("/benchmark/{exchange}")
def get_benchmark(exchange: str, limit: int = 400):
    exchange = exchange.upper()
    if exchange == "US":
        ticker_symbol = "^GSPC"
        benchmark_name = "S&P 500"
    elif exchange in ["NSE", "BSE"]:
        ticker_symbol = "^CRSLDX"
        benchmark_name = "NIFTY 500"
    else:
        raise HTTPException(status_code=400, detail="Unsupported exchange")

    # Yahoo is used first because it exposes both requested index series.
    try:
        data = yf.Ticker(ticker_symbol).history(period="5y", interval="1d", auto_adjust=False)
        if data is not None and not data.empty:
            values = [
                {"date": idx.date().isoformat(), "close": float(row["Close"])}
                for idx, row in data.iterrows()
                if row.get("Close") is not None
            ]
            return {
                "name": benchmark_name,
                "symbol": ticker_symbol,
                "data": values[-limit:],
                "method": "Broad-market index history from Yahoo Finance",
            }
    except Exception:
        pass

    # US fallback for deployments where Yahoo index history is temporarily unavailable.
    if exchange == "US":
        api_key = os.getenv("TWELVE_DATA_API_KEY")
        if api_key:
            try:
                response = requests.get(
                    "https://api.twelvedata.com/time_series",
                    params={"symbol": "SPY", "interval": "1day", "outputsize": limit, "apikey": api_key},
                    timeout=20,
                )
                payload = response.json()
                if payload.get("status") != "error":
                    values = payload.get("values", [])
                    return {
                        "name": "S&P 500 (SPY fallback)",
                        "symbol": "SPY",
                        "data": [{"date": item["datetime"], "close": float(item["close"])} for item in reversed(values)],
                        "warning": "Using SPY ETF as fallback because the S&P 500 index feed was unavailable.",
                    }
            except Exception:
                pass

    return {
        "name": benchmark_name,
        "symbol": ticker_symbol,
        "data": [],
        "warning": f"{benchmark_name} data is temporarily unavailable from the configured providers.",
    }


@router.get("/chart/{symbol}")
def get_chart_data(
    symbol: str,
    exchange: str = "US",
    timeframe: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    limit: int = 260,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(OHLCV)
        .filter(
            OHLCV.symbol == symbol.upper(),
            OHLCV.exchange == exchange.upper()
        )
        .order_by(OHLCV.date.asc())
        .all()
    )
    rows = _valid_trading_rows(rows, exchange)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No stored data found"
        )

    data = [
        {
            "date": row.date,
            "open": row.open,
            "high": row.high,
            "low": row.low,
            "close": row.close,
            "volume": row.volume
        }
        for row in rows
    ]

    if timeframe == "daily":
        result = data

    else:
        import pandas as pd

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"])
        df["actual_date"] = df["date"]
        df = df.set_index("date")

        rule = "W" if timeframe == "weekly" else "ME"

        df = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
            "actual_date": "last"
        }).dropna(subset=["open", "high", "low", "close"])

        df = df.reset_index(drop=True).rename(columns={"actual_date": "date"})

        result = df.to_dict(orient="records")

    return _json_safe({
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "timeframe": timeframe,
        "count": len(result[-limit:]),
        "data": result[-limit:]
    })

@router.post("/fundamentals/{symbol}")
def refresh_fundamentals(
    symbol: str,
    exchange: str = "US",
    db: Session = Depends(get_db)
):
    try:
        if exchange.upper() != "US":
            raise HTTPException(
                status_code=400,
                detail="Fundamental refresh currently supports US stocks only"
            )

        provider = YahooProvider()
        data = provider.get_fundamentals(symbol.upper())

        # Use statement-derived ratios for ROE/ROA when available. This keeps
        # the snapshot consistent with the annual table and uses average balance
        # sheet denominators instead of an opaque provider summary ratio.
        try:
            history = provider.get_fundamental_history(symbol.upper())
            latest_annual = (history.get("annual") or [None])[0]
            if latest_annual:
                if latest_annual.get("roe") is not None:
                    data["return_on_equity"] = latest_annual["roe"] / 100
                if latest_annual.get("roa") is not None:
                    data["return_on_assets"] = latest_annual["roa"] / 100
        except Exception:
            pass

        result = sync_fundamental_data(
            db=db,
            symbol=symbol.upper(),
            exchange="US",
            data=data
        )

        return {
            **result,
            "fundamentals": data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fundamental refresh failed: {str(e)}"
        )

@router.get("/fundamentals/{symbol}")
def get_fundamentals(
    symbol: str,
    exchange: str = "US",
    db: Session = Depends(get_db)
):
    fundamental = (
        db.query(Fundamental)
        .filter(
            Fundamental.symbol == symbol.upper(),
            Fundamental.exchange == exchange.upper()
        )
        .first()
    )

    ownership = (
        db.query(Ownership)
        .filter(
            Ownership.symbol == symbol.upper(),
            Ownership.exchange == exchange.upper()
        )
        .first()
    )

    if not fundamental and not ownership:
        raise HTTPException(
            status_code=404,
            detail="No fundamental data found"
        )

    return {
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "fundamentals": {
            "market_cap": fundamental.market_cap if fundamental else None,
            "trailing_eps": fundamental.trailing_eps if fundamental else None,
            "forward_eps": fundamental.forward_eps if fundamental else None,
            "revenue": fundamental.revenue if fundamental else None,
            "net_income": fundamental.net_income if fundamental else None,
            "profit_margin": fundamental.profit_margin if fundamental else None,
            "return_on_equity": fundamental.return_on_equity if fundamental else None,
            "return_on_assets": fundamental.return_on_assets if fundamental else None,
        },
        "ownership": {
            "insider_percent": ownership.insider_percent if ownership else None,
            "institution_percent": ownership.institution_percent if ownership else None,
            "shares_outstanding": ownership.shares_outstanding if ownership else None,
            "float_shares": ownership.float_shares if ownership else None,
        }
    }

@router.get("/fundamentals-history/{symbol}")
def get_fundamentals_history(
    symbol: str,
    exchange: str = "US"
):
    try:
        if exchange.upper() != "US":
            raise HTTPException(
                status_code=400,
                detail="Fundamental history currently supports US stocks only"
            )

        provider = YahooProvider()

        data = provider.get_fundamental_history(
            symbol.upper()
        )

        return data

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Fundamental history failed: {str(e)}"
        )

@router.get("/indicators/{symbol}")
def get_indicators(
    symbol: str,
    exchange: str = "US",
    timeframe: str = "daily",
    sma_short: int = 20,
    sma_long: int = 50,
    rsi_period: int = 14,
    db: Session = Depends(get_db)
):
    rows = (
        db.query(OHLCV)
        .filter(
            OHLCV.symbol == symbol.upper(),
            OHLCV.exchange == exchange.upper()
        )
        .order_by(OHLCV.date.asc())
        .all()
    )
    rows = _valid_trading_rows(rows, exchange)

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="No historical data found"
        )

    timeframe = timeframe.lower()

    # Build closes for selected timeframe
    if timeframe == "daily":
        closes = [float(r.close) for r in rows]

    elif timeframe == "weekly":
        weekly = {}

        for r in rows:
            # ISO year + ISO week prevents week-number collisions across years
            iso = r.date.isocalendar()
            key = (iso.year, iso.week)
            weekly[key] = float(r.close)

        closes = list(weekly.values())

    elif timeframe == "monthly":
        monthly = {}

        for r in rows:
            key = (r.date.year, r.date.month)
            monthly[key] = float(r.close)

        closes = list(monthly.values())

    else:
        raise HTTPException(
            status_code=400,
            detail="Timeframe must be daily, weekly, or monthly"
        )

    minimum_required = max(
        sma_short,
        sma_long,
        rsi_period + 1
    )

    if len(closes) < minimum_required:
        raise HTTPException(
            status_code=404,
            detail=f"Not enough {timeframe} historical data for selected indicator settings"
        )

    # SMA
    sma_short_value = sum(closes[-sma_short:]) / sma_short
    sma_long_value = sum(closes[-sma_long:]) / sma_long

    # EMA
    def calculate_ema(values, period):
        multiplier = 2 / (period + 1)

        ema = sum(values[:period]) / period

        for price in values[period:]:
            ema = ((price - ema) * multiplier) + ema

        return ema

    ema_short_value = calculate_ema(closes, sma_short)
    ema_long_value = calculate_ema(closes, sma_long)

    # RSI
    changes = [
        closes[i] - closes[i - 1]
        for i in range(1, len(closes))
    ]

    gains = [max(change, 0) for change in changes]
    losses = [max(-change, 0) for change in changes]

    def calculate_rma(values, period):
        rma = sum(values[:period]) / period
        alpha = 1 / period

        for value in values[period:]:
            rma = (alpha * value) + ((1 - alpha) * rma)

        return rma

    avg_gain = calculate_rma(gains, rsi_period)
    avg_loss = calculate_rma(losses, rsi_period)

    if avg_loss == 0:
        rsi_value = 100
    else:
        rs = avg_gain / avg_loss
        rsi_value = 100 - (100 / (1 + rs))

    return {
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "timeframe": timeframe,
        "settings": {
            "sma_short": sma_short,
            "sma_long": sma_long,
            "rsi_period": rsi_period
        },
        "sma_short": round(sma_short_value, 2),
        "sma_long": round(sma_long_value, 2),
        "ema_short": round(ema_short_value, 2),
        "ema_long": round(ema_long_value, 2),
        "rsi": round(rsi_value, 2)
    }