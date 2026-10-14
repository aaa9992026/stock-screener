"""Real stored sector history, separate market cohorts, explicit coverage."""
import json
from statistics import median
from app.models import RankingSnapshot, RSHistory
from app.services.rs_history import decode_points
from app.services.rs_universe_backfill import eligible_companies, evaluation_date


def sector_analytics(db, market, sector=None):
    from app.api.market import (_screener_market_exchanges, _rs_market_group, _sector_scores_from_enriched, _benchmark_close_points, _point_date, _weighted_relative_return_from_points, _json_safe)
    exchanges = _screener_market_exchanges(market)
    market_groups = {_rs_market_group(ex) for ex in exchanges}
    groups, enrichment = {}, {}
    for snapshot in db.query(RankingSnapshot).filter(RankingSnapshot.exchange.in_(exchanges)).all():
        try:
            enrichment[(snapshot.exchange, snapshot.symbol)] = json.loads(snapshot.payload_json)
        except (TypeError, ValueError):
            continue
    rows, sector_stats = [], {}
    histories = {(r.exchange, r.symbol): decode_points(r.points_payload) for r in db.query(RSHistory).filter(RSHistory.exchange.in_(exchanges)).all() if r.points_payload}
    for group in market_groups:
        market_rows = []
        for company in eligible_companies(db, group):
            if company.exchange not in exchanges:
                continue
            payload = enrichment.get((company.exchange, company.symbol), {})
            classification = company.sector or (payload.get("metadata") or {}).get("sector") or "Unclassified"
            if sector and classification != sector:
                continue
            row = {"symbol": company.symbol, "exchange": company.exchange, "sector": classification}
            market_rows.append(row)
            rows.append(row)
        sector_stats[group] = _sector_scores_from_enriched(market_rows, enrichment)
    benchmarks = {}
    for group in market_groups:
        try:
            points, *_ = _benchmark_close_points("US" if group == "US" else "NSE", db=db)
            benchmarks[group] = [p for p in points if _point_date(p) <= evaluation_date(db, group)]
        except Exception:
            benchmarks[group] = []
    for row in rows:
        group = _rs_market_group(row["exchange"])
        name = row["sector"]
        bucket = groups.setdefault((group, name), {"stock_count": 0, "enriched": 0, "returns": [], "relative": []})
        bucket["stock_count"] += 1
        if enrichment.get((row["exchange"], row["symbol"])):
            bucket["enriched"] += 1
        points = histories.get((row["exchange"], row["symbol"]), [])
        if points and benchmarks[group]:
            _, values = _weighted_relative_return_from_points(points, benchmarks[group], {"1m": 1})
            value = values.get("1m") or {}
            if value.get("stock_return_percent") is not None:
                bucket["returns"].append(value["stock_return_percent"])
                bucket["relative"].append(value["relative_return_percent"])
    output = []
    for (group, name), bucket in groups.items():
        stats = sector_stats[group].get(name, {}) if name != "Unclassified" else {}
        output.append({"market": group, "sector": name, "stock_count": bucket["stock_count"], "enriched_count": bucket["enriched"], "price_count": len(bucket["returns"]), "data_coverage_percent": bucket["enriched"] / bucket["stock_count"] * 100,
            **{k: stats.get(k) for k in ("eps_growth_rs", "pat_growth_rs", "sales_growth_rs", "growth_acceleration_rs", "growth_breadth", "acceleration_breadth")},
            "eps_growth_percent": stats.get("eps_raw"), "pat_growth_percent": stats.get("pat_raw"), "sales_growth_percent": stats.get("sales_raw"), "acceleration": stats.get("acceleration_raw"), "sector_rs_score": stats.get("score"),
            "momentum_1m_percent": median(bucket["returns"]) if bucket["returns"] else None, "relative_return_1m_percent": median(bucket["relative"]) if bucket["relative"] else None,
            "price_breadth_percent": sum(v > 0 for v in bucket["returns"]) / len(bucket["returns"]) * 100 if bucket["returns"] else None,
            "status": "Provisional", "history_status": "Partial stored constituent coverage; no final universe rank", "evaluation_date": str(evaluation_date(db, group)), "component_coverage_percent": stats.get("component_coverage_percent", 0)})
    output.sort(key=lambda row: (row["market"], row["sector_rs_score"] is None, -(row["sector_rs_score"] or 0), row["sector"]))
    for group in market_groups:
        ranked = [r for r in output if r["market"] == group and r["sector_rs_score"] is not None]
        for index, row in enumerate(ranked, 1):
            row["rank"] = index
            row["leadership"] = "Leading" if index <= max(1, len(ranked) // 3) else "Lagging" if index > len(ranked) * 2 / 3 else "Middle"
    return _json_safe({"market": market.upper(), "rows": output, "formula": "EPS Growth RS 30% + PAT Growth RS 25% + Sales Growth RS 20% + Growth Acceleration RS 15% + Growth Breadth 5% + Acceleration Breadth 5%", "aggregation": "Median stock growth; US and India ranked separately; deduplicated constituents.", "data_rule": "Persisted real statement enrichment and dated prices only. Missing components stay N/A; all sector ranks are provisional until constituent coverage is verified."})
