import os
import re
from datetime import datetime
from functools import lru_cache

import requests
import yfinance as yf
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class SECFundamentalsProvider:
    """Official SEC EDGAR submissions + company-facts provider.

    SEC data is supplemental to market-price data. Requests are deliberately
    conservative, identified with the configured contact User-Agent, retried
    on transient failures, and never replaced with fabricated values.
    """

    TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
    TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
    COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

    def __init__(self):
        self.user_agent = os.getenv("SEC_USER_AGENT", "").strip()
        if not self.user_agent:
            raise RuntimeError(
                "SEC_USER_AGENT is not configured. Set it to a project/app name "
                "and a real contact email before using SEC EDGAR."
            )

        retry = Retry(
            total=3,
            connect=3,
            read=3,
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET"}),
            respect_retry_after_header=True,
            raise_on_status=False,
        )
        self.session = requests.Session()
        adapter = HTTPAdapter(max_retries=retry, pool_connections=4, pool_maxsize=4)
        self.session.mount("https://", adapter)

    def _headers(self):
        return {
            "User-Agent": self.user_agent,
            "Accept-Encoding": "gzip, deflate",
            "Accept": "application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "close",
        }

    @staticmethod
    def _normalize_cik(value):
        if value is None:
            return None
        match = re.search(r"(\d{6,10})", str(value))
        return match.group(1).zfill(10) if match else None

    @classmethod
    def _extract_cik_from_object(cls, value):
        """Best-effort CIK extraction from provider metadata/SEC URLs."""
        if value is None:
            return None
        if isinstance(value, dict):
            for key in ("cik", "cik_str", "cikNumber", "cik_number"):
                cik = cls._normalize_cik(value.get(key))
                if cik:
                    return cik
            for item in value.values():
                cik = cls._extract_cik_from_object(item)
                if cik:
                    return cik
            return None
        if isinstance(value, (list, tuple)):
            for item in value:
                cik = cls._extract_cik_from_object(item)
                if cik:
                    return cik
            return None
        text = str(value)
        for pattern in (r"/edgar/data/(\d{6,10})/", r"CIK[=: ]+(\d{6,10})"):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if match:
                return match.group(1).zfill(10)
        return None

    @lru_cache(maxsize=512)
    def _fallback_cik_from_yahoo(self, symbol: str):
        """Resolve only the identifier when SEC's ticker-map file is unavailable.

        SEC submissions/companyfacts remain the authoritative data source. Yahoo
        is used only as a resilient ticker -> CIK resolver when its metadata
        exposes an SEC archive URL or CIK value.
        """
        symbol = symbol.upper()
        try:
            ticker = yf.Ticker(symbol)
            try:
                info = ticker.info or {}
                cik = self._extract_cik_from_object(info)
                if cik:
                    return cik
            except Exception:
                pass

            candidates = []
            for attr in ("sec_filings", "get_sec_filings"):
                try:
                    value = getattr(ticker, attr, None)
                    if callable(value):
                        value = value()
                    if value is not None:
                        candidates.append(value)
                except Exception:
                    continue
            for candidate in candidates:
                cik = self._extract_cik_from_object(candidate)
                if cik:
                    return cik
        except Exception:
            return None
        return None

    @lru_cache(maxsize=512)
    def _resolve_cik(self, symbol: str):
        symbol = symbol.upper().strip()

        # Optional operator override for an edge-case ticker; format:
        # SEC_CIK_OVERRIDES=AAPL:0000320193,BRK-B:0001067983
        raw_overrides = os.getenv("SEC_CIK_OVERRIDES", "").strip()
        if raw_overrides:
            for item in raw_overrides.split(","):
                if ":" not in item:
                    continue
                ticker, raw_cik = item.split(":", 1)
                if ticker.strip().upper() == symbol:
                    cik = self._normalize_cik(raw_cik)
                    if cik:
                        return cik, "operator override"

        ticker_map_error = None
        try:
            cik = self._ticker_map().get(symbol)
            if cik:
                return cik, "SEC ticker association"
        except Exception as exc:
            ticker_map_error = str(exc)

        cik = self._fallback_cik_from_yahoo(symbol)
        if cik:
            return cik, "provider metadata fallback"

        if ticker_map_error:
            raise RuntimeError(f"Could not resolve SEC CIK for {symbol}: {ticker_map_error}")
        return None, None

    @staticmethod
    def _safe_http_error(response):
        status = getattr(response, "status_code", None)
        if status == 403:
            return "SEC EDGAR denied this automated request (HTTP 403). Verify the SEC_USER_AGENT contact and retry later."
        if status == 429:
            return "SEC EDGAR rate limit reached (HTTP 429). Please retry after the provider cooldown."
        if status:
            return f"SEC EDGAR temporarily returned HTTP {status}."
        return "SEC EDGAR request failed temporarily."

    def _request_json(self, url: str, timeout: int = 30):
        response = self.session.get(url, headers=self._headers(), timeout=timeout)
        if not response.ok:
            raise RuntimeError(self._safe_http_error(response))
        try:
            payload = response.json()
        except Exception as exc:
            raise RuntimeError("SEC EDGAR returned a non-JSON response.") from exc
        if not isinstance(payload, (dict, list)):
            raise RuntimeError("SEC EDGAR returned an unexpected response format.")
        return payload

    @lru_cache(maxsize=1)
    def _ticker_map(self):
        """Resolve ticker -> CIK from official SEC association files.

        The ordinary company_tickers file is the primary source. The exchange
        variant is an official fallback in case SEC changes the primary file's
        availability/shape.
        """
        errors = []
        try:
            payload = self._request_json(self.TICKERS_URL, timeout=25)
            result = {}
            for item in payload.values() if isinstance(payload, dict) else []:
                ticker = str((item or {}).get("ticker", "")).upper().strip()
                cik = (item or {}).get("cik_str")
                if ticker and cik is not None:
                    result[ticker] = str(cik).zfill(10)
            if result:
                return result
        except Exception as exc:
            errors.append(str(exc))

        try:
            payload = self._request_json(self.TICKERS_EXCHANGE_URL, timeout=25)
            fields = payload.get("fields", []) if isinstance(payload, dict) else []
            data = payload.get("data", []) if isinstance(payload, dict) else []
            field_index = {str(name): i for i, name in enumerate(fields)}
            ticker_i = field_index.get("ticker")
            cik_i = field_index.get("cik")
            result = {}
            if ticker_i is not None and cik_i is not None:
                for row in data:
                    if not isinstance(row, list) or max(ticker_i, cik_i) >= len(row):
                        continue
                    ticker = str(row[ticker_i] or "").upper().strip()
                    cik = row[cik_i]
                    if ticker and cik is not None:
                        result[ticker] = str(cik).zfill(10)
            if result:
                return result
        except Exception as exc:
            errors.append(str(exc))

        detail = errors[-1] if errors else "official ticker files were unavailable"
        raise RuntimeError(f"Could not load the SEC ticker/CIK map: {detail}")

    @lru_cache(maxsize=256)
    def _company_facts(self, symbol: str):
        cik, _ = self._resolve_cik(symbol)
        if not cik:
            return None
        return self._request_json(self.COMPANY_FACTS_URL.format(cik=cik), timeout=30)

    @lru_cache(maxsize=256)
    def _submissions(self, symbol: str):
        cik, _ = self._resolve_cik(symbol)
        if not cik:
            return None
        return self._request_json(self.SUBMISSIONS_URL.format(cik=cik), timeout=30)

    def get_recent_filings(self, symbol: str, limit: int = 12):
        """Return recent official EDGAR filings for a US ticker."""
        symbol = symbol.upper()
        cik, _ = self._resolve_cik(symbol)
        if not cik:
            return {
                "symbol": symbol, "cik": None, "company_name": None,
                "filings": [], "source": "SEC EDGAR submissions",
            }
        payload = self._submissions(symbol)
        if not payload:
            return {
                "symbol": symbol, "cik": cik, "company_name": None,
                "filings": [], "source": "SEC EDGAR submissions",
            }

        recent = ((payload.get("filings") or {}).get("recent") or {})
        forms = recent.get("form") or []
        accession = recent.get("accessionNumber") or []
        filed = recent.get("filingDate") or []
        report = recent.get("reportDate") or []
        primary = recent.get("primaryDocument") or []
        descriptions = recent.get("primaryDocDescription") or []

        useful_prefixes = ("10-K", "10-Q", "8-K", "3", "4", "5", "SC 13D", "SC 13G")
        filings = []
        for i, form in enumerate(forms):
            form = str(form or "")
            if not form.startswith(useful_prefixes):
                continue
            accession_number = accession[i] if i < len(accession) else None
            primary_document = primary[i] if i < len(primary) else None
            archive_url = None
            if accession_number and primary_document:
                accession_compact = str(accession_number).replace("-", "")
                archive_url = (
                    f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/"
                    f"{accession_compact}/{primary_document}"
                )
            filings.append({
                "form": form,
                "filing_date": filed[i] if i < len(filed) else None,
                "report_date": report[i] if i < len(report) else None,
                "accession_number": accession_number,
                "primary_document": primary_document,
                "description": descriptions[i] if i < len(descriptions) else None,
                "url": archive_url,
            })
            if len(filings) >= max(1, min(int(limit), 50)):
                break

        return {
            "symbol": symbol, "cik": cik, "company_name": payload.get("name"),
            "filings": filings, "source": "SEC EDGAR submissions",
        }

    def get_snapshot(self, symbol: str, filings_limit: int = 12):
        """Return SEC data without letting one transient SEC sub-endpoint break the dashboard.

        Filings and company-facts are independent official SEC resources. If one
        is temporarily unavailable, the other can still be shown; no missing
        values are fabricated.
        """
        symbol = symbol.upper()
        warnings = []
        try:
            cik, cik_source = self._resolve_cik(symbol)
        except Exception as exc:
            return {
                "symbol": symbol, "cik": None, "company_name": None,
                "filings": [], "fundamental_history": None,
                "source": "SEC EDGAR", "companyfacts_source": None,
                "available": False, "status": "temporarily_unavailable",
                "warnings": [f"CIK resolution temporarily unavailable: {exc}"],
                "note": "No SEC values were substituted. Stored market/fundamental data remains available independently.",
            }

        if not cik:
            return {
                "symbol": symbol, "cik": None, "company_name": None,
                "filings": [], "fundamental_history": None,
                "source": "SEC EDGAR", "companyfacts_source": None,
                "available": False, "status": "not_found",
                "warnings": ["Ticker could not be associated with an SEC CIK."],
                "note": "No SEC values were substituted.",
            }

        if cik_source and cik_source != "SEC ticker association":
            warnings.append(
                f"CIK was resolved using {cik_source}; filings/company facts still come directly from official SEC EDGAR endpoints."
            )
        try:
            filing_data = self.get_recent_filings(symbol, filings_limit)
        except Exception as exc:
            filing_data = {
                "symbol": symbol, "cik": cik, "company_name": None,
                "filings": [], "source": "SEC EDGAR submissions",
            }
            warnings.append(f"Filings temporarily unavailable: {exc}")

        try:
            history = self.get_history(symbol)
        except Exception as exc:
            history = None
            warnings.append(f"Company facts temporarily unavailable: {exc}")

        has_filings = bool(filing_data.get("filings"))
        has_history = bool(history and (history.get("quarterly") or history.get("annual")))
        status = "available" if has_filings and has_history else "partial" if (has_filings or has_history) else "temporarily_unavailable"
        return {
            **filing_data,
            "fundamental_history": history,
            "companyfacts_source": "SEC EDGAR companyfacts" if has_history else None,
            "available": bool(has_filings or has_history),
            "status": status,
            "warnings": warnings,
            "note": (
                "Official SEC EDGAR data is used for US filing history and XBRL fundamentals. "
                "Price/OHLCV data remains sourced from the configured market-data provider. "
                "Unavailable SEC fields remain empty and are never substituted."
            ),
        }

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
            form = item.get("form")
            fp = str(item.get("fp") or "").upper()
            if form not in {"10-Q", "10-K"}:
                continue

            # SEC companyfacts may contain comparative/YTD facts with annual-like
            # durations. For annual history accept only true fiscal-year facts
            # reported on a 10-K with fp=FY. This prevents Q2/Q3/YTD periods from
            # being mistaken for separate annual years.
            if kind == "annual" and not (form == "10-K" and fp == "FY"):
                continue

            # Quarterly facts are selected by duration, not by fiscal-period label.
            # Some issuers expose Q4 as a genuine ~90-day fact in the 10-K with
            # fp=FY.  Keeping those quarter-duration facts prevents the fourth
            # quarter from disappearing from the history table.

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
        for date in quarter_dates[:12]:
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
        for date in annual_dates[:7]:
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
