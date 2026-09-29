from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import SessionLocal
from app.models import Company
from app.services.company_sync import sync_companies
from app.services.nse_company_provider import NSECompanyProvider
from app.services.us_company_provider import USCompanyProvider
from app.services.company_auto_sync import sync_all_companies


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

    rows = (
        query
        .filter(Company.is_active == 1)
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
