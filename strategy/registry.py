"""Registry for all available strategy implementations."""

from __future__ import annotations

from typing import Dict, Type

from strategy.base import BaseStrategy as BaseStrategyImpl
from strategy.config import StrategyConfig
from strategy.risk_controlled.strategy import RiskControlledStrategy
from strategy.trend_breakout.strategy import TrendBreakoutStrategy


class BaseStrategy(BaseStrategyImpl):
    """Compatibility alias for the base strategy implementation."""

    name = "base"


STRATEGY_REGISTRY: Dict[str, Type[BaseStrategy]] = {
    "base": BaseStrategy,
    "core": BaseStrategy,
    "trend_breakout": TrendBreakoutStrategy,
    "risk_controlled": RiskControlledStrategy,
}


def get_strategy(name: str | None = None, config: StrategyConfig | None = None) -> BaseStrategy:
    strategy_name = (name or (config.strategy_name if config else "base")).lower()
    strategy_cls = STRATEGY_REGISTRY.get(strategy_name, BaseStrategy)
    return strategy_cls(config=config or StrategyConfig())


class StrategyRegistry:
    """Simple registry wrapper for strategies."""

    @staticmethod
    def get(name: str | None = None, config: StrategyConfig | None = None) -> BaseStrategy:
        return get_strategy(name=name, config=config)

    @staticmethod
    def available() -> list[str]:
        return sorted(STRATEGY_REGISTRY.keys())
