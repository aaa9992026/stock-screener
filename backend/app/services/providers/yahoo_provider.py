import requests
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from urllib.parse import quote
import math
import logging

logger = logging.getLogger(__name__)
import yfinance as yf
from app.services.base_provider import BaseMarketDataProvider
from app.services.providers.sec_provider import SECFundamentalsProvider


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

        # Yahoo uses hyphens for US share classes (for example BRK-B, AKO-A)
        # while official symbol masters may use dots/slashes. Keep the canonical
        # database symbol unchanged and translate only for the Yahoo request.
        if exchange == "US":
            return symbol.replace(".", "-").replace("/", "-")

        return symbol

    def get_ohlcv(self, symbol: str, exchange: str = "US", start_date=None, end_date=None):
        provider_symbol = self.format_symbol(symbol.strip(), exchange.strip())
        rows = []
        error = None
        try:
            data = yf.Ticker(provider_symbol).history(
                start=start_date, end=end_date, interval="1d", auto_adjust=False, timeout=10, raise_errors=True
            )
            for dt, row in data.iterrows():
                values = [float(row[k]) for k in ("Open", "High", "Low", "Close")]
                if any(not math.isfinite(v) or v <= 0 for v in values):
                    continue
                volume = float(row["Volume"]) if row.get("Volume") is not None else None
                rows.append({"date": dt.date(), "open": values[0], "high": values[1],
                             "low": values[2], "close": values[3],
                             "volume": volume if volume is not None and math.isfinite(volume) else None})
        except Exception as exc:
            error = str(exc)
        if not rows:
            rows = self.get_chart_history(symbol, exchange, start_date, end_date)
        if not rows and error:
            raise RuntimeError(f"Yahoo history unavailable for {exchange}:{symbol}: {error}")
        return rows

    def get_chart_history(self, symbol, exchange="US", start_date=None, end_date=None):
        """Same approved Yahoo source, without yfinance crumb negotiation."""
        ticker = self.format_symbol(symbol.strip(), exchange.strip())
        def timestamp(value, default):
            if value is None:
                value = default
            if isinstance(value, str):
                value = datetime.fromisoformat(value)
            elif isinstance(value, date) and not isinstance(value, datetime):
                value = datetime.combine(value, datetime.min.time())
            return int(value.replace(tzinfo=timezone.utc).timestamp())
        end = datetime.now(timezone.utc) + timedelta(days=1)
        params = {"period1": timestamp(start_date, end - timedelta(days=730)),
                  "period2": timestamp(end_date, end), "interval": "1d", "events": "history"}
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            try:
                response = requests.get(f"https://{host}/v8/finance/chart/{quote(ticker, safe='')}",
                                        params=params, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"}, timeout=10)
                response.raise_for_status()
                payload = response.json()
                result = ((payload.get("chart") or {}).get("result") or [None])[0]
                rows = self.parse_chart_history(result)
                if rows:
                    return rows
            except Exception as exc:
                logger.warning("Yahoo chart fallback failed for %s:%s: %s", exchange, symbol, exc)
        return []

    @staticmethod
    def parse_chart_history(result):
        if not result:
            return []
        quotes = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        timezone_name = (result.get("meta") or {}).get("exchangeTimezoneName") or "UTC"
        try:
            tz = ZoneInfo(timezone_name)
        except (ValueError, KeyError):
            tz = timezone.utc
        rows = {}
        for i, stamp in enumerate(result.get("timestamp") or []):
            try:
                values = [quotes.get(k, [])[i] for k in ("open", "high", "low", "close")]
                if any(v is None or not math.isfinite(float(v)) or float(v) <= 0 for v in values):
                    continue
                dt = datetime.fromtimestamp(stamp, tz=tz).date()
                volume_values = quotes.get("volume") or []
                volume = volume_values[i] if i < len(volume_values) else None
                if volume is not None and not math.isfinite(float(volume)):
                    volume = None
                rows[dt] = dict(zip(("open", "high", "low", "close"), map(float, values)), date=dt, volume=volume)
            except (TypeError, ValueError, IndexError, OverflowError):
                continue
        return [rows[d] for d in sorted(rows)]

    def get_fundamentals(self, symbol: str, exchange: str = "US"):
        provider_symbol = self.format_symbol(symbol, exchange)
        ticker = yf.Ticker(provider_symbol)
        info = ticker.info

        isin = info.get("isin")
        if not isin:
            try:
                raw_isin = getattr(ticker, "isin", None)
                if callable(raw_isin):
                    raw_isin = raw_isin()
                if raw_isin and str(raw_isin).strip() not in {"-", "None", "nan"}:
                    isin = str(raw_isin).strip()
            except Exception:
                isin = None

        return {
            "name": info.get("longName") or info.get("shortName"),
            "isin": isin,
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
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

    def get_fundamental_history(self, symbol: str, exchange: str = "US"):
        provider_symbol = self.format_symbol(symbol, exchange)
        ticker = yf.Ticker(provider_symbol)

        quarterly = ticker.quarterly_financials
        annual = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow

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

        def get_matching_value(df, names, target_column):
            if df is None or df.empty:
                return None

            for column in df.columns:
                if column.date() == target_column.date():
                    return get_value(df, names, column)

            return None

        def get_average_matching_value(df, names, target_column):
            """Average current and previous reported balance for return ratios."""
            if df is None or df.empty:
                return None

            columns = list(df.columns)
            for index, column in enumerate(columns):
                if column.date() == target_column.date():
                    current = get_value(df, names, column)
                    previous = None
                    if index + 1 < len(columns):
                        previous = get_value(df, names, columns[index + 1])
                    if current is None:
                        return None
                    if previous is None:
                        return current
                    return (current + previous) / 2

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

                total_debt = get_matching_value(
                    balance_sheet,
                    ["Total Debt"],
                    column
                )

                stockholders_equity = get_matching_value(
                    balance_sheet,
                    [
                        "Stockholders Equity",
                        "Total Stockholder Equity",
                        "Common Stock Equity"
                    ],
                    column
                )

                average_equity = get_average_matching_value(
                    balance_sheet,
                    [
                        "Stockholders Equity",
                        "Total Stockholder Equity",
                        "Common Stock Equity"
                    ],
                    column
                )

                operating_cash_flow = get_matching_value(
                    cashflow,
                    [
                        "Operating Cash Flow",
                        "Total Cash From Operating Activities"
                    ],
                    column
                )

                free_cash_flow = get_matching_value(
                    cashflow,
                    ["Free Cash Flow"],
                    column
                )

                total_assets = get_matching_value(
                    balance_sheet,
                    ["Total Assets"],
                    column
                )

                average_assets = get_average_matching_value(
                    balance_sheet,
                    ["Total Assets"],
                    column
                )

                current_liabilities = get_matching_value(
                    balance_sheet,
                    ["Current Liabilities", "Total Current Liabilities"],
                    column
                )

                average_current_liabilities = get_average_matching_value(
                    balance_sheet,
                    ["Current Liabilities", "Total Current Liabilities"],
                    column
                )

                net_income_to_common = get_value(
                    df,
                    ["Net Income Common Stockholders", "Net Income"],
                    column
                )

                shares_diluted = get_value(
                    df,
                    ["Diluted Average Shares", "Basic Average Shares"],
                    column
                )

                roe = None
                roa = None
                roce = None
                cash_flow_per_share = None

                if (
                    net_income_to_common is not None
                    and stockholders_equity not in (None, 0)
                ):
                    roe = (net_income_to_common / stockholders_equity) * 100

                if (
                    operating_cash_flow is not None
                    and shares_diluted not in (None, 0)
                ):
                    cash_flow_per_share = operating_cash_flow / shares_diluted

                if (
                    net_income_to_common is not None
                    and total_assets not in (None, 0)
                ):
                    roa = (net_income_to_common / total_assets) * 100

                capital_employed = None
                if total_assets is not None and current_liabilities is not None:
                    capital_employed = total_assets - current_liabilities

                if ebit is not None and capital_employed not in (None, 0):
                    roce = (ebit / capital_employed) * 100

                debt_to_equity = None

                if (
                    total_debt is not None
                    and stockholders_equity not in (None, 0)
                ):
                    debt_to_equity = total_debt / stockholders_equity

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
                    "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
                    "operating_cash_flow": operating_cash_flow,
                    "free_cash_flow": free_cash_flow,
                    "roe": round(roe, 2) if roe is not None else None,
                    "roa": round(roa, 2) if roa is not None else None,
                    "roce": round(roce, 2) if roce is not None else None,
                    "cash_flow_per_share": round(cash_flow_per_share, 2) if cash_flow_per_share is not None else None,
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

        quarterly_results = build_periods(quarterly, 12)

        # The client's exact handwritten EPS/PAT/Sales formulas compare the
        # latest, prior and second-prior quarterly YoY growth values. Compute
        # YoY for every quarter that has a matching year-ago quarter instead
        # of only calculating it for the latest row.
        for i, current in enumerate(quarterly_results):
            year_ago = quarterly_results[i + 4] if i + 4 < len(quarterly_results) else None
            current["yoy_sales"] = growth(current.get("sales"), year_ago.get("sales")) if year_ago else None
            current["yoy_pat"] = growth(current.get("pat"), year_ago.get("pat")) if year_ago else None
            current["yoy_eps"] = growth(current.get("eps"), year_ago.get("eps")) if year_ago else None

        annual_results = build_periods(annual, 7)

        for i in range(len(annual_results) - 1):
            current = annual_results[i]
            previous = annual_results[i + 1]

            current["yoy_sales"] = growth(
                current["sales"],
                previous["sales"]
            )

            current["yoy_pat"] = growth(
                current["pat"],
                previous["pat"]
            )

            current["yoy_eps"] = growth(
                current["eps"],
                previous["eps"]
            )

        if annual_results:
            annual_results[-1]["yoy_sales"] = None
            annual_results[-1]["yoy_pat"] = None
            annual_results[-1]["yoy_eps"] = None

        def calculate_cagr(latest_value, old_value, years):
            if (
                latest_value is None
                or old_value is None
                or latest_value <= 0
                or old_value <= 0
                or years <= 0
            ):
                return None

            return round(
                ((latest_value / old_value) ** (1 / years) - 1) * 100,
                2
            )

        cagr_3y = {
            "sales": None,
            "pat": None,
            "eps": None,
        }

        if len(annual_results) >= 4:
            latest = annual_results[0]
            old = annual_results[3]

            cagr_3y["sales"] = calculate_cagr(
                latest["sales"],
                old["sales"],
                3
            )

            cagr_3y["pat"] = calculate_cagr(
                latest["pat"],
                old["pat"],
                3
            )

            cagr_3y["eps"] = calculate_cagr(
                latest["eps"],
                old["eps"],
                3
            )

        cagr_5y = {
            "sales": None,
            "pat": None,
            "eps": None,
        }

        if len(annual_results) >= 6:
            latest = annual_results[0]
            old = annual_results[5]

            cagr_5y["sales"] = calculate_cagr(latest["sales"], old["sales"], 5)
            cagr_5y["pat"] = calculate_cagr(latest["pat"], old["pat"], 5)
            cagr_5y["eps"] = calculate_cagr(latest["eps"], old["eps"], 5)

        yahoo_result = {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "quarterly": quarterly_results,
            "annual": annual_results,
            "cagr_3y": cagr_3y,
            "cagr_5y": cagr_5y,
            "source": "Yahoo Finance statements",
            "ratio_methodology": {
                "roe": "Net income / period-end stockholders equity",
                "roa": "Net income / period-end total assets",
                "roce": "EBIT / (period-end total assets - period-end current liabilities)",
            },
        }

        # Merge official SEC companyfacts into Yahoo history field-by-field.
        # This is stronger than replacing an entire table only when it has more
        # rows: issuers can have the same row count but different missing fields.
        try:
            sec_result = SECFundamentalsProvider().get_history(symbol.upper()) if exchange.upper() == "US" else None
            if sec_result:
                from datetime import datetime as _dt

                def _bucket(period, annual=False):
                    try:
                        d = _dt.strptime(str(period)[:10], "%Y-%m-%d")
                        return (d.year,) if annual else (d.year, ((d.month - 1) // 3) + 1)
                    except Exception:
                        return (str(period),)

                def _merge_rows(primary, fallback, limit, annual=False):
                    merged = {}
                    # Yahoo seeds the row; official SEC companyfacts then
                    # overrides matching non-null financial-statement fields.
                    for source_rows, prefer in ((primary or [], False), (fallback or [], True)):
                        for row in source_rows:
                            key = _bucket(row.get("period"), annual=annual)
                            current = merged.get(key, {}).copy()
                            if not current:
                                current = dict(row)
                            else:
                                for field, value in row.items():
                                    if field == "period":
                                        if str(value or "") > str(current.get(field) or ""):
                                            current[field] = value
                                    elif value is not None and (prefer or current.get(field) is None):
                                        current[field] = value
                            merged[key] = current
                    rows = list(merged.values())
                    rows.sort(key=lambda r: str(r.get("period") or ""), reverse=True)
                    return rows[:limit]

                merged_quarters = _merge_rows(quarterly_results, sec_result.get("quarterly") or [], 12, False)
                merged_annual = _merge_rows(annual_results, sec_result.get("annual") or [], 7, True)

                for i, row in enumerate(merged_quarters):
                    previous = merged_quarters[i + 1] if i + 1 < len(merged_quarters) else None
                    year_ago = merged_quarters[i + 4] if i + 4 < len(merged_quarters) else None
                    row["qoq_sales"] = growth(row.get("sales"), previous.get("sales")) if previous else None
                    row["qoq_pat"] = growth(row.get("pat"), previous.get("pat")) if previous else None
                    row["qoq_eps"] = growth(row.get("eps"), previous.get("eps")) if previous else None
                    row["yoy_sales"] = growth(row.get("sales"), year_ago.get("sales")) if year_ago else None
                    row["yoy_pat"] = growth(row.get("pat"), year_ago.get("pat")) if year_ago else None
                    row["yoy_eps"] = growth(row.get("eps"), year_ago.get("eps")) if year_ago else None

                for i, row in enumerate(merged_annual):
                    previous = merged_annual[i + 1] if i + 1 < len(merged_annual) else None
                    row["yoy_sales"] = growth(row.get("sales"), previous.get("sales")) if previous else None
                    row["yoy_pat"] = growth(row.get("pat"), previous.get("pat")) if previous else None
                    row["yoy_eps"] = growth(row.get("eps"), previous.get("eps")) if previous else None

                yahoo_result["quarterly"] = merged_quarters
                yahoo_result["annual"] = merged_annual
                if len(merged_annual) >= 4:
                    yahoo_result["cagr_3y"] = {
                        "sales": calculate_cagr(merged_annual[0].get("sales"), merged_annual[3].get("sales"), 3),
                        "pat": calculate_cagr(merged_annual[0].get("pat"), merged_annual[3].get("pat"), 3),
                        "eps": calculate_cagr(merged_annual[0].get("eps"), merged_annual[3].get("eps"), 3),
                    }
                if len(merged_annual) >= 6:
                    yahoo_result["cagr_5y"] = {
                        "sales": calculate_cagr(merged_annual[0].get("sales"), merged_annual[5].get("sales"), 5),
                        "pat": calculate_cagr(merged_annual[0].get("pat"), merged_annual[5].get("pat"), 5),
                        "eps": calculate_cagr(merged_annual[0].get("eps"), merged_annual[5].get("eps"), 5),
                    }
                yahoo_result["source"] = "SEC companyfacts + Yahoo Finance merged fallback"
        except Exception:
            pass

        return yahoo_result

    def get_ownership_details(self, symbol: str, exchange: str = "US"):
        provider_symbol = self.format_symbol(symbol, exchange)
        ticker = yf.Ticker(provider_symbol)

        def dataframe_records(df, limit=10):
            if df is None or getattr(df, "empty", True):
                return []

            frame = df.reset_index()
            records = []

            for _, row in frame.head(limit).iterrows():
                item = {}
                for key, value in row.items():
                    if value is None:
                        item[str(key)] = None
                        continue

                    try:
                        if value != value:  # NaN
                            item[str(key)] = None
                            continue
                    except Exception:
                        pass

                    if hasattr(value, "isoformat"):
                        item[str(key)] = value.isoformat()
                    elif hasattr(value, "item"):
                        try:
                            item[str(key)] = value.item()
                        except Exception:
                            item[str(key)] = str(value)
                    else:
                        item[str(key)] = value

                records.append(item)

            return records

        try:
            institutional = dataframe_records(ticker.institutional_holders, 10)
        except Exception:
            institutional = []

        try:
            mutual_funds = dataframe_records(ticker.mutualfund_holders, 10)
        except Exception:
            mutual_funds = []

        try:
            insider_transactions = dataframe_records(ticker.insider_transactions, 10)
        except Exception:
            insider_transactions = []

        try:
            major_holders = dataframe_records(ticker.major_holders, 10)
        except Exception:
            major_holders = []

        current_summary = {
            "institutional_percent": None,
            "insider_percent": None,
            "retail_public_percent": None,
            "retail_public_method": None,
        }
        try:
            info = ticker.info or {}
            institution = info.get("heldPercentInstitutions")
            insider = info.get("heldPercentInsiders")
            if institution is not None:
                institution = float(institution) * 100 if abs(float(institution)) <= 1.5 else float(institution)
                current_summary["institutional_percent"] = round(institution, 4)
            if insider is not None:
                insider = float(insider) * 100 if abs(float(insider)) <= 1.5 else float(insider)
                current_summary["insider_percent"] = round(insider, 4)
            if institution is not None and insider is not None:
                current_summary["retail_public_percent"] = round(max(0.0, 100.0 - institution - insider), 4)
                current_summary["retail_public_method"] = "100% - institutional ownership - insider ownership"
        except Exception:
            pass

        note = None
        if exchange.upper() == "US":
            note = (
                "US ownership uses the market-appropriate headings Institutional Ownership, "
                "Insider Ownership and Retail/Public Investors. Yahoo provides current aggregate "
                "institutional/insider percentages; Retail/Public is the transparent remainder "
                "100% - institutional - insider when both aggregates are available. Historical "
                "top-holder tables are kept as source detail and are not presented as total-market history."
            )
        elif exchange.upper() in ["NSE", "BSE"]:
            note = (
                "Verified FII/DII/promoter-change breakdown is not exposed by the "
                "configured Yahoo provider. Available holder data is shown without "
                "estimating unavailable categories."
            )

        return {
            "symbol": symbol.upper(),
            "exchange": exchange.upper(),
            "change_semantics": "For Yahoo holder tables, pctChange is the provider-reported proportional change in the holder position (shares), not a quarter-over-quarter change in ownership percentage points.",
            "institutional_holders": institutional,
            "mutual_fund_holders": mutual_funds,
            "insider_transactions": insider_transactions,
            "major_holders": major_holders,
            "current_summary": current_summary,
            "provider_note": note,
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