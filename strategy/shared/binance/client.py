"""Common Binance public-data client used by all strategies."""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests


BASE_URL = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")


class BinancePublicClient:
    """Reusable public Binance Futures client for strategy implementations."""

    def __init__(self, base_url: str = BASE_URL, session: Optional[requests.Session] = None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "BloomingLotus-Strategy-Client/1.0"})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None):
        last_error: Optional[Exception] = None
        for attempt in range(3):
            try:
                response = self.session.get(self.base_url + path, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt)
        raise last_error

    def exchange_info(self) -> Dict[str, Any]:
        return self.get("/fapi/v1/exchangeInfo")

    def perpetual_symbols(self) -> List[str]:
        data = self.exchange_info()
        return [
            item["symbol"]
            for item in data.get("symbols", [])
            if item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT"
        ]

    def tickers_24h(self) -> Dict[str, Dict[str, float]]:
        rows = self.get("/fapi/v1/ticker/24hr")
        return {
            item["symbol"]: {
                "price": float(item["lastPrice"]),
                "volume": float(item["quoteVolume"]),
                "change": float(item["priceChangePercent"]),
                "high": float(item["highPrice"]),
                "low": float(item["lowPrice"]),
            }
            for item in rows
        }

    def klines(self, symbol: str, interval: str, limit: int = 250) -> List[Dict[str, float]]:
        rows = self.get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        return [
            {
                "time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "quote_volume": float(row[7]),
            }
            for row in rows
        ]

    def funding(self, symbol: str) -> float:
        rows = self.get("/fapi/v1/premiumIndex", {"symbol": symbol})
        row = rows[0] if isinstance(rows, list) else rows
        return float(row["lastFundingRate"])

    def open_interest(self, symbol: str, period: str = "5m", limit: int = 20) -> List[float]:
        rows = self.get("/futures/data/openInterestHist", {"symbol": symbol, "period": period, "limit": limit})
        return [float(row["sumOpenInterestValue"]) for row in rows]

    def depth_imbalance(self, symbol: str, limit: int = 20) -> float:
        data = self.get("/fapi/v1/depth", {"symbol": symbol, "limit": limit})
        bids = sum(float(row[1]) for row in data.get("bids", []))
        asks = sum(float(row[1]) for row in data.get("asks", []))
        total = bids + asks
        return (bids - asks) / total if total else 0.0

    def all_time_extremes(self, symbol: str) -> Tuple[float, float]:
        lows: List[float] = []
        highs: List[float] = []
        start_time = 0
        while True:
            rows = self.get(
                "/fapi/v1/klines",
                {"symbol": symbol, "interval": "1d", "limit": 1500, "startTime": start_time},
            )
            if not rows:
                break
            lows.extend(float(row[3]) for row in rows)
            highs.extend(float(row[2]) for row in rows)
            if len(rows) < 1500:
                break
            start_time = int(rows[-1][0]) + 1
        return (min(lows), max(highs)) if lows else (0.0, 0.0)
