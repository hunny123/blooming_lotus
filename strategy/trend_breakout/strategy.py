"""Trend breakout strategy implementation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from strategy.base import BaseStrategy
from strategy.config import StrategyConfig
from shared.indicators import ema


class TrendBreakoutStrategy(BaseStrategy):
    """A trend-following strategy built on the reusable base contract."""

    name = "trend_breakout"

    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config=config)

    def run(self, symbols: Iterable[str], previous_result: Optional[dict] = None, **kwargs: Any) -> dict:
        token_list = list(symbols)
        base_result = super().run(token_list, previous_result=previous_result, **kwargs)
        base_result["strategy"] = self.name
        base_result["mode"] = "trend_breakout"
        return base_result

    def build_selection(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        selection = super().build_selection(symbol, market_data)
        closes = [float(value) for value in market_data.get("closes", [])]
        breakout_high = max(closes[-20:]) if closes else None
        current_price = float(market_data.get("price") or (closes[-1] if closes else 0.0))
        selection["indicators"].update({
            "ema_20": ema(closes, 20),
            "ema_50": ema(closes, 50),
            "breakout_high_20": breakout_high,
            "breakout_confirmed": bool(breakout_high is not None and current_price >= breakout_high),
        })
        selection["label"] = "trend_breakout_candidate"
        return selection
