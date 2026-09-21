from app.models import OHLCV

from fastapi import APIRouter, Depends, HTTPException
from fastapi import Query
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.services.providers.yahoo_provider import YahooProvider
from app.services.ohlcv_sync import sync_ohlcv
from app.services.fundamental_sync import sync_fundamental_data
from app.models import Fundamental, Ownership
from app.services.providers.bse_provider import BSEProvider

router = APIRouter(prefix="/market", tags=["market"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


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
    gains = []
    losses = []

    for i in range(-rsi_period, 0):
        change = closes[i] - closes[i - 1]

        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))

    avg_gain = sum(gains) / rsi_period
    avg_loss = sum(losses) / rsi_period

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