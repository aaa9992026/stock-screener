from sqlalchemy import Column, Integer, String, Float, Date, DateTime, Text, UniqueConstraint
from sqlalchemy.sql import func

from .database import Base


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    isin = Column(String, nullable=True, index=True)
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

class RankingSnapshot(Base):
    """Compact persisted Top-200 enrichment cache.

    This stores only derived scores and small provider metadata, never OHLCV
    history, so it is safe for the 500 MB Railway volume.
    """
    __tablename__ = "ranking_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "exchange",
            name="uq_ranking_snapshot_symbol_exchange"
        ),
    )



class RSHistory(Base):
    """Compact real-provider history and retry state; survives OHLCV compaction."""
    __tablename__ = "rs_histories"
    id = Column(Integer, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    points_payload = Column(Text, nullable=True)
    first_date = Column(Date)
    last_date = Column(Date)
    row_count = Column(Integer, default=0)
    status = Column(String, default="pending")
    provider = Column(String)
    error = Column(Text)
    retry_after = Column(DateTime)
    retry_count = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("symbol", "exchange", name="uq_rs_history_symbol_exchange"),)


class RSBackfillState(Base):
    __tablename__ = "rs_backfill_states"
    market = Column(String, primary_key=True)
    evaluation_date = Column(Date)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class RankingResponse(Base):
    """Last complete response per market; additive cache, not financial history."""
    __tablename__ = "ranking_responses"
    market = Column(String, primary_key=True)
    request_key = Column(String, nullable=False)
    payload_json = Column(Text, nullable=False)
    updated_at = Column(DateTime, nullable=False, default=func.now())


class ScoreSnapshot(Base):
    """Immutable, compact scoring source for a ranking row and its detail/export."""
    __tablename__ = "score_snapshots"
    id = Column(String, primary_key=True)
    symbol = Column(String, nullable=False, index=True)
    exchange = Column(String, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now(), index=True)


class Portfolio(Base):
    __tablename__ = "portfolios"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    currency = Column(String, nullable=False)
    inception_date = Column(Date, nullable=False)
    starting_capital = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    max_position_percent = Column(Float, nullable=False)
    max_exposure_percent = Column(Float, nullable=False)
    risk_percent = Column(Float, nullable=False)
    commission_bps = Column(Float, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class PortfolioTrade(Base):
    __tablename__ = "portfolio_trades"
    id = Column(String, primary_key=True)
    portfolio_id = Column(String, nullable=False, index=True)
    request_id = Column(String, nullable=False)
    sequence = Column(Integer, nullable=False)
    symbol = Column(String, nullable=False)
    exchange = Column(String, nullable=False)
    side = Column(String, nullable=False)
    date = Column(Date, nullable=False)
    quantity = Column(Integer, nullable=False)
    price = Column(Float, nullable=False)
    fee = Column(Float, nullable=False)
    initial_stop = Column(Float)
    realized_pnl = Column(Float, default=0)
    __table_args__ = (UniqueConstraint("portfolio_id", "request_id", name="uq_portfolio_request"),)


class PortfolioValuation(Base):
    __tablename__ = "portfolio_valuations"
    id = Column(Integer, primary_key=True)
    portfolio_id = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    equity = Column(Float, nullable=False)
    cash = Column(Float, nullable=False)
    __table_args__ = (UniqueConstraint("portfolio_id", "date", name="uq_portfolio_valuation"),)
