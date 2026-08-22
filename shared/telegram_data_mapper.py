"""Map strategy results into flat per-token Telegram records."""

from __future__ import annotations

from typing import Any, Dict, List


def map_telegram_data(strategy_result: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return one flat notification record per selection with its Gemini review."""
    gemini_scores = {
        str(score.get("token")): score
        for score in (strategy_result.get("gemini_review") or {}).get("scores", [])
    }
    records = []
    for selection in strategy_result.get("selections") or []:
        token = str(selection.get("token", "UNKNOWN"))
        review = gemini_scores.get(token)
        records.append(
            {
                "token": token,
                "signal": selection.get("signal"),
                "confidence": selection.get("confidence"),
                "type": selection.get("type"),
                "label": selection.get("label"),
                "entry_range": selection.get("entry_range"),
                "sl_range": selection.get("sl_range"),
                "tp_range": selection.get("tp_range"),
                "trade_plan": selection.get("trade_plan"),
                "indicators": selection.get("indicators") or {},
                "reasons": selection.get("reasons") or [],
                "warnings": selection.get("warnings") or [],
                "gemini_review": {
                    "score": review.get("score") if review else None,
                    "decision": review.get("decision") if review else "UNAVAILABLE",
                    "reasons": review.get("reasons", []) if review else [],
                    "risk_flags": review.get("risk_flags", []) if review else [],
                },
            }
        )
    return records