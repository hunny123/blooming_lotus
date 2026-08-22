"""Core-compatible default strategy implementation."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from shared.binance.client import BinancePublicClient
from strategy.config import StrategyConfig
from utils.core_logic import (
    location,
    lower_structure,
    momentum,
    nearest_levels,
    oi_change,
    signal,
    swing_levels,
    trade_plan,
    trend,
    volume_strength,
)
from strategy.market_history import MarketHistory


TIMEFRAME_INTERVALS = {
    "5m": "5m",
    "15m": "15m",
    "1h": "1h",
    "4h": "4h",
    "1d": "1d",
    "24h": "1d",
}


class BaseStrategy:
    """Default strategy with the former core-engine decision model."""

    name = "base"

    def __init__(self, config: Optional[StrategyConfig] = None, history: Optional[MarketHistory] = None):
        self.config = config or StrategyConfig()
        default_history_path = Path(__file__).resolve().parents[2] / "market_history.json"
        self.history = history or MarketHistory(default_history_path)

    def should_run(self) -> bool:
        return bool(self.config.enabled)

    def candidates_budget(self) -> Dict[str, int]:
        counts = {rule.dir: rule.count for rule in self.config.initial_tokens}
        return {"top": counts.get("top", 0), "low": counts.get("low", 0), "max_candidates": self.config.max_candidates}

    def scan_interval_seconds(self) -> int:
        return self.config.scan_interval_seconds

    def repeat_scan_enabled(self) -> bool:
        return bool(self.config.repeat_scan_enabled)

    def observation_scan_enabled(self) -> bool:
        return bool(self.config.observation_scan_enabled)

    def filter_symbols(self, symbols: Iterable[str]) -> List[str]:
        return list(symbols)[: self.config.max_candidates]

    def collect_market_data(self, client: BinancePublicClient, tokens: Sequence[str]) -> Dict[str, Any]:
        """Collect all market inputs consumed by the base decision model."""
        tickers = client.tickers_24h()
        result: Dict[str, Any] = {}
        for token in tokens:
            candles = {
                timeframe: client.klines(token, interval, limit=250)
                for timeframe, interval in TIMEFRAME_INTERVALS.items()
            }
            primary = candles["5m"]
            ticker = tickers.get(token, {})
            try:
                funding = client.funding(token)
            except Exception:
                funding = 0.0
            try:
                open_interest = client.open_interest(token)
            except Exception:
                open_interest = []
            try:
                all_time_low, all_time_high = client.all_time_extremes(token)
            except Exception:
                all_time_low, all_time_high = None, None
            result[token] = {
                "price": ticker.get("price") or (primary[-1]["close"] if primary else 0.0),
                "high": ticker.get("high"),
                "low": ticker.get("low"),
                "change": ticker.get("change"),
                "volume": ticker.get("volume"),
                "closes": [item["close"] for item in primary],
                "timeframes": candles,
                "funding": funding,
                "oi_history": open_interest,
                "all_time_low": all_time_low,
                "all_time_high": all_time_high,
            }
        return result

    def run(self, symbols: Iterable[str], *args: Any, **kwargs: Any) -> Dict[str, Any]:
        """Find eligible tokens, wait, then observe only those tokens again."""
        client = kwargs.pop("client", None)
        if client is None:
            return self.analyze_symbols(symbols, *args, **kwargs)

        token_list = list(symbols)
        print(f"[strategy] first scan started for {len(token_list)} tokens", flush=True)
        initial_data = self.collect_market_data(client, token_list)
        self.history.save_snapshot("initial", token_list, initial_data)
        initial_result = self.analyze_symbols(token_list, market_data=initial_data)

        eligible_tokens = self.eligible_tokens(initial_result)
        print(
            f"[strategy] first scan complete: {len(eligible_tokens)} eligible tokens",
            flush=True,
        )
        if not eligible_tokens:
            print("[strategy] no eligible tokens; second scan skipped", flush=True)
            initial_result["eligible_tokens"] = []
            initial_result["observation_skipped"] = True
            initial_result["observation_changes"] = {}
            return initial_result

        if not self.observation_scan_enabled():
            print(
                "[strategy] observation scan disabled; sending first-scan eligible tokens",
                flush=True,
            )
            initial_result["selections"] = [
                selection for selection in initial_result["selections"]
                if selection.get("token") in eligible_tokens
            ]
            initial_result["symbols"] = eligible_tokens
            initial_result["count"] = len(eligible_tokens)
            initial_result["eligible_tokens"] = eligible_tokens
            initial_result["observation_skipped"] = True
            initial_result["observation_wait_seconds"] = 0
            initial_result["observation_changes"] = {}
            return initial_result

        wait_seconds = kwargs.pop("wait_seconds", self.config.observation_scan_interval_seconds)
        sleep_fn = kwargs.pop("sleep_fn", time.sleep)
        print(
            f"[strategy] waiting {wait_seconds} seconds before second scan",
            flush=True,
        )
        if wait_seconds > 0:
            sleep_fn(wait_seconds)

        print(
            f"[strategy] second scan started for {len(eligible_tokens)} eligible tokens",
            flush=True,
        )
        observation_data = self.collect_market_data(client, eligible_tokens)
        self.history.save_snapshot("observation", eligible_tokens, observation_data)
        result = self.analyze_symbols(
            eligible_tokens,
            market_data=observation_data,
            previous_result=initial_result,
            **kwargs,
        )
        result["eligible_tokens"] = eligible_tokens
        result["observation_wait_seconds"] = wait_seconds
        result["observation_changes"] = self.history.compare()
        print("[strategy] second scan complete", flush=True)
        return result

    def eligible_tokens(self, result: Dict[str, Any]) -> List[str]:
        """Keep first-pass tokens with a valid directional setup and trade plan."""
        return [
            selection["token"]
            for selection in result.get("selections", [])
            if selection.get("signal") in {"LONG", "SHORT"}
            and selection.get("trade_plan") is not None
            and float(selection.get("confidence", 0.0)) >= self.config.min_confidence
        ]

    def analyze_symbols(self, symbols: Iterable[str], *args: Any, **kwargs: Any) -> Dict[str, Any]:
        token_list = self.filter_symbols(symbols)
        market_data = kwargs.get("market_data") or {}
        selections = [self.build_selection(token, market_data.get(token, {})) for token in token_list]
        return {
            "strategy": self.name,
            "symbols": [item["token"] for item in selections],
            "selections": selections,
            "config": self.config.to_dict(),
            "count": len(selections),
        }

    def build_selection(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply core-engine evidence scoring and trade-plan rules to one token."""
        timeframes = market_data.get("timeframes") or {}
        fast = timeframes.get("5m", [])
        confirm = timeframes.get("15m", [])
        hourly = timeframes.get("1h", [])
        four_hour = timeframes.get("4h", [])
        daily = timeframes.get("1d", [])
        closes = [float(value) for value in market_data.get("closes", [])]
        price = float(market_data.get("price") or (closes[-1] if closes else 0.0))
        if not fast and closes:
            fast = [{"open": value, "high": value, "low": value, "close": value} for value in closes]

        supports_1h, resistances_1h = swing_levels(hourly)
        supports_4h, resistances_4h = swing_levels(four_hour)
        support, resistance = nearest_levels(price, supports_1h + supports_4h, resistances_1h + resistances_4h)
        daily_window = daily[-30:]
        month_high = max((item["high"] for item in daily_window), default=market_data.get("high"))
        month_low = min((item["low"] for item in daily_window), default=market_data.get("low"))
        oi_delta, oi_direction = oi_change(market_data.get("oi_history", []))
        core_data = {
            "price": price,
            "momentum": momentum(fast),
            "volume_strength": volume_strength(fast),
            "oi_change": oi_delta,
            "oi_direction": oi_direction,
            "funding": float(market_data.get("funding", 0.0)) * 100,
            "trend_1h": trend(hourly),
            "trend_4h": trend(four_hour),
            "trend_1d": trend(daily),
            "fast_structure": lower_structure(fast),
            "confirm_structure": lower_structure(confirm),
            "support": support,
            "resistance": resistance,
            "month_high": month_high,
            "month_low": month_low,
            "location": location(price, support, resistance, month_high, month_low),
        }
        decision = signal(core_data)
        plan = trade_plan({**core_data, **decision})
        indicators = {
            key: value for key, value in core_data.items()
            if key not in {"price", "support", "resistance", "month_high", "month_low", "location"}
        }
        indicators.update({"location": core_data["location"], "support": support, "resistance": resistance})
        return {
            "token": symbol,
            "signal": decision["signal"],
            "confidence": decision["confidence"],
            "type": decision["type"],
            "entry_range": self._range(plan["entry"], plan["entry"]) if plan else self._range(price, price),
            "sl_range": self._range(plan["sl"], plan["sl"]) if plan else self._range(price, price),
            "tp_range": self._range(plan["tp1"], plan["tp3"] or plan["tp2"]) if plan else self._range(price, price),
            "trade_plan": plan,
            "indicators": indicators,
            "reasons": decision["reasons"],
            "warnings": decision["warnings"],
            "label": decision["type"].lower().replace(" ", "_"),
        }

    @staticmethod
    def _range(lower: float, upper: float) -> List[float]:
        return [round(min(lower, upper), 8), round(max(lower, upper), 8)]

    def evaluate(self, *args: Any, **kwargs: Any) -> Dict[str, Any]:
        return {"strategy": self.name, "config": self.config.to_dict()}
