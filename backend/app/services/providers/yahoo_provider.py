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