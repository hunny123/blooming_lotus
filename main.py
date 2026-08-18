"""Deployment entry point for the Binance signal engine."""

from app.engine import SignalApplication


def main():
    return SignalApplication().run()


if __name__ == "__main__":
    main()
