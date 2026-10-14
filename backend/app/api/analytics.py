from datetime import date, timedelta
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.market import get_db, _market_rows_with_live_fallback, _load_benchmark_points, _json_safe
from app.services.risk_metrics import beta_batch
from app.services.providers.yahoo_provider import YahooProvider
import time
_benchmark_cache = {}

def backtest_benchmark(exchange):
    symbol = "^GSPC" if exchange == "US" else "^CRSLDX"
    cached = _benchmark_cache.get(symbol)
    if cached and time.time() - cached[0] < 3600:
        return cached[1], symbol
    try:
        rows = YahooProvider().get_ohlcv(symbol, "US", start_date=str(date.today()-timedelta(days=366*20+120)), end_date=str(date.today()+timedelta(days=1)))
    except Exception:
        rows = []
    _benchmark_cache[symbol] = (time.time(), rows)
    return rows, symbol
from app.services.trade_backtest import simulate, HistoricalDataUnavailable

router = APIRouter(prefix="/market", tags=["Historical strategy"])


@router.get("/risk-metrics/{symbol}")
def risk_metrics(symbol: str, exchange: Literal["US", "NSE", "BSE"] = "US"):
    result = beta_batch([{"exchange": exchange, "symbol": symbol.upper()}])
    return {"symbol": symbol.upper(), "exchange": exchange, **result[(exchange, symbol.upper())]}


class BacktestInput(BaseModel):
    exchange: Literal["US", "NSE", "BSE"] = "US"
    start_date: date
    end_date: date
    components: list[Literal["technical", "relative_strength", "fundamental", "ownership"]] = ["technical"]
    starting_capital: float = Field(default=100000, gt=0, le=1e12, allow_inf_nan=False)
    allocation_percent: float = Field(default=25, gt=0, le=100, allow_inf_nan=False)
    risk_percent: float = Field(default=2, gt=0, le=100, allow_inf_nan=False)
    initial_stop_percent: float = Field(default=10, gt=0, lt=100, allow_inf_nan=False)
    trailing_stop_percent: float = Field(default=10, gt=0, lt=100, allow_inf_nan=False)
    ema_period: int = Field(default=50, ge=2, le=500)
    ema_stop: bool = False
    rs_lookback: int = Field(default=63, ge=5, le=252)
    commission_bps: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)
    slippage_bps: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)


@router.post("/trade-backtest/{symbol}")
def trade_backtest(symbol: str, body: BacktestInput, db: Session = Depends(get_db)):
    if body.start_date >= body.end_date or body.end_date > date.today() or body.start_date < date.today() - timedelta(days=366 * 20 + 30):
        raise HTTPException(400, "Choose a valid range within the last 20 years, ending no later than today")
    if set(body.components) & {"fundamental", "ownership"}:
        raise HTTPException(422, "BLOCKED: verified historical announcement-time financial statements / published ownership are not configured. Current snapshots cannot be used for historical qualification.")
    try:
        rows = _market_rows_with_live_fallback(db, symbol.upper(), body.exchange, min_rows=5200, years=20)
        normalized = [{k: getattr(r, k) for k in ("date", "open", "high", "low", "close", "volume")} for r in rows]
        benchmarks, benchmark_symbol = backtest_benchmark(body.exchange)
        result = simulate(normalized, benchmarks, body.model_dump())
        return _json_safe({"symbol": symbol.upper(), "exchange": body.exchange, "benchmark": benchmark_symbol, **result})
    except (HistoricalDataUnavailable, ValueError) as exc:
        raise HTTPException(422, str(exc))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, "Verified historical provider data is unavailable; retry later")
