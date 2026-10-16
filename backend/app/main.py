import logging
import os
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .database import engine, ensure_schema_compatibility, SessionLocal
from .models import Base
from .api.market import router as market_router
from .api.companies import router as companies_router
from .api.portfolio import router as portfolio_router
from .api.analytics import router as analytics_router
from .services.scheduler import start_scheduler
from .services.company_sync import bootstrap_companies_from_stored_data

logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Screener API")
app.state.db_ready = False
app.state.db_error = None
app.state.init_thread_started = False
app.state.init_thread = None
_init_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After", "X-Ranking-Cache", "Age"],
)

app.include_router(market_router)
app.include_router(companies_router)
app.include_router(portfolio_router)
app.include_router(analytics_router)


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _free_tier_compact_if_needed():
    """Report storage pressure without removing existing market observations."""
    if not _env_flag("FREE_TIER_MODE", True):
        return
    if getattr(engine.dialect, "name", "") != "postgresql":
        return
    threshold_mb = max(50, int(os.getenv("FREE_TIER_OHLCV_COMPACT_MB", "180") or 180))
    threshold_bytes = threshold_mb * 1024 * 1024
    try:
        with engine.begin() as conn:
            exists = conn.execute(text("SELECT to_regclass('public.ohlcv')")).scalar()
            if not exists:
                return
            size = conn.execute(text("SELECT pg_total_relation_size('public.ohlcv')")).scalar() or 0
            if int(size) >= threshold_bytes:
                logger.warning(
                    "FREE_TIER_MODE: OHLCV cache is %.1f MB; existing records retained. Review storage capacity.",
                    int(size) / 1024 / 1024,
                )
    except Exception:
        # A failed compaction must not prevent the API process from starting.
        logger.exception("FREE_TIER_MODE cache compaction failed")


def _database_initialize_loop():
    """Initialize PostgreSQL without making the whole web process fail cold-start.

    A short Railway/Postgres reconnect window should not turn the public backend
    domain into a 502.  The HTTP process starts immediately, while this daemon
    retries schema/bootstrap work and starts background jobs only after the DB is
    actually reachable.
    """
    delays = [0, 2, 5, 10, 20, 30, 60]
    attempt = 0
    while True:
        delay = delays[min(attempt, len(delays) - 1)]
        if delay:
            time.sleep(delay)
        try:
            _free_tier_compact_if_needed()
            Base.metadata.create_all(bind=engine)
            ensure_schema_compatibility()

            db = SessionLocal()
            try:
                bootstrap_companies_from_stored_data(db)
            except Exception:
                db.rollback()
                logger.exception("Stored-company bootstrap failed; continuing")
            finally:
                db.close()

            app.state.db_ready = True
            app.state.db_error = None
            try:
                start_scheduler()
            except Exception:
                logger.exception("Scheduler start failed; API remains available")
            logger.info("Database initialization completed")
            return
        except Exception as exc:
            app.state.db_ready = False
            app.state.db_error = str(exc)[:300]
            logger.exception("Database initialization attempt %s failed", attempt + 1)
            attempt += 1


def _start_initialization():
    with _init_lock:
        if app.state.init_thread is None or not app.state.init_thread.is_alive():
            app.state.init_thread_started = True
            app.state.init_thread = threading.Thread(target=_database_initialize_loop, daemon=True, name="db-init")
            app.state.init_thread.start()


@app.on_event("startup")
def startup_event():
    _start_initialization()


@app.middleware("http")
async def database_readiness(request, call_next):
    if request.url.path.startswith(("/market/", "/companies/", "/portfolios")) and not app.state.db_ready:
        _start_initialization()
        return JSONResponse(status_code=503, content={"detail": "Database is initializing or reconnecting; retry shortly"})
    return await call_next(request)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "Stock Screener API is running",
        "database": "ready" if app.state.db_ready else "initializing",
    }


@app.get("/health")
def health():
    # Do not report the database as ready until schema/bootstrap initialization
    # has completed. A bare SELECT 1 can succeed before create_all() finishes,
    # which previously let the frontend race into missing-table errors.
    if not app.state.db_ready:
        _start_initialization()
        return {
            "status": "initializing" if not app.state.db_error else "degraded",
            "database": "initializing" if not app.state.db_error else "unavailable",
            "detail": app.state.db_error,
        }
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ready"}
    except Exception as exc:
        app.state.db_ready = False
        app.state.db_error = str(exc)[:300]
        _start_initialization()
        return {
            "status": "degraded",
            "database": "unavailable",
            "detail": app.state.db_error,
        }
