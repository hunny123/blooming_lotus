"""Telegram notification service."""

class TelegramService:
    """Own Telegram message formatting and delivery operations."""

    def __init__(self, implementation):
        self._implementation = implementation

    def send(self, message):
        return self._implementation.send_telegram(message)

    def send_pending(self, result):
        return self._implementation.send_pending_telegram(result)

    def send_confirmed(self, result):
        return self._implementation.send_confirmed_telegram(result)

    def format_confirmed(self, result):
        return self._implementation.telegram_message(result)

    def format_pending(self, result):
        return self._implementation.telegram_pending_message(result)
