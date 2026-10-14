"""Persisted paper portfolios. No broker orders or sample holdings are created."""
import uuid
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.api.market import get_db, _market_rows_with_live_fallback
from app.models import Portfolio, PortfolioTrade, PortfolioValuation
from app.services.portfolio import money, positions_from_trades

router = APIRouter(prefix="/portfolios", tags=["Paper portfolio"])


class PortfolioInput(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    currency: Literal["USD", "INR"] = "USD"
    inception_date: date
    starting_capital: float = Field(gt=0, le=1e12, allow_inf_nan=False)
    max_position_percent: float = Field(default=25, gt=0, le=100, allow_inf_nan=False)
    max_exposure_percent: float = Field(default=90, gt=0, le=100, allow_inf_nan=False)
    risk_percent: float = Field(default=2, gt=0, le=100, allow_inf_nan=False)
    commission_bps: float = Field(default=0, ge=0, le=1000, allow_inf_nan=False)


class TradeInput(BaseModel):
    request_id: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=30, pattern=r"^[A-Za-z0-9.^/-]+$")
    exchange: Literal["US", "NSE", "BSE"]
    side: Literal["BUY", "SELL"]
    date: date
    quantity: int = Field(gt=0, le=100000000)
    stop_percent: float = Field(default=10, gt=0, lt=100, allow_inf_nan=False)


@router.get("")
def list_portfolios(db: Session = Depends(get_db)):
    return [{"id": p.id, "name": p.name, "currency": p.currency, "inception_date": str(p.inception_date)} for p in db.query(Portfolio).order_by(Portfolio.created_at).all()]


@router.post("", status_code=201)
def create_portfolio(body: PortfolioInput, db: Session = Depends(get_db)):
    if body.inception_date > date.today():
        raise HTTPException(400, "Inception date cannot be in the future")
    capital = money(body.starting_capital)
    if capital <= 0:
        raise HTTPException(400, "Capital must be at least 0.01")
    record = Portfolio(id=uuid.uuid4().hex, **body.model_dump(exclude={"starting_capital"}), starting_capital=capital, cash=capital)
    db.add(record)
    db.add(PortfolioValuation(portfolio_id=record.id, date=record.inception_date, equity=capital, cash=capital))
    db.commit()
    return {"id": record.id, "mode": "Paper portfolio", "cash": record.cash}


def load_portfolio(db, identifier, lock=False):
    query = db.query(Portfolio).filter_by(id=identifier)
    record = (query.with_for_update() if lock else query).first()
    if not record:
        raise HTTPException(404, "Portfolio not found")
    return record


@router.post("/{identifier}/trades", status_code=201)
def add_trade(identifier: str, body: TradeInput, db: Session = Depends(get_db)):
    body.symbol = body.symbol.upper()
    record = load_portfolio(db, identifier, lock=True)
    existing = db.query(PortfolioTrade).filter_by(portfolio_id=identifier, request_id=body.request_id).first()
    if existing:
        if any(getattr(existing, k) != getattr(body, k) for k in ("symbol", "exchange", "side", "date", "quantity")) or (existing.side == "BUY" and abs(existing.initial_stop - existing.price * (1 - body.stop_percent / 100)) > 1e-8):
            raise HTTPException(409, "Request ID was already used for a different trade")
        return {"id": existing.id, "cash": record.cash, "duplicate": True}
    trades = db.query(PortfolioTrade).filter_by(portfolio_id=identifier).order_by(PortfolioTrade.sequence).all()
    if body.date > date.today() or body.date < record.inception_date or (trades and body.date < trades[-1].date):
        raise HTTPException(400, "Trade date must be on or after inception/latest trade and cannot be in the future")
    if (body.exchange == "US") != (record.currency == "USD"):
        raise HTTPException(400, "Trade market must match portfolio currency; no inferred FX conversion")
    rows = _market_rows_with_live_fallback(db, body.symbol.upper(), body.exchange, min_rows=1, years=20)
    row = next((r for r in rows if r.date == body.date), None)
    if row is None:
        raise HTTPException(422, "No verified daily close exists on this trade date")
    price = float(row.close)
    cost = money(price * body.quantity)
    fee = money(cost * record.commission_bps / 10000)
    positions = positions_from_trades(trades)
    key = (body.exchange, body.symbol.upper())
    position = positions.get(key, {"quantity": 0, "cost": 0})
    realized, stop = 0, None
    if body.side == "BUY":
        if cost + fee > record.cash:
            raise HTTPException(409, "Insufficient cash")
        # Price all current positions using only observations <= the trade date.
        values = {}
        for (exchange, symbol), holding in positions.items():
            history = rows if (exchange, symbol) == key else _market_rows_with_live_fallback(db, symbol, exchange, min_rows=1, years=20)
            past = [r for r in history if r.date <= body.date]
            if not past:
                raise HTTPException(422, "Position valuation unavailable on trade date")
            values[(exchange, symbol)] = holding["quantity"] * float(past[-1].close)
        equity = record.cash + sum(values.values())
        if values.get(key, 0) + cost > equity * record.max_position_percent / 100 + .005:
            raise HTTPException(409, "Position concentration limit exceeded")
        if sum(values.values()) + cost > equity * record.max_exposure_percent / 100 + .005:
            raise HTTPException(409, "Portfolio exposure limit exceeded")
        if (values.get(key, 0) + cost) * body.stop_percent / 100 > equity * record.risk_percent / 100 + .005:
            raise HTTPException(409, "Position risk limit exceeded")
        stop = price * (1 - body.stop_percent / 100)
        record.cash = money(record.cash - cost - fee)
    else:
        if body.quantity > position["quantity"]:
            raise HTTPException(409, "Cannot sell more than the open quantity")
        realized = money(cost - fee - position["cost"] / position["quantity"] * body.quantity)
        record.cash = money(record.cash + cost - fee)
    trade = PortfolioTrade(id=uuid.uuid4().hex, portfolio_id=identifier, sequence=len(trades) + 1, **body.model_dump(exclude={"stop_percent", "symbol"}), symbol=body.symbol.upper(), price=price, fee=fee, initial_stop=stop, realized_pnl=realized)
    db.add(trade)
    db.commit()
    return {"id": trade.id, "cash": record.cash, "price": price, "fee": fee, "realized_pnl": realized, "mode": "Paper trade at verified daily close; stops are recorded, not broker orders"}


@router.get("/{identifier}")
def portfolio_summary(identifier: str, db: Session = Depends(get_db)):
    record = load_portfolio(db, identifier)
    trades = db.query(PortfolioTrade).filter_by(portfolio_id=identifier).order_by(PortfolioTrade.sequence).all()
    positions = positions_from_trades(trades)
    output, complete = [], True
    for (exchange, symbol), holding in positions.items():
        try:
            history = [r for r in _market_rows_with_live_fallback(db, symbol, exchange, min_rows=1, years=2) if r.date <= date.today()]
            latest = history[-1] if history else None
        except Exception:
            latest = None
        value = money(latest.close * holding["quantity"]) if latest else None
        complete = complete and latest is not None
        output.append({"symbol": symbol, "exchange": exchange, **holding, "average_entry": holding["cost"] / holding["quantity"], "price": float(latest.close) if latest else None, "price_date": str(latest.date) if latest else None, "value": value, "unrealized_pnl": money(value - holding["cost"]) if value is not None else None})
    equity = money(record.cash + sum(p["value"] for p in output)) if complete else None
    if complete:
        valuation = db.query(PortfolioValuation).filter_by(portfolio_id=identifier, date=date.today()).first()
        if valuation is None:
            valuation = PortfolioValuation(portfolio_id=identifier, date=date.today())
            db.add(valuation)
        valuation.equity, valuation.cash = equity, record.cash
        db.commit()
    history = db.query(PortfolioValuation).filter_by(portfolio_id=identifier).order_by(PortfolioValuation.date).all()
    return {"id": record.id, "name": record.name, "currency": record.currency, "inception_date": str(record.inception_date), "mode": "Paper portfolio", "starting_capital": record.starting_capital, "cash": record.cash, "equity": equity, "realized_pnl": money(sum(t.realized_pnl for t in trades)), "unrealized_pnl": money(sum(p["unrealized_pnl"] for p in output)) if complete else None, "return_percent": (equity / record.starting_capital - 1) * 100 if equity is not None else None, "exposure_percent": (equity - record.cash) / equity * 100 if equity else None, "positions": output, "trades": [{k: (str(getattr(t, k)) if k == "date" else getattr(t, k)) for k in ("id", "date", "symbol", "exchange", "side", "quantity", "price", "fee", "realized_pnl")} for t in trades], "equity_history": [{"date": str(v.date), "equity": v.equity, "cash": v.cash} for v in history], "history_note": "Persisted observed valuations only; no invented daily equity history. Marks identify each price date. Stops are informational until an explicit sell is recorded.", "status": "Available" if complete else "Partial: missing position prices", "limits": {k: getattr(record, k) for k in ("max_position_percent", "max_exposure_percent", "risk_percent", "commission_bps")}}
