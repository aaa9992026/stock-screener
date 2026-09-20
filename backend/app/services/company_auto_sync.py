from app.database import SessionLocal
from app.services.company_sync import sync_companies
from app.services.nse_company_provider import NSECompanyProvider
from app.services.us_company_provider import USCompanyProvider


def sync_all_companies():
    db = SessionLocal()

    try:
        nse_provider = NSECompanyProvider()
        us_provider = USCompanyProvider()

        nse_companies = nse_provider.get_companies()
        us_companies = us_provider.get_companies()

        nse_result = sync_companies(db, nse_companies)
        us_result = sync_companies(db, us_companies)

        return {
            "NSE": {
                "received": len(nse_companies),
                **nse_result
            },
            "US": {
                "received": len(us_companies),
                **us_result
            }
        }

    finally:
        db.close()