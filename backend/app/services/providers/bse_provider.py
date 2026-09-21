import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class BSEProvider:
    BASE_URL = "https://api.twelvedata.com"

    def __init__(self):
        self.api_key = os.getenv("TWELVE_DATA_API_KEY")

    def get_ohlcv(self, symbol: str):
        if not self.api_key:
            raise RuntimeError("TWELVE_DATA_API_KEY is not configured")

        response = requests.get(
            f"{self.BASE_URL}/time_series",
            params={
                "symbol": symbol,
                "mic_code": "XBOM",
                "interval": "1day",
                "outputsize": 5000,
                "apikey": self.api_key,
            },
            timeout=30,
        )

        if response.status_code == 404:
            raise RuntimeError(
                "This BSE symbol is not available with the currently configured data plan."
            )

        response.raise_for_status()
        payload = response.json()

        if payload.get("status") == "error":
            raise RuntimeError(payload.get("message", "BSE provider error"))

        values = payload.get("values", [])

        rows = []

        for item in reversed(values):
            rows.append({
                "date": datetime.strptime(
                    item["datetime"], "%Y-%m-%d"
                ).date(),
                "open": float(item["open"]),
                "high": float(item["high"]),
                "low": float(item["low"]),
                "close": float(item["close"]),
                "volume": float(item.get("volume") or 0),
            })

        return rows