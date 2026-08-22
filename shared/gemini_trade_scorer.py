"""Gemini-based scoring for strategy trade plans."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# 1. Define the strict JSON schema
class TradeScoreItem(BaseModel):
    token: str
    score: int = Field(ge=0, le=10, description="Score integer from 0 to 10")
    decision: Literal["PASS", "REJECT", "REVIEW"]
    reasons: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)


class TradeScorePayload(BaseModel):
    scores: List[TradeScoreItem]


class GeminiTradeScorer:
    """Score strategy selections using Google's Gemini API."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        debug_logging: Optional[bool] = None,
        client: Any = None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        # Flash is faster and cost-effective for JSON scoring
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        # Increased token limit to prevent JSON truncation
        self.max_tokens =20000
        raw_debug_logging = os.getenv("GEMINI_DEBUG_LOGGING", "true")
        self.debug_logging = (
            debug_logging
            if debug_logging is not None
            else str(raw_debug_logging).strip().lower() in {"1", "true", "yes", "on"}
        )
        self.client = client

    def score(self, strategy_result: Dict[str, Any]) -> Dict[str, Any]:
        plans = [
            selection
            for selection in strategy_result.get("selections", [])
            if selection.get("trade_plan") is not None
        ]
        if not plans:
            return {"status": "skipped", "reason": "no trade plans", "scores": []}
        if not self.api_key and self.client is None:
            return {"status": "skipped", "reason": "GEMINI_API_KEY is not configured", "scores": []}

        if self.client is None:
            from google import genai
            self.client = genai.Client(api_key=self.api_key)

        from google.genai import types

        prompt = f"Evaluate these trade plans:\n{json.dumps({'trades': plans}, default=str)}"
        
        if self.debug_logging:
            print(f"Gemini request model: {self.model}")

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=self._system_prompt(),
                    temperature=0.0,
                    max_output_tokens=self.max_tokens,
                    response_mime_type="application/json",
                    response_schema=TradeScorePayload,  # Strict schema enforcement
                ),
            )
            content = response.text or ""
        except Exception as error:
            return {
                "status": "error",
                "reason": f"Gemini request failed: {error}",
                "model": self.model,
                "scores": [],
            }

        if self.debug_logging:
            print(f"Gemini response body: {content}")

        try:
            payload = json.loads(content)
        except (TypeError, ValueError) as error:
            return {
                "status": "error",
                "reason": f"Gemini returned invalid JSON: {error}",
                "model": self.model,
                "scores": [],
            }

        scores = [self._normalize_score(item) for item in payload.get("scores", [])]
        return {"status": "ok", "model": self.model, "scores": scores}

    @staticmethod
    def _system_prompt() -> str:
        return (
            "You are a conservative trade-plan reviewer. Review each supplied trade plan "
            "using only its data. Evaluate entry, stop loss, risk-reward ratio, and structure. "
            "Assign an integer score from 0 to 10. Do not invent market data or modify prices. "
            "REJECT plans with invalid direction, missing risk controls, or clearly excessive risk."
        )

    @staticmethod
    def _normalize_score(item: Dict[str, Any]) -> Dict[str, Any]:
        try:
            score = max(0, min(10, int(float(item.get("score", 0)))))
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
            "reasons": [str(v) for v in reasons] if isinstance(reasons, list) else [str(reasons)],
            "risk_flags": [str(v) for v in risk_flags] if isinstance(risk_flags, list) else [str(risk_flags)],
        }