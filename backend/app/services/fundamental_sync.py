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

    if data.get("market_cap") is not None:
        fundamental.market_cap = data["market_cap"]
    if data.get("trailing_eps") is not None:
        fundamental.trailing_eps = data["trailing_eps"]
    if data.get("forward_eps") is not None:
        fundamental.forward_eps = data["forward_eps"]
    if data.get("revenue") is not None:
        fundamental.revenue = data["revenue"]
    if data.get("net_income") is not None:
        fundamental.net_income = data["net_income"]
    if data.get("profit_margin") is not None:
        fundamental.profit_margin = data["profit_margin"]
    if data.get("return_on_equity") is not None:
        fundamental.return_on_equity = data["return_on_equity"]
    if data.get("return_on_assets") is not None:
        fundamental.return_on_assets = data["return_on_assets"]

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

    if data.get("insider_percent") is not None:
        ownership.insider_percent = data["insider_percent"]
    if data.get("institution_percent") is not None:
        ownership.institution_percent = data["institution_percent"]
    if data.get("shares_outstanding") is not None:
        ownership.shares_outstanding = data["shares_outstanding"]
    if data.get("float_shares") is not None:
        ownership.float_shares = data["float_shares"]

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