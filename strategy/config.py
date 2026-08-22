"""Config-driven strategy settings for the signal bot."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_CONFIG_PATH = Path(__file__).with_name("default_config.json")


@dataclass
class TokenScanConfig:
    count: int = 50
    dir: str = "top"
    timeframe: str = "24h"
    min_volume: float = 20_000_000.0


@dataclass
class StrategyConfig:
    strategy_name: str = "base"
    enabled: bool = True
    scan_top_count: int = 50
    scan_last_count: int = 50
    initial_tokens: list[TokenScanConfig] = field(default_factory=lambda: [
        TokenScanConfig(count=3, dir="top"),
        TokenScanConfig(count=2, dir="low"),
    ])
    mandatory_tokens: list[str] = field(default_factory=list)
    scan_interval_seconds: int = 300
    repeat_scan_enabled: bool = True
    observation_scan_enabled: bool = True
    observation_scan_interval_seconds: int = 300
    max_candidates: int = 50
    min_quote_volume: float = 20_000_000.0
    confirmation_scans: int = 2
    min_confidence: float = 60.0
    min_confirmation_confidence: float = 60.0
    run_once: bool = False
    telegram_enabled: bool = False
    groq_enabled: bool = False
    groq_max_tokens: int = 5
    groq_debug_logging: bool = True
    gemini_enabled: bool = False
    gemini_model: str = "gemini-3.6-flash"
    gemini_max_tokens: int = 1024
    gemini_debug_logging: bool = True

    def __post_init__(self) -> None:
        self.initial_tokens = [
            item if isinstance(item, TokenScanConfig) else TokenScanConfig(**item)
            for item in self.initial_tokens
        ]

    @classmethod
    def from_env(cls, env: Optional[Dict[str, str]] = None) -> "StrategyConfig":
        env = env or os.environ
        config = cls()

        if env.get("STRATEGY_NAME"):
            config.strategy_name = env["STRATEGY_NAME"]
        if env.get("STRATEGY_ENABLED"):
            config.enabled = env["STRATEGY_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("SCAN_TOP_COUNT"):
            config.scan_top_count = int(env["SCAN_TOP_COUNT"])
        if env.get("SCAN_LAST_COUNT"):
            config.scan_last_count = int(env["SCAN_LAST_COUNT"])
        if env.get("SCAN_INTERVAL_SECONDS"):
            config.scan_interval_seconds = int(env["SCAN_INTERVAL_SECONDS"])
        if env.get("REPEAT_SCAN_ENABLED"):
            config.repeat_scan_enabled = env["REPEAT_SCAN_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("OBSERVATION_SCAN_ENABLED"):
            config.observation_scan_enabled = env["OBSERVATION_SCAN_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("OBSERVATION_SCAN_INTERVAL_SECONDS"):
            config.observation_scan_interval_seconds = int(env["OBSERVATION_SCAN_INTERVAL_SECONDS"])
        if env.get("MAX_CANDIDATES"):
            config.max_candidates = int(env["MAX_CANDIDATES"])
        if env.get("MIN_QUOTE_VOLUME"):
            config.min_quote_volume = float(env["MIN_QUOTE_VOLUME"])
        if env.get("CONFIRMATION_SCANS"):
            config.confirmation_scans = int(env["CONFIRMATION_SCANS"])
        if env.get("MIN_CONFIDENCE"):
            config.min_confidence = float(env["MIN_CONFIDENCE"])
        if env.get("MIN_CONFIRMATION_CONFIDENCE"):
            config.min_confirmation_confidence = float(env["MIN_CONFIRMATION_CONFIDENCE"])
        if env.get("RUN_ONCE"):
            config.run_once = env["RUN_ONCE"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("TELEGRAM_ENABLED"):
            config.telegram_enabled = env["TELEGRAM_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("GROQ_ENABLED"):
            config.groq_enabled = env["GROQ_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("GROQ_MAX_TOKENS"):
            config.groq_max_tokens = int(env["GROQ_MAX_TOKENS"])
        if env.get("GROQ_DEBUG_LOGGING"):
            config.groq_debug_logging = env["GROQ_DEBUG_LOGGING"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("GEMINI_ENABLED"):
            config.gemini_enabled = env["GEMINI_ENABLED"].strip().lower() in {"1", "true", "yes", "on"}
        if env.get("GEMINI_MODEL"):
            config.gemini_model = env["GEMINI_MODEL"]
        if env.get("GEMINI_MAX_TOKENS"):
            config.gemini_max_tokens = int(env["GEMINI_MAX_TOKENS"])
        if env.get("GEMINI_DEBUG_LOGGING"):
            config.gemini_debug_logging = env["GEMINI_DEBUG_LOGGING"].strip().lower() in {"1", "true", "yes", "on"}

        return config

    @classmethod
    def from_file(cls, path: Optional[str] = None) -> "StrategyConfig":
        config_path = Path(path) if path else DEFAULT_CONFIG_PATH
        if not config_path.exists():
            return cls()

        with config_path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        config = cls()
        for field_name, value in payload.items():
            if hasattr(config, field_name):
                if field_name == "initial_tokens":
                    value = [TokenScanConfig(**item) for item in value]
                setattr(config, field_name, value)
        return config

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_strategy_config(config_path: Optional[str] = None) -> StrategyConfig:
    """Load the strategy config. File values are the defaults, then env overrides win."""
    config = StrategyConfig.from_file(config_path)
    env_config = StrategyConfig.from_env()

    merged = config.to_dict()
    environment_fields = {
        "strategy_name": "STRATEGY_NAME",
        "enabled": "STRATEGY_ENABLED",
        "scan_top_count": "SCAN_TOP_COUNT",
        "scan_last_count": "SCAN_LAST_COUNT",
        "scan_interval_seconds": "SCAN_INTERVAL_SECONDS",
        "repeat_scan_enabled": "REPEAT_SCAN_ENABLED",
        "observation_scan_enabled": "OBSERVATION_SCAN_ENABLED",
        "observation_scan_interval_seconds": "OBSERVATION_SCAN_INTERVAL_SECONDS",
        "max_candidates": "MAX_CANDIDATES",
        "min_quote_volume": "MIN_QUOTE_VOLUME",
        "confirmation_scans": "CONFIRMATION_SCANS",
        "min_confidence": "MIN_CONFIDENCE",
        "min_confirmation_confidence": "MIN_CONFIRMATION_CONFIDENCE",
        "run_once": "RUN_ONCE",
        "telegram_enabled": "TELEGRAM_ENABLED",
        "groq_enabled": "GROQ_ENABLED",
        "groq_max_tokens": "GROQ_MAX_TOKENS",
        "groq_debug_logging": "GROQ_DEBUG_LOGGING",
        "gemini_enabled": "GEMINI_ENABLED",
        "gemini_model": "GEMINI_MODEL",
        "gemini_max_tokens": "GEMINI_MAX_TOKENS",
        "gemini_debug_logging": "GEMINI_DEBUG_LOGGING",
    }
    for field_name, environment_name in environment_fields.items():
        if os.environ.get(environment_name):
            merged[field_name] = getattr(env_config, field_name)
    return StrategyConfig(**merged)
