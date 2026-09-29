"""Incremental RS-universe OHLCV backfill.

The client defined two separate Relative Strength universes:
- US: 6,000 stocks
- INDIA: 5,500 stocks (NSE + BSE)

This service intentionally backfills only real provider OHLCV data. It never
creates synthetic bars to make the universe count reach the requested target.
Jobs are incremental and idempotent: symbols with enough recent history are
skipped, failed/empty symbols remain pending and can be retried on a later run.
"""

from __future__ import annotations

import logging
import math
import os
import threading
from datetime import date, datetime, timedelta

import pandas as pd
import yfinance as yf
from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Company, OHLCV
from app.services.ohlcv_sync import sync_ohlcv


logger = logging.getLogger(__name__)

RS_UNIVERSE_TARGETS = {"US": 6000, "INDIA": 5500}
RS_MARKET_EXCHANGES = {"US": ("US",), "INDIA": ("NSE", "BSE")}

# 1Y RS needs roughly one year of history. We request a larger window so
# holidays/IPO dates do not accidentally make an otherwise usable stock fail.
DEFAULT_HISTORY_DAYS = 500
MIN_HISTORY_ROWS = 180
MIN_HISTORY_SPAN_DAYS = 350
MAX_STALE_DAYS = 14

_market_locks = {"US": threading.Lock(), "INDIA": threading.Lock()}
_last_results: dict[str, dict] = {}


def normalize_market(market: str) -> str:
    value = str(market or "").strip().upper()
    if value in {"NSE", "BSE", "INDIA", "IN"}:
        return "INDIA"
    if value in {"US", "USA"}:
        return "US"
    raise ValueError("market must be US or INDIA")


def market_exchanges(market: str) -> tuple[str, ...]:
    return RS_MARKET_EXCHANGES[normalize_market(market)]


def _provider_symbol(symbol: str, exchange: str) -> str:
    exchange = exchange.upper()
    symbol = symbol.upper()
    if exchange == "NSE":
        return f"{symbol}.NS"
    if exchange == "BSE":
        return f"{symbol}.BO"
    return symbol


def _history_stats(db: Session, market: str) -> dict[tuple[str, str], dict]:
    exchanges = market_exchanges(market)
    cutoff = date.today() - timedelta(days=DEFAULT_HISTORY_DAYS + 45)
    rows = (
        db.query(
            OHLCV.exchange,
            OHLCV.symbol,
            func.count(OHLCV.id),
            func.min(OHLCV.date),
            func.max(OHLCV.date),
        )
        .join(
            Company,
            and_(
                Company.symbol == OHLCV.symbol,
                Company.exchange == OHLCV.exchange,
            ),
        )
        .filter(
            Company.is_active == 1,
            Company.exchange.in_(exchanges),
            OHLCV.date >= cutoff,
        )
        .group_by(OHLCV.exchange, OHLCV.symbol)
        .all()
    )
    return {
        (str(exchange).upper(), str(symbol).upper()): {
            "rows": int(count or 0),
            "first_date": first_date,
            "last_date": last_date,
        }
        for exchange, symbol, count, first_date, last_date in rows
    }


def _is_ready(stat: dict | None, today: date | None = None) -> bool:
    if not stat:
        return False
    today = today or date.today()
    first_date = stat.get("first_date")
    last_date = stat.get("last_date")
    count = int(stat.get("rows") or 0)
    if first_date is None or last_date is None:
        return False
    span_days = (last_date - first_date).days
    stale_days = (today - last_date).days
    return (
        count >= MIN_HISTORY_ROWS
        and span_days >= MIN_HISTORY_SPAN_DAYS
        and stale_days <= MAX_STALE_DAYS
    )


def universe_backfill_status(db: Session, market: str) -> dict:
    market = normalize_market(market)
    exchanges = market_exchanges(market)
    target = RS_UNIVERSE_TARGETS[market]

    companies = (
        db.query(Company)
        .filter(Company.exchange.in_(exchanges), Company.is_active == 1)
        .order_by(Company.exchange.asc(), Company.symbol.asc())
        .all()
    )
    stats = _history_stats(db, market)

    ready = 0
    no_history = 0
    stale_or_short = 0
    by_exchange: dict[str, dict] = {}
    for company in companies:
        exchange = company.exchange.upper()
        bucket = by_exchange.setdefault(exchange, {"active": 0, "ready": 0, "pending": 0})
        bucket["active"] += 1
        stat = stats.get((exchange, company.symbol.upper()))
        if _is_ready(stat):
            ready += 1
            bucket["ready"] += 1
        else:
            bucket["pending"] += 1
            if stat is None:
                no_history += 1
            else:
                stale_or_short += 1

    active = len(companies)
    pending = max(0, active - ready)
    return {
        "market": market,
        "target_rs_universe": target,
        "active_symbols": active,
        "history_ready_symbols": ready,
        "pending_active_symbols": pending,
        "no_history_symbols": no_history,
        "stale_or_short_history_symbols": stale_or_short,
        "target_coverage_percent": round(min(100.0, (ready / target) * 100.0), 2) if target else 0.0,
        "active_coverage_percent": round((ready / active) * 100.0, 2) if active else 0.0,
        "symbol_master_shortfall": max(0, target - active),
        "complete": ready >= target,
        "history_requirements": {
            "minimum_rows": MIN_HISTORY_ROWS,
            "minimum_span_days": MIN_HISTORY_SPAN_DAYS,
            "maximum_stale_days": MAX_STALE_DAYS,
            "requested_backfill_days": DEFAULT_HISTORY_DAYS,
        },
        "by_exchange": by_exchange,
        "last_batch": _last_results.get(market),
    }


def _candidate_companies(db: Session, market: str, limit: int) -> list[Company]:
    market = normalize_market(market)
    exchanges = market_exchanges(market)
    stats = _history_stats(db, market)
    companies = (
        db.query(Company)
        .filter(Company.exchange.in_(exchanges), Company.is_active == 1)
        .all()
    )

    candidates = []
    for company in companies:
        key = (company.exchange.upper(), company.symbol.upper())
        stat = stats.get(key)
        if _is_ready(stat):
            continue
        # Symbols with no history first, then oldest/stalest history.
        last_date = stat.get("last_date") if stat else None
        sort_date = last_date or date(1900, 1, 1)
        candidates.append((sort_date, company.exchange.upper(), company.symbol.upper(), company))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return [item[3] for item in candidates[: max(1, int(limit))]]


def _extract_symbol_frame(downloaded: pd.DataFrame, ticker: str, ticker_count: int) -> pd.DataFrame | None:
    if downloaded is None or downloaded.empty:
        return None

    frame = None
    if isinstance(downloaded.columns, pd.MultiIndex):
        level0 = [str(v) for v in downloaded.columns.get_level_values(0)]
        level1 = [str(v) for v in downloaded.columns.get_level_values(1)]
        if ticker in level0:
            try:
                frame = downloaded[ticker]
            except Exception:
                frame = None
        elif ticker in level1:
            try:
                frame = downloaded.xs(ticker, axis=1, level=1)
            except Exception:
                frame = None
    elif ticker_count == 1:
        frame = downloaded

    if frame is None or getattr(frame, "empty", True):
        return None
    return frame


def _frame_to_rows(frame: pd.DataFrame | None) -> list[dict]:
    if frame is None or frame.empty:
        return []
    rows = []
    for idx, row in frame.iterrows():
        try:
            open_value = row.get("Open")
            high_value = row.get("High")
            low_value = row.get("Low")
            close_value = row.get("Close")
            volume_value = row.get("Volume")
            values = (open_value, high_value, low_value, close_value)
            if any(
                v is None
                or not math.isfinite(float(v))
                or float(v) <= 0
                for v in values
            ):
                continue
            dt = idx.date() if hasattr(idx, "date") else idx
            if dt is None or dt.weekday() >= 5:
                continue
            volume = 0.0
            if volume_value is not None:
                try:
                    numeric_volume = float(volume_value)
                    if math.isfinite(numeric_volume):
                        volume = numeric_volume
                except Exception:
                    pass
            rows.append({
                "date": dt,
                "open": float(open_value),
                "high": float(high_value),
                "low": float(low_value),
                "close": float(close_value),
                "volume": volume,
            })
        except Exception:
            continue
    return rows


def backfill_market_batch(market: str, batch_size: int | None = None) -> dict:
    """Fetch one idempotent batch of real OHLCV history for an RS market.

    Designed for scheduler use on Railway: each invocation is bounded, so a
    provider rate-limit or deployment restart does not lose overall progress.
    """
    market = normalize_market(market)
    default_batch = int(os.getenv("RS_BACKFILL_BATCH_SIZE", "25") or 25)
    batch_size = max(1, min(100, int(batch_size or default_batch)))
    lock = _market_locks[market]
    if not lock.acquire(blocking=False):
        return {
            "market": market,
            "status": "busy",
            "message": "A backfill batch is already running for this market.",
        }

    db = SessionLocal()
    started_at = datetime.utcnow()
    try:
        before = universe_backfill_status(db, market)
        if before["complete"]:
            result = {
                "market": market,
                "status": "complete",
                "requested_batch_size": batch_size,
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "empty": 0,
                "before": before,
                "after": before,
                "started_at": started_at.isoformat() + "Z",
                "finished_at": datetime.utcnow().isoformat() + "Z",
                "message": f"The client target of {before['target_rs_universe']:,} ready stocks is already met.",
            }
            _last_results[market] = result
            return result

        candidates = _candidate_companies(db, market, batch_size)
        remaining_to_target = max(0, before["target_rs_universe"] - before["history_ready_symbols"])
        candidates = candidates[:remaining_to_target]
        if not candidates:
            result = {
                "market": market,
                "status": "complete" if before["complete"] else "idle",
                "requested_batch_size": batch_size,
                "attempted": 0,
                "succeeded": 0,
                "failed": 0,
                "empty": 0,
                "before": before,
                "after": before,
                "started_at": started_at.isoformat() + "Z",
                "finished_at": datetime.utcnow().isoformat() + "Z",
            }
            _last_results[market] = result
            return result

        mapping = {
            _provider_symbol(company.symbol, company.exchange): (
                company.exchange.upper(),
                company.symbol.upper(),
            )
            for company in candidates
        }
        tickers = list(mapping.keys())
        start_date = date.today() - timedelta(days=DEFAULT_HISTORY_DAYS)
        # yfinance's end date is exclusive, so include tomorrow.
        end_date = date.today() + timedelta(days=1)

        downloaded = yf.download(
            tickers=tickers,
            start=start_date.isoformat(),
            end=end_date.isoformat(),
            auto_adjust=False,
            group_by="ticker",
            threads=True,
            progress=False,
        )

        succeeded = 0
        failed = 0
        empty = 0
        details = []
        for provider_ticker, (exchange, symbol) in mapping.items():
            try:
                frame = _extract_symbol_frame(downloaded, provider_ticker, len(tickers))
                rows = _frame_to_rows(frame)
                if not rows:
                    empty += 1
                    details.append({
                        "symbol": symbol,
                        "exchange": exchange,
                        "status": "empty",
                    })
                    continue
                sync_result = sync_ohlcv(db, symbol, exchange, rows)
                succeeded += 1
                details.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "status": "success",
                    "records_received": len(rows),
                    **sync_result,
                })
            except Exception as exc:
                db.rollback()
                failed += 1
                logger.exception("RS backfill failed for %s:%s", exchange, symbol)
                details.append({
                    "symbol": symbol,
                    "exchange": exchange,
                    "status": "error",
                    "error": str(exc),
                })

        after = universe_backfill_status(db, market)
        result = {
            "market": market,
            "status": "completed",
            "requested_batch_size": batch_size,
            "attempted": len(candidates),
            "succeeded": succeeded,
            "failed": failed,
            "empty": empty,
            "provider": "Yahoo Finance/yfinance bulk OHLCV",
            "real_data_only": True,
            "before_ready": before["history_ready_symbols"],
            "after_ready": after["history_ready_symbols"],
            "remaining_active": after["pending_active_symbols"],
            "started_at": started_at.isoformat() + "Z",
            "finished_at": datetime.utcnow().isoformat() + "Z",
            "details": details,
        }
        _last_results[market] = result
        return result
    except Exception as exc:
        db.rollback()
        logger.exception("RS universe batch failed for %s", market)
        result = {
            "market": market,
            "status": "error",
            "error": str(exc),
            "started_at": started_at.isoformat() + "Z",
            "finished_at": datetime.utcnow().isoformat() + "Z",
        }
        _last_results[market] = result
        return result
    finally:
        db.close()
        lock.release()


def backfill_all_markets_once(batch_size: int | None = None) -> dict:
    return {
        "US": backfill_market_batch("US", batch_size=batch_size),
        "INDIA": backfill_market_batch("INDIA", batch_size=batch_size),
    }
