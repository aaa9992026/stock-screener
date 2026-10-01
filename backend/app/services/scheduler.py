import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.services.company_auto_sync import sync_all_companies
from app.services.fundamental_sync import sync_fundamental_data
from app.services.ohlcv_sync import sync_ohlcv
from app.services.providers.bse_provider import BSEProvider
from app.services.providers.yahoo_provider import YahooProvider
from app.services.rs_universe_backfill import backfill_all_markets_once
from app.services.equity_filters import deactivate_legacy_us_non_equities
from app.services.universe_data_backfill import backfill_all_fundamentals_once


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



def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def refresh_rs_universe_history():
    """Run a small resumable batch for each client-defined RS market."""
    batch_size = max(1, min(100, int(os.getenv("RS_BACKFILL_BATCH_SIZE", "10") or 10)))
    try:
        result = backfill_all_markets_once(batch_size=batch_size)
        logger.info("RS universe backfill batch completed: %s", result)
        return result
    except Exception:
        logger.exception("RS universe backfill scheduler job failed")
        return {"status": "error"}



def cleanup_legacy_universe():
    db = SessionLocal()
    try:
        result = deactivate_legacy_us_non_equities(db)
        logger.info("Legacy US non-equity cleanup completed: %s", result)
        return result
    except Exception:
        db.rollback()
        logger.exception("Legacy US non-equity cleanup failed")
        return {"status": "error"}
    finally:
        db.close()


def refresh_universe_fundamentals():
    """Fill missing current fundamentals/ownership in bounded provider batches."""
    batch_size = max(1, min(50, int(os.getenv("FUNDAMENTAL_BACKFILL_BATCH_SIZE", "8") or 8)))
    try:
        result = backfill_all_fundamentals_once(batch_size=batch_size)
        logger.info("Universe fundamental enrichment completed: %s", result)
        return result
    except Exception:
        logger.exception("Universe fundamental enrichment job failed")
        return {"status": "error"}


def start_scheduler():
    if scheduler.running:
        return

    scheduler.add_job(
        cleanup_legacy_universe,
        "interval",
        hours=6,
        id="legacy_universe_cleanup",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(seconds=5),
    )

    scheduler.add_job(
        sync_all_companies,
        "interval",
        hours=24,
        id="company_sync",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now() + timedelta(seconds=3),
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

    if _env_flag("RS_BACKFILL_ENABLED", True):
        interval_minutes = max(5, int(os.getenv("RS_BACKFILL_INTERVAL_MINUTES", "10") or 10))
        scheduler.add_job(
            refresh_rs_universe_history,
            "interval",
            minutes=interval_minutes,
            id="rs_universe_backfill",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now() + timedelta(minutes=2),
        )

    if _env_flag("FUNDAMENTAL_BACKFILL_ENABLED", True):
        fundamental_interval = max(5, int(os.getenv("FUNDAMENTAL_BACKFILL_INTERVAL_MINUTES", "10") or 10))
        scheduler.add_job(
            refresh_universe_fundamentals,
            "interval",
            minutes=fundamental_interval,
            id="fundamental_universe_backfill",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
            next_run_time=datetime.now() + timedelta(minutes=3),
        )

    scheduler.start()
