import math

from sqlalchemy.orm import Session
from app.models import OHLCV


def _bar_has_valid_ohlc(row) -> bool:
    try:
        values = [float(row.open), float(row.high), float(row.low), float(row.close)]
    except (TypeError, ValueError):
        return False
    return all(math.isfinite(value) and value > 0 for value in values)


def _incoming_bar_is_valid(row: dict) -> bool:
    try:
        values = [float(row.get("open")), float(row.get("high")), float(row.get("low")), float(row.get("close"))]
    except (TypeError, ValueError):
        return False
    return all(math.isfinite(value) and value > 0 for value in values)


def _remove_invalid_rows(db: Session, symbol: str, exchange: str) -> int:
    """Delete legacy weekend/zero/non-finite bars for normal stock exchanges."""
    if exchange.upper() not in {"US", "NSE", "BSE"}:
        return 0

    existing = (
        db.query(OHLCV)
        .filter(OHLCV.symbol == symbol.upper(), OHLCV.exchange == exchange.upper())
        .all()
    )
    invalid = [
        row for row in existing
        if row.date is None
        or row.date.weekday() >= 5
        or not _bar_has_valid_ohlc(row)
    ]
    for row in invalid:
        db.delete(row)
    return len(invalid)


def sync_ohlcv(
    db: Session,
    symbol: str,
    exchange: str,
    rows: list[dict]
):
    """Append/update OHLCV and enforce weekday-only stock bars."""
    added = 0
    updated = 0
    symbol = symbol.upper()
    exchange = exchange.upper()

    # Always clean old invalid rows, even if the provider returns no new rows.
    removed_invalid_dates = _remove_invalid_rows(db, symbol, exchange)

    rows = rows or []
    if exchange in {"US", "NSE", "BSE"}:
        rows = [
            row for row in rows
            if row.get("date") is not None
            and row["date"].weekday() < 5
            and _incoming_bar_is_valid(row)
        ]

    if not rows:
        db.commit()
        return {
            "added": 0,
            "updated": 0,
            "removed_invalid_dates": removed_invalid_dates,
        }

    incoming_dates = [row["date"] for row in rows]
    existing_rows = (
        db.query(OHLCV)
        .filter(
            OHLCV.symbol == symbol,
            OHLCV.exchange == exchange,
            OHLCV.date.in_(incoming_dates),
        )
        .all()
    )
    existing_by_date = {row.date: row for row in existing_rows}

    for row in rows:
        existing = existing_by_date.get(row["date"])
        if existing:
            existing.open = row["open"]
            existing.high = row["high"]
            existing.low = row["low"]
            existing.close = row["close"]
            existing.volume = row["volume"]
            updated += 1
        else:
            db.add(
                OHLCV(
                    symbol=symbol,
                    exchange=exchange,
                    date=row["date"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                )
            )
            added += 1

    db.commit()
    return {
        "added": added,
        "updated": updated,
        "removed_invalid_dates": removed_invalid_dates,
    }
