from sqlalchemy.orm import Session
from app.models import Company


def sync_companies(db: Session, companies: list[dict]):
    added = 0
    updated = 0

    for item in companies:
        company = (
            db.query(Company)
            .filter(
                Company.symbol == item["symbol"],
                Company.exchange == item["exchange"]
            )
            .first()
        )

        if company:
            company.name = item["name"]
            company.sector = item.get("sector")
            company.industry = item.get("industry")
            company.is_active = 1
            updated += 1
        else:
            company = Company(
                symbol=item["symbol"],
                exchange=item["exchange"],
                name=item["name"],
                sector=item.get("sector"),
                industry=item.get("industry"),
                is_active=1
            )
            db.add(company)
            added += 1

    db.commit()

    return {
        "added": added,
        "updated": updated
    }