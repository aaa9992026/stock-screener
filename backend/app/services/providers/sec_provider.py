import os
import re
from datetime import datetime
from functools import lru_cache

import requests


class SECFundamentalsProvider:
    """Official SEC company-facts fallback for US fundamental history.

    Used only to fill history that Yahoo does not expose (for example, more
    than ~5 quarterly periods). It does not replace price data.
    """

    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"

    def __init__(self):
        self.user_agent = os.getenv(
            "SEC_USER_AGENT",
            "StockScreener/1.0 contact: admin@example.com",
        )

    def _headers(self):
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Host": "data.sec.gov",
        }

    @lru_cache(maxsize=1)
    def _ticker_map(self):
        headers = {"User-Agent": self.user_agent, "Accept-Encoding": "gzip, deflate"}
        response = requests.get(self.TICKERS_URL, headers=headers, timeout=25)
        response.raise_for_status()
        payload = response.json()
        result = {}
        for item in payload.values():
            ticker = str(item.get("ticker", "")).upper()
            cik = item.get("cik_str")
            if ticker and cik is not None:
                result[ticker] = str(cik).zfill(10)
        return result

    def _company_facts(self, symbol: str):
        cik = self._ticker_map().get(symbol.upper())
        if not cik:
            return None
        url = self.COMPANY_FACTS_URL.format(cik=cik)
        response = requests.get(url, headers=self._headers(), timeout=30)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _duration_days(item):
        try:
            start = datetime.strptime(item["start"], "%Y-%m-%d").date()
            end = datetime.strptime(item["end"], "%Y-%m-%d").date()
            return (end - start).days
        except Exception:
            return None

    @staticmethod
    def _pick_units(fact, preferred_units):
        units = (fact or {}).get("units", {})
        for unit in preferred_units:
            if unit in units:
                return units[unit]
        for values in units.values():
            return values
        return []

    def _fact_items(self, facts, tags, preferred_units):
        usgaap = (facts or {}).get("facts", {}).get("us-gaap", {})
        for tag in tags:
            fact = usgaap.get(tag)
            if fact:
                values = self._pick_units(fact, preferred_units)
                if values:
                    return values
        return []

    def _duration_series(self, facts, tags, preferred_units, kind):
        values = self._fact_items(facts, tags, preferred_units)
        chosen = {}
        for item in values:
            if item.get("form") not in {"10-Q", "10-K"}:
                continue
            days = self._duration_days(item)
            if days is None:
                continue
            if kind == "quarter" and not (55 <= days <= 135):
                continue
            if kind == "annual" and not (250 <= days <= 430):
                continue
            end = item.get("end")
            val = item.get("val")
            if not end or val is None:
                continue
            filed = item.get("filed", "")
            current = chosen.get(end)
            if current is None or filed > current.get("filed", ""):
                chosen[end] = {"value": float(val), "filed": filed}
        return {k: v["value"] for k, v in sorted(chosen.items(), reverse=True)}

    def _instant_series(self, facts, tags, preferred_units):
        values = self._fact_items(facts, tags, preferred_units)
        chosen = {}
        for item in values:
            if item.get("form") not in {"10-Q", "10-K"}:
                continue
            end = item.get("end")
            val = item.get("val")
            if not end or val is None:
                continue
            filed = item.get("filed", "")
            current = chosen.get(end)
            if current is None or filed > current.get("filed", ""):
                chosen[end] = {"value": float(val), "filed": filed}
        return {k: v["value"] for k, v in sorted(chosen.items(), reverse=True)}

    @staticmethod
    def _nearest(series, target_date, max_days=45):
        if not series:
            return None
        target = datetime.strptime(target_date, "%Y-%m-%d").date()
        best = None
        best_gap = None
        for date_text, value in series.items():
            try:
                date = datetime.strptime(date_text, "%Y-%m-%d").date()
            except Exception:
                continue
            gap = abs((date - target).days)
            if gap <= max_days and (best_gap is None or gap < best_gap):
                best = value
                best_gap = gap
        return best

    @staticmethod
    def _growth(current, previous):
        if current is None or previous in (None, 0):
            return None
        return round(((current - previous) / abs(previous)) * 100, 2)

    @staticmethod
    def _cagr(latest, oldest, years):
        if latest is None or oldest is None or latest <= 0 or oldest <= 0 or years <= 0:
            return None
        return round(((latest / oldest) ** (1 / years) - 1) * 100, 2)

    def get_history(self, symbol: str):
        facts = self._company_facts(symbol)
        if not facts:
            return None

        revenue_tags = [
            "RevenueFromContractWithCustomerExcludingAssessedTax",
            "Revenues",
            "SalesRevenueNet",
        ]
        net_income_tags = ["NetIncomeLoss", "ProfitLoss"]
        eps_tags = ["EarningsPerShareDiluted", "EarningsPerShareBasicAndDiluted"]
        operating_income_tags = ["OperatingIncomeLoss"]
        cfo_tags = ["NetCashProvidedByUsedInOperatingActivities"]
        capex_tags = [
            "PaymentsToAcquirePropertyPlantAndEquipment",
            "PaymentsForAdditionsToPropertyPlantAndEquipment",
        ]
        shares_tags = ["WeightedAverageNumberOfDilutedSharesOutstanding"]
        assets_tags = ["Assets"]
        current_liability_tags = ["LiabilitiesCurrent"]
        equity_tags = ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]
        debt_tags = [
            "LongTermDebtAndFinanceLeaseObligations",
            "LongTermDebt",
            "LongTermDebtCurrent",
        ]

        q_revenue = self._duration_series(facts, revenue_tags, ["USD"], "quarter")
        q_income = self._duration_series(facts, net_income_tags, ["USD"], "quarter")
        q_eps = self._duration_series(facts, eps_tags, ["USD/shares"], "quarter")
        q_op_income = self._duration_series(facts, operating_income_tags, ["USD"], "quarter")

        a_revenue = self._duration_series(facts, revenue_tags, ["USD"], "annual")
        a_income = self._duration_series(facts, net_income_tags, ["USD"], "annual")
        a_eps = self._duration_series(facts, eps_tags, ["USD/shares"], "annual")
        a_op_income = self._duration_series(facts, operating_income_tags, ["USD"], "annual")
        a_cfo = self._duration_series(facts, cfo_tags, ["USD"], "annual")
        a_capex = self._duration_series(facts, capex_tags, ["USD"], "annual")
        a_shares = self._duration_series(facts, shares_tags, ["shares"], "annual")
        assets = self._instant_series(facts, assets_tags, ["USD"])
        current_liabilities = self._instant_series(facts, current_liability_tags, ["USD"])
        equity = self._instant_series(facts, equity_tags, ["USD"])
        debt = self._instant_series(facts, debt_tags, ["USD"])

        # Use revenue quarter dates as the backbone because it is the most
        # consistently reported operating metric.
        quarter_dates = list(q_revenue.keys())
        quarterly = []
        for date in quarter_dates[:8]:
            sales = q_revenue.get(date)
            pat = self._nearest(q_income, date, 20)
            eps = self._nearest(q_eps, date, 20)
            ebit = self._nearest(q_op_income, date, 20)
            opm = (ebit / sales * 100) if sales not in (None, 0) and ebit is not None else None
            npm = (pat / sales * 100) if sales not in (None, 0) and pat is not None else None
            quarterly.append({
                "period": date,
                "sales": sales,
                "pat": pat,
                "eps": eps,
                "ebit": ebit,
                "opm": round(opm, 2) if opm is not None else None,
                "npm": round(npm, 2) if npm is not None else None,
                "debt_to_equity": None,
                "operating_cash_flow": None,
                "free_cash_flow": None,
                "roe": None,
                "roa": None,
                "roce": None,
                "cash_flow_per_share": None,
            })

        for i, row in enumerate(quarterly):
            previous = quarterly[i + 1] if i + 1 < len(quarterly) else None
            year_ago = quarterly[i + 4] if i + 4 < len(quarterly) else None
            row["qoq_sales"] = self._growth(row["sales"], previous["sales"]) if previous else None
            row["qoq_pat"] = self._growth(row["pat"], previous["pat"]) if previous else None
            row["qoq_eps"] = self._growth(row["eps"], previous["eps"]) if previous else None
            row["yoy_sales"] = self._growth(row["sales"], year_ago["sales"]) if year_ago else None
            row["yoy_pat"] = self._growth(row["pat"], year_ago["pat"]) if year_ago else None
            row["yoy_eps"] = self._growth(row["eps"], year_ago["eps"]) if year_ago else None

        annual_dates = list(a_revenue.keys())
        annual = []
        for date in annual_dates[:6]:
            sales = a_revenue.get(date)
            pat = self._nearest(a_income, date, 45)
            eps = self._nearest(a_eps, date, 45)
            ebit = self._nearest(a_op_income, date, 45)
            cfo = self._nearest(a_cfo, date, 45)
            capex = self._nearest(a_capex, date, 45)
            shares = self._nearest(a_shares, date, 45)
            asset_value = self._nearest(assets, date, 45)
            current_liability_value = self._nearest(current_liabilities, date, 45)
            equity_value = self._nearest(equity, date, 45)
            debt_value = self._nearest(debt, date, 45)

            opm = (ebit / sales * 100) if sales not in (None, 0) and ebit is not None else None
            npm = (pat / sales * 100) if sales not in (None, 0) and pat is not None else None
            roe = (pat / equity_value * 100) if pat is not None and equity_value not in (None, 0) else None
            roa = (pat / asset_value * 100) if pat is not None and asset_value not in (None, 0) else None
            capital_employed = None
            if asset_value is not None and current_liability_value is not None:
                capital_employed = asset_value - current_liability_value
            roce = (ebit / capital_employed * 100) if ebit is not None and capital_employed not in (None, 0) else None
            debt_to_equity = (debt_value / equity_value) if debt_value is not None and equity_value not in (None, 0) else None
            fcf = (cfo - capex) if cfo is not None and capex is not None else None
            cfps = (cfo / shares) if cfo is not None and shares not in (None, 0) else None

            annual.append({
                "period": date,
                "sales": sales,
                "pat": pat,
                "eps": eps,
                "ebit": ebit,
                "opm": round(opm, 2) if opm is not None else None,
                "npm": round(npm, 2) if npm is not None else None,
                "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else None,
                "operating_cash_flow": cfo,
                "free_cash_flow": fcf,
                "roe": round(roe, 2) if roe is not None else None,
                "roa": round(roa, 2) if roa is not None else None,
                "roce": round(roce, 2) if roce is not None else None,
                "cash_flow_per_share": round(cfps, 2) if cfps is not None else None,
            })

        for i, row in enumerate(annual):
            previous = annual[i + 1] if i + 1 < len(annual) else None
            row["yoy_sales"] = self._growth(row["sales"], previous["sales"]) if previous else None
            row["yoy_pat"] = self._growth(row["pat"], previous["pat"]) if previous else None
            row["yoy_eps"] = self._growth(row["eps"], previous["eps"]) if previous else None

        cagr_3y = {"sales": None, "pat": None, "eps": None}
        cagr_5y = {"sales": None, "pat": None, "eps": None}
        if len(annual) >= 4:
            cagr_3y = {
                "sales": self._cagr(annual[0]["sales"], annual[3]["sales"], 3),
                "pat": self._cagr(annual[0]["pat"], annual[3]["pat"], 3),
                "eps": self._cagr(annual[0]["eps"], annual[3]["eps"], 3),
            }
        if len(annual) >= 6:
            cagr_5y = {
                "sales": self._cagr(annual[0]["sales"], annual[5]["sales"], 5),
                "pat": self._cagr(annual[0]["pat"], annual[5]["pat"], 5),
                "eps": self._cagr(annual[0]["eps"], annual[5]["eps"], 5),
            }

        return {
            "symbol": symbol.upper(),
            "quarterly": quarterly,
            "annual": annual,
            "cagr_3y": cagr_3y,
            "cagr_5y": cagr_5y,
            "source": "SEC companyfacts",
            "ratio_methodology": {
                "roe": "Net income / period-end stockholders equity",
                "roa": "Net income / period-end total assets",
                "roce": "Operating income / (period-end total assets - period-end current liabilities)",
            },
        }
