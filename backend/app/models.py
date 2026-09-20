from sqlalchemy import Column, Integer, String, Float, Date, DateTime, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    sector = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    is_active = Column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_company_symbol_exchange"
        ),
    )


class OHLCV(Base):
    __tablename__ = "ohlcv"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)

    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            "date",
            name="uq_ohlcv_symbol_exchange_date"
        ),
    )

class Fundamental(Base):
    __tablename__ = "fundamentals"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)

    market_cap = Column(Float, nullable=True)
    trailing_eps = Column(Float, nullable=True)
    forward_eps = Column(Float, nullable=True)
    revenue = Column(Float, nullable=True)
    net_income = Column(Float, nullable=True)
    profit_margin = Column(Float, nullable=True)
    return_on_equity = Column(Float, nullable=True)
    return_on_assets = Column(Float, nullable=True)

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_fundamental_symbol_exchange"
        ),
    )


class Ownership(Base):
    __tablename__ = "ownership"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)

    insider_percent = Column(Float, nullable=True)
    institution_percent = Column(Float, nullable=True)
    shares_outstanding = Column(Float, nullable=True)
    float_shares = Column(Float, nullable=True)

    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_ownership_symbol_exchange"
        ),
    )