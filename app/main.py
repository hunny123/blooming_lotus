"""Main orchestration for the configurable strategy pipeline."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(PROJECT_ROOT / ".env.local")

from shared.binance.client import BinancePublicClient
from shared.get_initial_tokens import get_initial_tokens
from shared.groq_trade_scorer import GroqTradeScorer
from shared.gemini_trade_scorer import GeminiTradeScorer
from shared.telegram_message_sender import TelegramMessageSender
from shared.telegram_data_mapper import map_telegram_data
from strategy.config import load_strategy_config
from strategy.registry import get_strategy


def run(
    config_path: Optional[str] = None,
    *,
    client: Optional[BinancePublicClient] = None,
    telegram: Optional[TelegramMessageSender] = None,
    groq: Optional[GroqTradeScorer] = None,
    gemini: Optional[GeminiTradeScorer] = None,
    mandatory_tokens: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Select tokens, observe the same universe twice, analyze it, and notify Telegram."""
    config = load_strategy_config(config_path)
    market_client = client or BinancePublicClient()
    rules = [rule.__dict__ for rule in config.initial_tokens]
    required_tokens = mandatory_tokens if mandatory_tokens is not None else config.mandatory_tokens

    tokens = get_initial_tokens(
        rules,
        required_tokens,
        client=market_client,
    )
    strategy = get_strategy(config=config)
    result = strategy.run(tokens, client=market_client)

    if config.groq_enabled:
        scorer = groq or GroqTradeScorer(
            max_tokens=config.groq_max_tokens,
            debug_logging=config.groq_debug_logging,
        )
        result["groq_review"] = scorer.score(result)
    else:
        result["groq_review"] = {"status": "disabled", "scores": []}

    if config.gemini_enabled:
        scorer = gemini or GeminiTradeScorer(
            model=config.gemini_model,
            max_tokens=config.gemini_max_tokens,
            debug_logging=config.gemini_debug_logging,
        )
        result["gemini_review"] = scorer.score(result)
    else:
        result["gemini_review"] = {"status": "disabled", "scores": []}

    result["telegram_data"] = map_telegram_data(result)

    if config.telegram_enabled:
        sender = telegram or TelegramMessageSender()
        result["telegram_sent"] = sender.send(result)
        print(json.dumps(result["telegram_data"], indent=2, default=str))
    else:
        result["telegram_sent"] = False
        print(json.dumps(result, indent=2, default=str))
    return result


def main() -> Dict[str, Any]:
    return run()


if __name__ == "__main__":
    main()