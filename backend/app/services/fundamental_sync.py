from sqlalchemy.orm import Session

from app.models import Fundamental, Ownership, Company


def sync_fundamental_data(
    db: Session,
    symbol: str,
    exchange: str,
    data: dict
):
    fundamental = (
        db.query(Fundamental)
        .filter(
            Fundamental.symbol == symbol,
            Fundamental.exchange == exchange
        )
        .first()
    )

    if not fundamental:
        fundamental = Fundamental(
            symbol=symbol,
            exchange=exchange
        )
        db.add(fundamental)

    fundamental.market_cap = data.get("market_cap")
    fundamental.trailing_eps = data.get("trailing_eps")
    fundamental.forward_eps = data.get("forward_eps")
    fundamental.revenue = data.get("revenue")
    fundamental.net_income = data.get("net_income")
    fundamental.profit_margin = data.get("profit_margin")
    fundamental.return_on_equity = data.get("return_on_equity")
    fundamental.return_on_assets = data.get("return_on_assets")

    ownership = (
        db.query(Ownership)
        .filter(
            Ownership.symbol == symbol,
            Ownership.exchange == exchange
        )
        .first()
    )

    if not ownership:
        ownership = Ownership(
            symbol=symbol,
            exchange=exchange
        )
        db.add(ownership)

    ownership.insider_percent = data.get("insider_percent")
    ownership.institution_percent = data.get("institution_percent")
    ownership.shares_outstanding = data.get("shares_outstanding")
    ownership.float_shares = data.get("float_shares")

    company = (
        db.query(Company)
        .filter(
            Company.symbol == symbol,
            Company.exchange == exchange
        )
        .first()
    )

    # A successful provider refresh must also make the symbol visible in the
    # stock-universe screener. Railway databases can contain OHLCV/fundamental
    # history from an older deployment while the company-master table is still
    # empty or has not finished its background symbol sync yet.
    name = data.get("name")
    isin = data.get("isin")
    sector = data.get("sector")
    industry = data.get("industry")
    if not company:
        company = Company(
            symbol=symbol,
            exchange=exchange,
            name=str(name).strip() if name not in (None, "", "nan", "NaN", "-") else symbol,
            isin=str(isin).strip() if isin not in (None, "", "nan", "NaN", "-") else None,
            sector=sector if sector not in (None, "", "nan", "NaN") else None,
            industry=industry if industry not in (None, "", "nan", "NaN") else None,
            is_active=1,
        )
        db.add(company)
    else:
        # Keep previously enriched classification when a provider temporarily
        # omits sector/industry instead of erasing it with None.  Provider
        # identity is also allowed to repair an old mismatched company name.
        if name not in (None, "", "nan", "NaN", "-"):
            company.name = str(name).strip()
        if isin not in (None, "", "nan", "NaN", "-"):
            company.isin = str(isin).strip()
        if sector not in (None, "", "nan", "NaN"):
            company.sector = sector
        if industry not in (None, "", "nan", "NaN"):
            company.industry = industry
        company.is_active = 1

    db.commit()

    return {
        "status": "success",
        "symbol": symbol,
        "exchange": exchange
    }