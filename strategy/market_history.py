"""Strategy-owned persistence for staged market observations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


class MarketHistory:
    """Store initial and follow-up observations for one strategy token universe."""

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {}
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

    def save_snapshot(self, stage: str, tokens: list[str], market_data: Dict[str, Any]) -> None:
        history = self.load()
        history[stage] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tokens": list(tokens),
            "market_data": market_data,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(history, handle, indent=2)

    def compare(self) -> Dict[str, Dict[str, Optional[float]]]:
        history = self.load()
        first = history.get("initial", {})
        second = history.get("observation", {})
        changes: Dict[str, Dict[str, Optional[float]]] = {}
        for token in first.get("tokens", []):
            first_price = first.get("market_data", {}).get(token, {}).get("price")
            second_price = second.get("market_data", {}).get(token, {}).get("price")
            change = None
            if first_price and second_price is not None:
                change = ((second_price - first_price) / first_price) * 100
            changes[token] = {
                "initial_price": first_price,
                "observation_price": second_price,
                "change_percent": change,
            }
        return changes
