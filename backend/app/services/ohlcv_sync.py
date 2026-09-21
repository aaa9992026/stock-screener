from sqlalchemy.orm import Session
from app.models import OHLCV


def sync_ohlcv(
    db: Session,
    symbol: str,
    exchange: str,
    rows: list[dict]
):
    """Append/update OHLCV efficiently without one SELECT per incoming row."""
    added = 0
    updated = 0

    if not rows:
        return {"added": 0, "updated": 0, "removed_invalid_dates": 0}

    exchange = exchange.upper()

    # Stocks on US/NSE/BSE do not have normal weekend trading sessions.
    # Some upstream feeds can expose a live/UTC timestamp that converts to a
    # Saturday/Sunday calendar date. Never persist those rows as daily bars.
    if exchange in {"US", "NSE", "BSE"}:
        rows = [
            row for row in rows
            if row.get("date") is not None and row["date"].weekday() < 5
        ]

        # Clean any previously stored weekend rows for this symbol as well.
        existing_all = (
            db.query(OHLCV)
            .filter(OHLCV.symbol == symbol, OHLCV.exchange == exchange)
            .all()
        )
        invalid_existing = [row for row in existing_all if row.date.weekday() >= 5]
        for row in invalid_existing:
            db.delete(row)
        removed_invalid_dates = len(invalid_existing)
    else:
        removed_invalid_dates = 0

    if not rows:
        db.commit()
        return {"added": 0, "updated": 0, "removed_invalid_dates": removed_invalid_dates}

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
