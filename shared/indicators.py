"""Shared indicator utilities used by all strategies."""

from __future__ import annotations

from typing import Sequence


def ema(values: Sequence[float], period: int) -> float | None:
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    for value in values[period:]:
        result = (value - result) * multiplier + result
    return result


def trend_score(closes: Sequence[float]) -> str:
    if len(closes) < 3:
        return "UNKNOWN"
    previous = closes[-2]
    current = closes[-1]
    if current > previous:
        return "UP"
    if current < previous:
        return "DOWN"
    return "SIDEWAYS"
