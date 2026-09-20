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

        companies = []

        for _, row in df.iterrows():
            symbol = str(row.get("SYMBOL", "")).strip()
            name = str(row.get("NAME OF COMPANY", "")).strip()

            if not symbol or not name:
                continue

            companies.append({
                "symbol": symbol,
                "name": name,
                "exchange": "NSE",
                "sector": None,
                "industry": None
            })

        return companies