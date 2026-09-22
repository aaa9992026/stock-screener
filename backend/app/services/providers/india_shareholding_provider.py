import re
from datetime import datetime

import requests
from bs4 import BeautifulSoup


class IndiaShareholdingProvider:
    """Public Indian shareholding-history fallback.

    Screener.in exposes a public quarterly Shareholding Pattern table for many
    NSE/BSE companies.  This provider reads only that public table and never
    invents missing categories.
    """

    BASE_URL = "https://www.screener.in/company/{symbol}/"

    def __init__(self, timeout=15):
        self.timeout = timeout

    @staticmethod
    def _clean_label(value):
        return re.sub(r"\s+", " ", (value or "").replace("+", " " )).strip().lower()

    @staticmethod
    def _percent(value):
        if value is None:
            return None
        text = str(value).strip().replace(",", "").replace("%", "")
        if not text or text in {"-", "—"}:
            return None
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else None

    @staticmethod
    def _period_date(text):
        text = re.sub(r"\s+", " ", (text or "").strip())
        for fmt in ("%b %Y", "%B %Y"):
            try:
                dt = datetime.strptime(text, fmt)
                month = dt.month
                # Quarter-end style date keeps the UI consistent.
                day = 31 if month in (3, 12) else 30
                return f"{dt.year:04d}-{month:02d}-{day:02d}"
            except ValueError:
                pass
        return text

    def _fetch(self, symbol):
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; StockScreener/1.0; +public-market-data)",
            "Accept-Language": "en-US,en;q=0.9",
        }
        urls = [
            self.BASE_URL.format(symbol=symbol.upper()),
            self.BASE_URL.format(symbol=symbol.upper()) + "consolidated/",
        ]
        last_error = None
        for url in urls:
            try:
                response = requests.get(url, headers=headers, timeout=self.timeout)
                if response.status_code == 200 and "Shareholding Pattern" in response.text:
                    return response.text, url
                last_error = f"HTTP {response.status_code}"
            except Exception as exc:
                last_error = str(exc)
        raise RuntimeError(f"Indian shareholding source unavailable: {last_error or 'no usable response'}")

    def get_history(self, symbol, limit=8):
        html, source_url = self._fetch(symbol)
        soup = BeautifulSoup(html, "html.parser")

        selected = None
        for table in soup.find_all("table"):
            rows = table.find_all("tr")
            if not rows:
                continue
            text = table.get_text(" ", strip=True)
            lowered = text.lower()
            if "promoter" in lowered and "public" in lowered and re.search(r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+20\d{2}", lowered):
                selected = table
                break

        if selected is None:
            raise RuntimeError("Shareholding Pattern table was not found for this symbol")

        rows = selected.find_all("tr")
        header_cells = rows[0].find_all(["th", "td"])
        periods = [c.get_text(" ", strip=True) for c in header_cells[1:]]
        if not periods:
            # Some layouts use a second row for the period headings.
            for row in rows[:3]:
                cells = row.find_all(["th", "td"])
                candidate = [c.get_text(" ", strip=True) for c in cells[1:]]
                if sum(bool(re.search(r"20\d{2}", x)) for x in candidate) >= 2:
                    periods = candidate
                    break

        categories = {
            "promoter": None,
            "fii": None,
            "dii": None,
            "mutual_funds": None,
            "public": None,
            "government": None,
        }
        extracted = {}

        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if len(cells) < 2:
                continue
            label = self._clean_label(cells[0].get_text(" ", strip=True))
            values = [self._percent(c.get_text(" ", strip=True)) for c in cells[1:1 + len(periods)]]
            key = None
            if label.startswith("promoter"):
                key = "promoter"
            elif label in {"fiis", "fii", "foreign institutional investors", "foreign portfolio investors"}:
                key = "fii"
            elif label in {"diis", "dii", "domestic institutional investors"}:
                key = "dii"
            elif "mutual fund" in label:
                key = "mutual_funds"
            elif label.startswith("public"):
                key = "public"
            elif label.startswith("government"):
                key = "government"

            if key and key not in extracted:
                extracted[key] = values

        history = []
        for i, period in enumerate(periods):
            item = {
                "period": self._period_date(period),
                "promoter": (extracted.get("promoter") or [None] * len(periods))[i] if i < len(extracted.get("promoter") or []) else None,
                "fii": (extracted.get("fii") or [None] * len(periods))[i] if i < len(extracted.get("fii") or []) else None,
                "dii": (extracted.get("dii") or [None] * len(periods))[i] if i < len(extracted.get("dii") or []) else None,
                "mutual_funds": (extracted.get("mutual_funds") or [None] * len(periods))[i] if i < len(extracted.get("mutual_funds") or []) else None,
                "public": (extracted.get("public") or [None] * len(periods))[i] if i < len(extracted.get("public") or []) else None,
                "government": (extracted.get("government") or [None] * len(periods))[i] if i < len(extracted.get("government") or []) else None,
            }
            history.append(item)

        # Public table is normally oldest -> newest.  Sort by normalized date so
        # upstream layout changes do not break change calculations.
        history.sort(key=lambda x: x["period"])

        for idx, item in enumerate(history):
            previous = history[idx - 1] if idx > 0 else None
            for key in ("promoter", "fii", "dii", "mutual_funds", "public"):
                current_value = item.get(key)
                previous_value = previous.get(key) if previous else None
                item[f"{key}_change"] = (
                    round(current_value - previous_value, 2)
                    if current_value is not None and previous_value is not None
                    else None
                )

        history = history[-max(1, min(int(limit), 12)):][::-1]
        latest = history[0] if history else None

        mf_available = any(row.get("mutual_funds") is not None for row in history)
        note = (
            "Quarterly Indian shareholding is read from Screener.in's public Shareholding Pattern table. "
            "Values are shown exactly when the source exposes them; missing categories are not estimated."
        )
        if not mf_available:
            note += " Mutual-fund holding is not separately exposed in the public summary table for this symbol; DII is shown separately and MF remains unavailable rather than being guessed."

        return {
            "symbol": symbol.upper(),
            "source": "Screener.in public Shareholding Pattern",
            "source_url": source_url,
            "latest": latest,
            "history": history,
            "mutual_fund_separate_available": mf_available,
            "provider_note": note,
        }
