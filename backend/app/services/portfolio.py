"""Paper portfolio ledger; only verified market prices are accepted by the API."""
from decimal import Decimal, ROUND_HALF_UP


def money(value):
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def positions_from_trades(trades):
    positions = {}
    for trade in trades:
        key = (trade.exchange, trade.symbol)
        position = positions.setdefault(key, {"quantity": 0, "cost": 0.0, "entry_date": str(trade.date), "initial_stop": None})
        if trade.side == "BUY":
            position["quantity"] += trade.quantity
            position["cost"] = money(position["cost"] + trade.price * trade.quantity + trade.fee)
            position["initial_stop"] = trade.initial_stop
        else:
            average = position["cost"] / position["quantity"]
            position["cost"] = money(position["cost"] - average * trade.quantity)
            position["quantity"] -= trade.quantity
        if position["quantity"] == 0:
            positions.pop(key)
    return positions
