from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base

from .config import settings


engine = create_engine(settings.database_url)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

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
