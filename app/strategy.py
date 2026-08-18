"""Core signal and trade-plan strategy service."""

class StrategyEngine:
    """Own the market-analysis and signal-decision operations."""

    def __init__(self, implementation):
        self._implementation = implementation

    def generate_signal(self, data):
        return self._implementation.generate_signal(data)

    def calculate_trade_plan(self, result):
        return self._implementation.calculate_trade_plan(result)

    def confirm_signal(self, result):
        return self._implementation.confirm_signal(result)

    def analyze_symbol(self, symbol, ticker, funding):
        return self._implementation.analyze_symbol(symbol, ticker, funding)

    def analyze_trend(self, candles):
        return self._implementation.analyze_trend(candles)

    def lower_structure(self, candles):
        return self._implementation.lower_structure(candles)
