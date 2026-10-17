"""Bounded public GET smoke check after an explicitly approved deployment.
No credentials, database access, POSTs, forced refreshes or deployment actions.
"""
import argparse
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--backend', default='https://stock-screener-production-d90e.up.railway.app')
parser.add_argument('--frontend', default='https://stock-screener-two-pied.vercel.app')
parser.add_argument('--output', default='.completion-qa/approved-release-public-checks.json')
args = parser.parse_args()
checks = []

def get(base, path):
    started = time.monotonic()
    try:
        with urllib.request.urlopen(base.rstrip('/') + path, timeout=20) as response:
            status, headers, raw = response.status, response.headers, response.read(2*1024*1024+1)
    except urllib.error.HTTPError as error:
        status, headers, raw = error.code, error.headers, error.read(2000)
    except (OSError, TimeoutError) as error:
        status, headers, raw = 0, {}, type(error).__name__.encode()
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeError):
        body = None
    checks.append({'at': datetime.now(timezone.utc).isoformat(), 'path':path, 'base':base,
                   'status':status, 'seconds':round(time.monotonic()-started,3),
                   'bytes':len(raw), 'sha256':hashlib.sha256(raw).hexdigest(),
                   'retry_after':headers.get('Retry-After'),
                   'cache':headers.get('X-Ranking-Cache'), 'age':headers.get('Age'),
                   'request_id':headers.get('X-Railway-Request-Id'),
                   'body':body if status!=200 else None})
    print(status, path, flush=True)
    return status, body

get(args.frontend, '/')
health, _ = get(args.backend, '/health')
if health == 200:
    for group in ['US','INDIA']:
        _, population = get(args.backend, '/companies/rs-backfill/status?market='+group)
        checks[-1]['population'] = population
        path = '/market/top-composite?market='+group+'&candidate_limit=220&limit=200'
        deadline = time.monotonic()+50
        status, body = get(args.backend, path)
        # Retry only the application's explicit warmup, never generic 502/503.
        for _ in range(9):
            detail = body.get('detail') if isinstance(body,dict) else None
            if status!=503 or not isinstance(detail,dict) or detail.get('code')!='RANKING_WARMING' or time.monotonic()+5>=deadline:
                break
            time.sleep(5)
            status, body = get(args.backend, path)
        if status==200 and isinstance(body,dict):
            rows=body.get('rows',[]);weights=body.get('score_weights',{})
            fields={'technical':'technical_score','fundamental':'fundamental_score',
                    'relative_strength':'rs_score','ownership':'ownership_score','sector':'sector_score'}
            errors=[]
            for row in rows:
                value=sum((Decimal(str(row[field]))*Decimal(str(weights[key]))/100 for key,field in fields.items() if row.get(field) is not None),Decimal(0))
                if value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP)!=Decimal(str(row['composite_score'])):
                    errors.append(row.get('symbol'))
            checks[-1]['ranking']={'rows':len(rows),'snapshot_at':body.get('snapshot_at'),
                                    'final_qualified_count':body.get('final_qualified_count'),
                                    'rs_progress':body.get('rs_progress'),'composite_errors':errors}
        after, _ = get(args.backend, '/health')
        if after!=200:
            break  # Stop expensive checks if the backend is already unhealthy.
get(args.backend, '/portfolios')
output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True)
report={'scope':'Bounded public GET smoke only; not full financial/history or runtime-root-cause acceptance','checks':checks}
output.write_text(json.dumps(report,indent=2),encoding='utf-8')
failed=any(c['status']!=200 and not(c['status']==503 and isinstance(c.get('body'),dict) and isinstance(c['body'].get('detail'),dict) and c['body']['detail'].get('code')=='RANKING_WARMING') for c in checks)
rankings=[c['ranking'] for c in checks if 'ranking' in c]
failed=failed or len(rankings)!=2 or any(r['composite_errors'] or not 0<r['rows']<=200 for r in rankings)
sys.exit(1 if failed else 0)
