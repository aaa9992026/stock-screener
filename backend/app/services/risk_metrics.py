"""Date-aligned risk metrics. Production inputs must identify adjustment basis."""
from datetime import date, timedelta
import math
import time
import threading
import pandas as pd
import yfinance as yf
from app.services.providers.yahoo_provider import YahooProvider

_cache = {}
_warming = threading.Lock()


def cached_beta_batch(rows):
    output = { (r["exchange"], r["symbol"]): _cache.get((r["exchange"], r["symbol"]), (0, {}))[1]
               for r in rows }
    if _warming.acquire(blocking=False):
        def warm():
            try:
                beta_batch(rows)
            finally:
                _warming.release()
        threading.Thread(target=warm, name="weekly-beta", daemon=True).start()
    return output


def weekly_beta(stock, benchmark, as_of=None, minimum_returns=60):
    """Two calendar years of shared dates; exclude the current unfinished week.

    Inputs are dated adjusted closes, never independently tail-aligned arrays.
    Missing shared dates do not create an observation. Covariance and variance
    use the same sample convention, with annualized weekly alpha.
    """
    as_of = as_of or date.today()
    end = as_of - timedelta(days=as_of.weekday())
    start = end - timedelta(days=731)
    def series(points):
        values = {}
        for day, close in points:
            day = pd.Timestamp(day).date()
            if start <= day < end and close is not None and math.isfinite(float(close)) and float(close) > 0:
                values[day] = float(close)
        return pd.Series(values, dtype=float)
    aligned = pd.concat([series(stock).rename("stock"), series(benchmark).rename("benchmark")], axis=1).dropna()
    result = {"beta": None, "alpha": None, "observations": 0, "basis": "2Y weekly adjusted closes; common daily observation dates; completed weeks", "as_of": end.isoformat()}
    if aligned.empty:
        return result
    aligned.index = pd.to_datetime(aligned.index)
    weekly = aligned.sort_index().resample("W-FRI").last().dropna()
    # No returns across missing weekly observations.
    returns = weekly.pct_change(fill_method=None)
    consecutive = weekly.index.to_series().diff().dt.days.eq(7)
    returns = returns[consecutive].dropna()
    result["observations"] = len(returns)
    if len(returns) < minimum_returns or (weekly.index[-1] - weekly.index[0]).days < 365:
        return result
    variance = returns.benchmark.var(ddof=1)
    if variance <= 0:
        return result
    beta = returns.stock.cov(returns.benchmark) / variance
    result.update(beta=round(float(beta), 6), alpha=round(float((returns.stock.mean() - beta * returns.benchmark.mean()) * 52 * 100), 6))
    return result


def beta_batch(rows):
    """Bounded, cached provider request; no undated raw-close substitution."""
    provider = YahooProvider()
    output, missing = {}, []
    now = time.time()
    for row in rows:
        key = (row["exchange"], row["symbol"])
        cached = _cache.get(key)
        if cached and now - cached[0] < 3600:
            output[key] = cached[1]
        else:
            missing.append(row)
    for offset in range(0, len(missing), 60):
        chunk = missing[offset:offset + 60]
        mapping = {provider.format_symbol(r["symbol"], r["exchange"]): (r["exchange"], r["symbol"]) for r in chunk}
        tickers = list(mapping) + ["^GSPC", "^CRSLDX"]
        try:
            frame = yf.download(tickers=tickers, start=(date.today() - timedelta(days=750)).isoformat(), end=date.today().isoformat(), auto_adjust=True, group_by="ticker", threads=4, progress=False, timeout=10)
            def points(ticker):
                if frame.empty or ticker not in frame.columns.get_level_values(0):
                    return []
                return [(d.date(), float(c)) for d, c in frame[ticker]["Close"].dropna().items()]
            for ticker, key in mapping.items():
                value = weekly_beta(points(ticker), points("^GSPC" if key[0] == "US" else "^CRSLDX"))
                value["provider"] = "Yahoo auto_adjust=True"
                output[key] = value
                _cache[key] = (now, value)
        except Exception:
            for key in mapping.values():
                output[key] = {"beta": None, "alpha": None, "observations": 0, "basis": "Adjusted weekly provider history unavailable"}
                _cache[key] = (now, output[key])
    if len(_cache) > 1500:
        for key in list(_cache)[:len(_cache) - 1500]:
            _cache.pop(key, None)
    return output
