import logging

from app.database import SessionLocal
from app.services.company_sync import sync_companies, bootstrap_companies_from_stored_data
from app.services.nse_company_provider import NSECompanyProvider
from app.services.us_company_provider import USCompanyProvider
from app.services.providers.bse_provider import BSEProvider


logger = logging.getLogger(__name__)


def sync_all_companies():
    """Sync each symbol master independently so one provider outage cannot
    leave the entire stock-universe screener empty.
    """
    results = {}

    # First expose any provider-backed symbols already present in PostgreSQL.
    db = SessionLocal()
    try:
        try:
            results["stored_bootstrap"] = bootstrap_companies_from_stored_data(db)
        except Exception as exc:
            db.rollback()
            results["stored_bootstrap"] = {"status": "error", "error": str(exc)[:180]}
    finally:
        db.close()

    providers = {
        "NSE": NSECompanyProvider,
        "US": USCompanyProvider,
        "BSE": BSEProvider,
    }

    for market, provider_cls in providers.items():
        db = SessionLocal()
        try:
            try:
                companies = provider_cls().get_companies()
                sync_result = sync_companies(db, companies)
                results[market] = {
                    "status": "success",
                    "received": len(companies),
                    **sync_result,
                }
            except Exception as exc:
                db.rollback()
                logger.exception("Company-master sync failed for %s", market)
                results[market] = {
                    "status": "error",
                    "received": 0,
                    "error": str(exc)[:250],
                }
        finally:
            db.close()

    return results
