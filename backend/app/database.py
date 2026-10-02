from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings


def _normalize_database_url(url: str) -> str:
    """Accept both modern SQLAlchemy and legacy Railway/Postgres URL forms."""
    value = str(url or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://"):]
    return value


DATABASE_URL = _normalize_database_url(settings.database_url)

engine_kwargs = {
    # Railway/Postgres can close idle connections. Validate every pooled
    # connection before using it so a stale socket does not blank the UI.
    "pool_pre_ping": True,
}
if DATABASE_URL.startswith("postgresql"):
    engine_kwargs.update({
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
        "pool_timeout": 20,
        "connect_args": {"connect_timeout": 10},
    })
elif DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def database_ping() -> bool:
    """Return True only when the configured database accepts a simple query."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def ensure_schema_compatibility():
    """Add small backwards-compatible columns required by newer deployments.

    SQLAlchemy create_all() does not alter existing Railway/Postgres tables, so
    keep additive schema upgrades explicit and safe.
    """
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())
    if "companies" not in tables:
        return
    columns = {col["name"] for col in inspector.get_columns("companies")}
    if "isin" not in columns:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE companies ADD COLUMN isin VARCHAR"))
