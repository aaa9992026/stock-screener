"""Incremental enrichment of current screener fundamentals/ownership.

The stock-universe screener intentionally never fabricates missing values.  To
reduce N/A cells over time, this service fills real provider data in small,
resumable batches.  It is separate from the RS OHLCV backfill because current
fundamentals and ownership have different provider/rate-limit characteristics.
"""

from datetime import datetime, timedelta
import logging

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Company, Fundamental, Ownership, OHLCV
from app.services.equity_filters import apply_eligible_equity_filter
from app.services.fundamental_sync import sync_fundamental_data
from app.services.providers.yahoo_provider import YahooProvider

logger = logging.getLogger(__name__)


def normalize_data_market(market: str) -> str:
    value = str(market or "").strip().upper()
    if value in {"IN", "INDIA"}:
        return "INDIA"
    if value in {"NSE", "BSE"}:
        return value
    if value == "US":
        return "US"
    if value in {"ALL", ""}:
        return "ALL"
    raise ValueError("market must be US, INDIA, NSE, BSE or ALL")


def _exchanges_for_market(market: str):
    market = normalize_data_market(market)
    if market == "US":
        return ["US"]
    if market == "INDIA":
        return ["NSE", "BSE"]
    if market == "NSE":
        return ["NSE"]
    if market == "BSE":
        return ["BSE"]
    return ["US", "NSE", "BSE"]


def _eligible_company_query(db: Session, market: str):
    exchanges = _exchanges_for_market(market)
    query = db.query(Company).filter(Company.is_active == 1, Company.exchange.in_(exchanges))
    return apply_eligible_equity_filter(query, exchanges)


def _has_any_fundamental_expr():
    return or_(
        Fundamental.market_cap.isnot(None),
        Fundamental.trailing_eps.isnot(None),
        Fundamental.revenue.isnot(None),
        Fundamental.net_income.isnot(None),
        Fundamental.profit_margin.isnot(None),
        Fundamental.return_on_equity.isnot(None),
        Fundamental.return_on_assets.isnot(None),
    )


def _has_any_ownership_expr():
    return or_(
        Ownership.institution_percent.isnot(None),
        Ownership.insider_percent.isnot(None),
        Ownership.shares_outstanding.isnot(None),
        Ownership.float_shares.isnot(None),
    )


def universe_data_status(db: Session, market: str) -> dict:
    market = normalize_data_market(market)
    exchanges = _exchanges_for_market(market)

    base = _eligible_company_query(db, market)
    total = int(base.count())

    price_exists = db.query(OHLCV.id).filter(
        OHLCV.symbol == Company.symbol,
        OHLCV.exchange == Company.exchange,
    ).exists()
    price_ready = int(base.filter(price_exists).count())

    fundamentals_ready = int(
        base.join(
            Fundamental,
            and_(Fundamental.symbol == Company.symbol, Fundamental.exchange == Company.exchange),
            isouter=True,
        )
        .filter(_has_any_fundamental_expr())
        .count()
    )

    ownership_ready = int(
        base.join(
            Ownership,
            and_(Ownership.symbol == Company.symbol, Ownership.exchange == Company.exchange),
            isouter=True,
        )
        .filter(_has_any_ownership_expr())
        .count()
    )

    classified = int(
        base.filter(
            or_(
                and_(Company.sector.isnot(None), Company.sector != ""),
                and_(Company.industry.isnot(None), Company.industry != ""),
            )
        ).count()
    )

    def pct(value):
        return round((value / total) * 100, 1) if total else 0.0

    return {
        "market": market,
        "eligible_equities": total,
        "price_history_available": price_ready,
        "price_history_percent": pct(price_ready),
        "fundamentals_available": fundamentals_ready,
        "fundamentals_percent": pct(fundamentals_ready),
        "ownership_available": ownership_ready,
        "ownership_percent": pct(ownership_ready),
        "classification_available": classified,
        "classification_percent": pct(classified),
        "automatic_enrichment": True,
        "data_rule": "Only real provider values are stored; unavailable fields remain N/A.",
    }


def _mark_attempt(db: Session, company: Company):
    """Persist an attempt timestamp so one unsupported symbol cannot block the queue."""
    row = (
        db.query(Fundamental)
        .filter(Fundamental.symbol == company.symbol, Fundamental.exchange == company.exchange)
        .first()
    )
    if not row:
        row = Fundamental(symbol=company.symbol, exchange=company.exchange)
        db.add(row)
    row.updated_at = datetime.utcnow()
    db.commit()


def backfill_market_fundamentals(market: str, batch_size: int = 8, retry_hours: int = 24) -> dict:
    market = normalize_data_market(market)
    if market == "ALL":
        raise ValueError("Use backfill_all_fundamentals_once for ALL markets")

    batch_size = max(1, min(int(batch_size), 50))
    retry_hours = max(1, int(retry_hours))
    cutoff = datetime.utcnow() - timedelta(hours=retry_hours)
    db = SessionLocal()
    provider = YahooProvider()

    results = []
    attempted = 0
    completed = 0
    try:
        exchanges = _exchanges_for_market(market)
        query = (
            db.query(Company, Fundamental)
            .outerjoin(
                Fundamental,
                and_(Fundamental.symbol == Company.symbol, Fundamental.exchange == Company.exchange),
            )
            .filter(Company.is_active == 1, Company.exchange.in_(exchanges))
        )
        query = apply_eligible_equity_filter(query, exchanges)
        query = query.filter(
            or_(
                Fundamental.id.is_(None),
                and_(
                    or_(
                        Fundamental.market_cap.is_(None),
                        Fundamental.trailing_eps.is_(None),
                        Fundamental.revenue.is_(None),
                        Fundamental.net_income.is_(None),
                    ),
                    or_(Fundamental.updated_at.is_(None), Fundamental.updated_at < cutoff),
                ),
            )
        )
        # Missing rows first, then oldest attempted rows.  Extra candidates let
        # the batch continue past unsupported/delisted tickers.
        candidates = query.order_by(Fundamental.updated_at.asc().nullsfirst(), Company.id.asc()).limit(batch_size * 4).all()

        for company, _fundamental in candidates:
            if completed >= batch_size:
                break
            attempted += 1
            try:
                data = provider.get_fundamentals(company.symbol, company.exchange)
                if not isinstance(data, dict) or not any(
                    data.get(key) is not None
                    for key in ("market_cap", "trailing_eps", "revenue", "net_income", "profit_margin", "return_on_equity")
                ):
                    _mark_attempt(db, company)
                    results.append({"symbol": company.symbol, "exchange": company.exchange, "status": "no_data"})
                    continue

                sync_fundamental_data(db, company.symbol, company.exchange, data)
                completed += 1
                results.append({"symbol": company.symbol, "exchange": company.exchange, "status": "updated"})
            except Exception as exc:
                db.rollback()
                try:
                    _mark_attempt(db, company)
                except Exception:
                    db.rollback()
                logger.info("Fundamental enrichment skipped %s:%s: %s", company.exchange, company.symbol, exc)
                results.append({"symbol": company.symbol, "exchange": company.exchange, "status": "error", "error": str(exc)[:180]})

        return {
            "market": market,
            "batch_size": batch_size,
            "attempted": attempted,
            "updated": completed,
            "results": results,
            "status": universe_data_status(db, market),
        }
    finally:
        db.close()


def backfill_all_fundamentals_once(batch_size: int = 8) -> dict:
    return {
        "US": backfill_market_fundamentals("US", batch_size=batch_size),
        "INDIA": backfill_market_fundamentals("INDIA", batch_size=batch_size),
    }
