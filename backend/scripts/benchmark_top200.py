"""Run from repository root with backend dependencies: python backend/scripts/benchmark_top200.py.
Isolated synthetic identities with recorded provider prices, never a production load test.
"""
import os,json,time,tracemalloc,sys
from pathlib import Path
from datetime import date,datetime
from unittest.mock import patch
from sqlalchemy import create_engine,event
from sqlalchemy.orm import sessionmaker
os.environ['DATABASE_URL']='sqlite:///'+str(Path('.completion-qa/ranking-502.sqlite').resolve())
os.environ['FREE_TIER_MODE']='1'
sys.path.insert(0,str(Path('backend').resolve()))
from app.models import Base,Company,Fundamental,Ownership,RSHistory,RankingSnapshot,RSBackfillState
from app.api import market
from app.services.rs_history import encode_points
label='http'
fixture=json.loads(Path('docs/ranking-502-fix-2026-10-16/benchmark-provider-inputs.json').read_text())
Path('.completion-qa').mkdir(exist_ok=True)
engine=create_engine(os.environ['DATABASE_URL']);Base.metadata.create_all(engine);Session=sessionmaker(bind=engine);db=Session()
real=fixture['stock']
benchmark=fixture['benchmark'];points=[(date.fromisoformat(r['date']),r['open'],r['close']) for r in benchmark if r['date']>='2025-04-20']
end=min(real[-1]['date'],points[-1][0].isoformat());points=[p for p in points if p[0].isoformat()<=end]
payload,ordered=encode_points(real)
history=fixture['statements'];bundle=market._ranking_snapshot_payload(market._ranking_fundamental_bundle(history))
encoded=json.dumps(bundle)
def symbol(i):
 out='';i+=1
 while i:out=chr(65+i%26)+out;i//=26
 return 'ZZ'+out
if db.query(Company).count()==0:
 for group,total,ready in [('US',5756,5426),('INDIA',5278,4423)]:
  companies=[];funds=[];owners=[];histories=[];snapshots=[]
  for i in range(total):
   ex='US' if group=='US' else 'NSE' if i%2==0 else 'BSE';sym=symbol(i)
   companies.append(dict(symbol=sym,exchange=ex,name='Benchmark Industries',sector='Technology',is_active=1))
   funds.append(dict(symbol=sym,exchange=ex,market_cap=total-i,trailing_eps=2,revenue=100,net_income=10,profit_margin=.1,return_on_equity=.1))
   owners.append(dict(symbol=sym,exchange=ex,institution_percent=.6,insider_percent=.01))
   snapshots.append(dict(symbol=sym,exchange=ex,payload_json=encoded,updated_at=datetime.utcnow()))
   if i<ready:histories.append(dict(symbol=sym,exchange=ex,points_payload=payload,first_date=date.fromisoformat(ordered[0][0]),last_date=date.fromisoformat(end),row_count=len(ordered),status='success'))
  for model,values in [(Company,companies),(Fundamental,funds),(Ownership,owners),(RSHistory,histories),(RankingSnapshot,snapshots)]:db.bulk_insert_mappings(model,values)
  db.add(RSBackfillState(market=group,evaluation_date=date.fromisoformat(end),payload_json='{}'));db.commit()

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.services.ranking_delivery import RankingDelivery
from app.models import RankingResponse,ScoreSnapshot
from statistics import median
# Delete only this isolated benchmark's new response cache, never source history.
db.query(RankingResponse).delete();db.commit()
delivery=RankingDelivery();app=FastAPI();app.include_router(market.router)
def get_db():
 session=Session()
 try:yield session
 finally:session.close()
app.dependency_overrides[market.get_db]=get_db
@app.get('/health')
def health():
 from sqlalchemy import text
 with Session() as session:session.execute(text('SELECT 1'))
 return {'status':'ok'}
client=TestClient(app);calculations=[];original=market.get_top_composite_dashboard

def build(**kw):
 t=time.perf_counter();result=original(**kw);calculations.append({'market':kw['market'],'seconds':time.perf_counter()-t});return result
reports=[]
with patch.object(market,'delivery',delivery),patch.object(market,'SessionLocal',Session),patch.object(market,'get_top_composite_dashboard',side_effect=build),patch.object(market,'_benchmark_close_points',return_value=(points,'INDEX','Benchmark','recorded-input benchmark')),patch.object(market,'_live_close_history_for_candidates',side_effect=lambda rows:{(r['exchange'],r['symbol']):[p['close'] for p in real] for r in rows}),patch.object(market,'_warm_ranking_enrichment_background'),patch('app.services.risk_metrics.cached_beta_batch',return_value={}):
 for group in ['US','INDIA']:
  url=f'/market/top-composite?market={group}&limit=200&candidate_limit=220'
  t=time.perf_counter();cold=client.get(url);cold_elapsed=time.perf_counter()-t
  assert cold.status_code==503 and cold.json()['detail']['code']=='RANKING_WARMING'
  burst=[]
  for i in range(10):
   t=time.perf_counter();r=client.get(url);burst.append({'status':r.status_code,'seconds':time.perf_counter()-t})
   assert r.status_code in (200,503)
  t=time.perf_counter();assert client.get('/health').status_code==200;health_elapsed=time.perf_counter()-t
  deadline=time.monotonic()+120
  while delivery.running and time.monotonic()<deadline:time.sleep(.05)
  assert not delivery.running
  hits=[];ids=[]
  for _ in range(10):
   t=time.perf_counter();response=client.get(url);hits.append(time.perf_counter()-t)
   assert response.status_code==200
   body=response.json();ids.append([r['snapshot_id'] for r in body['rows']])
  assert all(v==ids[0] for v in ids)
  with Session() as saved:
   for row in body['rows']:
    snapshot=saved.get(ScoreSnapshot,row['snapshot_id']);assert json.loads(snapshot.payload_json)['composite_score']==row['composite_score']
  # Simulate a process restart: load the completed response from SQLite.
  restarted=RankingDelivery()
  with patch.object(market,'delivery',restarted):
   t=time.perf_counter();again=client.get(url);restart_elapsed=time.perf_counter()-t
  assert again.status_code==200 and again.content==response.content
  reports.append({'market':group,'cold_status':cold.status_code,'cold_seconds':cold_elapsed,'burst':burst,'health_while_building_seconds':health_elapsed,'warm_http_median_seconds':median(hits),'warm_http_max_seconds':max(hits),'restart_read_seconds':restart_elapsed,'rows':len(body['rows']),'response_bytes':len(response.content),'stable_immutable_snapshot_ids':True,'snapshot_database_matches':True,'cohort':body['rs_progress']})
  print(json.dumps(reports[-1]),flush=True)
assert len(calculations)==2
Path('docs/ranking-502-fix-2026-10-16/http-load.json').write_text(json.dumps({'scope':'Local actual FastAPI HTTP routes with production-sized isolated persisted SQLite cohorts; repeated recorded provider prices; provider I/O stubbed. No production load test.','calculations':calculations,'results':reports},indent=2),encoding='utf-8')
db.close();engine.dispose()
