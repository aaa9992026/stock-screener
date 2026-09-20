import requests


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

            test_issue = row.get("Test Issue", "N").strip()

            if not symbol or not name or test_issue == "Y":
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