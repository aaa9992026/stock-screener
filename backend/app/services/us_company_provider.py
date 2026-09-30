import re
import requests


_NON_EQUITY_NAME_PATTERNS = [
    r"\bwarrants?\b",
    r"\bunits?\b",
    r"\brights?\b",
    r"\bsubscription rights?\b",
    r"\bacquisition (?:corp\.?|corporation|company|co\.?)\b",
    r"\bblank check\b",
    r"\bspac\b",
    r"\bpreferred (?:stock|shares?)\b",
    r"\bpreference shares?\b",
    r"\bdebt securities?\b",
    r"\bdebentures?\b",
    r"\bbonds? due\b",
    r"\bnotes? due\b",
]


def is_supported_us_equity(symbol: str, name: str, row: dict | None = None) -> bool:
    """Return True only for ordinary US equity-like listings.

    Nasdaq Trader files include ETFs, warrants, units, rights and SPAC-related
    securities alongside regular operating-company shares.  Those instruments
    must not consume the client's 6,000-stock RS universe or appear in the
    default stock screener.  ADR/ADS/common/ordinary shares remain allowed.
    """
    symbol = str(symbol or "").strip().upper()
    name = str(name or "").strip()
    if not symbol or not name:
        return False

    row = row or {}
    if str(row.get("ETF", "N") or "N").strip().upper() == "Y":
        return False
    if str(row.get("Test Issue", "N") or "N").strip().upper() == "Y":
        return False

    lower_name = name.lower()
    if any(re.search(pattern, lower_name, flags=re.IGNORECASE) for pattern in _NON_EQUITY_NAME_PATTERNS):
        return False

    return True


class USCompanyProvider:
    NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
    OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"

    def _parse_file(self, text, exchange_name):
        lines = text.strip().splitlines()

        if len(lines) < 2:
            return []

        headers = lines[0].split("|")
        companies = []

        for line in lines[1:]:
            if "File Creation Time" in line:
                continue

            values = line.split("|")

            if len(values) != len(headers):
                continue

            row = dict(zip(headers, values))

            symbol = (
                row.get("Symbol")
                or row.get("ACT Symbol")
                or ""
            ).strip()

            name = row.get("Security Name", "").strip()

            if not is_supported_us_equity(symbol, name, row):
                continue

            companies.append({
                "symbol": symbol,
                "name": name,
                "exchange": "US",
                "sector": None,
                "industry": None
            })

        return companies

    def get_companies(self):
        headers = {
            "User-Agent": "Mozilla/5.0"
        }

        nasdaq_response = requests.get(
            self.NASDAQ_URL,
            headers=headers,
            timeout=30
        )
        nasdaq_response.raise_for_status()

        other_response = requests.get(
            self.OTHER_URL,
            headers=headers,
            timeout=30
        )
        other_response.raise_for_status()

        companies = []

        companies.extend(
            self._parse_file(
                nasdaq_response.text,
                "NASDAQ"
            )
        )

        companies.extend(
            self._parse_file(
                other_response.text,
                "OTHER"
            )
        )

        # Remove duplicate symbols
        unique = {}

        for company in companies:
            unique[company["symbol"]] = company

        return list(unique.values())
