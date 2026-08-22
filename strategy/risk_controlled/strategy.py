"""Risk-controlled strategy implementation."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from strategy.base import BaseStrategy
from strategy.config import StrategyConfig
from shared.risk import risk_check


class RiskControlledStrategy(BaseStrategy):
    """A conservative strategy that can consume a previous result from another strategy."""

    name = "risk_controlled"

    def __init__(self, config: Optional[StrategyConfig] = None):
        super().__init__(config=config)

    def run(self, symbols: Iterable[str], previous_result: Optional[dict] = None, **kwargs: Any) -> dict:
        token_list = list(symbols)
        base_result = super().run(token_list, previous_result=previous_result, **kwargs)
        base_result["strategy"] = self.name
        base_result["mode"] = "risk_controlled"
        base_result["previous_result_used"] = previous_result is not None
        return base_result

    def build_selection(self, symbol: str, market_data: Dict[str, Any]) -> Dict[str, Any]:
        selection = super().build_selection(symbol, market_data)
        entry = sum(selection["entry_range"]) / 2
        stop = sum(selection["sl_range"]) / 2
        risk_percent = abs(entry - stop) / entry * 100 if entry else None
        selection["indicators"].update({
            "risk_percent": round(risk_percent, 4) if risk_percent is not None else None,
            "risk_allowed": risk_check(entry, stop),
        })
        selection["label"] = "risk_controlled_candidate"
        return selection
