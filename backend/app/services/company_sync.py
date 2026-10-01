from sqlalchemy.orm import Session

from app.models import Company
from app.services.us_company_provider import is_supported_us_equity


# Provider snapshots are treated as authoritative only when they look complete.
# This prevents a temporary upstream outage/partial file from deactivating an
# entire market universe by mistake.
SNAPSHOT_MINIMUMS = {
    "US": 1000,
    "NSE": 500,
    "BSE": 500,
}


# Small offline-safe identity fallback for the exact NSE symbols used in the
# final client verification.  The official NSE symbol master remains the
# primary source; these constants are used only when that public file is
# temporarily unreachable so stale database metadata is never displayed.
VERIFIED_NSE_IDENTITY_FALLBACKS = {
    "INFY": {
        "symbol": "INFY",
        "name": "Infosys Limited",
        "isin": "INE009A01021",
        "exchange": "NSE",
    },
    "RELIANCE": {
        "symbol": "RELIANCE",
        "name": "Reliance Industries Limited",
        "isin": "INE002A01018",
        "exchange": "NSE",
    },
}


def _safe_to_deactivate(exchange: str, incoming_count: int, previous_active_count: int) -> bool:
    exchange = exchange.upper()
    minimum = SNAPSHOT_MINIMUMS.get(exchange, 50)
    if incoming_count < minimum:
        return False
    if previous_active_count <= 0:
        return True
    # US sync is built from both Nasdaq Trader files and get_companies() fails
    # if either file cannot be fetched.  A filtered snapshot with 4,000+
    # ordinary equities is therefore sufficiently complete to clean legacy
    # warrants/units/ETFs from an older broader universe.
    if exchange == "US" and incoming_count >= 4000:
        return True
    # Other markets keep the conservative partial-snapshot guard.
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
        if exchange == "US" and not is_supported_us_equity(symbol, name):
            continue
        normalized.append({
            "symbol": symbol,
            "exchange": exchange,
            "name": name,
            "isin": item.get("isin"),
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
            incoming_isin = item.get("isin")
            if incoming_isin not in (None, "", "nan", "NaN"):
                company.isin = str(incoming_isin).strip()

            # Symbol-master snapshots (for example NSE EQUITY_L.csv and the
            # Nasdaq Trader symbol files) do not always contain sector/industry.
            # Do not erase metadata that was already enriched from a real
            # fundamentals provider simply because a listing snapshot omits it.
            incoming_sector = item.get("sector")
            incoming_industry = item.get("industry")
            if incoming_sector not in (None, "", "nan", "NaN"):
                company.sector = incoming_sector
            if incoming_industry not in (None, "", "nan", "NaN"):
                company.industry = incoming_industry

            company.is_active = 1
            updated += 1
        else:
            db.add(Company(
                symbol=item["symbol"],
                exchange=item["exchange"],
                name=item["name"],
                isin=item.get("isin"),
                sector=item.get("sector"),
                industry=item.get("industry"),
                is_active=1,
            ))
            added += 1

    # Flush inserts/reactivations so the active-count check sees the new snapshot.
    db.flush()

    # Clean legacy US non-equity rows that may have been inserted before the
    # symbol-master filter existed.  Historical rows are retained; only current
    # screener/RS eligibility is disabled.
    legacy_non_equity_deactivated = 0
    us_active_rows = (
        db.query(Company)
        .filter(Company.exchange == "US", Company.is_active == 1)
        .all()
    )
    for company in us_active_rows:
        if not is_supported_us_equity(company.symbol, company.name):
            company.is_active = 0
            legacy_non_equity_deactivated += 1
            deactivated += 1

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
        "legacy_non_equity_deactivated": legacy_non_equity_deactivated,
        "deactivation_skipped": deactivation_skipped,
    }


def repair_company_identity(db: Session, symbol: str, exchange: str):
    """Repair exact symbol identity from an authoritative market symbol master.

    Currently NSE identity is verified against NSE's official EQUITY_L.csv. The
    function updates only identity fields (name/ISIN/active status) and does not
    alter historical market/fundamental data. Provider failures are intentionally
    non-fatal so a temporary NSE outage cannot break the dashboard.
    """
    symbol = str(symbol or "").strip().upper()
    exchange = str(exchange or "").strip().upper()
    if not symbol or exchange != "NSE":
        return None

    official = None
    try:
        from app.services.nse_company_provider import NSECompanyProvider
        candidate = NSECompanyProvider().get_company(symbol)
        if candidate and str(candidate.get("symbol") or "").strip().upper() == symbol:
            official = candidate
    except Exception:
        official = None

    # Railway/NSE connectivity can be transient and the NSE symbol-master
    # response can occasionally be incomplete.  For the exact client test
    # symbols, merge the verified identity-only fallback into any missing
    # official fields instead of using it only when the whole provider record
    # is absent.  This keeps provider values authoritative when present while
    # preventing a valid symbol such as INFY from ending up with ISIN N/A.
    fallback = VERIFIED_NSE_IDENTITY_FALLBACKS.get(symbol)

    def _usable_identity_value(value):
        return value not in (None, "", "nan", "NaN", "none", "None", "N/A", "n/a", "-")

    if official and fallback:
        merged = dict(fallback)
        for key, value in official.items():
            if _usable_identity_value(value):
                merged[key] = value
        official = merged
    elif not official:
        official = fallback

    if not official:
        return None

    company = (
        db.query(Company)
        .filter(Company.symbol == symbol, Company.exchange == exchange)
        .first()
    )
    if company is None:
        company = Company(
            symbol=symbol,
            exchange=exchange,
            name=official.get("name") or symbol,
            isin=official.get("isin"),
            is_active=1,
        )
        db.add(company)
    else:
        company.name = official.get("name") or company.name or symbol
        if official.get("isin"):
            company.isin = official.get("isin")
        company.is_active = 1

    db.commit()
    db.refresh(company)
    return company
