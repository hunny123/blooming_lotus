"""Telegram notifications for config-driven strategy selections."""

from __future__ import annotations

import html
import os
import time
from typing import Any, Dict, List, Optional

import requests


class TelegramMessageSender:
    """Format and deliver strategy output to Telegram."""

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        session: Optional[requests.Session] = None,
        send_per_token: bool = True,  # Sends distinct message per token
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        self.session = session or requests.Session()
        self.send_per_token = send_per_token

    def format_token_message(self, strategy_name: str, selection: Dict[str, Any]) -> str:
        """Format an individual token selection into a clean, dedicated message."""
        strategy = html.escape(str(strategy_name))
        lines = [f"⚡ <b>{strategy.upper()} SIGNAL</b>", ""]
        lines.extend(self._format_selection(selection))
        return "\n".join(lines).rstrip()

    def format(self, strategy_result: Dict[str, Any]) -> str:
        """Format all selections into a single combined message with clear dividers."""
        strategy = html.escape(str(strategy_result.get("strategy", "strategy")))
        selections = (
            strategy_result.get("telegram_data")
            or strategy_result.get("selections")
            or []
        )
        lines = [
            f"📢 <b>{strategy.upper()} SELECTIONS</b>",
            f"Total Candidates: <b>{len(selections)}</b>",
            "",
        ]

        for i, selection in enumerate(selections):
            if i > 0:
                # Strong distinct visual separator between tokens
                lines.extend(["", "═══════════════════════════════", ""])
            lines.extend(self._format_selection(selection))

        return "\n".join(lines).rstrip()

    def send(self, strategy_result: Dict[str, Any]) -> bool:
        """Send formatted strategy output. Returns True if all sends succeed."""
        if not self.bot_token or not self.chat_id:
            return False

        selections = (
            strategy_result.get("telegram_data")
            or strategy_result.get("selections")
            or []
        )

        if not selections:
            return False

        # Mode A: Send separate message for each token (Recommended)
        if self.send_per_token:
            strategy_name = strategy_result.get("strategy", "strategy")
            all_successful = True

            for selection in selections:
                text = self.format_token_message(strategy_name, selection)
                success = self._send_raw_message(text)
                if not success:
                    all_successful = False
                time.sleep(0.1)  # Brief pause to respect Telegram rate limits

            return all_successful

        # Mode B: Send single combined message with dividers
        return self._send_raw_message(self.format(strategy_result))

    def _send_raw_message(self, text: str) -> bool:
        """Helper to post a single message payload to Telegram API."""
        try:
            response = self.session.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": "HTML",
                    "disable_web_page_preview": True,
                },
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
            return bool(payload.get("ok"))
        except Exception as error:
            print(f"Telegram send failed: {error}")
            return False

    @classmethod
    def _format_selection(cls, selection: Dict[str, Any]) -> List[str]:
        token = html.escape(str(selection.get("token", "unknown")))
        label = html.escape(str(selection.get("label", "candidate")))
        indicators = selection.get("indicators") or {}
        signal = html.escape(str(selection.get("signal", "WAIT")))
        confidence = selection.get("confidence")
        confidence_text = f"{float(confidence):.1f}%" if confidence is not None else "n/a"
        
        gemini_review = selection.get("gemini_review") or {}
        gemini_score = gemini_review.get("score")
        gemini_score_text = (
            f"{html.escape(str(gemini_score))}/10"
            if gemini_score is not None
            else "N/A"
        )
        gemini_decision = html.escape(str(gemini_review.get("decision", "UNAVAILABLE")))

        # Header Block
        signal_icon = "🟢" if signal == "LONG" else "🔴" if signal == "SHORT" else "⏳"
        lines = [
            f"{signal_icon} <b>{signal}</b> | <b>{token}</b>",
            f"Label: <i>{label}</i>",
            f"Confidence: <b>{confidence_text}</b>",
            f"🤖 Gemini Review: <b>{gemini_score_text}</b> ({gemini_decision})",
        ]

        # Market Section
        lines.extend(["", "📊 <b>MARKET CONTEXT</b>"])
        market_keys = ("price", "trend_1h", "trend_4h", "trend_1d", "fast_structure", "confirm_structure")
        for key in market_keys:
            if key in indicators:
                lines.append(f"• {html.escape(key.replace('_', ' ').title())}: <code>{html.escape(str(indicators[key]))}</code>")

        deriv_keys = ("oi_change", "oi_direction", "volume_strength", "funding")
        has_deriv = any(k in indicators for k in deriv_keys)
        if has_deriv:
            lines.append("")
            for key in deriv_keys:
                if key in indicators:
                    lines.append(f"• {html.escape(key.replace('_', ' ').title())}: <code>{html.escape(str(indicators[key]))}</code>")

        # Levels Section
        lines.extend(["", "📍 <b>KEY LEVELS</b>"])
        level_keys = ("support", "resistance", "month_high", "month_low")
        for key in level_keys:
            value = indicators.get(key)
            lbl = {
                "month_high": "30D High",
                "month_low": "30D Low",
            }.get(key, key.title())
            lines.append(f"• {lbl}: <code>{html.escape(str(value)) if value is not None else 'n/a'}</code>")

        # Trade Plan Section
        lines.extend(["", "🎯 <b>TRADE PLAN</b>"])
        lines.append(f"• Entry: <b>{cls._format_range(selection.get('entry_range'))}</b>")
        lines.append(f"• Stop Loss: <b>{cls._format_range(selection.get('sl_range'))}</b>")
        lines.append(f"• Take Profit: <b>{cls._format_range(selection.get('tp_range'))}</b>")

        # Gemini Insights & Risk Flags
        review_reasons = gemini_review.get("reasons") or []
        risk_flags = gemini_review.get("risk_flags") or []

        if review_reasons:
            lines.append("")
            lines.append("🤖 <b>Gemini Rationale</b>")
            lines.extend(f"  ▫️ {html.escape(str(reason))}" for reason in review_reasons)

        if risk_flags:
            lines.append("")
            lines.append("⚠️ <b>Risk Flags</b>")
            lines.extend(f"  ▫️ {html.escape(str(flag))}" for flag in risk_flags)

        return lines

    @staticmethod
    def _format_range(value: Any) -> str:
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            return "n/a"
        return f"{value[0]} - {value[1]}"