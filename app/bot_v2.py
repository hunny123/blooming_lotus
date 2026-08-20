"""Staged Binance Futures Bot V2 signal pipeline.

This module is intentionally separate from the existing signal engine. It is
signal-only: no Binance order endpoint is called.
"""

from dataclasses import dataclass, asdict
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import requests
from dotenv import load_dotenv


load_dotenv(".env.local")

BASE_URL = os.getenv("BINANCE_BASE_URL", "https://fapi.binance.com")
MIN_QUOTE_VOLUME = 20_000_000.0
TOP_VOLUME_COUNT = 30
TOP_DECLINER_COUNT = 20
MAX_CANDIDATE_COUNT = 30
DEFAULT_WORKERS = 30
CHECKPOINT_COUNT = 6
CHECKPOINT_INTERVAL_SECONDS = 300
MIN_SCORE = 60.0
MAX_STOP_DISTANCE_PCT = 5.0


@dataclass
class Checkpoint:
    """One closed 5-minute observation in the hour-long session."""

    close: float
    high: float
    low: float
    volume: float
    volume_average: float
    time: int


@dataclass
class TradePlan:
    entry: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: Optional[float]
    risk_percent: float


class BinanceV2Client:
    """Small public-data client for Binance USDT perpetuals."""

    def __init__(self, base_url: str = BASE_URL, session=None):
        self.base_url = base_url.rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "Binance-Signal-Bot-V2/1.0"})

    def get(self, path: str, params: Optional[Dict[str, Any]] = None):
        last_error = None
        for attempt in range(3):
            try:
                response = self.session.get(self.base_url + path, params=params, timeout=20)
                response.raise_for_status()
                return response.json()
            except (requests.RequestException, ValueError) as error:
                last_error = error
                if attempt < 2:
                    time.sleep(1 + attempt)
        raise last_error

    def perpetual_symbols(self) -> List[str]:
        data = self.get("/fapi/v1/exchangeInfo")
        return [
            item["symbol"] for item in data["symbols"]
            if item.get("status") == "TRADING"
            and item.get("contractType") == "PERPETUAL"
            and item.get("quoteAsset") == "USDT"
        ]

    def tickers(self) -> Dict[str, Dict[str, float]]:
        return {
            item["symbol"]: {
                "price": float(item["lastPrice"]),
                "volume": float(item["quoteVolume"]),
                "change": float(item["priceChangePercent"]),
                "high": float(item["highPrice"]),
                "low": float(item["lowPrice"]),
            }
            for item in self.get("/fapi/v1/ticker/24hr")
        }

    def klines(self, symbol: str, interval: str, limit: int = 250) -> List[Dict[str, float]]:
        return [
            {
                "time": int(row[0]), "open": float(row[1]), "high": float(row[2]),
                "low": float(row[3]), "close": float(row[4]), "volume": float(row[5]),
                "quote_volume": float(row[7]),
            }
            for row in self.get("/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit})
        ]

    def funding(self, symbol: str) -> float:
        rows = self.get("/fapi/v1/premiumIndex", {"symbol": symbol})
        row = rows[0] if isinstance(rows, list) else rows
        return float(row["lastFundingRate"])

    def open_interest(self, symbol: str, limit: int = 20) -> List[float]:
        rows = self.get("/futures/data/openInterestHist", {"symbol": symbol, "period": "5m", "limit": limit})
        return [float(row["sumOpenInterestValue"]) for row in rows]

    def depth_imbalance(self, symbol: str) -> float:
        data = self.get("/fapi/v1/depth", {"symbol": symbol, "limit": 20})
        bids = sum(float(row[1]) for row in data.get("bids", []))
        asks = sum(float(row[1]) for row in data.get("asks", []))
        return (bids - asks) / (bids + asks) if bids + asks else 0.0

    def all_time_extremes(self, symbol: str) -> Tuple[float, float]:
        lows: List[float] = []
        highs: List[float] = []
        start_time = 0
        while True:
            rows = self.get("/fapi/v1/klines", {"symbol": symbol, "interval": "1d", "limit": 1500, "startTime": start_time})
            if not rows:
                break
            lows.extend(float(row[3]) for row in rows)
            highs.extend(float(row[2]) for row in rows)
            if len(rows) < 1500:
                break
            start_time = int(rows[-1][0]) + 1
        return (min(lows), max(highs)) if lows else (0.0, 0.0)


def ema(values: Sequence[float], period: int) -> Optional[float]:
    if len(values) < period:
        return None
    result = sum(values[:period]) / period
    multiplier = 2 / (period + 1)
    for value in values[period:]:
        result = (value - result) * multiplier + result
    return result


def trend(candles: Sequence[Dict[str, float]]) -> str:
    closes = [candle["close"] for candle in candles]
    fast, medium, slow = ema(closes, 20), ema(closes, 50), ema(closes, 200)
    if None in (fast, medium, slow):
        return "UNKNOWN"
    if fast > medium > slow:
        return "UP"
    if fast < medium < slow:
        return "DOWN"
    return "RANGE"


def proximity(price: float, thirty_day: Sequence[Dict[str, float]], ath: float, atl: float) -> Dict[str, Any]:
    high_30 = max(candle["high"] for candle in thirty_day)
    low_30 = min(candle["low"] for candle in thirty_day)
    return {
        "thirty_day_high": high_30, "thirty_day_low": low_30,
        "ath": ath, "atl": atl,
        "near_30_day_high": price >= high_30 * 0.97,
        "near_30_day_low": price <= low_30 * 1.03,
        "near_ath": ath > 0 and price >= ath * 0.97,
        "near_atl": atl > 0 and price <= atl * 1.03,
    }


def select_universe(client: BinanceV2Client) -> List[str]:
    symbols = set(client.perpetual_symbols())
    ticker_map = client.tickers()
    # Tickers are filtered against exchangeInfo so delisted/non-perpetual rows cannot enter.
    liquid = [item for symbol, item in ticker_map.items() if symbol in symbols and item["volume"] >= MIN_QUOTE_VOLUME]
    ranked_liquid = sorted(
        ((symbol, item) for symbol, item in ticker_map.items() if symbol in symbols and item["volume"] >= MIN_QUOTE_VOLUME),
        key=lambda pair: pair[1]["volume"],
        reverse=True,
    )
    ranked_decliners = sorted(
        (pair for pair in ranked_liquid if pair[1]["change"] < 0),
        key=lambda pair: pair[1]["change"],
    )
    volume_symbols = [symbol for symbol, _ in ranked_liquid[:TOP_VOLUME_COUNT]]
    decline_symbols = [symbol for symbol, _ in ranked_decliners[:TOP_DECLINER_COUNT]]
    return list(dict.fromkeys(volume_symbols + decline_symbols))[:MAX_CANDIDATE_COUNT]


def classify_checkpoints(checkpoints: Sequence[Checkpoint], support: float, resistance: float) -> Tuple[str, str]:
    if len(checkpoints) < CHECKPOINT_COUNT:
        return "WAIT", "incomplete observation window"
    closes = [point.close for point in checkpoints]
    for index in range(len(closes) - 3):
        if closes[index] > resistance and all(close > resistance for close in closes[index + 1:index + 4]):
            return "LONG", "confirmed break above higher-timeframe resistance"
        if closes[index] < support and all(close < support for close in closes[index + 1:index + 4]):
            return "SHORT", "confirmed break below higher-timeframe support"
    entered_resistance = max(point.high for point in checkpoints) >= resistance
    entered_support = min(point.low for point in checkpoints) <= support
    if entered_resistance and closes[-1] < resistance and sum(close < resistance for close in closes[-3:]) == 3:
        return "SHORT", "rejection from higher-timeframe resistance"
    if entered_support and closes[-1] > support and sum(close > support for close in closes[-3:]) == 3:
        return "LONG", "rejection from higher-timeframe support"
    return "WAIT", "unconfirmed touch or unstable follow-through"


def trade_plan(direction: str, entry: float, support: float, resistance: float, next_level: Optional[float] = None) -> Optional[TradePlan]:
    stop = support * 0.99 if direction == "LONG" and support < entry else entry * 0.985 if direction == "LONG" else resistance * 1.01 if resistance > entry else entry * 1.015
    risk = abs(entry - stop)
    risk_percent = risk / entry * 100 if entry else 100.0
    if not entry or risk_percent > MAX_STOP_DISTANCE_PCT:
        return None
    sign = 1 if direction == "LONG" else -1
    return TradePlan(entry, stop, entry + sign * risk * 2, entry + sign * risk * 3, next_level, risk_percent)


class BotV2:
    """Coordinates selection, context, observation, scoring, and output."""

    def __init__(self, client: BinanceV2Client, sleep: Callable[[float], None] = time.sleep):
        self.client = client
        self.sleep = sleep

    def prequalify(self, symbol: str) -> bool:
        """Keep only liquid candidates with current 15-minute activity."""
        candles = self.client.klines(symbol, "15m", 22)
        if len(candles) < 22:
            return False
        completed = candles[-2]
        average_volume = sum(candle["volume"] for candle in candles[-22:-2]) / 20
        return completed["close"] > 0 and completed["volume"] >= average_volume

    def observe(self, symbol: str, initial: Dict[str, Any]) -> List[Checkpoint]:
        checkpoints = []
        for checkpoint_number in range(CHECKPOINT_COUNT):
            candles = self.client.klines(symbol, "5m", 21)
            candle = candles[-2] if len(candles) > 1 else candles[-1]
            checkpoints.append(Checkpoint(candle["close"], candle["high"], candle["low"], candle["volume"], sum(item["volume"] for item in candles[-21:-1]) / 20, candle["time"]))
            if checkpoint_number + 1 < CHECKPOINT_COUNT:
                self.sleep(CHECKPOINT_INTERVAL_SECONDS)
        return checkpoints

    def analyze(self, symbol: str) -> Dict[str, Any]:
        ticker = self.client.tickers()[symbol]
        daily = self.client.klines(symbol, "1d", 250)
        four_hour = self.client.klines(symbol, "4h", 250)
        hourly = self.client.klines(symbol, "1h", 250)
        confirm = self.client.klines(symbol, "15m", 21)
        initial = {"price": ticker["price"], "trend_1d": trend(daily), "trend_4h": trend(four_hour), "trend_1h": trend(hourly)}
        initial["support"] = min(candle["low"] for candle in four_hour[-50:])
        initial["resistance"] = max(candle["high"] for candle in four_hour[-50:])
        atl, ath = self.client.all_time_extremes(symbol)
        initial["proximity"] = proximity(ticker["price"], daily[-30:], ath, atl)
        checkpoints = self.observe(symbol, initial)
        direction, checkpoint_reason = classify_checkpoints(checkpoints, initial["support"], initial["resistance"])
        btc_trend_1h = trend(self.client.klines("BTCUSDT", "1h", 250))
        btc_trend_4h = trend(self.client.klines("BTCUSDT", "4h", 250))
        oi = self.client.open_interest(symbol)
        oi_rising = len(oi) > 1 and oi[-1] > oi[0]
        momentum_up = checkpoints[-1].close > checkpoints[0].close
        volume_expansion = checkpoints[-1].volume > checkpoints[-1].volume_average
        flow = self.client.depth_imbalance(symbol)
        funding = self.client.funding(symbol)
        confirmation_volume = confirm[-1]["volume"] > sum(item["volume"] for item in confirm[:-1]) / 20
        score = self._score(direction, initial, btc_trend_1h, btc_trend_4h, checkpoints, oi_rising, momentum_up, volume_expansion or confirmation_volume, flow)
        crowded_long = funding > 0 and oi_rising and momentum_up and direction == "LONG" and ticker["price"] >= initial["resistance"] * 0.99
        crowded_short = funding < 0 and oi_rising and not momentum_up and direction == "SHORT" and ticker["price"] <= initial["support"] * 1.01
        macro_conflict = (direction == "LONG" and (btc_trend_1h == "DOWN" or btc_trend_4h == "DOWN")) or (direction == "SHORT" and (btc_trend_1h == "UP" or btc_trend_4h == "UP"))
        next_level = initial["resistance"] if direction == "LONG" else initial["support"] if direction == "SHORT" else None
        plan = trade_plan(direction, ticker["price"], initial["support"], initial["resistance"], next_level) if direction != "WAIT" else None
        hard_rejection = crowded_long or crowded_short or macro_conflict or plan is None
        signal = direction if direction != "WAIT" and score >= MIN_SCORE and not hard_rejection else "WAIT"
        return {"symbol": symbol, "signal": signal, "score": round(score, 2), "reason": checkpoint_reason, "btc_trend_1h": btc_trend_1h, "btc_trend_4h": btc_trend_4h, "funding": funding, "oi_rising": oi_rising, "volume_expansion": volume_expansion or confirmation_volume, "order_flow_imbalance": round(flow, 4), "proximity": initial["proximity"], "trade_plan": asdict(plan) if plan else None, "hard_rejection": hard_rejection}

    @staticmethod
    def _score(direction, initial, btc_trend_1h, btc_trend_4h, checkpoints, oi_rising, momentum_up, volume_expansion, flow):
        if direction == "WAIT":
            return 0.0
        long = direction == "LONG"
        trend_score = 25 if all((initial[key] == "UP") == long for key in ("trend_1d", "trend_4h", "trend_1h")) else 12.5
        stability = 25 if (momentum_up == long) else 0
        flow_score = 20 if (oi_rising and ((flow > 0) == long)) else 10 if oi_rising else 5
        volume_score = 15 if all(point.volume > point.volume_average for point in checkpoints[-3:]) else 7.5 if volume_expansion else 0
        beta_score = 15 if btc_trend_1h == btc_trend_4h == ("UP" if long else "DOWN") else 7.5 if btc_trend_1h == ("UP" if long else "DOWN") or btc_trend_4h == ("UP" if long else "DOWN") else 0
        return trend_score + stability + flow_score + volume_score + beta_score


def main() -> None:
    client = BinanceV2Client()
    bot = BotV2(client)
    symbols = select_universe(client)
    observation_symbols = []
    for symbol in symbols:
        try:
            if bot.prequalify(symbol):
                observation_symbols.append(symbol)
        except Exception as error:
            print(f"{symbol}: failed pre-observation filter ({error})")
    symbols = observation_symbols
    worker_count = max(1, int(os.getenv("V2_WORKERS", DEFAULT_WORKERS)))
    print(f"Bot V2 qualified {len(symbols)} of {MAX_CANDIDATE_COUNT} liquid candidates; running {min(worker_count, len(symbols))} in parallel")
    if not symbols:
        print("Bot V2 found no candidates with sufficient recent activity")
        return
    try:
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(bot.analyze, symbol): symbol for symbol in symbols}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    print(future.result())
                except Exception as error:
                    print(f"{symbol}: skipped ({error})")
    except KeyboardInterrupt:
        print("Bot V2 stopped by user")


if __name__ == "__main__":
    main()