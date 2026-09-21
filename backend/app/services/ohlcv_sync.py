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
        return {"added": 0, "updated": 0}

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
    }
