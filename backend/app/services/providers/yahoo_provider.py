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

    def get_fundamental_history(self, symbol: str):
        ticker = yf.Ticker(symbol)

        quarterly = ticker.quarterly_financials
        annual = ticker.financials

        def get_value(df, names, column):
            for name in names:
                if name in df.index:
                    value = df.loc[name, column]

                    try:
                        if value != value:  # NaN
                            return None
                    except Exception:
                        pass

                    return float(value)

            return None

        def build_periods(df, limit):
            results = []

            if df is None or df.empty:
                return results

            columns = list(df.columns)[:limit]

            for column in columns:
                revenue = get_value(
                    df,
                    ["Total Revenue", "Operating Revenue"],
                    column
                )

                net_income = get_value(
                    df,
                    ["Net Income", "Net Income Common Stockholders"],
                    column
                )

                ebit = get_value(
                    df,
                    ["EBIT", "Operating Income"],
                    column
                )

                eps = get_value(
                    df,
                    ["Diluted EPS", "Basic EPS"],
                    column
                )

                operating_income = get_value(
                    df,
                    ["Operating Income"],
                    column
                )

                opm = None
                npm = None

                if revenue not in (None, 0):
                    if operating_income is not None:
                        opm = (operating_income / revenue) * 100

                    if net_income is not None:
                        npm = (net_income / revenue) * 100

                results.append({
                    "period": column.strftime("%Y-%m-%d"),
                    "sales": revenue,
                    "pat": net_income,
                    "eps": eps,
                    "ebit": ebit,
                    "opm": round(opm, 2) if opm is not None else None,
                    "npm": round(npm, 2) if npm is not None else None,
                })

            # Add QoQ growth using the next older quarter
            for i in range(len(results) - 1):
                current = results[i]
                previous = results[i + 1]

                def growth(current_value, previous_value):
                    if (
                        current_value is None
                        or previous_value is None
                        or previous_value == 0
                    ):
                        return None

                    return round(
                        ((current_value - previous_value) / abs(previous_value)) * 100,
                        2
                    )

                current["qoq_sales"] = growth(
                    current["sales"],
                    previous["sales"]
                )

                current["qoq_pat"] = growth(
                    current["pat"],
                    previous["pat"]
                )

                current["qoq_eps"] = growth(
                    current["eps"],
                    previous["eps"]
                )

            if results:
                results[-1]["qoq_sales"] = None
                results[-1]["qoq_pat"] = None
                results[-1]["qoq_eps"] = None

            return results

        return {
            "symbol": symbol.upper(),
            "quarterly": build_periods(quarterly, 4),
            "annual": build_periods(annual, 3),
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