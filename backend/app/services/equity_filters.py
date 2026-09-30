from sqlalchemy import and_, or_

from app.models import Company
from app.services.us_company_provider import is_supported_us_equity

# SQL-safe patterns used as a defensive second layer for legacy rows that may
# still be active in the database before the latest symbol-master sync runs.
# The authoritative provider-level filter remains is_supported_us_equity().
_US_NAME_EXCLUDE_PATTERNS = [
    "%Warrant%",
    "%Warrants%",
    "% - Unit%",
    "% - Units%",
    "% Unit",
    "% Units",
    "% Unit - %",
    "% Units - %",
    "% - Right%",
    "% - Rights%",
    "% Right",
    "% Rights",
    "% Acquisition Corp%",
    "% Acquisition Corporation%",
    "% Acquisition Company%",
    "% Blank Check%",
    "% SPAC%",
    "% ETF%",
    "%Exchange Traded Fund%",
    "% Preferred Stock%",
    "% Preferred Shares%",
    "% Preference Shares%",
    "% Debt Securities%",
    "% Debentures%",
    "% Notes due %",
    "% Bonds due %",
]


def us_equity_sql_condition():
    """SQL predicate excluding obvious legacy non-equity US rows.

    Nasdaq Trader's live ETF/Test Issue flags are applied before rows are stored.
    This predicate is deliberately a defensive legacy filter so stale warrants,
    units and SPAC acquisition rows cannot leak into the user-facing screener
    while a provider sync is delayed or unavailable.
    """
    conditions = [Company.name.notilike(pattern) for pattern in _US_NAME_EXCLUDE_PATTERNS]
    return and_(*conditions)


def eligible_equity_condition(exchanges):
    exchanges = [str(item).upper() for item in (exchanges or [])]
    if "US" not in exchanges:
        return None
    us_condition = us_equity_sql_condition()
    if set(exchanges) == {"US"}:
        return us_condition
    return or_(Company.exchange != "US", and_(Company.exchange == "US", us_condition))


def apply_eligible_equity_filter(query, exchanges):
    condition = eligible_equity_condition(exchanges)
    return query.filter(condition) if condition is not None else query


def deactivate_legacy_us_non_equities(db):
    """Deactivate obvious legacy non-equity US rows without deleting history."""
    rows = (
        db.query(Company)
        .filter(Company.exchange == "US", Company.is_active == 1)
        .all()
    )
    changed = 0
    for company in rows:
        if not is_supported_us_equity(company.symbol, company.name):
            company.is_active = 0
            changed += 1
    if changed:
        db.commit()
    return {"checked": len(rows), "deactivated": changed}
