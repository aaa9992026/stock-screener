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
import requests
from datetime import datetime, timedelta, date
import yfinance as yf

router = APIRouter(prefix="/market", tags=["market"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ema(values, period):
    if len(values) < period:
        return None
    multiplier = 2 / (period + 1)
    value = sum(values[:period]) / period
    for price in values[period:]:
        value = ((price - value) * multiplier) + value
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


def _score_symbol(db: Session, symbol: str, exchange: str):
    rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol, OHLCV.exchange == exchange)
        .order_by(OHLCV.date.asc())
        .all()
    )
    fundamental = (
        db.query(Fundamental)
        .filter(Fundamental.symbol == symbol, Fundamental.exchange == exchange)
        .first()
    )

    points = 0.0
    possible = 0.0
    closes = [float(row.close) for row in rows if row.close is not None]

    if closes:
        latest = closes[-1]
        for period, weight in [(20, 8), (50, 8), (150, 7), (200, 7)]:
            ema = _ema(closes, period)
            if ema is not None:
                possible += weight
                if latest > ema:
                    points += weight

        rsi = _rsi(closes, 14)
        if rsi is not None:
            possible += 10
            if 50 <= rsi <= 70:
                points += 10
            elif 40 <= rsi < 50 or 70 < rsi <= 80:
                points += 5

        if len(closes) >= 60:
            possible += 10
            low = min(closes[-60:])
            high = max(closes[-60:])
            if high > low:
                position = (latest - low) / (high - low)
                points += max(0, min(10, position * 10))

    if fundamental:
        checks = [
            (fundamental.trailing_eps, lambda x: x > 0, 10),
            (fundamental.net_income, lambda x: x > 0, 10),
            (fundamental.profit_margin, lambda x: x > 0, 10),
            (fundamental.return_on_equity, lambda x: x >= 0.15, 10),
            (fundamental.return_on_assets, lambda x: x >= 0.05, 10),
        ]
        for value, check, weight in checks:
            if value is not None:
                possible += weight
                if check(float(value)):
                    points += weight
                elif float(value) > 0:
                    points += weight * 0.5

    if possible == 0:
        return None, 0

    score = round((points / possible) * 100)
    coverage = round((possible / 100) * 100)
    return max(0, min(100, score)), max(0, min(100, coverage))


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
                start_date="2025-01-01"
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
    limit: int = 100,
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
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    exchange = exchange.upper()

    company = (
        db.query(Company)
        .filter(Company.symbol == symbol, Company.exchange == exchange)
        .first()
    )

    score, coverage = _score_symbol(db, symbol, exchange)
    if score is None:
        raise HTTPException(status_code=404, detail="Not enough data to calculate dashboard score")

    if score >= 70:
        signal = "Buy"
    elif score >= 45:
        signal = "Watch"
    else:
        signal = "Sell"

    sector_rank = _rank_within(db, company, "sector") if company else None
    industry_rank = _rank_within(db, company, "industry") if company else None

    return {
        "symbol": symbol,
        "exchange": exchange,
        "score": score,
        "signal": signal,
        "score_coverage_percent": coverage,
        "sector": company.sector if company else None,
        "industry": company.industry if company else None,
        "sector_rank": sector_rank,
        "industry_rank": industry_rank,
        "method_note": "Rule-based score from available stored technical and fundamental data; rank coverage grows as peer data is populated."
    }


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
    db: Session = Depends(get_db)
):
    symbol = symbol.upper()
    exchange = exchange.upper()

    rows = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol, OHLCV.exchange == exchange)
        .order_by(OHLCV.date.asc())
        .all()
    )
    if len(rows) < 20:
        raise HTTPException(status_code=404, detail="Not enough historical data for technical summary")

    closes = [float(row.close) for row in rows]
    volumes = [float(row.volume or 0) for row in rows]
    ema_periods = [20, 30, 50, 100, 150, 200]
    emas = {str(period): (_ema(closes, period)) for period in ema_periods}

    available_emas = [emas[str(p)] for p in ema_periods if emas[str(p)] is not None]
    ema_alignment = "Unavailable"
    if len(available_emas) == len(ema_periods):
        bullish = all(available_emas[i] > available_emas[i + 1] for i in range(len(available_emas) - 1))
        bearish = all(available_emas[i] < available_emas[i + 1] for i in range(len(available_emas) - 1))
        if bullish:
            ema_alignment = "Bullish"
        elif bearish:
            ema_alignment = "Bearish"
        else:
            ema_alignment = "Mixed"

    avg_volume_20 = sum(volumes[-20:]) / 20
    volume_ratio = (volumes[-1] / avg_volume_20) if avg_volume_20 else None

    adr_values = []
    for row in rows[-20:]:
        if row.close not in (None, 0) and row.high is not None and row.low is not None:
            adr_values.append(((float(row.high) - float(row.low)) / float(row.close)) * 100)
    adr = sum(adr_values) / len(adr_values) if adr_values else None

    previous = rows[-21:-1] if len(rows) >= 21 else rows[:-1]
    previous_high = max((float(row.high) for row in previous if row.high is not None), default=None)
    latest_close = closes[-1]
    if previous_high is None:
        breakout_status = "Unavailable"
    elif latest_close > previous_high:
        breakout_status = "Breakout"
    elif latest_close >= previous_high * 0.97:
        breakout_status = "Near Breakout"
    else:
        breakout_status = "No Breakout"

    recent10 = rows[-10:]
    prior20 = rows[-30:-10] if len(rows) >= 30 else []
    def avg_range_percent(items):
        vals = []
        for row in items:
            if row.close not in (None, 0) and row.high is not None and row.low is not None:
                vals.append(((float(row.high) - float(row.low)) / float(row.close)) * 100)
        return sum(vals) / len(vals) if vals else None

    recent_range = avg_range_percent(recent10)
    prior_range = avg_range_percent(prior20)
    recent_volume = sum(float(row.volume or 0) for row in recent10) / len(recent10) if recent10 else None
    prior_volume = sum(float(row.volume or 0) for row in prior20) / len(prior20) if prior20 else None
    vcp_stage = "Not Detected"
    if recent_range is not None and prior_range is not None and recent_volume is not None and prior_volume not in (None, 0):
        if recent_range < prior_range * 0.8 and recent_volume < prior_volume * 0.85:
            vcp_stage = "Possible VCP"

    if breakout_status == "Breakout":
        pattern = "20-Day Breakout"
    elif breakout_status == "Near Breakout":
        pattern = "Near 20-Day High"
    elif recent_range is not None and recent_range < 2.5:
        pattern = "Tight Consolidation"
    else:
        pattern = "None"

    rs_rating, rs_universe = _stored_rs_rating(db, symbol, exchange)

    return {
        "symbol": symbol,
        "exchange": exchange,
        "ema": {key: (round(value, 2) if value is not None else None) for key, value in emas.items()},
        "ema_alignment": ema_alignment,
        "average_volume_20": round(avg_volume_20, 2),
        "volume_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        "adr_percent": round(adr, 2) if adr is not None else None,
        "breakout_status": breakout_status,
        "vcp_stage": vcp_stage,
        "pattern": pattern,
        "rs_rating": rs_rating,
        "rs_universe_size": rs_universe,
        "rs_minimum_universe": 20,
        "rs_note": (
            "RS rating is shown only when at least 20 symbols have sufficient stored history."
            if rs_rating is None
            else "RS rating is a percentile within symbols that currently have sufficient stored history in this deployment."
        )
    }


@router.get("/benchmark/{exchange}")
def get_benchmark(
    exchange: str,
    limit: int = 100
):
    try:
        exchange = exchange.upper()

        if exchange == "US":
            ticker_symbol = "SPY"
            benchmark_name = "S&P 500"

        elif exchange in ["NSE", "BSE"]:
            ticker_symbol = "MONIFTY500"
            benchmark_name = "NIFTY 500 Proxy"

            api_key = os.getenv("TWELVE_DATA_API_KEY")

            response = requests.get(
                "https://api.twelvedata.com/time_series",
                params={
                    "symbol": "MONIFTY500",
                    "interval": "1day",
                    "outputsize": limit,
                    "apikey": api_key,
                },
                timeout=20,
            )

            payload = response.json()

            if payload.get("status") == "error":
                return {
                    "name": benchmark_name,
                    "symbol": ticker_symbol,
                    "data": [],
                    "warning": "NIFTY 500 benchmark data is not available from the currently configured provider."
                }

            values = payload.get("values", [])

            benchmark_data = [
                {
                    "date": item["datetime"],
                    "close": float(item["close"])
                }
                for item in reversed(values)
            ]

            return {
                "name": benchmark_name,
                "symbol": ticker_symbol,
                "data": benchmark_data
            }

        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported exchange"
            )

        api_key = os.getenv("TWELVE_DATA_API_KEY")

        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="TWELVE_DATA_API_KEY is not configured"
            )

        response = requests.get(
            "https://api.twelvedata.com/time_series",
            params={
                "symbol": ticker_symbol,
                "exchange": "NSE" if exchange in ["NSE", "BSE"] else None,
                "interval": "1day",
                "outputsize": limit,
                "apikey": api_key,
            },
            timeout=20,
        )

        response.raise_for_status()

        payload = response.json()

        if payload.get("status") == "error":
            raise HTTPException(
                status_code=502,
                detail=payload.get("message", "Benchmark provider error")
            )

        values = payload.get("values", [])

        benchmark_data = [
            {
                "date": item["datetime"],
                "close": float(item["close"])
            }
            for item in reversed(values)
        ]

        return {
            "name": benchmark_name,
            "symbol": ticker_symbol,
            "data": benchmark_data
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Benchmark data failed: {str(e)}"
        )

@router.get("/chart/{symbol}")
def get_chart_data(
    symbol: str,
    exchange: str = "US",
    timeframe: str = Query("daily", pattern="^(daily|weekly|monthly)$"),
    limit: int = 100,
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
        df = df.set_index("date")

        rule = "W" if timeframe == "weekly" else "ME"

        df = df.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum"
        }).dropna()

        df = df.reset_index()

        result = df.to_dict(orient="records")

    return {
        "symbol": symbol.upper(),
        "exchange": exchange.upper(),
        "timeframe": timeframe,
        "count": len(result[-limit:]),
        "data": result[-limit:]
    }

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