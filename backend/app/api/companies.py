from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Company
from app.services.company_sync import sync_companies
from app.services.nse_company_provider import NSECompanyProvider
from app.services.us_company_provider import USCompanyProvider
from app.services.company_auto_sync import sync_all_companies
from app.services.equity_filters import apply_eligible_equity_filter, deactivate_legacy_us_non_equities
from app.services.universe_data_backfill import (
    backfill_all_fundamentals_once,
    backfill_market_fundamentals,
    normalize_data_market,
    universe_data_status,
)
from app.services.rs_universe_backfill import (
    backfill_all_markets_once,
    backfill_market_batch,
    normalize_market,
    universe_backfill_status,
)


router = APIRouter(prefix="/companies", tags=["companies"])


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.get("/search")
def search_companies(
    q: str = Query("", min_length=0),
    exchange: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(Company)

    if exchange:
        query = query.filter(
            Company.exchange == exchange.upper()
        )

    if q:
        pattern = f"%{q.upper()}%"
        query = query.filter(
            (Company.symbol.ilike(pattern)) |
            (Company.name.ilike(f"%{q}%"))
        )

    query = query.filter(Company.is_active == 1)
    exchanges = [exchange.upper()] if exchange else ["US", "NSE", "BSE"]
    query = apply_eligible_equity_filter(query, exchanges)

    rows = (
        query
        .order_by(Company.symbol.asc())
        .limit(limit)
        .all()
    )

    return [
        {
            "symbol": row.symbol,
            "name": row.name,
            "exchange": row.exchange,
            "sector": row.sector,
            "industry": row.industry,
        }
        for row in rows
    ]

@router.post("/sync/nse")
def sync_nse_companies(
    db: Session = Depends(get_db)
):
    provider = NSECompanyProvider()
    companies = provider.get_companies()

    result = sync_companies(
        db=db,
        companies=companies
    )

    return {
        "status": "success",
        "exchange": "NSE",
        "received": len(companies),
        **result
    }

@router.post("/sync/us")
def sync_us_companies(
    db: Session = Depends(get_db)
):
    provider = USCompanyProvider()
    companies = provider.get_companies()

    result = sync_companies(
        db=db,
        companies=companies
    )

    return {
        "status": "success",
        "exchange": "US",
        "received": len(companies),
        **result
    }

@router.post("/sync/all")
def sync_all():
    result = sync_all_companies()

    return {
        "status": "success",
        "markets": result
    }

@router.post("/cleanup-us-equities")
def cleanup_us_equities(db: Session = Depends(get_db)):
    """Deactivate legacy warrants/units/SPAC rows without deleting history."""
    return {"status": "success", **deactivate_legacy_us_non_equities(db)}


@router.get("/data-backfill/status")
def data_backfill_status(
    market: str = Query("ALL", description="US, INDIA, NSE, BSE or ALL"),
    db: Session = Depends(get_db),
):
    try:
        normalized = normalize_data_market(market)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(exc))
    if normalized == "ALL":
        return {
            "US": universe_data_status(db, "US"),
            "INDIA": universe_data_status(db, "INDIA"),
        }
    return universe_data_status(db, normalized)


@router.post("/data-backfill/run")
def run_data_backfill(
    market: str = Query(..., description="US, INDIA, NSE or BSE"),
    batch_size: int = Query(8, ge=1, le=50),
):
    try:
        normalized = normalize_data_market(market)
        if normalized == "ALL":
            return backfill_all_fundamentals_once(batch_size=batch_size)
        return backfill_market_fundamentals(normalized, batch_size=batch_size)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/data-backfill/run-all")
def run_all_data_backfill(batch_size: int = Query(8, ge=1, le=50)):
    return backfill_all_fundamentals_once(batch_size=batch_size)


@router.get("/universe-status")
def universe_status(db: Session = Depends(get_db)):
    """Show active symbol-master coverage for the client-defined RS markets."""
    grouped = (
        db.query(Company.exchange, Company.is_active, func.count(Company.id))
        .group_by(Company.exchange, Company.is_active)
        .all()
    )
    counts = {}
    for exchange, is_active, count in grouped:
        counts.setdefault(exchange, {"active": 0, "inactive": 0})
        key = "active" if int(is_active or 0) == 1 else "inactive"
        counts[exchange][key] = int(count or 0)

    india_active = int((counts.get("NSE") or {}).get("active", 0)) + int((counts.get("BSE") or {}).get("active", 0))
    us_active = int((counts.get("US") or {}).get("active", 0))
    return {
        "US": {
            "target_rs_universe": 6000,
            "active_symbols": us_active,
            "exchanges": ["US"],
            "symbol_master": "Nasdaq Trader listed-security files",
        },
        "INDIA": {
            "target_rs_universe": 5500,
            "active_symbols": india_active,
            "exchanges": ["NSE", "BSE"],
            "symbol_master": "NSE official equity list; BSE remains limited until a BSE symbol-master feed is configured",
        },
        "by_exchange": counts,
        "automatic_sync": {
            "interval_hours": 24,
            "new_listings": "added/reactivated on provider sync",
            "delistings": "marked inactive on a trustworthy provider snapshot; historical rows are retained",
        },
    }


@router.get("/rs-backfill/status")
def rs_backfill_status(
    market: str | None = None,
    db: Session = Depends(get_db),
):
    """Show real-history readiness for the client-defined RS universes."""
    if market:
        try:
            return universe_backfill_status(db, normalize_market(market))
        except ValueError as exc:
            from fastapi import HTTPException
            raise HTTPException(status_code=400, detail=str(exc))
    return {
        "US": universe_backfill_status(db, "US"),
        "INDIA": universe_backfill_status(db, "INDIA"),
    }


@router.post("/rs-backfill/run")
def run_rs_backfill(
    market: str = Query(..., description="US or INDIA"),
    batch_size: int = Query(25, ge=1, le=100),
):
    """Run one bounded/resumable RS-history backfill batch."""
    try:
        return backfill_market_batch(normalize_market(market), batch_size=batch_size)
    except ValueError as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/rs-backfill/run-all")
def run_all_rs_backfill(
    batch_size: int = Query(25, ge=1, le=100),
):
    """Run one bounded batch for both US and India."""
    return backfill_all_markets_once(batch_size=batch_size)
