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
from app.services.providers.india_shareholding_provider import IndiaShareholdingProvider

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


def _shift_months(value_date, months):
    import calendar
    month_index = value_date.year * 12 + (value_date.month - 1) - months
    year = month_index // 12
    month = (month_index % 12) + 1
    day = min(value_date.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _rs_anchor_date(end_date, label):
    if label == "1w":
        return end_date - timedelta(days=7)
    if label == "2w":
        return end_date - timedelta(days=14)
    if label == "1m":
        return _shift_months(end_date, 1)
    if label == "2m":
        return _shift_months(end_date, 2)
    if label == "3m":
        return _shift_months(end_date, 3)
    if label == "6m":
        return _shift_months(end_date, 6)
    if label == "1y":
        return _shift_months(end_date, 12)
    return end_date


def _close_on_or_before(points, target_date):
    for trade_date, close in reversed(points):
        if trade_date <= target_date and close not in (None, 0):
            return trade_date, float(close)
    return None


def _weighted_relative_return_from_points(stock_points, benchmark_points, weights):
    """Client method: period relative return = stock return % - benchmark return %."""
    if not stock_points or not benchmark_points:
        return None, {}

    end_date = min(stock_points[-1][0], benchmark_points[-1][0])
    stock_end = _close_on_or_before(stock_points, end_date)
    bench_end = _close_on_or_before(benchmark_points, end_date)
    if not stock_end or not bench_end:
        return None, {}

    metrics = {}
    weighted_sum = 0.0
    available_weight = 0.0
    for label in ("1w", "2w", "1m", "2m", "3m", "6m", "1y"):
        weight = max(0.0, float(weights.get(label, 0) or 0))
        anchor = _rs_anchor_date(end_date, label)
        stock_old = _close_on_or_before(stock_points, anchor)
        bench_old = _close_on_or_before(benchmark_points, anchor)
        if not stock_old or not bench_old or stock_old[1] == 0 or bench_old[1] == 0:
            continue

        stock_return = ((stock_end[1] / stock_old[1]) - 1) * 100
        benchmark_return = ((bench_end[1] / bench_old[1]) - 1) * 100
        relative_return = stock_return - benchmark_return
        metrics[label] = {
            "weight_percent": weight,
            "stock_return_percent": round(stock_return, 2),
            "benchmark_return_percent": round(benchmark_return, 2),
            "relative_return_percent": round(relative_return, 2),
            "start_date": stock_old[0].isoformat(),
            "end_date": stock_end[0].isoformat(),
        }
        if weight > 0:
            weighted_sum += relative_return * weight
            available_weight += weight

    if available_weight <= 0:
        return None, metrics
    return weighted_sum / available_weight, metrics


def _percentile_rank(values, target_value):
    """Client percentile: (lower + 0.5 * equal) * 100 / total."""
    values = [float(v) for v in values if v is not None and math.isfinite(float(v))]
    if target_value is None or not values:
        return None
    tolerance = 1e-9
    lower = sum(1 for value in values if value < target_value - tolerance)
    equal = sum(1 for value in values if abs(value - target_value) <= tolerance)
    percentile = ((lower + 0.5 * equal) * 100.0) / len(values)
    return round(max(0.0, min(100.0, percentile)), 2)


def _rs_universe_metrics(db: Session, exchange: str, benchmark_points):
    """Return period relative returns for each stored symbol in the market universe."""
    if db is None:
        return {}, {}

    cutoff = date.today() - timedelta(days=430)
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.exchange == exchange.upper(), OHLCV.date >= cutoff)
        .order_by(OHLCV.symbol.asc(), OHLCV.date.asc())
        .all()
    )
    grouped = {}
    for row in _valid_trading_rows(rows, exchange):
        if row.close is None:
            continue
        grouped.setdefault(row.symbol, []).append((row.date, float(row.close)))

    # The relative-return metrics themselves do not depend on scoring weights.
    metric_weights = {key: 1.0 for key in ("1w", "2w", "1m", "2m", "3m", "6m", "1y")}
    symbol_metrics = {}
    for symbol, points in grouped.items():
        _, metrics = _weighted_relative_return_from_points(points, benchmark_points, metric_weights)
        if metrics:
            symbol_metrics[symbol] = metrics

    sector_by_symbol = {
        row.symbol: row.sector
        for row in db.query(Company).filter(Company.exchange == exchange.upper()).all()
        if row.sector
    }
    return symbol_metrics, sector_by_symbol


def _weighted_rs_against_benchmark(daily_rows, exchange: str, period_weights=None, db: Session = None):
    """Client RS method: period relative returns -> period percentiles -> weighted RS score."""
    benchmark_symbol = "^GSPC" if exchange.upper() == "US" else "^CRSLDX"
    benchmark_name = "S&P 500" if exchange.upper() == "US" else "NIFTY 500"

    # Latest client handwritten RS reference:
    # 1W*0.30 + 1M*0.25 + 3M*0.20 + 6M*0.15 + 12M*0.10
    # 2W/2M remain optional custom periods with zero default weight. Sector is informational only.
    defaults = {"1w": 30.0, "2w": 0.0, "1m": 25.0, "2m": 0.0, "3m": 20.0, "6m": 15.0, "1y": 10.0, "sector": 0.0}
    weights = defaults.copy()
    if period_weights:
        for key, value in period_weights.items():
            if key in weights:
                try:
                    weights[key] = max(0.0, float(value))
                except Exception:
                    pass

    try:
        hist = yf.Ticker(benchmark_symbol).history(period="5y", interval="1d", auto_adjust=False)
        benchmark_points = [
            (idx.date(), float(row["Close"]))
            for idx, row in hist.iterrows()
            if row.get("Close") is not None and math.isfinite(float(row["Close"]))
        ]
        stock_points = [
            (r.date, float(r.close))
            for r in daily_rows
            if r.date is not None and r.close is not None and math.isfinite(float(r.close))
        ]
        stock_points.sort(key=lambda item: item[0])
        benchmark_points.sort(key=lambda item: item[0])

        benchmark_by_date = dict(benchmark_points)
        aligned = [(d, c, benchmark_by_date.get(d)) for d, c in stock_points if benchmark_by_date.get(d) is not None]
        rs_chart = []
        base_ratio = None
        for trade_date, stock_close, bench_close in aligned:
            if not stock_close or not bench_close:
                continue
            ratio = stock_close / bench_close
            if base_ratio is None:
                base_ratio = ratio
            if base_ratio:
                rs_chart.append({"date": trade_date.isoformat(), "rs": round((ratio / base_ratio) * 100, 4)})

        metric_weights = {key: 1.0 for key in ("1w", "2w", "1m", "2m", "3m", "6m", "1y")}
        _, metrics = _weighted_relative_return_from_points(stock_points, benchmark_points, metric_weights)
        if not metrics:
            return None, None, metrics, benchmark_name, rs_chart

        universe_metrics, sector_by_symbol = _rs_universe_metrics(db, exchange, benchmark_points)
        for label in ("1w", "2w", "1m", "2m", "3m", "6m", "1y"):
            target_rr = (metrics.get(label) or {}).get("relative_return_percent")
            universe_values = [
                m[label]["relative_return_percent"]
                for m in universe_metrics.values()
                if label in m and m[label].get("relative_return_percent") is not None
            ]
            pct = _percentile_rank(universe_values, target_rr)
            if label in metrics:
                metrics[label]["percentile"] = pct
                metrics[label]["universe_size"] = len(universe_values)
                metrics[label]["score_weight_percent"] = weights.get(label, 0.0)

        # First calculate each stock's period-percentile composite (without sector).
        period_labels = ("1w", "2w", "1m", "2m", "3m", "6m", "1y")
        period_universe_values = {
            label: [
                m[label]["relative_return_percent"]
                for m in universe_metrics.values()
                if label in m and m[label].get("relative_return_percent") is not None
            ]
            for label in period_labels
        }

        stock_period_scores = {}
        for symbol, sym_metrics in universe_metrics.items():
            score_sum = 0.0
            score_weight = 0.0
            for label in period_labels:
                weight = weights.get(label, 0.0)
                if weight <= 0 or label not in sym_metrics:
                    continue
                rr = sym_metrics[label].get("relative_return_percent")
                pct = _percentile_rank(period_universe_values[label], rr)
                if pct is None:
                    continue
                score_sum += pct * weight
                score_weight += weight
            if score_weight > 0:
                stock_period_scores[symbol] = score_sum / score_weight

        # Sector RS Score = percentile rank of the target sector's average member RS
        # versus the average RS of all other represented sectors.
        sector_groups = {}
        for symbol, score in stock_period_scores.items():
            sector = sector_by_symbol.get(symbol)
            if sector:
                sector_groups.setdefault(sector, []).append(score)
        sector_scores = {sector: sum(vals) / len(vals) for sector, vals in sector_groups.items() if vals}

        target_symbol = daily_rows[-1].symbol if daily_rows else None
        target_sector = sector_by_symbol.get(target_symbol)
        target_sector_raw = sector_scores.get(target_sector) if target_sector else None
        sector_percentile = _percentile_rank(list(sector_scores.values()), target_sector_raw)
        metrics["sector"] = {
            "sector": target_sector,
            "score": round(target_sector_raw, 2) if target_sector_raw is not None else None,
            "percentile": sector_percentile,
            "universe_size": len(sector_scores),
            "score_weight_percent": weights.get("sector", 0.0),
        }

        weighted_score = 0.0
        available_weight = 0.0
        for label in period_labels:
            weight = weights.get(label, 0.0)
            pct = (metrics.get(label) or {}).get("percentile")
            if weight > 0 and pct is not None:
                weighted_score += pct * weight
                available_weight += weight
        # Latest client reference excludes Sector RS from the final RS score.
        # Sector percentile is retained only as optional informational output.

        if available_weight <= 0:
            return None, None, metrics, benchmark_name, rs_chart

        rating = round(weighted_score / available_weight, 2)
        # Diagnostic weighted relative return retained for display/API compatibility only.
        old_period_weights = {k: weights.get(k, 0.0) for k in period_labels}
        weighted_relative, _ = _weighted_relative_return_from_points(stock_points, benchmark_points, old_period_weights)
        metrics["_universe_size"] = len(universe_metrics)
        metrics["_score_weight_total"] = available_weight
        return rating, weighted_relative, metrics, benchmark_name, rs_chart
    except Exception:
        return None, None, {}, benchmark_name, []


def _normalize_score_weights(weights=None):
    defaults = {
        "technical": 35.0,
        "fundamental": 35.0,
        "relative_strength": 15.0,
        "ownership": 10.0,
    }
    if not weights:
        return defaults

    merged = {**defaults, **{k: max(0.0, float(v)) for k, v in weights.items() if k in defaults}}
    total = sum(merged.values())
    if total <= 0:
        return defaults
    return {k: (v / total) * 100.0 for k, v in merged.items()}


def _score_symbol(db: Session, symbol: str, exchange: str, weights=None, include_components=False, subweights=None, rs_period_weights=None):
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
    }

    closes = [float(row.close) for row in rows if row.close is not None]
    highs = [float(row.high) for row in rows if row.high is not None]
    lows = [float(row.low) for row in rows if row.low is not None]
    volumes = [float(row.volume or 0) for row in rows]

    if closes:
        latest = closes[-1]
        configured_subweights = subweights or {}
        technical_weights = configured_subweights.get("technical", {
            "ema20": 20, "ema50": 20, "ema150": 20, "ema200": 20, "rsi": 20,
        })
        technical_metrics = {}
        for period, key in [(20, "ema20"), (50, "ema50"), (150, "ema150"), (200, "ema200")]:
            ema = _ema(closes, period)
            if ema is not None:
                technical_metrics[key] = 100.0 if latest > ema else 0.0

        rsi = _rsi(closes, 14)
        if rsi is not None:
            technical_metrics["rsi"] = 100.0 if 50 <= rsi <= 70 else 50.0 if (40 <= rsi < 50 or 70 < rsi <= 80) else 0.0

        tw_sum = sum(max(0.0, float(technical_weights.get(k, 0))) for k in technical_metrics)
        if tw_sum > 0:
            components["technical"] = round(sum(technical_metrics[k] * max(0.0, float(technical_weights.get(k, 0))) for k in technical_metrics) / tw_sum, 2)

        # Keep dashboard RS aligned with the customizable Technical Summary model.
        rs_component, _, _, _, _ = _weighted_rs_against_benchmark(rows, exchange, rs_period_weights, db=db)
        if rs_component is not None:
            components["relative_strength"] = rs_component


    if fundamental:
        fundamental_weights = (subweights or {}).get("fundamental", {
            "eps": 20, "net_income": 20, "profit_margin": 20, "roe": 20, "roa": 20,
        })
        raw_checks = {
            "eps": (fundamental.trailing_eps, lambda x: x > 0),
            "net_income": (fundamental.net_income, lambda x: x > 0),
            "profit_margin": (fundamental.profit_margin, lambda x: x > 0),
            "roe": (fundamental.return_on_equity, lambda x: x >= 0.15),
            "roa": (fundamental.return_on_assets, lambda x: x >= 0.05),
        }
        fundamental_metrics = {}
        for key, (value, check) in raw_checks.items():
            if value is None:
                continue
            numeric = float(value)
            fundamental_metrics[key] = 100.0 if check(numeric) else (50.0 if numeric > 0 else 0.0)
        fw_sum = sum(max(0.0, float(fundamental_weights.get(k, 0))) for k in fundamental_metrics)
        if fw_sum > 0:
            components["fundamental"] = round(sum(fundamental_metrics[k] * max(0.0, float(fundamental_weights.get(k, 0))) for k in fundamental_metrics) / fw_sum, 2)

    if ownership:
        ownership_weights = (subweights or {}).get("ownership", {"institution": 70, "insider": 30})
        ownership_metrics = {}
        if ownership.institution_percent is not None:
            pct = float(ownership.institution_percent)
            if pct <= 1:
                pct *= 100
            ownership_metrics["institution"] = max(0, min(100, pct))
        if ownership.insider_percent is not None:
            pct = float(ownership.insider_percent)
            if pct <= 1:
                pct *= 100
            ownership_metrics["insider"] = max(0, min(100, pct * 5))
        ow_sum = sum(max(0.0, float(ownership_weights.get(k, 0))) for k in ownership_metrics)
        if ow_sum > 0:
            components["ownership"] = round(sum(ownership_metrics[k] * max(0.0, float(ownership_weights.get(k, 0))) for k in ownership_metrics) / ow_sum, 2)

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
    technical_ema20_weight: float = 20,
    technical_ema50_weight: float = 20,
    technical_ema150_weight: float = 20,
    technical_ema200_weight: float = 20,
    technical_rsi_weight: float = 20,
    fundamental_eps_weight: float = 20,
    fundamental_net_income_weight: float = 20,
    fundamental_profit_margin_weight: float = 20,
    fundamental_roe_weight: float = 20,
    fundamental_roa_weight: float = 20,
    ownership_institution_weight: float = 70,
    ownership_insider_weight: float = 30,
    rs_1w_weight: float = 30,
    rs_2w_weight: float = 0,
    rs_1m_weight: float = 25,
    rs_2m_weight: float = 0,
    rs_3m_weight: float = 20,
    rs_6m_weight: float = 15,
    rs_1y_weight: float = 10,
    rs_sector_weight: float = 0,
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
    }
    ranking_subweights = {
        "technical": {"ema20": technical_ema20_weight, "ema50": technical_ema50_weight, "ema150": technical_ema150_weight, "ema200": technical_ema200_weight, "rsi": technical_rsi_weight},
        "fundamental": {"eps": fundamental_eps_weight, "net_income": fundamental_net_income_weight, "profit_margin": fundamental_profit_margin_weight, "roe": fundamental_roe_weight, "roa": fundamental_roa_weight},
        "ownership": {"institution": ownership_institution_weight, "insider": ownership_insider_weight},
    }
    rs_period_weights = {"1w": rs_1w_weight, "2w": rs_2w_weight, "1m": rs_1m_weight, "2m": rs_2m_weight, "3m": rs_3m_weight, "6m": rs_6m_weight, "1y": rs_1y_weight, "sector": rs_sector_weight}
    score, coverage, components, normalized_weights = _score_symbol(
        db, symbol, exchange, weights=requested_weights, include_components=True,
        subweights=ranking_subweights, rs_period_weights=rs_period_weights
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
        "ranking_subweights": ranking_subweights,
        "rs_period_weights": rs_period_weights,
        "sector": company.sector if company else None,
        "industry": company.industry if company else None,
        "sector_rank": sector_rank,
        "industry_rank": industry_rank,
        "method_note": "Overall score combines Technical, Fundamental, Ownership, and Relative Strength categories. Breakout/VCP remains available as technical analysis but is not a separate final-ranking category. For NSE/BSE, a score is withheld when a positively weighted fundamental or ownership category is unavailable, rather than producing a misleading partial ranking."
    })


@router.get("/ownership-details/{symbol}")
def get_ownership_details(symbol: str, exchange: str = "US"):
    try:
        provider = YahooProvider()
        return provider.get_ownership_details(symbol.upper(), exchange.upper())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ownership details failed: {str(e)}")


@router.get("/india-shareholding/{symbol}")
def get_india_shareholding(symbol: str, exchange: str = "NSE", limit: int = 8):
    exchange = exchange.upper()
    if exchange not in {"NSE", "BSE"}:
        raise HTTPException(status_code=400, detail="Indian shareholding supports NSE/BSE symbols only")
    try:
        provider = IndiaShareholdingProvider()
        return _json_safe(provider.get_history(symbol.upper(), limit=limit))
    except Exception as e:
        # Keep a clean 503 instead of turning a third-party provider outage into
        # a generic 500 that makes the whole dashboard look broken.
        raise HTTPException(status_code=503, detail=f"Indian shareholding data unavailable: {str(e)}")


@router.get("/technical-summary/{symbol}")
def get_technical_summary(
    symbol: str,
    exchange: str = "US",
    timeframe: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    rs_1w_weight: float = 30,
    rs_2w_weight: float = 0,
    rs_1m_weight: float = 25,
    rs_2m_weight: float = 0,
    rs_3m_weight: float = 20,
    rs_6m_weight: float = 15,
    rs_1y_weight: float = 10,
    rs_sector_weight: float = 0,
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

    avg_volume_10 = sum(volumes[-10:]) / 10 if len(volumes) >= 10 else None
    avg_volume_20 = sum(volumes[-20:]) / 20
    avg_volume_40 = sum(volumes[-40:]) / 40 if len(volumes) >= 40 else None
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

    # Handwritten client ranking factors compare short ATR% averages with a
    # 20-period ATR% average.  Expose the raw comparable values so the UI can
    # score exactly those factors without inventing hidden inputs.
    atr_percent_series = [
        (true_ranges[i] / closes[i] * 100) if closes[i] else None
        for i in range(len(true_ranges))
    ]
    def _tail_average(values, period):
        usable = [v for v in values[-period:] if v is not None]
        return (sum(usable) / len(usable)) if len(usable) == period else None

    avg_atr_percent_5 = _tail_average(atr_percent_series, 5)
    avg_atr_percent_10 = _tail_average(atr_percent_series, 10)
    avg_atr_percent_20 = _tail_average(atr_percent_series, 20)
    rsi14 = _rsi(closes, 14)

    recent20 = closes[-20:]
    sma20 = sum(recent20) / 20
    variance20 = sum((x - sma20) ** 2 for x in recent20) / 20
    sd20 = variance20 ** 0.5
    bb_upper = sma20 + 2 * sd20
    bb_lower = sma20 - 2 * sd20
    # Client-specified Bollinger Band width formula:
    # (Upper BB - Lower BB) * 100 / Lower BB
    bb_width = ((bb_upper - bb_lower) / bb_lower * 100) if bb_lower not in (None, 0) else None

    range20 = ((max(highs[-20:]) - min(lows[-20:])) / min(lows[-20:]) * 100) if min(lows[-20:]) else None

    # Daily rolling metric series requested by the client so ADR%, ATR%,
    # Bollinger width %, and 20-day price range can be drawn as trends.
    metric_daily = daily_rows
    metric_series = []
    daily_trs = []
    running_atr = None
    for i, r in enumerate(metric_daily):
        h = float(r.high)
        l = float(r.low)
        c = float(r.close)
        prev_c = float(metric_daily[i - 1].close) if i > 0 else c
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        daily_trs.append(tr)
        if i == 13:
            running_atr = sum(daily_trs[:14]) / 14
        elif i > 13 and running_atr is not None:
            running_atr = ((running_atr * 13) + tr) / 14

        if i < 19:
            continue

        window = metric_daily[i - 19:i + 1]
        closes20 = [float(x.close) for x in window]
        highs20 = [float(x.high) for x in window]
        lows20 = [float(x.low) for x in window]
        adr_pct_values = [
            ((float(x.high) - float(x.low)) / float(x.low)) * 100
            for x in window if float(x.low) != 0
        ]
        adr_pct_20 = (sum(adr_pct_values) / len(adr_pct_values)) if adr_pct_values else None

        mean20 = sum(closes20) / 20
        variance = sum((v - mean20) ** 2 for v in closes20) / 20
        sd = variance ** 0.5
        upper = mean20 + 2 * sd
        lower = mean20 - 2 * sd
        bb_pct = ((upper - lower) / lower * 100) if lower else None
        price_range_pct = ((max(highs20) - min(lows20)) / min(lows20) * 100) if min(lows20) else None
        atr_pct_day = (running_atr / c * 100) if running_atr is not None and c else None

        metric_series.append({
            "date": r.date.isoformat() if hasattr(r.date, "isoformat") else str(r.date),
            "adr_percent": round(adr_pct_20, 2) if adr_pct_20 is not None else None,
            "atr_percent": round(atr_pct_day, 2) if atr_pct_day is not None else None,
            "bollinger_width_percent": round(bb_pct, 2) if bb_pct is not None else None,
            "range_20d_percent": round(price_range_pct, 2) if price_range_pct is not None else None,
        })
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

    rs_period_weights = {"1w": rs_1w_weight, "2w": rs_2w_weight, "1m": rs_1m_weight, "2m": rs_2m_weight, "3m": rs_3m_weight, "6m": rs_6m_weight, "1y": rs_1y_weight, "sector": rs_sector_weight}
    rs_rating, rs_weighted_relative_return, rs_metrics, benchmark_name, rs_chart = _weighted_rs_against_benchmark(daily_rows, exchange, rs_period_weights, db=db)

    return _json_safe({
        "symbol": symbol,
        "exchange": exchange,
        "timeframe": timeframe,
        "ema": {key: (round(value, 2) if value is not None else None) for key, value in emas.items()},
        "ema_alignment": ema_alignment,
        "average_volume_10": round(avg_volume_10, 2) if avg_volume_10 is not None else None,
        "average_volume_20": round(avg_volume_20, 2),
        "average_volume_40": round(avg_volume_40, 2) if avg_volume_40 is not None else None,
        "average_volume_50": round(avg_volume_50, 2) if avg_volume_50 is not None else None,
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "volume_ratio_50": round(volume_ratio_50, 2) if volume_ratio_50 is not None else None,
        "adr_20": round(adr_value, 2) if adr_value is not None else None,
        "adr_percent": round(adr_percent, 2) if adr_percent is not None else None,
        "atr_14": round(atr14, 2) if atr14 is not None else None,
        "atr_percent": round(atr_percent, 2) if atr_percent is not None else None,
        "average_atr_percent_5": round(avg_atr_percent_5, 2) if avg_atr_percent_5 is not None else None,
        "average_atr_percent_10": round(avg_atr_percent_10, 2) if avg_atr_percent_10 is not None else None,
        "average_atr_percent_20": round(avg_atr_percent_20, 2) if avg_atr_percent_20 is not None else None,
        "rsi_14": round(rsi14, 2) if rsi14 is not None else None,
        "bollinger_width_percent": round(bb_width, 2) if bb_width is not None else None,
        "range_20d_percent": round(range20, 2) if range20 is not None else None,
        "technical_metric_series": metric_series[-260:],
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
        "rs_available": rs_rating is not None and len(rs_chart) > 1,
        "rs_weighted_relative_return_percent": round(rs_weighted_relative_return, 2) if rs_weighted_relative_return is not None else None,
        "rs_benchmark": benchmark_name,
        "rs_periods": rs_metrics,
        "rs_chart": rs_chart,
        "rs_period_weights": rs_period_weights,
        "rs_note": "Relative Strength: each period relative return = stock return % - benchmark return %. Each period is converted to the client percentile [(lower stocks + 0.5 x equal stocks) x 100 / total]. Final RS Score follows the latest handwritten reference: 1W x 30% + 1M x 25% + 3M x 20% + 6M x 15% + 12M x 10%. 2W/2M are optional custom periods with zero default weight. Sector RS is informational and is not included in the final RS score.",
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