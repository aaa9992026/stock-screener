import logging
import os

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.company_auto_sync import sync_all_companies
from app.services.fundamental_sync import sync_fundamental_data
from app.services.ohlcv_sync import sync_ohlcv
from app.services.providers.bse_provider import BSEProvider
from app.services.providers.yahoo_provider import YahooProvider


logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


def configured_refresh_symbols():
    """Parse AUTO_REFRESH_SYMBOLS=US:AAPL,NSE:RELIANCE,BSE:INFY."""
    raw = os.getenv("AUTO_REFRESH_SYMBOLS", "").strip()
    result = []
    seen = set()
    for item in raw.split(","):
        item = item.strip()
        if not item or ":" not in item:
            continue
        exchange, symbol = item.split(":", 1)
        exchange = exchange.strip().upper()
        symbol = symbol.strip().upper()
        if exchange not in {"US", "NSE", "BSE"} or not symbol:
            continue
        key = (exchange, symbol)
        if key not in seen:
            result.append(key)
            seen.add(key)
    return result


def refresh_configured_market_data():
    """Automatically refresh configured symbols without any CSV upload.

    The list belongs to the deployment owner through AUTO_REFRESH_SYMBOLS;
    there is no dependency on the developer's personal machine/account.
    """
    symbols = configured_refresh_symbols()
    if not symbols:
        return {"status": "skipped", "reason": "AUTO_REFRESH_SYMBOLS is empty", "results": []}

    db = SessionLocal()
    results = []
    try:
        yahoo = YahooProvider()
        bse = BSEProvider()
        for exchange, symbol in symbols:
            try:
                if exchange == "BSE":
                    rows = bse.get_ohlcv(symbol)
                else:
                    rows = yahoo.get_ohlcv(
                        symbol=symbol,
                        exchange=exchange,
                        start_date="2000-01-01",
                    )

                sync_result = sync_ohlcv(
                    db=db,
                    symbol=symbol,
                    exchange=exchange,
                    rows=rows,
                )

                fundamentals_refreshed = False
                if exchange == "US":
                    fundamentals = yahoo.get_fundamentals(symbol)
                    if fundamentals:
                        sync_fundamental_data(
                            db=db,
                            symbol=symbol,
                            exchange=exchange,
                            data=fundamentals,
                        )
                        fundamentals_refreshed = True

                results.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "status": "success",
                    "records_received": len(rows or []),
                    "fundamentals_refreshed": fundamentals_refreshed,
                    **sync_result,
                })
            except Exception as exc:
                db.rollback()
                logger.exception("Automatic refresh failed for %s:%s", exchange, symbol)
                results.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "status": "error",
                    "error": str(exc),
                })
    finally:
        db.close()

    return {
        "status": "completed",
        "configured_count": len(symbols),
        "results": results,
    }


def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        sync_all_companies,
        "interval",
        hours=24,
        id="company_sync",
        replace_existing=True,
    )

    refresh_hours = max(1, int(os.getenv("AUTO_REFRESH_HOURS", "6") or 6))
    if configured_refresh_symbols():
        scheduler.add_job(
            refresh_configured_market_data,
            "interval",
            hours=refresh_hours,
            id="market_data_refresh",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    scheduler.start()
