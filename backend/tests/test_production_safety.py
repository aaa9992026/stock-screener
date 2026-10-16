"""Production safety regressions; observations here are deterministic fixtures."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import unittest
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from app.models import Base, Company, RSHistory, OHLCV
from app.services import rs_universe_backfill as rs
from app.services.rs_history import persist_history, decode_points


class ProductionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_partial_refresh_preserves_verified_history(self):
        today = date.today()
        rows = [{'date': today-timedelta(days=i), 'open': 100, 'close': 101} for i in range(450)]
        original = persist_history(self.db, 'AAPL', 'US', rows)
        old_count = original.row_count
        last = original.last_date
        updated = persist_history(self.db, 'AAPL', 'US', [{'date': last, 'open': 102, 'close': 103}])
        self.assertEqual(updated.row_count, old_count)
        self.assertEqual(decode_points(updated.points_payload)[-1], (last, 102, 103))
        empty = persist_history(self.db, 'AAPL', 'US', [])
        self.assertEqual(empty.row_count, old_count)

    def test_progress_and_candidate_queries_do_not_select_payloads(self):
        self.db.add(Company(symbol='AAPL', exchange='US', name='Apple', is_active=1))
        persist_history(self.db, 'AAPL', 'US', [{'date': date.today()-timedelta(days=i), 'open': 100, 'close': 101} for i in range(450)])
        statements = []
        def capture(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement.lower())
        event.listen(self.engine, 'before_cursor_execute', capture)
        try:
            status = rs.universe_backfill_status(self.db, 'US')
            rs._candidate_companies(self.db, 'US', 1)
        finally:
            event.remove(self.engine, 'before_cursor_execute', capture)
        self.assertEqual(status['history_ready_symbols'], 1)
        for sql in statements:
            if 'select' in sql and 'rs_histories' in sql:
                selected = sql.split('from')[0]
                self.assertNotIn('rs_histories.points_payload as ', selected)
        self.assertFalse(status['scheduler']['running'])

    def test_large_postgres_table_is_never_deleted_at_startup(self):
        from app import main
        engine = MagicMock()
        engine.dialect.name = 'postgresql'
        conn = engine.begin.return_value.__enter__.return_value
        conn.execute.return_value.scalar.side_effect = ['ohlcv', 300*1024*1024]
        with patch.object(main, 'engine', engine), patch.dict(os.environ, {'FREE_TIER_MODE':'1'}):
            main._free_tier_compact_if_needed()
        statements = [str(c.args[0]).upper() for c in conn.execute.call_args_list]
        self.assertEqual(len(statements), 2)
        self.assertTrue(all(s.startswith('SELECT') for s in statements))

    def test_free_tier_registers_bounded_enrichment(self):
        from app.services import scheduler as jobs
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler = BackgroundScheduler()
        with patch.object(jobs, 'scheduler', scheduler), patch.object(scheduler, 'start'), patch.dict(os.environ, {'FREE_TIER_MODE':'1','FUNDAMENTAL_BACKFILL_ENABLED':'1'}):
            jobs.start_scheduler()
            self.assertIsNotNone(scheduler.get_job('fundamental_universe_backfill'))
            with patch.object(jobs, 'backfill_all_fundamentals_once', return_value={}) as run:
                jobs.refresh_universe_fundamentals()
                self.assertEqual(run.call_args.kwargs['batch_size'], 2)

    def test_compact_prices_count_without_claiming_full_ohlcv(self):
        from app.services.universe_data_backfill import universe_data_status
        self.db.add(Company(symbol='AAPL', exchange='US', name='Apple', is_active=1))
        persist_history(self.db, 'AAPL', 'US', [{'date':date.today()-timedelta(days=7),'open':100,'close':101}])
        status = universe_data_status(self.db, 'US')
        self.assertEqual(status['price_history_available'], 1)
        self.assertEqual(self.db.query(OHLCV).count(), 0)
        self.assertFalse(status['automatic_enrichment'])

    def test_dashboard_fetches_real_prices_without_stored_ohlcv(self):
        from app.api import market
        from types import SimpleNamespace
        rows = [SimpleNamespace(date=date.today()-timedelta(days=250-i),open=100+i,high=102+i,low=99+i,close=101+i,volume=1000) for i in range(250)]
        with patch.object(market, '_market_rows_with_live_fallback', return_value=rows) as live, patch.object(market, '_weighted_rs_against_benchmark', return_value=(None,None,{},None,[])):
            score, coverage = market._score_symbol(self.db, 'TCS', 'BSE', live_fallback=True)
        self.assertIsNotNone(score)
        self.assertGreater(coverage, 0)
        live.assert_called_once()

    def test_live_history_cache_has_a_fixed_memory_budget(self):
        from app.api import market
        day = date.today() - timedelta(days=date.today().weekday())
        rows = [dict(date=day, open=100, high=102, low=99, close=101, volume=1000)]
        with patch.dict(market._LIVE_ROW_CACHE, {}, clear=True), patch.object(market.YahooProvider, 'get_ohlcv', return_value=rows):
            for i in range(70):
                market._live_provider_rows(f'ZZ{i}', 'US')
            self.assertEqual(len(market._LIVE_ROW_CACHE), 64)
            self.assertNotIn(('US', 'ZZ0', 2), market._LIVE_ROW_CACHE)
            self.assertIn(('US', 'ZZ69', 2), market._LIVE_ROW_CACHE)


if __name__ == '__main__':
    unittest.main()
