"""One dated, deduplicated statement cohort for all sector score consumers."""
import hashlib
import json
from datetime import datetime, timedelta
from app.models import RankingSnapshot
from app.services.rs_universe_backfill import eligible_companies, market_exchanges


def sector_inputs(db, market):
    from app.api.market import FINANCIAL_CALCULATION_VERSION, _ranking_snapshot_ttl_seconds
    cutoff = datetime.utcnow() - timedelta(seconds=_ranking_snapshot_ttl_seconds())
    enrichment = {}
    query = db.query(RankingSnapshot.exchange, RankingSnapshot.symbol, RankingSnapshot.payload_json).filter(
        RankingSnapshot.exchange.in_(market_exchanges(market)), RankingSnapshot.updated_at >= cutoff)
    for snapshot in query.yield_per(50):
        try:
            payload = json.loads(snapshot.payload_json)
            if payload.get('financial_calculation_version') == FINANCIAL_CALCULATION_VERSION:
                enrichment[(snapshot.exchange, snapshot.symbol)] = payload
        except (TypeError, ValueError):
            continue
    rows = []
    for company in eligible_companies(db, market):
        payload = enrichment.get((company.exchange, company.symbol), {})
        sector = company.sector or (payload.get('metadata') or {}).get('sector') or 'Unclassified'
        rows.append({'exchange': company.exchange, 'symbol': company.symbol, 'sector': sector})
    return rows, enrichment


def sector_scores(db, market):
    from app.api.market import _sector_scores_from_enriched, FINANCIAL_CALCULATION_VERSION
    rows, enrichment = sector_inputs(db, market)
    stats = _sector_scores_from_enriched([r for r in rows if r['sector'] != 'Unclassified'], enrichment)
    fields = ('eps_latest_yoy', 'pat_latest_yoy', 'sales_latest_yoy', 'eps_acceleration', 'pat_acceleration', 'sales_acceleration')
    observations = [(r['exchange'], r['symbol'], r['sector'], [enrichment[(r['exchange'], r['symbol'])].get(f) for f in fields]) for r in rows if (r['exchange'], r['symbol']) in enrichment]
    cohort_id = hashlib.sha256(json.dumps([market, FINANCIAL_CALCULATION_VERSION, sorted(observations)], sort_keys=True).encode()).hexdigest()[:20]
    # Apply the same minimum genuine constituent count to every consumer.
    for value in stats.values():
        if value.get('peer_count', 0) < 5:
            value['score'] = None
    return stats, cohort_id, rows, enrichment
