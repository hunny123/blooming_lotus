"""Application orchestration layer for the signal engine."""

from app import core_engine
from app.binance_api import BinanceApi
from app.strategy import StrategyEngine
from app.telegram_service import TelegramService


class SignalApplication:
    """Class-based entry point that preserves the existing scanner behavior."""

    def __init__(
        self,
        core=None,
        runner=None,
        market_api=None,
        strategy=None,
        telegram=None
    ):
        self.core = core or core_engine
        self._runner = runner or self.core.main
        self.market_api = market_api or BinanceApi(self.core)
        self.strategy = strategy or StrategyEngine(self.core)
        self.telegram = telegram or TelegramService(self.core)

    def run(self):
        """Run the configured observation session."""
        return self._runner()
