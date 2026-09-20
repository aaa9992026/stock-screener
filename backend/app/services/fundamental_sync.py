from sqlalchemy.orm import Session

from app.models import Fundamental, Ownership


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

    db.commit()

    return {
        "status": "success",
        "symbol": symbol,
        "exchange": exchange
    }