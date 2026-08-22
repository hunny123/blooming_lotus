"""Initial-token selection helpers for strategy scanning.

This module returns a list of symbols from an array of scan rules. Each rule
contains a count, direction, and timeframe.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence

from shared.binance.client import BinancePublicClient


TIMEFRAME_MAP = {
    "24h": "1d",
    "8h": "8h",
    "4h": "4h",
    "15m": "15m",
    "5m": "5m",
}


DEFAULT_RULES = [
    {"count": 50, "dir": "top", "timeframe": "24h"},
    {"count": 50, "dir": "low", "timeframe": "24h"},
]


@dataclass
class InitialTokenRequest:
    count: int = 50
    direction: str = "top"
    timeframe: str = "24h"
    min_volume: float = 20_000_000.0

    def __post_init__(self) -> None:
        self.count = max(1, int(self.count))
        self.direction = (self.direction or "top").lower()
        if self.direction not in {"top", "low"}:
            raise ValueError("direction must be 'top' or 'low'")
        self.timeframe = (self.timeframe or "24h").lower()
        if self.timeframe not in TIMEFRAME_MAP:
            raise ValueError("timeframe must be one of: 24h, 8h, 4h, 15m, 5m")


class TokenGetter:
    """Selects candidate symbols using the configured scan request."""

    def __init__(self, client: BinancePublicClient, rule: Dict[str, Any]):
        self.client = client
        self.request = InitialTokenRequest(
            count=rule.get("count", 50),
            direction=rule.get("dir", rule.get("direction", "top")),
            timeframe=str(rule.get("timeframe", "24h")),
            min_volume=rule.get("min_volume", 20_000_000.0),
        )

    def get_tokens(self) -> List[str]:
        if self.request.timeframe == "24h":
            return self._select_from_24h_tickers()
        return self._select_from_timeframe_candles()

    def _select_from_24h_tickers(self) -> List[str]:
        tickers = self.client.tickers_24h()
        filtered = {
            symbol: data
            for symbol, data in tickers.items()
            if data.get("volume", 0.0) >= self.request.min_volume
        }

        if self.request.direction == "top":
            ranked = sorted(filtered.items(), key=lambda item: item[1]["volume"], reverse=True)
        else:
            ranked = sorted(filtered.items(), key=lambda item: item[1]["change"])

        return [symbol for symbol, _ in ranked[: self.request.count]]

    def _select_from_timeframe_candles(self) -> List[str]:
        interval = TIMEFRAME_MAP[self.request.timeframe]
        results: List[tuple[str, float, float]] = []

        for symbol in self.client.perpetual_symbols():
            try:
                candles = self.client.klines(symbol, interval, limit=80)
                if len(candles) < 2:
                    continue

                recent = candles[-20:]
                avg_volume = sum(item["quote_volume"] for item in recent) / max(len(recent), 1)
                if avg_volume < self.request.min_volume:
                    continue

                start = candles[0]
                end = candles[-1]
                change_pct = ((end["close"] - start["open"]) / start["open"]) * 100 if start["open"] else 0.0
                results.append((symbol, change_pct, avg_volume))
            except Exception:
                continue

        if self.request.direction == "top":
            ranked = sorted(results, key=lambda item: item[2], reverse=True)
        else:
            ranked = sorted(results, key=lambda item: item[1])

        return [symbol for symbol, _, _ in ranked[: self.request.count]]


def get_initial_tokens(
    rules: Optional[Sequence[Dict[str, Any]]] = None,
    mandatory_tokens: Optional[Sequence[str]] = None,
    client: Optional[BinancePublicClient] = None,
) -> List[str]:
    """Return unique symbols selected by rules, preserving mandatory symbols.

    Example:
        get_initial_tokens(
            [{"count": 30, "dir": "top", "timeframe": "24h"},
             {"count": 30, "dir": "low", "timeframe": "4h"}],
            ["BTCUSDT"],
        )
    """
    if client is None:
        client = BinancePublicClient()

    selected: List[str] = []
    seen = set()
    for symbol in mandatory_tokens or []:
        normalized = str(symbol).upper()
        if normalized and normalized not in seen:
            selected.append(normalized)
            seen.add(normalized)

    for rule in rules or DEFAULT_RULES:
        for symbol in TokenGetter(client=client, rule=rule).get_tokens():
            if symbol not in seen:
                selected.append(symbol)
                seen.add(symbol)

    return selected
