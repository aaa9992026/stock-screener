import requests
from datetime import datetime
import yfinance as yf
from app.services.base_provider import BaseMarketDataProvider


class YahooProvider(BaseMarketDataProvider):

    def get_companies(self):
        return []

    def format_symbol(self, symbol: str, exchange: str):
        symbol = symbol.upper()
        exchange = exchange.upper()

        if exchange == "NSE":
            return f"{symbol}.NS"

        if exchange == "BSE":
            return f"{symbol}.BO"

        return symbol

    def get_ohlcv(
        self,
        symbol: str,
        exchange: str = "US",
        start_date=None,
        end_date=None
    ):
        if exchange.upper() == "BSE":
            rows = self._get_bse_history_direct(symbol)

            if len(rows) >= 10:
                return rows

        provider_symbol = self.format_symbol(symbol, exchange)

        ticker = yf.Ticker(provider_symbol)

        data = ticker.history(
            start=start_date,
            end=end_date,
            auto_adjust=False
        )

        # Some BSE symbols may return incomplete history.
        # Retry using a fixed period.
        if data.empty or len(data) <= 1:
            data = ticker.history(
                period="2y",
                interval="1d",
                auto_adjust=False
            )

        results = []

        for date, row in data.iterrows():
            results.append({
                "date": date.date(),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": float(row["Volume"])
            })

        return results

    def get_fundamentals(self, symbol: str):
        ticker = yf.Ticker(symbol)
        info = ticker.info

        return {
            "market_cap": info.get("marketCap"),
            "trailing_eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "revenue": info.get("totalRevenue"),
            "net_income": info.get("netIncomeToCommon"),
            "profit_margin": info.get("profitMargins"),
            "return_on_equity": info.get("returnOnEquity"),
            "return_on_assets": info.get("returnOnAssets"),
            "insider_percent": info.get("heldPercentInsiders"),
            "institution_percent": info.get("heldPercentInstitutions"),
            "shares_outstanding": info.get("sharesOutstanding"),
            "float_shares": info.get("floatShares"),
        }

    def _get_bse_history_direct(self, symbol: str):
        yahoo_symbol = f"{symbol}.BO"

        url = (
            f"https://query1.finance.yahoo.com/v8/finance/chart/"
            f"{yahoo_symbol}?range=2y&interval=1d"
        )

        response = requests.get(
            url,
            timeout=20,
            headers={
                "User-Agent": "Mozilla/5.0"
            }
        )

        response.raise_for_status()

        payload = response.json()

        result = payload["chart"]["result"][0]

        timestamps = result.get("timestamp", [])
        quote = result["indicators"]["quote"][0]

        rows = []

        for i, ts in enumerate(timestamps):
            try:
                open_price = quote["open"][i]
                high = quote["high"][i]
                low = quote["low"][i]
                close = quote["close"][i]
                volume = quote["volume"][i]

                if None in [open_price, high, low, close]:
                    continue

                rows.append({
                    "date": datetime.fromtimestamp(ts).date(),
                    "open": float(open_price),
                    "high": float(high),
                    "low": float(low),
                    "close": float(close),
                    "volume": float(volume or 0),
                })

            except (IndexError, TypeError):
                continue

        return rows