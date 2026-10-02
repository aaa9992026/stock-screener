import logging
import threading
import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import engine, ensure_schema_compatibility, SessionLocal
from .models import Base
from .api.market import router as market_router
from .api.companies import router as companies_router
from .services.scheduler import start_scheduler
from .services.company_sync import bootstrap_companies_from_stored_data

logger = logging.getLogger(__name__)

app = FastAPI(title="Stock Screener API")
app.state.db_ready = False
app.state.db_error = None
app.state.init_thread_started = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router)
app.include_router(companies_router)


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


@app.on_event("startup")
def startup_event():
    if not app.state.init_thread_started:
        app.state.init_thread_started = True
        threading.Thread(target=_database_initialize_loop, daemon=True, name="db-init").start()


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
        return {
            "status": "degraded",
            "database": "unavailable",
            "detail": app.state.db_error,
        }
