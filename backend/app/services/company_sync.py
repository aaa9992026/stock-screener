from sqlalchemy.orm import Session

from app.models import Company


# Provider snapshots are treated as authoritative only when they look complete.
# This prevents a temporary upstream outage/partial file from deactivating an
# entire market universe by mistake.
SNAPSHOT_MINIMUMS = {
    "US": 1000,
    "NSE": 500,
    "BSE": 500,
}


def _safe_to_deactivate(exchange: str, incoming_count: int, previous_active_count: int) -> bool:
    minimum = SNAPSHOT_MINIMUMS.get(exchange.upper(), 50)
    if incoming_count < minimum:
        return False
    if previous_active_count <= 0:
        return True
    # Accept normal listing/delisting churn, but reject suspiciously small
    # snapshots (for example a provider returning only a partial file).
    return incoming_count >= max(minimum, int(previous_active_count * 0.50))


def sync_companies(db: Session, companies: list[dict], deactivate_missing: bool = True):
    """Synchronize a provider's current company snapshot.

    New symbols are inserted, returning symbols are reactivated, and symbols
    missing from a trustworthy current snapshot are marked inactive. Historical
    OHLCV/fundamental rows are intentionally retained so delisting does not erase
    historical data.
    """
    normalized = []
    for item in companies or []:
        symbol = str(item.get("symbol") or "").strip().upper()
        exchange = str(item.get("exchange") or "").strip().upper()
        name = str(item.get("name") or "").strip()
        if not symbol or not exchange or not name:
            continue
        normalized.append({
            "symbol": symbol,
            "exchange": exchange,
            "name": name,
            "sector": item.get("sector"),
            "industry": item.get("industry"),
        })

    incoming_by_exchange: dict[str, set[str]] = {}
    for item in normalized:
        incoming_by_exchange.setdefault(item["exchange"], set()).add(item["symbol"])

    added = 0
    updated = 0
    reactivated = 0
    deactivated = 0
    deactivation_skipped = {}

    for item in normalized:
        company = (
            db.query(Company)
            .filter(
                Company.symbol == item["symbol"],
                Company.exchange == item["exchange"],
            )
            .first()
        )

        if company:
            if company.is_active != 1:
                reactivated += 1
            company.name = item["name"]
            company.sector = item.get("sector")
            company.industry = item.get("industry")
            company.is_active = 1
            updated += 1
        else:
            db.add(Company(
                symbol=item["symbol"],
                exchange=item["exchange"],
                name=item["name"],
                sector=item.get("sector"),
                industry=item.get("industry"),
                is_active=1,
            ))
            added += 1

    # Flush inserts/reactivations so the active-count check sees the new snapshot.
    db.flush()

    if deactivate_missing:
        for exchange, incoming_symbols in incoming_by_exchange.items():
            active_rows = (
                db.query(Company)
                .filter(Company.exchange == exchange, Company.is_active == 1)
                .all()
            )
            previous_active_count = len(active_rows)
            incoming_count = len(incoming_symbols)
            if not _safe_to_deactivate(exchange, incoming_count, previous_active_count):
                deactivation_skipped[exchange] = {
                    "incoming": incoming_count,
                    "active_before": previous_active_count,
                    "reason": "provider snapshot looked incomplete; no symbols were deactivated",
                }
                continue

            for company in active_rows:
                if company.symbol not in incoming_symbols:
                    company.is_active = 0
                    deactivated += 1

    db.commit()

    return {
        "added": added,
        "updated": updated,
        "reactivated": reactivated,
        "deactivated": deactivated,
        "deactivation_skipped": deactivation_skipped,
    }
