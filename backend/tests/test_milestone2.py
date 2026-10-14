"""Deterministic calculation fixtures only; never production observations."""
import os
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["FREE_TIER_MODE"] = "1"
import json
import math
import unittest
from datetime import date, timedelta, datetime
from types import SimpleNamespace
from unittest.mock import patch
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.models import Base, RSHistory, Company, RankingSnapshot
from app.services.risk_metrics import weekly_beta
from app.services.financial_periods import align_financial_history
from app.services.trade_backtest import simulate, HistoricalDataUnavailable
from app.services.rs_universe_backfill import _persist_retry
from app.api.portfolio import create_portfolio, add_trade, portfolio_summary, PortfolioInput, TradeInput
from fastapi import HTTPException


class MasterCalculationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_beta_known_two_and_date_alignment(self):
        asof = date(2026, 10, 14)
        stock, benchmark, s, b = [], [], 100, 100
        start = asof - timedelta(days=740)
        for i in range(105):
            day = start + timedelta(weeks=i)
            value = .003 + math.sin(i * .7) * .01
            b *= 1 + value
            s *= 1 + 2 * value
            stock.append((day, s)); benchmark.append((day, b))
        result = weekly_beta(stock, benchmark, asof)
        self.assertAlmostEqual(result["beta"], 2, places=5)
        self.assertGreaterEqual(result["observations"], 100)
        wrong_dates = [(d + timedelta(days=1), c) for d, c in benchmark]
        self.assertIsNone(weekly_beta(stock, wrong_dates, asof)["beta"])
        self.assertIsNone(weekly_beta(stock[:10], benchmark[:10], asof)["beta"])
        self.assertIsNone(weekly_beta(stock, [(d, 100) for d, _ in benchmark], asof)["beta"])

    def test_repeated_idle_checkpoints_remain_bounded(self):
        from app.services import rs_universe_backfill as backfill
        from app.models import RSBackfillState
        with patch.object(backfill, "SessionLocal", sessionmaker(bind=self.engine)):
            for _ in range(20):
                result = backfill.backfill_market_batch("US", 1)
                self.assertEqual(result["status"], "idle")
                self.db.expire_all()
                state = self.db.query(RSBackfillState).filter_by(market="US").one()
                self.assertLess(len(state.payload_json), 5000)
                self.assertNotIn("last_batch", json.loads(state.payload_json)["before"])

    def test_scoring_cohort_requires_same_history_as_progress(self):
        from app.api.market import _rs_universe_metrics
        from app.services.rs_history import persist_history, decode_points
        from test_completion import observations
        self.db.add(Company(symbol="AAPL", exchange="US", name="Test only", is_active=1))
        self.db.commit()
        item = persist_history(self.db, "AAPL", "US", observations()[-220:])
        points = decode_points(item.points_payload)
        metrics, _ = _rs_universe_metrics(self.db, "US", points)
        self.assertEqual(metrics, {})

    def test_fiscal_missing_quarter_not_shifted(self):
        result = align_financial_history({"quarterly": [
            {"period": "2026-06-30", "eps": 3},
            {"period": "2025-12-31", "eps": 2},
            {"period": "2025-06-30", "eps": 1},
        ]})["quarterly"]
        self.assertEqual(result[0]["yoy_eps"], 200)
        self.assertIsNone(result[0]["qoq_eps"])

    def test_retry_exponential_and_persistent(self):
        now = datetime.now()
        _persist_retry(self.db, "US", "TEST", "error", "rate limit", now)
        self.db.expire_all()
        first = self.db.query(RSHistory).one().retry_after
        _persist_retry(self.db, "US", "TEST", "error", "rate limit", now)
        self.db.expire_all()
        second = self.db.query(RSHistory).one()
        self.assertEqual(second.retry_count, 2)
        self.assertGreater((second.retry_after - first).total_seconds(), 7100)

    def test_portfolio_reconciles_partial_sales_and_idempotency(self):
        inception = date.today() - timedelta(days=10)
        portfolio = create_portfolio(PortfolioInput(name="TEST ONLY", inception_date=inception, starting_capital=10000, max_position_percent=100, max_exposure_percent=100, risk_percent=100, commission_bps=10), self.db)
        rows = [SimpleNamespace(date=inception, open=100, high=101, low=99, close=100), SimpleNamespace(date=date.today(), open=120, high=121, low=119, close=120)]
        buy = TradeInput(request_id="buy", symbol="AAPL", exchange="US", side="BUY", date=inception, quantity=10)
        with patch("app.api.portfolio._market_rows_with_live_fallback", return_value=rows):
            first = add_trade(portfolio["id"], buy, self.db)
            duplicate = add_trade(portfolio["id"], buy, self.db)
            self.assertEqual(first["cash"], 8999)
            self.assertTrue(duplicate["duplicate"])
            add_trade(portfolio["id"], TradeInput(request_id="sell", symbol="AAPL", exchange="US", side="SELL", date=date.today(), quantity=4), self.db)
            result = portfolio_summary(portfolio["id"], self.db)
        self.assertEqual(result["cash"], 9478.52)
        self.assertEqual(result["positions"][0]["quantity"], 6)
        self.assertEqual(result["equity"], 10198.52)
        self.assertEqual(result["realized_pnl"], 79.12)
        self.assertAlmostEqual(result["realized_pnl"] + result["unrealized_pnl"], result["equity"] - 10000)

    def test_portfolio_rejects_overselling_currency_future_and_cash(self):
        inception = date.today() - timedelta(days=3)
        portfolio = create_portfolio(PortfolioInput(name="TEST ONLY", inception_date=inception, starting_capital=100, max_position_percent=100, max_exposure_percent=100, risk_percent=100), self.db)
        row = SimpleNamespace(date=date.today(), close=200)
        with patch("app.api.portfolio._market_rows_with_live_fallback", return_value=[row]):
            for side, exchange, day in [("BUY", "US", date.today()), ("SELL", "US", date.today()), ("BUY", "NSE", date.today()), ("BUY", "US", date.today() + timedelta(days=1))]:
                with self.assertRaises(HTTPException):
                    add_trade(portfolio["id"], TradeInput(request_id=side + exchange + str(day), symbol="TEST", exchange=exchange, side=side, date=day, quantity=1), self.db)

    def test_trade_simulation_independent_accounting_and_no_future_signal(self):
        start = date.today() - timedelta(days=100)
        rows = [{"date": start + timedelta(days=i), "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 1000} for i in range(100)]
        cfg = dict(start_date=start + timedelta(days=10), end_date=date.today(), components=["technical"], starting_capital=10000, ema_period=5, initial_stop_percent=20, trailing_stop_percent=50, allocation_percent=50, risk_percent=100, commission_bps=10, slippage_bps=0)
        result = simulate(rows, rows, cfg)
        self.assertEqual(result["trade_count"], 1)
        trade = result["trades"][0]
        self.assertLess(trade["signal_date"], trade["entry_date"])
        expected = (trade["exit_price"] - trade["entry_price"]) * trade["quantity"] - trade["entry_fee"] - trade["exit_fee"]
        self.assertAlmostEqual(result["net_profit"], expected)
        self.assertAlmostEqual(result["total_return_percent"], expected / 10000 * 100)
        expected_cagr = (result["ending_value"] / 10000) ** (365.25 / 89) - 1
        self.assertAlmostEqual(result["cagr_percent"], expected_cagr * 100)
        self.assertAlmostEqual(result["equity_curve"][-1]["equity"], result["ending_value"])
        self.assertTrue(all(p["cash"] >= 0 for p in result["equity_curve"]))
        with self.assertRaises(HistoricalDataUnavailable):
            simulate(rows, rows, {**cfg, "components": ["fundamental"]})

    def test_trailing_stop_does_not_use_same_bar_high(self):
        start = date.today() - timedelta(days=110)
        rows = [{"date": start + timedelta(days=i), "open": 100 + i, "high": 101 + i, "low": 99 + i, "close": 100 + i, "volume": 1000} for i in range(100)]
        rows[21].update(open=121, high=200, low=120, close=190)
        rows[22].update(open=121, high=122, low=120, close=121)
        cfg = dict(start_date=rows[20]["date"], end_date=date.today(), components=["technical"], starting_capital=10000, ema_period=5, initial_stop_percent=10, trailing_stop_percent=10, allocation_percent=100, risk_percent=100)
        result = simulate(rows, rows, cfg)
        first = result["trades"][0]
        self.assertEqual(first["exit_date"], str(rows[22]["date"]))
        self.assertEqual(first["exit_reason"], "Gap through stop")
        self.assertEqual(first["exit_price"], 121)

    def test_sector_market_separation_and_missing_breadth(self):
        from app.api.market import _sector_scores_from_enriched
        rows = [{"symbol": "A", "exchange": "US", "sector": "Technology"}, {"symbol": "B", "exchange": "US", "sector": "Energy"}]
        values = {("US", "A"): {"eps_latest_yoy": 10, "pat_latest_yoy": 10}, ("US", "B"): {"eps_latest_yoy": 20, "pat_latest_yoy": 20}}
        result = _sector_scores_from_enriched(rows, values)
        self.assertIsNone(result["Energy"]["growth_breadth"])
        self.assertEqual(result["Energy"]["score"], 55)
        self.assertIsNone(_sector_scores_from_enriched(rows[:1], values)["Technology"]["score"])


if __name__ == "__main__":
    unittest.main()
