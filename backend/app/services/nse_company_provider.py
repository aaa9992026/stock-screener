import io
import time
import requests
import pandas as pd


class NSECompanyProvider:
    URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
    CACHE_SECONDS = 6 * 60 * 60
    _companies_cache = None
    _symbol_cache = None
    _cache_time = 0.0

    @classmethod
    def _cache_valid(cls):
        return bool(cls._companies_cache) and (time.time() - cls._cache_time) < cls.CACHE_SECONDS

    def _fetch_companies(self):
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
            "Accept": "text/csv,text/plain,*/*",
        }

        response = requests.get(
            self.URL,
            headers=headers,
            timeout=30
        )
        response.raise_for_status()

        df = pd.read_csv(io.StringIO(response.text))
        # NSE has changed whitespace/casing in CSV headers over time. Normalize
        # them once so ISIN remains available without depending on exact spacing.
        normalized_columns = {str(col).strip().upper(): col for col in df.columns}
        isin_column = normalized_columns.get("ISIN NUMBER") or normalized_columns.get("ISIN")

        companies = []

        for _, row in df.iterrows():
            symbol = str(row.get("SYMBOL", "")).strip().upper()
            name = str(row.get("NAME OF COMPANY", "")).strip()
            isin = str(row.get(isin_column, "")).strip().upper() if isin_column else ""
            if isin.lower() in {"nan", "none", "-"}:
                isin = ""

            if not symbol or not name:
                continue

            companies.append({
                "symbol": symbol,
                "name": name,
                "isin": isin or None,
                "exchange": "NSE",
                "sector": None,
                "industry": None
            })

        return companies

    def get_companies(self, force_refresh: bool = False):
        cls = self.__class__
        if not force_refresh and cls._cache_valid():
            return list(cls._companies_cache)

        companies = self._fetch_companies()
        cls._companies_cache = list(companies)
        cls._symbol_cache = {item["symbol"]: item for item in companies}
        cls._cache_time = time.time()
        return companies

    def get_company(self, symbol: str):
        """Return the exact official NSE symbol-master record when available.

        The official NSE EQUITY_L.csv is cached in-process so dashboard/search
        identity checks do not repeatedly hit NSE. This is used to repair stale
        or accidentally mismatched Company name/ISIN metadata in PostgreSQL.
        """
        symbol = str(symbol or "").strip().upper()
        if not symbol:
            return None

        cls = self.__class__
        if not cls._cache_valid() or not cls._symbol_cache:
            self.get_companies()
        return dict((cls._symbol_cache or {}).get(symbol) or {}) or None
