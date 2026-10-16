"""Regression fixtures for confirmed live statement and scoring pipeline faults."""
import os
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import json
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Company, RankingSnapshot, Fundamental, Ownership
from app.api import market
from app.services.fundamental_sync import sync_fundamental_data
from app.services.providers.sec_provider import SECFundamentalsProvider
from app.services.sector_cohort import sector_scores
from app.services.sector_analytics import sector_analytics


class ScoringPipelineTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(bind=self.engine)
        self.db = self.sessions()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_sec_missing_q4_does_not_shift_yoy(self):
        values = [dict(start=start, end=end, val=value, form='10-Q', fp='Q3', filed='2026-08-01') for start,end,value in [
            ('2026-03-29','2026-06-27',110),('2025-12-28','2026-03-28',90),
            ('2025-03-30','2025-06-28',100),('2024-12-29','2025-03-29',80),
            ('2024-09-29','2024-12-28',40)]]
        facts={'facts':{'us-gaap':{'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':values}}}}}
        provider=object.__new__(SECFundamentalsProvider)
        with patch.object(provider,'_company_facts',return_value=facts):
            history=provider.get_history('AAPL')
        self.assertAlmostEqual(history['quarterly'][0]['yoy_sales'],10)
        self.assertIsNone(history['quarterly'][1]['qoq_sales'])

    def test_ranking_recomputes_raw_dates_instead_of_trusting_bad_growth(self):
        history={'quarterly':[{'period':p,'eps':v,'yoy_eps':999,'qoq_eps':999} for p,v in [('2026-06-27',11),('2026-03-28',9),('2025-06-28',10),('2025-03-29',8)]],'annual':[]}
        result=market._ranking_history_metric_score(history,'eps')
        self.assertAlmostEqual(result['latest_yoy'],10)
        self.assertLess(result['coverage'],100)

    def test_detail_and_ranking_use_same_statement_source(self):
        history={'quarterly':[{'period':'2026-06-30','eps':2.02,'pat':100,'sales':200}],'annual':[],'source':'Verified merged provider fixture'}
        with patch.dict(market._RANKING_ENRICH_CACHE,{},clear=True), patch.object(market.YahooProvider,'get_fundamental_history',return_value=history), patch.object(market.YahooProvider,'get_fundamentals',return_value={}), patch.object(market,'_get_ranking_sec_provider',side_effect=AssertionError('must not override merged history')):
            detail=market.get_fundamentals_history('AAPL','US')
            rank=market._fetch_ranking_enrichment({'symbol':'AAPL','exchange':'US'})
        self.assertEqual(detail,rank['history'])
        self.assertEqual(rank['financial_calculation_version'],market.FINANCIAL_CALCULATION_VERSION)

    def test_partial_snapshot_preserves_values_and_verified_zero(self):
        sync_fundamental_data(self.db,'AAPL','US',dict(revenue=100,net_income=20,institution_percent=.65,insider_percent=.02))
        sync_fundamental_data(self.db,'AAPL','US',dict(revenue=None,institution_percent=None,insider_percent=0))
        self.assertEqual(self.db.query(Fundamental).one().revenue,100)
        ownership=self.db.query(Ownership).one()
        self.assertEqual(ownership.institution_percent,.65)
        self.assertEqual(ownership.insider_percent,0)

    def test_ownership_only_gap_is_backfilled(self):
        from app.services import universe_data_backfill as worker
        self.db.add(Company(symbol='AAPL',exchange='US',name='Apple Inc',is_active=1))
        self.db.add(Fundamental(symbol='AAPL',exchange='US',market_cap=100,trailing_eps=1,revenue=100,net_income=10,updated_at=datetime.utcnow()-timedelta(days=2)))
        self.db.commit()
        with patch.object(worker,'SessionLocal',self.sessions), patch.object(worker.YahooProvider,'get_fundamentals',return_value=dict(revenue=100,institution_percent=.65,insider_percent=.01)) as provider:
            result=worker.backfill_market_fundamentals('US',1)
        self.assertEqual(result['updated'],1)
        provider.assert_called_once()
        self.db.expire_all()
        self.assertEqual(self.db.query(Ownership).one().institution_percent,.65)

    def test_sector_detail_and_filtered_analysis_share_cohort(self):
        for i in range(12):
            symbol=f'ZZ{i:02}'
            sector='Technology' if i<6 else 'Energy'
            self.db.add(Company(symbol=symbol,exchange='US',name=f'Company {i}',sector=sector,is_active=1))
            payload={'financial_calculation_version':market.FINANCIAL_CALCULATION_VERSION,'metadata':{'sector':sector},**{k:i for k in ['eps_latest_yoy','pat_latest_yoy','sales_latest_yoy','eps_acceleration','pat_acceleration','sales_acceleration']}}
            self.db.add(RankingSnapshot(symbol=symbol,exchange='US',payload_json=json.dumps(payload),updated_at=datetime.utcnow()))
        self.db.commit()
        stats,cohort,*_=sector_scores(self.db,'US')
        company=self.db.query(Company).filter_by(symbol='ZZ00').one()
        score,peers,_,selected_cohort=market._selected_sector_component(self.db,company)
        with patch.object(market,'_benchmark_close_points',return_value=([],None,None,None)):
            filtered=sector_analytics(self.db,'US','Technology')['rows'][0]
        self.assertEqual(score,stats['Technology']['score'])
        self.assertEqual(score,filtered['sector_rs_score'])
        self.assertEqual(cohort,selected_cohort)
        self.assertEqual(cohort,filtered['sector_cohort_id'])
        self.assertEqual(peers,6)

    def test_legacy_financial_snapshot_is_not_reused(self):
        self.db.add(RankingSnapshot(symbol='AAPL',exchange='US',payload_json=json.dumps({'fundamental_score':100}),updated_at=datetime.utcnow()))
        self.db.commit()
        with patch.object(market,'SessionLocal',self.sessions):
            self.assertEqual(market._load_persisted_ranking_enrichment([{'symbol':'AAPL','exchange':'US'}]),{})

    def test_week_based_fiscal_end_does_not_duplicate_calendar_quarter(self):
        from app.services.financial_periods import merge_statement_rows
        result=merge_statement_rows(
            [{'period':'2023-06-30','sales':100,'operating_cash_flow':20}],
            [{'period':'2023-07-01','sales':101,'operating_cash_flow':None}],12)
        self.assertEqual(len(result),1)
        self.assertEqual(result[0]['period'],'2023-07-01')
        self.assertEqual(result[0]['sales'],101)
        self.assertEqual(result[0]['operating_cash_flow'],20)

    def test_current_ownership_is_not_historical_aggregate_evidence(self):
        from unittest.mock import MagicMock
        from app.services.providers.yahoo_provider import YahooProvider
        ticker=MagicMock()
        ticker.info={'heldPercentInstitutions':.65,'heldPercentInsiders':.02}
        ticker.institutional_holders=None
        ticker.mutualfund_holders=None
        ticker.insider_transactions=None
        ticker.major_holders=None
        with patch('app.services.providers.yahoo_provider.yf.Ticker',return_value=ticker):
            result=YahooProvider().get_ownership_details('AAPL','US')
        self.assertEqual(result['current_summary']['institutional_percent'],65)
        self.assertFalse(result['historical_aggregate_series_available'])
        self.assertEqual(result['historical_score_status'],'BLOCKED')

    def test_sec_quarter_cfo_does_not_use_ytd_cash_flow(self):
        def fact(start,end,value):
            return dict(start=start,end=end,val=value,form='10-Q',fp='Q2',filed='2026-08-01')
        sales=[fact('2026-03-29','2026-06-27',110)]
        cfo=[fact('2026-03-29','2026-06-27',20),fact('2025-09-28','2026-06-27',100)]
        facts={'facts':{'us-gaap':{
            'RevenueFromContractWithCustomerExcludingAssessedTax':{'units':{'USD':sales}},
            'NetCashProvidedByUsedInOperatingActivities':{'units':{'USD':cfo}}}}}
        provider=object.__new__(SECFundamentalsProvider)
        with patch.object(provider,'_company_facts',return_value=facts):
            history=provider.get_history('AAPL')
        self.assertEqual(history['quarterly'][0]['operating_cash_flow'],20)
        facts['facts']['us-gaap']['NetCashProvidedByUsedInOperatingActivities']['units']['USD']=cfo[1:]
        with patch.object(provider,'_company_facts',return_value=facts):
            history=provider.get_history('AAPL')
        self.assertIsNone(history['quarterly'][0]['operating_cash_flow'])


if __name__ == '__main__':
    unittest.main()
