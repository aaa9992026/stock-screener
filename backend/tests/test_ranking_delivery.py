"""Ranking delivery bounds; explicit test data never enters production."""
import os
os.environ['DATABASE_URL']='sqlite:///:memory:'
import json
import tempfile
import threading
import time
import unittest
from datetime import date,datetime,timedelta
from pathlib import Path
from unittest.mock import patch
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.models import Base,RankingResponse,RankingSnapshot
from app.services.ranking_delivery import RankingDelivery
from app.api import market


class RankingDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.engine=create_engine('sqlite:///'+str(Path(self.tmp.name)/'ranking.sqlite'),connect_args={'check_same_thread':False})
        Base.metadata.create_all(self.engine)
        self.factory=sessionmaker(bind=self.engine)
        self.db=self.factory();self.delivery=RankingDelivery();self.gate=threading.Event();self.calls=0
        self.args=dict(market='US',limit=200,candidate_limit=220,technical_weight=25.,fundamental_weight=30.,ownership_weight=15.,sector_weight=5.,relative_strength_weight=25.)

    def tearDown(self):
        self.gate.set();self.idle();self.db.close();self.engine.dispose();self.tmp.cleanup()

    def idle(self):
        deadline=time.monotonic()+5
        while self.delivery.running and time.monotonic()<deadline:time.sleep(.005)
        self.assertFalse(self.delivery.running)

    def build(self,db,**args):
        self.calls+=1
        self.gate.wait(3)
        return {'market':args['market'],'rows':[{'symbol':'TEST','composite_score':0,'ownership_score':None}], 'snapshot_at':'dated-test-snapshot'}

    def serve(self,args=None,builder=None):
        return self.delivery.serve(self.db,args or self.args,self.factory,builder or self.build)

    def warm(self):
        self.gate.set()
        with self.assertRaises(HTTPException):self.serve()
        self.idle()
        return self.serve()

    def age(self,seconds):
        self.delivery.cache.clear();self.db.expire_all()
        row=self.db.get(RankingResponse,'US');row.updated_at=datetime.utcnow()-timedelta(seconds=seconds);self.db.commit()

    def test_cold_burst_is_single_flight_and_does_not_wait_for_build(self):
        start=time.monotonic()
        for _ in range(20):
            with self.assertRaises(HTTPException) as caught:self.serve()
            self.assertEqual(caught.exception.detail['code'],'RANKING_WARMING')
            self.assertEqual(caught.exception.status_code,503)
        self.assertLess(time.monotonic()-start,1)
        self.assertTrue(self.gate.wait(.01) is False)
        self.assertEqual(len(self.delivery.active)+len(self.delivery.pending),1)
        self.gate.set();self.idle()
        response=self.serve()
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.headers['x-ranking-cache'],'fresh')
        self.assertEqual(json.loads(response.body)['rows'][0]['ownership_score'],None)
        self.assertEqual(self.calls,1)

    def test_persisted_response_survives_process_cache_loss(self):
        expected=self.warm().body
        self.delivery=RankingDelivery()
        response=self.serve(builder=lambda **_:self.fail('must not rebuild a fresh persisted response'))
        self.assertEqual(response.body,expected)
        self.assertEqual(self.db.query(RankingResponse).count(),1)

    def test_changed_weights_never_receive_other_configuration(self):
        self.warm();self.gate.clear()
        changed={**self.args,'technical_weight':0.}
        with self.assertRaises(HTTPException):self.serve(changed)
        self.gate.set();self.idle()
        self.assertEqual(self.calls,2)

    def test_stale_response_returns_while_one_refresh_runs(self):
        old=self.warm().body;self.age(121);self.gate.clear()
        start=time.monotonic();response=self.serve()
        self.assertEqual(response.body,old)
        self.assertEqual(response.headers['x-ranking-cache'],'stale')
        self.assertLess(time.monotonic()-start,.5)
        self.gate.set();self.idle()

    def test_expired_response_is_not_served_as_current(self):
        self.warm();self.age(901);self.gate.clear()
        with self.assertRaises(HTTPException):self.serve()
        self.gate.set();self.idle()

    def test_memory_failure_is_sanitized_and_retries_back_off(self):
        def fail(**_):
            self.calls+=1
            raise MemoryError('secret-token-do-not-log')
        with self.assertLogs('app.services.ranking_delivery',level='ERROR') as logs:
            with self.assertRaises(HTTPException):self.serve(builder=fail)
            self.idle()
        self.assertIn('MemoryError',' '.join(logs.output));self.assertNotIn('secret-token',' '.join(logs.output))
        with self.assertRaises(HTTPException):self.serve(builder=fail)
        self.assertEqual(self.calls,1)

    def test_failed_refresh_preserves_previous_completed_database_response(self):
        old=self.warm().body;self.age(121)
        with self.assertLogs('app.services.ranking_delivery',level='ERROR'):
            response=self.serve(builder=lambda **_:(_ for _ in ()).throw(RuntimeError('failure')))
            self.idle()
        self.assertEqual(response.body,old)
        self.db.expire_all();self.assertEqual(self.db.get(RankingResponse,'US').payload_json.encode(),old)

    def test_database_failure_never_logs_sql_or_parameters(self):
        with patch.object(self.db,'get',side_effect=OperationalError('secret-query',{'password':'secret-value'},Exception('secret-message'))),self.assertLogs('app.services.ranking_delivery',level='ERROR') as logs:
            with self.assertRaises(HTTPException) as caught:self.serve()
        self.assertEqual(caught.exception.status_code,503)
        self.assertNotIn('secret',' '.join(logs.output))

    def test_enrichment_query_only_materializes_requested_candidates(self):
        self.db.bulk_insert_mappings(RankingSnapshot,[dict(symbol='T'+str(i),exchange='US',payload_json=json.dumps({'financial_calculation_version':market.FINANCIAL_CALCULATION_VERSION,'fundamental_score':0}),updated_at=datetime.utcnow()) for i in range(300)])
        self.db.commit();loaded=[]
        def observe(session,instance):
            if isinstance(instance,RankingSnapshot):loaded.append(instance.symbol)
        event.listen(self.factory,'loaded_as_persistent',observe)
        try:
            with patch.object(market,'SessionLocal',self.factory):result=market._load_persisted_ranking_enrichment([{'exchange':'US','symbol':'T1'}])
        finally:event.remove(self.factory,'loaded_as_persistent',observe)
        self.assertEqual(loaded,['T1'])
        self.assertEqual(result[('US','T1')]['fundamental_score'],0)

    def test_both_http_markets_wait_off_request_and_return_own_snapshot(self):
        app=FastAPI();app.include_router(market.router)
        app.dependency_overrides[market.get_db]=lambda:self.db
        @app.get('/health')
        def health():
            from sqlalchemy import text
            self.db.execute(text('SELECT 1'))
            return {'status':'ok'}
        client=TestClient(app)
        with patch.object(market,'delivery',self.delivery),patch.object(market,'SessionLocal',self.factory),patch.object(market,'get_top_composite_dashboard',side_effect=self.build):
            for name in ['US','INDIA']:
                response=client.get('/market/top-composite',params={'market':name,'candidate_limit':220})
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.json()['detail']['code'],'RANKING_WARMING')
            self.assertEqual(client.get('/health').json(),{'status':'ok'})
            self.gate.set();self.idle()
            for name in ['US','INDIA']:
                response=client.get('/market/top-composite',params={'market':name,'candidate_limit':220})
                self.assertEqual(response.status_code,200)
                self.assertEqual(response.json()['market'],name)
            self.assertEqual(client.get('/market/top-composite?limit=201').status_code,422)
            self.assertEqual(client.get('/market/top-composite?technical_weight=inf').status_code,400)
        self.assertEqual(self.calls,2)

    def test_oversized_response_is_not_persisted_or_returned(self):
        with self.assertLogs('app.services.ranking_delivery',level='ERROR'):
            with self.assertRaises(HTTPException):
                self.serve(builder=lambda **_:{'rows':['x'*(2*1024*1024)]})
            self.idle()
        self.assertEqual(self.db.query(RankingResponse).count(),0)

    def test_rs_fallback_does_not_read_covered_ohlcv_histories(self):
        from test_completion import observations
        from app.models import Company,OHLCV,RSHistory
        from app.services.rs_history import encode_points
        rows=observations();payload,points=encode_points(rows)
        self.db.add(Company(symbol='AAPL',exchange='US',name='Apple Inc.',is_active=1))
        self.db.add(RSHistory(symbol='AAPL',exchange='US',points_payload=payload,first_date=date.fromisoformat(points[0][0]),last_date=rows[-1]['date'],row_count=len(points)))
        self.db.add_all([OHLCV(symbol='AAPL',exchange='US',**r) for r in rows])
        self.db.commit();queries=[]
        def record(conn,cursor,statement,parameters,context,executemany):queries.append(statement)
        event.listen(self.engine,'before_cursor_execute',record)
        try:
            metrics,_=market._rs_universe_metrics(self.db,'US',[(r['date'],r['open'],r['close']) for r in rows])
        finally:event.remove(self.engine,'before_cursor_execute',record)
        self.assertIn('US:AAPL',metrics)
        self.assertFalse(any('FROM ohlcv' in sql for sql in queries))

    def test_full_statement_memory_cache_has_a_fixed_bound(self):
        market._RANKING_ENRICH_CACHE.clear()
        try:
            with patch.object(market,'_verified_fundamental_history',return_value=None),patch.object(market.YahooProvider,'get_fundamentals',return_value={}):
                for i in range(600):
                    payload=market._fetch_ranking_enrichment({'exchange':'US','symbol':'TEST'+str(i)})
                    self.assertIsNone(payload['fundamental_score'])
            self.assertEqual(len(market._RANKING_ENRICH_CACHE),market._RANKING_ENRICH_CACHE_LIMIT)
        finally:market._RANKING_ENRICH_CACHE.clear()

    def test_many_configurations_cannot_spawn_unbounded_builds_or_responses(self):
        for i in range(20):
            with self.assertRaises(HTTPException):
                self.serve({**self.args,'technical_weight':float(i+1)})
        self.assertLessEqual(len(self.delivery.pending),8)
        self.assertLessEqual(len(self.delivery.active),1)
        self.gate.set();self.idle()
        self.assertLessEqual(self.calls,9)
        self.assertLessEqual(len(self.delivery.cache),8)
        # One replaceable complete-response slot per market; no growing history cache.
        self.assertEqual(self.db.query(RankingResponse).count(),1)
