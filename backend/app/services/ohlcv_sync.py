from sqlalchemy.orm import Session
from app.models import OHLCV


def sync_ohlcv(
    db: Session,
    symbol: str,
    exchange: str,
    rows: list[dict]
):
    added = 0
    updated = 0

    for row in rows:
        existing = (
            db.query(OHLCV)
            .filter(
                OHLCV.symbol == symbol,
                OHLCV.exchange == exchange,
                OHLCV.date == row["date"]
            )
            .first()
        )

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
                    volume=row["volume"]
                )
            )
            added += 1

    db.commit()

    return {
        "added": added,
        "updated": updated
    }