"""Groq-based scoring for strategy trade plans."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

import requests


class GroqTradeScorer:
    """Score strategy selections without coupling strategies to an LLM provider."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        max_tokens: Optional[int] = None,
        debug_logging: Optional[bool] = None,
        session: Optional[requests.Session] = None,
    ):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = (base_url or os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")).rstrip("/")
        self.max_tokens = max_tokens if max_tokens is not None else None
        raw_debug_logging = os.getenv("GROQ_DEBUG_LOGGING", "true")
        self.debug_logging = debug_logging if debug_logging is not None else str(raw_debug_logging).strip().lower() in {"1", "true", "yes", "on"}
        self.session = session or requests.Session()

    def score(self, strategy_result: Dict[str, Any]) -> Dict[str, Any]:
        """Return normalized Groq scores for every selection with a trade plan."""
        plans = [
            selection for selection in strategy_result.get("selections", [])
            if selection.get("trade_plan") is not None
        ]
        if not plans:
            return {"status": "skipped", "reason": "no trade plans", "scores": []}
        if not self.api_key:
            return {"status": "skipped", "reason": "GROQ_API_KEY is not configured", "scores": []}

        request_payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": self._system_prompt()},
                {"role": "user", "content": json.dumps({"trades": plans}, default=str)},
            ],
        }
        if self.max_tokens is not None:
            request_payload["max_tokens"] = self.max_tokens
        if self.debug_logging:
            print(f"Groq request payload: {json.dumps(request_payload, default=str, indent=2)}")

        response = self.session.post(
            f"{self.base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=request_payload,
            timeout=60,
        )
        if self.debug_logging:
            print(f"Groq response status: {response.status_code}")
            try:
                print(f"Groq response body: {json.dumps(response.json(), default=str)[:1500]}")
            except ValueError:
                print(f"Groq response body: {response.text[:1500]}")
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        payload = json.loads(content)
        scores = [self._normalize_score(item) for item in payload.get("scores", [])]
        return {"status": "ok", "model": self.model, "scores": scores}

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a conservative trade-plan reviewer. Review each supplied trade plan "
            "using only its data. Return JSON only in this shape: "
            '{"scores":[{"token":"BTCUSDT","score":0,"decision":"PASS|REJECT|REVIEW",'
            '"reasons":["short reason"],"risk_flags":["short flag"]}]}. '
            "score is an integer from 0 to 100. Do not invent market data or modify prices. "
            "REJECT plans with invalid direction, missing risk controls, or clearly excessive risk."
        )

    @staticmethod
    def _normalize_score(item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            score = max(0, min(100, int(float(item.get("score", 0)))))
        except (TypeError, ValueError):
            score = 0
        decision = str(item.get("decision", "REVIEW")).upper()
        if decision not in {"PASS", "REJECT", "REVIEW"}:
            decision = "REVIEW"
        reasons = item.get("reasons", [])
        risk_flags = item.get("risk_flags", [])
        return {
            "token": str(item.get("token", "UNKNOWN")),
            "score": score,
            "decision": decision,
            "reasons": [str(value) for value in reasons] if isinstance(reasons, list) else [str(reasons)],
            "risk_flags": [str(value) for value in risk_flags] if isinstance(risk_flags, list) else [str(risk_flags)],
        }
