"""Match actual fiscal dates; a missing quarter must not shift YoY comparisons."""
from datetime import date


def period_date(row):
    try:
        return date.fromisoformat(str(row.get("period", ""))[:10])
    except (TypeError, ValueError):
        return None


def match_period(rows, current, days, tolerance):
    stamp = period_date(current)
    if stamp is None:
        return None
    candidates = [(abs((stamp - period_date(r)).days - days), r) for r in rows if period_date(r) and period_date(r) < stamp]
    return min(candidates, key=lambda pair: pair[0])[1] if candidates and min(p[0] for p in candidates) <= tolerance else None


def merge_statement_rows(primary, official, limit, annual=False):
    """Match fiscal ends near normalized provider dates, preserving official dates.

    A 52/53-week fiscal quarter can end July 1 while Yahoo labels it June 30.
    Calendar-quarter buckets would incorrectly treat those as two periods.
    """
    merged = []
    for source_rows, prefer in ((primary or [], False), (official or [], True)):
        for incoming in source_rows:
            stamp = period_date(incoming)
            candidates = [(abs((stamp-period_date(row)).days), row) for row in merged if stamp and period_date(row)]
            closest = min(candidates, key=lambda pair: pair[0]) if candidates else None
            current = closest[1] if closest and closest[0] <= (14 if annual else 12) else None
            if current is None:
                merged.append(dict(incoming))
                continue
            for field, value in incoming.items():
                if value is not None and (prefer or current.get(field) is None):
                    current[field] = value
    merged.sort(key=lambda row: str(row.get('period') or ''), reverse=True)
    return merged[:limit]


def align_financial_history(history):
    history = history or {}
    result = dict(history)
    def growth(current, previous):
        if current is None or previous is None or previous == 0:
            return None
        return (float(current) - float(previous)) / abs(float(previous)) * 100
    for kind in ("quarterly", "annual"):
        rows = [dict(row) for row in history.get(kind, [])]
        rows.sort(key=lambda row: str(row.get("period", "")), reverse=True)
        for row in rows:
            previous = match_period(rows, row, 91 if kind == "quarterly" else 365, 25 if kind == "quarterly" else 20)
            year_ago = match_period(rows, row, 365, 20)
            for metric in ("eps", "pat", "sales"):
                row["yoy_" + metric] = growth(row.get(metric), year_ago.get(metric)) if year_ago else None
                if kind == "quarterly":
                    row["qoq_" + metric] = growth(row.get(metric), previous.get(metric)) if previous else None
        result[kind] = rows
    result["period_alignment"] = "Actual fiscal end dates; no index-shift substitution for missing quarters. Announcement availability is not inferred."
    return result
