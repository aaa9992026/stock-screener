import io
import requests
import pandas as pd


class NSECompanyProvider:
    URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

    def get_companies(self):
        headers = {
            "User-Agent": "Mozilla/5.0"
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
            symbol = str(row.get("SYMBOL", "")).strip()
            name = str(row.get("NAME OF COMPANY", "")).strip()
            isin = str(row.get(isin_column, "")).strip() if isin_column else ""
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