"""Binance Futures API service."""

class BinanceApi:
    """Exchange data facade used by the scanner and strategy services."""

    def __init__(self, implementation):
        self._implementation = implementation

    def get_usdt_perpetuals(self):
        return self._implementation.get_usdt_perpetuals()

    def get_24h_tickers(self):
        return self._implementation.get_24h_tickers()

    def get_current_funding(self):
        return self._implementation.get_current_funding()

    def get_klines(self, symbol, interval, limit=250):
        return self._implementation.get_klines(symbol, interval, limit)

    def get_oi_history(self, symbol, period="5m", limit=20):
        return self._implementation.get_oi_history(symbol, period, limit)

    def get_funding_history(self, symbol, limit=10):
        return self._implementation.get_funding_history(symbol, limit)
