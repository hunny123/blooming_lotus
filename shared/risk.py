"""Shared risk utilities used by strategies."""

from __future__ import annotations


def risk_check(entry: float, stop_loss: float) -> bool:
    if entry <= 0 or stop_loss <= 0:
        return False
    risk_pct = abs((entry - stop_loss) / entry) * 100
    return risk_pct <= 5.0
