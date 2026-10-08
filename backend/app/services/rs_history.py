"""Persist only compressed date/open/close observations for RS, not full OHLCV."""
import base64
import gzip
import json
import math
from datetime import date, datetime, timezone, timedelta
from app.models import RSHistory

def encode_points(rows):
    points = {}
    for row in rows:
        get = row.get if isinstance(row, dict) else lambda key: getattr(row, key, None)
        dt, opening, close = get("date"), get("open"), get("close")
        if isinstance(dt, datetime):
            dt = dt.date()
        if isinstance(dt, str):
            dt = date.fromisoformat(dt[:10])
        if not isinstance(dt, date) or dt.weekday() >= 5 or dt < date.today() - timedelta(days=545):
            continue
        if opening is None or close is None:
            continue
        opening, close = float(opening), float(close)
        if not all(math.isfinite(v) and v > 0 for v in (opening, close)):
            continue
        points[dt] = [dt.isoformat(), opening, close]
    ordered = [points[d] for d in sorted(points)]
    payload = base64.b64encode(gzip.compress(json.dumps(ordered, separators=(",", ":")).encode())).decode()
    return payload, ordered

def decode_points(payload):
    if not payload:
        return []
    try:
        return [(date.fromisoformat(d), float(o), float(c)) for d, o, c in json.loads(gzip.decompress(base64.b64decode(payload)))]
    except (ValueError, TypeError, OSError):
        return []

def persist_history(db, symbol, exchange, rows, provider="Yahoo Finance"):
    payload, points = encode_points(rows)
    item = db.query(RSHistory).filter_by(symbol=symbol.upper(), exchange=exchange.upper()).first()
    if item is None:
        item = RSHistory(symbol=symbol.upper(), exchange=exchange.upper())
        db.add(item)
    if points:
        item.points_payload = payload
        item.first_date = date.fromisoformat(points[0][0])
        item.last_date = date.fromisoformat(points[-1][0])
        item.row_count = len(points)
        item.provider = provider
        item.status = "success"
        item.error = None
        item.retry_after = None
        item.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.commit()
    return item
