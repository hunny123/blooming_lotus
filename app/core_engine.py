import os
import time
import json
import requests
from dotenv import load_dotenv
from datetime import datetime, timezone

from strategy.config import load_strategy_config


load_dotenv(".env.local")

STRATEGY_CONFIG = load_strategy_config()


# ============================================================
# BINANCE FUTURES SIGNAL ENGINE
# ============================================================
#
# SIGNAL ONLY
# NO ORDER EXECUTION
#
# Data comes directly from Binance public Futures API.
#
# Includes:
#   - Price
#   - Volume
#   - Open Interest
#   - Funding
#   - 5m / 15m structure
#   - 1H / 4H / 1D trend
#   - Support / Resistance
#   - 30-day high / low
#   - Reversal detection near lows/highs
#   - Signal confirmation
#   - Entry / SL / TP
#   - 2R / 3R targets
#   - Telegram alerts
#
# ============================================================


# ============================================================
# CONFIGURATION
# ============================================================

BASE_URL = "https://fapi.binance.com"

BINANCE_BASE_URLS = [
    os.getenv("BINANCE_BASE_URL", BASE_URL),
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
    "https://fapi4.binance.com"
]


# ------------------------------------------------------------
# Scanner
# ------------------------------------------------------------

TOP_N = STRATEGY_CONFIG.scan_top_count

LOW_CANDIDATE_N = STRATEGY_CONFIG.scan_last_count

ALL_TIME_LOW_PROXIMITY_PCT = 5.0

MIN_24H_VOLUME = STRATEGY_CONFIG.min_quote_volume

SCAN_INTERVAL = STRATEGY_CONFIG.scan_interval_seconds
# 5 minutes

REPEAT_SCAN_ENABLED = STRATEGY_CONFIG.repeat_scan_enabled

OBSERVATION_SCAN_ENABLED = STRATEGY_CONFIG.observation_scan_enabled

OBSERVATION_SCAN_INTERVAL_SECONDS = STRATEGY_CONFIG.observation_scan_interval_seconds


# ------------------------------------------------------------
# Confirmation
# ------------------------------------------------------------

CONFIRMATION_SCANS = STRATEGY_CONFIG.confirmation_scans

MIN_CONFIDENCE = STRATEGY_CONFIG.min_confidence

MIN_CONFIRMATION_CONFIDENCE = STRATEGY_CONFIG.min_confirmation_confidence


# ------------------------------------------------------------
# Timeframes
# ------------------------------------------------------------

FAST_TF = "5m"

CONFIRM_TF = "15m"

TREND_1H = "1h"

TREND_4H = "4h"

TREND_1D = "1d"


# ------------------------------------------------------------
# Candles
# ------------------------------------------------------------

KLINE_LIMIT = 250

VOLUME_LOOKBACK = 20

SWING_LOOKBACK = 5


# ------------------------------------------------------------
# Support / resistance
# ------------------------------------------------------------

SR_PROXIMITY_PCT = 1.5

EXTREME_ZONE_PCT = 3.0


# ------------------------------------------------------------
# Volume
# ------------------------------------------------------------

STRONG_VOLUME_PCT = 100

GOOD_VOLUME_PCT = 30


# ------------------------------------------------------------
# Risk management
# ------------------------------------------------------------

TP1_R = 2.0

TP2_R = 3.0

MAX_SL_DISTANCE_PCT = 5.0

HIGH_RETURN_MIN_PCT = 15.0

HIGH_RETURN_MAX_PCT = 20.0

TARGET_LEVERAGED_RETURN_PCT = 20.0

HIGHER_LEVERAGED_RETURN_PCT = 30.0

LEVERAGE_2X = 2.0

LEVERAGE_3X = 3.0

DEFAULT_LEVERAGE = "2x-3x"


# ------------------------------------------------------------
# Telegram
# ------------------------------------------------------------

TELEGRAM_ENABLED = True

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RUN_ONCE = STRATEGY_CONFIG.run_once

CONFIRMATION_WAIT = 600

HISTORY_FILE = os.path.join(
    os.getcwd(),
    "market_history.json"
)


# ============================================================
# SESSION
# ============================================================

session = requests.Session()

session.headers.update({

    "User-Agent":
        "Binance-Signal-Engine/5.0"

})


# ============================================================
# STATE
# ============================================================

pending_signals = {}

last_telegram_signal = {}

confirmation_symbols = None

confirmation_low_symbols = None


# ============================================================
# API
# ============================================================

def api_get(endpoint, params=None):

    last_error = None

    for base_url in BINANCE_BASE_URLS:

        for attempt in range(3):

            try:

                response = session.get(

                    base_url + endpoint,

                    params=params,

                    timeout=15

                )


                if response.status_code == 451:

                    print(
                        f"Binance host blocked (451): {base_url}. "
                        "Trying another host..."
                    )

                    break


                if response.status_code == 429:

                    retry_after = response.headers.get(
                        "Retry-After",
                        "5"
                    )

                    print(
                        f"Rate limited. "
                        f"Waiting {retry_after}s..."
                    )

                    time.sleep(
                        float(retry_after)
                    )

                    continue


                response.raise_for_status()

                try:

                    return response.json()

                except ValueError as error:

                    last_error = RuntimeError(
                        "Binance returned a non-JSON response from "
                        f"{base_url} (HTTP {response.status_code}). "
                        "The runner network may be blocked."
                    )

                    print(
                        f"Invalid Binance response from {base_url}: "
                        f"{error}. Trying another host..."
                    )

                    break


            except Exception as error:

                last_error = error

                print(
                    f"API error: {error} "
                    f"| {base_url} retry {attempt + 1}/3"
                )

                if attempt == 2:

                    break

                time.sleep(2)


    if last_error:

        raise last_error

    raise RuntimeError(
        "Binance API request failed"
    )


# ============================================================
# TELEGRAM
# ============================================================

def send_telegram(message):

    if not TELEGRAM_ENABLED:

        return False


    if not TELEGRAM_BOT_TOKEN:

        print(
            "Telegram enabled but "
            "TELEGRAM_BOT_TOKEN is missing."
        )

        return False


    if not TELEGRAM_CHAT_ID:

        print(
            "Telegram enabled but "
            "TELEGRAM_CHAT_ID is missing."
        )

        return False


    url = (
        "https://api.telegram.org/bot"
        + TELEGRAM_BOT_TOKEN
        + "/sendMessage"
    )


    payload = {

        "chat_id":
            TELEGRAM_CHAT_ID,

        "text":
            message,

        "parse_mode":
            "HTML",

        "disable_web_page_preview":
            True

    }


    try:

        response = session.post(

            url,

            json=payload,

            timeout=15

        )


        response.raise_for_status()

        data = response.json()


        if not data.get("ok"):

            print(
                "Telegram error:",
                data
            )

            return False


        return True


    except Exception as e:

        print(
            "Telegram send error:",
            e
        )

        return False


# ============================================================
# HELPERS
# ============================================================

def pct_change(current, previous):

    if previous == 0:

        return 0.0

    return (

        (
            current - previous
        )
        /
        previous

    ) * 100


def format_price(price):

    if price is None:

        return "N/A"

    if price >= 1000:

        return f"{price:,.2f}"

    if price >= 1:

        return f"{price:,.4f}"

    if price >= 0.01:

        return f"{price:,.6f}"

    return f"{price:,.8f}"


def escape_html(text):

    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


# ============================================================
# SYMBOLS
# ============================================================

def get_usdt_perpetuals():

    data = api_get(
        "/fapi/v1/exchangeInfo"
    )

    result = []

    for item in data["symbols"]:

        if item["status"] != "TRADING":

            continue

        if item["contractType"] != "PERPETUAL":

            continue

        if item["quoteAsset"] != "USDT":

            continue

        result.append(
            item["symbol"]
        )

    return result


# ============================================================
# 24H TICKERS
# ============================================================

def get_24h_tickers():

    data = api_get(
        "/fapi/v1/ticker/24hr"
    )

    result = {}

    for item in data:

        result[item["symbol"]] = {

            "price":
                float(item["lastPrice"]),

            "volume":
                float(item["quoteVolume"]),

            "change":
                float(item["priceChangePercent"]),

            "high":
                float(item["highPrice"]),

            "low":
                float(item["lowPrice"])

        }

    return result


def get_all_time_low(symbol):

    lowest = None
    start_time = 0

    while True:

        candles = api_get(
            "/fapi/v1/klines",
            {
                "symbol": symbol,
                "interval": "1d",
                "limit": 1500,
                "startTime": start_time
            }
        )

        if not candles:

            break

        batch_low = min(
            float(candle[3])
            for candle in candles
        )

        lowest = (
            batch_low
            if lowest is None
            else min(lowest, batch_low)
        )

        if len(candles) < 1500:

            break

        start_time = int(candles[-1][0]) + 1

    return lowest


# ============================================================
# FUNDING
# ============================================================

def get_current_funding():

    data = api_get(
        "/fapi/v1/premiumIndex"
    )

    result = {}

    for item in data:

        result[item["symbol"]] = {

            "funding":
                float(item["lastFundingRate"]),

            "mark_price":
                float(item["markPrice"])

        }

    return result


def get_funding_history(
    symbol,
    limit=10
):

    data = api_get(

        "/fapi/v1/fundingRate",

        {
            "symbol":
                symbol,

            "limit":
                limit
        }

    )

    return [

        float(x["fundingRate"])

        for x in data

    ]


# ============================================================
# OPEN INTEREST
# ============================================================

def get_oi_history(
    symbol,
    period="5m",
    limit=20
):

    data = api_get(

        "/futures/data/openInterestHist",

        {
            "symbol":
                symbol,

            "period":
                period,

            "limit":
                limit

        }

    )

    return [

        {

            "time":
                int(x["timestamp"]),

            "oi":
                float(
                    x["sumOpenInterest"]
                ),

            "oi_value":
                float(
                    x["sumOpenInterestValue"]
                )

        }

        for x in data

    ]


# ============================================================
# KLINES
# ============================================================

def get_klines(
    symbol,
    interval,
    limit=250
):

    data = api_get(

        "/fapi/v1/klines",

        {
            "symbol":
                symbol,

            "interval":
                interval,

            "limit":
                limit

        }

    )

    return [

        {

            "time":
                int(x[0]),

            "open":
                float(x[1]),

            "high":
                float(x[2]),

            "low":
                float(x[3]),

            "close":
                float(x[4]),

            "volume":
                float(x[5]),

            "quote_volume":
                float(x[7])

        }

        for x in data

    ]


# ============================================================
# EMA
# ============================================================

def ema(values, period):

    if len(values) < period:

        return None

    multiplier = 2 / (period + 1)

    result = sum(
        values[:period]
    ) / period


    for value in values[period:]:

        result = (

            (
                value - result
            )
            *
            multiplier

        ) + result


    return result


# ============================================================
# TREND
# ============================================================

def analyze_trend(candles):

    if len(candles) < 200:

        return "UNKNOWN"


    closes = [

        x["close"]

        for x in candles

    ]


    price = closes[-1]


    ema20 = ema(
        closes,
        20
    )

    ema50 = ema(
        closes,
        50
    )

    ema200 = ema(
        closes,
        200
    )


    bullish = 0

    bearish = 0


    if price > ema20:

        bullish += 1

    else:

        bearish += 1


    if price > ema50:

        bullish += 1

    else:

        bearish += 1


    if price > ema200:

        bullish += 2

    else:

        bearish += 2


    if (
        ema20 > ema50
        and
        ema50 > ema200
    ):

        bullish += 2


    if (
        ema20 < ema50
        and
        ema50 < ema200
    ):

        bearish += 2


    if bullish >= 6:

        return "BULLISH"

    if bullish >= 4:

        return "LEAN BULLISH"

    if bearish >= 6:

        return "BEARISH"

    if bearish >= 4:

        return "LEAN BEARISH"

    return "NEUTRAL"


# ============================================================
# LOWER TIMEFRAME
# ============================================================

def lower_structure(candles):

    if len(candles) < 30:

        return "UNKNOWN"


    closes = [

        x["close"]

        for x in candles

    ]


    price = closes[-1]


    ema9 = ema(
        closes,
        9
    )

    ema20 = ema(
        closes,
        20
    )


    score = 0


    if price > ema9:

        score += 1

    else:

        score -= 1


    if price > ema20:

        score += 1

    else:

        score -= 1


    if ema9 > ema20:

        score += 2

    else:

        score -= 2


    recent = candles[-5:]


    green = sum(

        1

        for x in recent

        if x["close"] > x["open"]

    )


    red = sum(

        1

        for x in recent

        if x["close"] < x["open"]

    )


    if green > red:

        score += 1

    elif red > green:

        score -= 1


    if score >= 2:

        return "BULLISH"

    if score <= -2:

        return "BEARISH"

    return "NEUTRAL"


# ============================================================
# MOMENTUM
# ============================================================

def momentum(candles, bars=3):

    if len(candles) <= bars:

        return 0


    return pct_change(

        candles[-1]["close"],

        candles[-1 - bars]["close"]

    )


# ============================================================
# VOLUME
# ============================================================

def volume_strength(candles):

    if len(candles) < (
        VOLUME_LOOKBACK + 1
    ):

        return 0


    current = candles[-1][
        "quote_volume"
    ]


    previous = candles[
        -(VOLUME_LOOKBACK + 1):-1
    ]


    average = sum(

        x["quote_volume"]

        for x in previous

    ) / len(previous)


    if average == 0:

        return 0


    return pct_change(
        current,
        average
    )


# ============================================================
# OI
# ============================================================

def analyze_oi(history):

    if len(history) < 2:

        return 0, "UNKNOWN"


    current = history[-1]["oi"]


    previous_index = max(
        0,
        len(history) - 4
    )


    previous = history[
        previous_index
    ]["oi"]


    change = pct_change(
        current,
        previous
    )


    if change > 0.5:

        direction = "RISING"

    elif change < -0.5:

        direction = "FALLING"

    else:

        direction = "FLAT"


    return change, direction


# ============================================================
# SWING LEVELS
# ============================================================

def swing_levels(
    candles,
    lookback=5
):

    supports = []

    resistances = []


    for i in range(

        lookback,

        len(candles) - lookback

    ):

        current = candles[i]


        left = candles[
            i - lookback:i
        ]


        right = candles[
            i + 1:
            i + 1 + lookback
        ]


        if current["low"] <= min(

            x["low"]

            for x in left

        ) and current["low"] <= min(

            x["low"]

            for x in right

        ):

            supports.append(
                current["low"]
            )


        if current["high"] >= max(

            x["high"]

            for x in left

        ) and current["high"] >= max(

            x["high"]

            for x in right

        ):

            resistances.append(
                current["high"]
            )


    return supports, resistances


# ============================================================
# NEAREST LEVELS
# ============================================================

def nearest_levels(
    price,
    supports,
    resistances
):

    below = [

        x for x in supports

        if x < price

    ]


    above = [

        x for x in resistances

        if x > price

    ]


    support = (
        max(below)
        if below
        else None
    )


    resistance = (
        min(above)
        if above
        else None
    )


    return support, resistance


# ============================================================
# 30 DAY HIGH / LOW
# ============================================================

def thirty_day_levels(
    daily_candles
):

    candles = daily_candles[-30:]


    if not candles:

        return None, None


    high = max(
        x["high"]
        for x in candles
    )


    low = min(
        x["low"]
        for x in candles
    )


    return high, low


# ============================================================
# LOCATION
# ============================================================

def location_info(
    price,
    support,
    resistance,
    month_high,
    month_low,
    all_time_low=None
):

    result = {

        "near_support":
            False,

        "near_resistance":
            False,

        "near_month_low":
            False,

        "near_month_high":
            False,

        "support_distance":
            None,

        "resistance_distance":
            None,

        "month_low_distance":
            None,

        "month_high_distance":
            None,

        "all_time_low_distance":
            None,

        "near_all_time_low":
            False

    }


    if support:

        distance = (
            (price - support)
            / price
        ) * 100


        result[
            "support_distance"
        ] = distance


        if (
            0 <= distance
            <= SR_PROXIMITY_PCT
        ):

            result[
                "near_support"
            ] = True


    if resistance:

        distance = (
            (resistance - price)
            / price
        ) * 100


        result[
            "resistance_distance"
        ] = distance


        if (
            0 <= distance
            <= SR_PROXIMITY_PCT
        ):

            result[
                "near_resistance"
            ] = True


    if month_low:

        distance = (
            (price - month_low)
            / price
        ) * 100


        result[
            "month_low_distance"
        ] = distance


        if (
            0 <= distance
            <= EXTREME_ZONE_PCT
        ):

            result[
                "near_month_low"
            ] = True


    if all_time_low:

        distance = (
            (price - all_time_low)
            / price
        ) * 100

        result[
            "all_time_low_distance"
        ] = distance

        if (
            0 <= distance
            <= ALL_TIME_LOW_PROXIMITY_PCT
        ):

            result[
                "near_all_time_low"
            ] = True


    if month_high:

        distance = (
            (month_high - price)
            / price
        ) * 100


        result[
            "month_high_distance"
        ] = distance


        if (
            0 <= distance
            <= EXTREME_ZONE_PCT
        ):

            result[
                "near_month_high"
            ] = True


    return result


# ============================================================
# SIGNAL ENGINE
# ============================================================

def generate_signal(data):

    long_score = 0

    short_score = 0

    long_reasons = []

    short_reasons = []

    warnings = []


    price = data["price"]

    mom = data["momentum"]

    volume = data["volume_strength"]

    oi = data["oi_change"]

    funding = data["funding"]

    fast = data["fast_structure"]

    confirm = data["confirm_structure"]

    trend1h = data["trend_1h"]

    trend4h = data["trend_4h"]

    trend1d = data["trend_1d"]

    loc = data["location"]

    long_crowded = (
        funding > 0.08
        and oi > 1.0
        and mom > 0.50
        and (
            "BULLISH" in trend1h
            or "BULLISH" in trend4h
            or "BULLISH" in trend1d
        )
    )

    short_crowded = (
        funding < -0.08
        and oi > 1.0
        and mom < -0.50
        and (
            "BEARISH" in trend1h
            or "BEARISH" in trend4h
            or "BEARISH" in trend1d
        )
    )

    if long_crowded:
        warnings.append(
            "long crowding risk: positive funding, rising OI, and rising price"
        )

    if short_crowded:
        warnings.append(
            "short crowding risk: negative funding, rising OI, and falling price"
        )


    # ========================================================
    # HIGHER TIMEFRAME
    # ========================================================

    bullish_htf = sum(

        1

        for x in [
            trend1h,
            trend4h,
            trend1d
        ]

        if "BULLISH" in x

    )


    bearish_htf = sum(

        1

        for x in [
            trend1h,
            trend4h,
            trend1d
        ]

        if "BEARISH" in x

    )


    if bullish_htf >= 2:

        long_score += 12

        long_reasons.append(
            "1H/4H/1D trend supports LONG"
        )


    if bearish_htf >= 2:

        short_score += 12

        short_reasons.append(
            "1H/4H/1D trend supports SHORT"
        )


    # ========================================================
    # LOWER TIMEFRAME
    # ========================================================

    if fast == "BULLISH":

        long_score += 10

        long_reasons.append(
            "5m structure is bullish"
        )


    elif fast == "BEARISH":

        short_score += 10

        short_reasons.append(
            "5m structure is bearish"
        )


    if confirm == "BULLISH":

        long_score += 10

        long_reasons.append(
            "15m structure confirms buying"
        )


    elif confirm == "BEARISH":

        short_score += 10

        short_reasons.append(
            "15m structure confirms selling"
        )


    # ========================================================
    # MOMENTUM
    # ========================================================

    if mom > 0.30:

        long_score += 8

        long_reasons.append(
            "short-term momentum is positive"
        )


    elif mom < -0.30:

        short_score += 8

        short_reasons.append(
            "short-term momentum is negative"
        )


    # ========================================================
    # OI
    # ========================================================

    if oi > 0.5:

        if mom > 0:

            long_score += 14

            long_reasons.append(
                "OI rising while price rises"
            )


        elif mom < 0:

            short_score += 14

            short_reasons.append(
                "OI rising while price falls"
            )


    elif oi < -0.5:

        if mom > 0:

            long_score += 4

            long_reasons.append(
                "OI falling during price recovery"
            )


        elif mom < 0:

            short_score += 4

            short_reasons.append(
                "OI falling during price decline"
            )


    # ========================================================
    # VOLUME
    # ========================================================

    if volume >= STRONG_VOLUME_PCT:

        if mom > 0:

            long_score += 14

            long_reasons.append(
                "strong volume expansion with buying"
            )


        elif mom < 0:

            short_score += 14

            short_reasons.append(
                "strong volume expansion with selling"
            )


    elif volume >= GOOD_VOLUME_PCT:

        if mom > 0:

            long_score += 7

            long_reasons.append(
                "volume is above average"
            )


        elif mom < 0:

            short_score += 7

            short_reasons.append(
                "volume is above average"
            )


    # ========================================================
    # FUNDING
    # ========================================================

    if funding < -0.05:

        long_score += 8

        long_reasons.append(
            "very negative funding indicates short crowding"
        )


    elif funding > 0.05:

        short_score += 8

        short_reasons.append(
            "very positive funding indicates long crowding"
        )


    elif funding < 0:

        long_score += 3

        long_reasons.append(
            "funding is negative"
        )


    elif funding > 0:

        short_score += 3

        short_reasons.append(
            "funding is positive"
        )


    # ========================================================
    # SUPPORT
    # ========================================================

    if loc["near_support"]:

        if (
            fast == "BULLISH"
            and
            mom > 0
        ):

            long_score += 16

            long_reasons.append(
                "price is bouncing from support"
            )


    # ========================================================
    # RESISTANCE
    # ========================================================

    if loc["near_resistance"]:

        if (
            fast == "BEARISH"
            and
            mom < 0
        ):

            short_score += 16

            short_reasons.append(
                "price is rejecting resistance"
            )


    # ========================================================
    # LOW REVERSAL
    # ========================================================

    near_low = (

        loc["near_month_low"]

    )


    if near_low:

        reversal_confirmation = (

            fast == "BULLISH"

            and

            confirm == "BULLISH"

            and

            mom > 0

            and

            volume >= GOOD_VOLUME_PCT

        )


        if reversal_confirmation:

            long_score += 24

            long_reasons.append(
                "price is near 30D low and buying reversal is confirmed"
            )


            if oi > 0.5:

                long_score += 5

                long_reasons.append(
                    "OI increasing during low-area buying"
                )


            if funding < 0:

                long_score += 5

                long_reasons.append(
                    "negative funding supports reversal"
                )


            if bearish_htf >= 2:

                warnings.append(
                    "counter-trend: higher timeframes remain bearish"
                )


    # ========================================================
    # HIGH REVERSAL
    # ========================================================

    near_high = (

        loc["near_month_high"]

    )


    if near_high:

        reversal_confirmation = (

            fast == "BEARISH"

            and

            confirm == "BEARISH"

            and

            mom < 0

            and

            volume >= GOOD_VOLUME_PCT

        )


        if reversal_confirmation:

            short_score += 24

            short_reasons.append(
                "price is near 30D high and selling reversal is confirmed"
            )


            if oi > 0.5:

                short_score += 5

                short_reasons.append(
                    "OI increasing during high-area selling"
                )


            if funding > 0:

                short_score += 5

                short_reasons.append(
                    "positive funding supports reversal"
                )


            if bullish_htf >= 2:

                warnings.append(
                    "counter-trend: higher timeframes remain bullish"
                )


    # ========================================================
    # CONFLICT
    # ========================================================

    total = (
        long_score
        +
        short_score
    )


    if total <= 0:

        return {

            "signal":
                "WAIT",

            "confidence":
                0,

            "type":
                "NO SETUP",

            "long_score":
                0,

            "short_score":
                0,

            "reasons":
                [
                    "not enough evidence"
                ],

            "warnings":
                warnings

        }


    difference = abs(
        long_score
        -
        short_score
    )


    if difference < 12:

        return {

            "signal":
                "WAIT",

            "confidence":
                round(
                    max(
                        long_score,
                        short_score
                    )
                    /
                    total
                    * 100,
                    1
                ),

            "type":
                "CONFLICTED",

            "long_score":
                round(
                    long_score,
                    1
                ),

            "short_score":
                round(
                    short_score,
                    1
                ),

            "reasons":
                [
                    "long and short evidence are too balanced"
                ],

            "warnings":
                warnings

        }


    # ========================================================
    # LONG
    # ========================================================

    if long_score > short_score:

        if long_crowded and loc["near_resistance"]:
            warnings.append(
                "LONG rejected: crowded longs are near resistance"
            )

            return {
                "signal": "WAIT",
                "confidence": round(
                    max(long_score, short_score) / total * 100,
                    1
                ),
                "type": "CROWDED LONG",
                "long_score": round(long_score, 1),
                "short_score": round(short_score, 1),
                "reasons": [
                    "long setup is vulnerable to a crowded-position reversal"
                ],
                "warnings": warnings
            }

        confidence = (
            long_score
            /
            total
        ) * 100


        if near_low:

            signal_type = (
                "REVERSAL LONG"
            )


        elif loc[
            "near_support"
        ]:

            signal_type = (
                "SUPPORT BOUNCE LONG"
            )


        else:

            signal_type = (
                "TREND LONG"
            )


        if bearish_htf >= 2:

            warnings.append(
                "higher-timeframe trend is bearish"
            )


        return {

            "signal":
                "LONG",

            "confidence":
                round(
                    confidence,
                    1
                ),

            "type":
                signal_type,

            "long_score":
                round(
                    long_score,
                    1
                ),

            "short_score":
                round(
                    short_score,
                    1
                ),

            "reasons":
                long_reasons,

            "warnings":
                warnings

        }


    # ========================================================
    # SHORT
    # ========================================================

    confidence = (
        short_score
        /
        total
    ) * 100

    if short_crowded and loc["near_support"]:
        warnings.append(
            "SHORT rejected: crowded shorts are near support"
        )

        return {
            "signal": "WAIT",
            "confidence": round(confidence, 1),
            "type": "CROWDED SHORT",
            "long_score": round(long_score, 1),
            "short_score": round(short_score, 1),
            "reasons": [
                "short setup is vulnerable to a crowded-position reversal"
            ],
            "warnings": warnings
        }


    if near_high:

        signal_type = (
            "REVERSAL SHORT"
        )


    elif loc[
        "near_resistance"
    ]:

        signal_type = (
            "RESISTANCE REJECTION SHORT"
        )


    else:

        signal_type = (
            "TREND SHORT"
        )


    if bullish_htf >= 2:

        warnings.append(
            "higher-timeframe trend is bullish"
        )


    return {

        "signal":
            "SHORT",

        "confidence":
            round(
                confidence,
                1
            ),

        "type":
            signal_type,

        "long_score":
            round(
                long_score,
                1
            ),

        "short_score":
            round(
                short_score,
                1
            ),

        "reasons":
            short_reasons,

        "warnings":
            warnings

    }


# ============================================================
# TRADE PLAN
# ============================================================

def calculate_trade_plan(result):

    price = result["price"]

    support = result["support"]

    resistance = result["resistance"]


    # ========================================================
    # LONG
    # ========================================================

    if result["signal"] == "LONG":

        entry = price


        # Prefer support as SL.
        # Add a small buffer below it.

        if support:

            sl = support * 0.997


        else:

            sl = price * 0.985


        risk = entry - sl


        if risk <= 0:

            return None


        risk_pct = (
            risk
            /
            entry
        ) * 100


        if risk_pct > MAX_SL_DISTANCE_PCT:

            # If structural SL is too wide,
            # don't manufacture a bad setup.

            return None


        tp1 = (
            entry
            +
            risk * TP1_R
        )


        tp2 = (
            entry
            +
            risk * TP2_R
        )


        # Optional TP3:
        # next resistance if it is beyond TP2.

        tp3 = None


        if resistance:

            if resistance > tp2:

                tp3 = resistance

        projected_target = tp3 or tp2

        projected_return_pct = (
            (projected_target - entry)
            /
            entry
        ) * 100

        return_at_2x_pct = projected_return_pct * LEVERAGE_2X

        return_at_3x_pct = projected_return_pct * LEVERAGE_3X


        return {

            "entry":
                entry,

            "sl":
                sl,

            "risk":
                risk,

            "risk_pct":
                risk_pct,

            "tp1":
                tp1,

            "tp2":
                tp2,

            "tp3":
                tp3,

            "projected_return_pct":
                projected_return_pct,

            "return_at_2x_pct":
                return_at_2x_pct,

            "return_at_3x_pct":
                return_at_3x_pct,

            "twenty_percent_setup":
                return_at_2x_pct >= TARGET_LEVERAGED_RETURN_PCT,

            "twenty_percent_leverage":
                "2x-3x"
                if return_at_2x_pct >= TARGET_LEVERAGED_RETURN_PCT
                else "3x"
                if return_at_3x_pct >= TARGET_LEVERAGED_RETURN_PCT
                else None,

            "higher_profit_setup":
                return_at_3x_pct >= HIGHER_LEVERAGED_RETURN_PCT,

            "direction":
                "LONG"

        }


    # ========================================================
    # SHORT
    # ========================================================

    if result["signal"] == "SHORT":

        entry = price


        if resistance:

            sl = resistance * 1.003


        else:

            sl = price * 1.015


        risk = sl - entry


        if risk <= 0:

            return None


        risk_pct = (
            risk
            /
            entry
        ) * 100


        if risk_pct > MAX_SL_DISTANCE_PCT:

            return None


        tp1 = (
            entry
            -
            risk * TP1_R
        )


        tp2 = (
            entry
            -
            risk * TP2_R
        )


        tp3 = None


        if support:

            if support < tp2:

                tp3 = support

        projected_target = tp3 or tp2

        projected_return_pct = (
            (entry - projected_target)
            /
            entry
        ) * 100

        return_at_2x_pct = projected_return_pct * LEVERAGE_2X

        return_at_3x_pct = projected_return_pct * LEVERAGE_3X


        return {

            "entry":
                entry,

            "sl":
                sl,

            "risk":
                risk,

            "risk_pct":
                risk_pct,

            "tp1":
                tp1,

            "tp2":
                tp2,

            "tp3":
                tp3,

            "projected_return_pct":
                projected_return_pct,

            "return_at_2x_pct":
                return_at_2x_pct,

            "return_at_3x_pct":
                return_at_3x_pct,

            "twenty_percent_setup":
                return_at_2x_pct >= TARGET_LEVERAGED_RETURN_PCT,

            "twenty_percent_leverage":
                "2x-3x"
                if return_at_2x_pct >= TARGET_LEVERAGED_RETURN_PCT
                else "3x"
                if return_at_3x_pct >= TARGET_LEVERAGED_RETURN_PCT
                else None,

            "higher_profit_setup":
                return_at_3x_pct >= HIGHER_LEVERAGED_RETURN_PCT,

            "direction":
                "SHORT"

        }


    return None


# ============================================================
# CONFIRMATION
# ============================================================

def confirm_signal(result):

    symbol = result["symbol"]

    signal = result["signal"]

    confidence = result["confidence"]


    if signal not in [
        "LONG",
        "SHORT"
    ]:

        pending_signals.pop(
            symbol,
            None
        )

        return None


    if confidence < (
        MIN_CONFIRMATION_CONFIDENCE
    ):

        pending_signals.pop(
            symbol,
            None
        )

        return None


    previous = pending_signals.get(
        symbol
    )


    # --------------------------------------------------------
    # First scan
    # --------------------------------------------------------

    if previous is None:

        pending_signals[symbol] = {

            "signal":
                signal,

            "count":
                1,

            "first_seen":
                time.time()

        }

        return None


    # --------------------------------------------------------
    # Same signal
    # --------------------------------------------------------

    if previous["signal"] == signal:

        previous["count"] += 1


        if previous["count"] >= (
            CONFIRMATION_SCANS
        ):

            result[
                "confirmed"
            ] = True


            result[
                "confirmation_count"
            ] = previous["count"]


            pending_signals.pop(
                symbol,
                None
            )


            return result


        return None


    # --------------------------------------------------------
    # Direction changed
    # --------------------------------------------------------

    pending_signals[symbol] = {

        "signal":
            signal,

        "count":
            1,

        "first_seen":
            time.time()

    }


    return None


# ============================================================
# TELEGRAM FORMAT
# ============================================================

def telegram_message(r):

    icon = (
        "🟢"
        if r["signal"] == "LONG"
        else
        "🔴"
    )

    crowding = None
    for warning in r.get("warnings", []):
        lower_warning = warning.lower()
        if "long crowding risk" in lower_warning:
            crowding = "OVERCROWDED LONG"
            break
        if "short crowding risk" in lower_warning:
            crowding = "OVERCROWDED SHORT"
            break

    plan = r.get(
        "trade_plan"
    )


    if plan is None:

        return None


    lines = []

    header = f"{icon} <b>CONFIRMED {r['signal']}</b>"
    if crowding:
        header = f"{header} — <b>{crowding}</b>"

    lines.append(header)


    lines.append("")

    lines.append(
        f"<b>{escape_html(r['symbol'])}</b>"
    )


    lines.append(
        f"{escape_html(r['type'])}"
    )


    lines.append(
        f"Confidence: "
        f"<b>{r['confidence']:.1f}%</b>"
    )


    lines.append(
        f"Confirmation: "
        f"{r.get('confirmation_count', 0)}/"
        f"{CONFIRMATION_SCANS}"
    )

    if plan.get("twenty_percent_leverage"):

        lines.append(
            "🚀 <b>20% RETURN SETUP: "
            f"{plan['twenty_percent_leverage']} LEVERAGE"
            " (PROJECTED)</b>"
        )

    if plan.get("higher_profit_setup"):

        lines.append(
            "🔥 <b>HIGHER PROFIT SETUP: "
            "30%+ AT 3X (PROJECTED)</b>"
        )


    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "📊 <b>MARKET</b>"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )


    lines.append(
        f"Price: "
        f"${format_price(r['price'])}"
    )


    lines.append(
        f"1H: {r['trend_1h']}"
    )

    lines.append(
        f"4H: {r['trend_4h']}"
    )

    lines.append(
        f"1D: {r['trend_1d']}"
    )


    lines.append(
        f"5m: {r['fast_structure']}"
    )

    lines.append(
        f"15m: {r['confirm_structure']}"
    )


    lines.append("")

    lines.append(
        f"OI: {r['oi_change']:+.2f}% "
        f"({r['oi_direction']})"
    )


    lines.append(
        f"Volume: "
        f"{r['volume_strength']:+.1f}%"
    )


    lines.append(
        f"Funding: "
        f"{r['funding']:+.4f}%"
    )


    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "📍 <b>LEVELS</b>"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )


    lines.append(
        f"Support: "
        f"${format_price(r['support'])}"
    )


    lines.append(
        f"Resistance: "
        f"${format_price(r['resistance'])}"
    )


    lines.append(
        f"30D High: "
        f"${format_price(r['month_high'])}"
    )


    lines.append(
        f"30D Low: "
        f"${format_price(r['month_low'])}"
    )


    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "🎯 <b>TRADE PLAN</b>"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )


    lines.append(
        f"Entry: "
        f"<b>${format_price(plan['entry'])}</b>"
    )


    lines.append(
        f"SL: "
        f"<b>${format_price(plan['sl'])}</b> "
        f"({plan['risk_pct']:.2f}% risk)"
    )


    lines.append(
        f"TP1: "
        f"<b>${format_price(plan['tp1'])}</b> "
        f"(+2R)"
    )


    lines.append(
        f"TP2: "
        f"<b>${format_price(plan['tp2'])}</b> "
        f"(+3R)"
    )

    lines.append(
        f"Projected return: "
        f"<b>{plan['projected_return_pct']:+.2f}% price move</b>"
    )

    lines.append(
        f"At 2x: <b>{plan['return_at_2x_pct']:+.2f}%</b> | "
        f"At 3x: <b>{plan['return_at_3x_pct']:+.2f}%</b>"
    )

    lines.append(
        f"Projected return: "
        f"<b>{plan['projected_return_pct']:+.2f}%</b>"
    )

    lines.append(
        f"At 2x: <b>{plan['return_at_2x_pct']:+.2f}%</b> | "
        f"At 3x: <b>{plan['return_at_3x_pct']:+.2f}%</b>"
    )


    if plan["tp3"]:

        lines.append(
            f"TP3: "
            f"<b>${format_price(plan['tp3'])}</b> "
            f"(major level)"
        )


    lines.append(
        f"Suggested leverage: "
        f"<b>{DEFAULT_LEVERAGE}</b>"
    )


    lines.append("")

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )

    lines.append(
        "💡 <b>WHY</b>"
    )

    lines.append(
        "━━━━━━━━━━━━━━━━"
    )


    for reason in r["reasons"][:8]:

        lines.append(
            f"✓ {escape_html(reason)}"
        )


    if r["warnings"]:

        lines.append("")

        lines.append(
            "⚠️ <b>WARNING</b>"
        )


        for warning in r["warnings"]:

            lines.append(
                f"⚠ {escape_html(warning)}"
            )


    lines.append("")

    lines.append(
        "Signal only — "
        "no Binance order execution."
    )


    return "\n".join(lines)


def telegram_pending_message(r):

    icon = (
        "🟢"
        if r["signal"] == "LONG"
        else
        "🔴"
    )

    lines = [
        f"{icon} <b>FIRST ANALYSIS {r['signal']}</b>",
        "",
        f"<b>{escape_html(r['symbol'])}</b>",
        escape_html(r["type"]),
        f"Confidence: <b>{r['confidence']:.1f}%</b>",
        f"Confirmation: 1/{CONFIRMATION_SCANS}",
        "",
        f"Price: ${format_price(r['price'])}",
        f"1H: {r['trend_1h']} | 4H: {r['trend_4h']} | 1D: {r['trend_1d']}",
        f"5m: {r['fast_structure']} | 15m: {r['confirm_structure']}",
        f"OI: {r['oi_change']:+.2f}% ({r['oi_direction']})",
        f"Volume: {r['volume_strength']:+.1f}%",
        f"Funding: {r['funding']:+.4f}%",
        "",
        "Waiting 10 minutes for second confirmation.",
        "Signal only - no Binance order execution."
    ]

    for reason in r["reasons"][:8]:

        lines.insert(
            -2,
            f"✓ {escape_html(reason)}"
        )

    return "\n".join(lines)


def send_pending_telegram(result):

    message = telegram_pending_message(result)

    send_telegram(message)


def low_to_high_reversal_message(result):

    lines = [
        "🟡 <b>LOW TO HIGH REVERSAL CAN COME</b>",
        "",
        f"<b>{escape_html(result['symbol'])}</b>",
        f"Price: ${format_price(result['price'])}",
        f"All-time low: ${format_price(result['all_time_low'])}",
        f"Distance from all-time low: "
        f"{result['location']['all_time_low_distance']:.2f}%",
        "",
        f"5m: {result['fast_structure']} | "
        f"15m: {result['confirm_structure']}",
        f"Momentum: {result['momentum']:+.2f}%",
        f"Volume: {result['volume_strength']:+.1f}%",
        f"OI: {result['oi_change']:+.2f}% ({result['oi_direction']})",
        "",
        "Early reversal watch only - not a confirmed trade signal.",
        "Signal only - no Binance order execution."
    ]

    return "\n".join(lines)


def send_low_to_high_reversal_telegram(result):

    symbol = result["symbol"]
    key = (symbol, "LOW_TO_HIGH_REVERSAL")

    if key in last_telegram_signal:

        return

    message = low_to_high_reversal_message(result)

    if send_telegram(message):

        last_telegram_signal[key] = True

        print(
            f"Telegram sent: {symbol} LOW TO HIGH REVERSAL"
        )


def save_market_history(results):

    try:

        with open(
            HISTORY_FILE,
            "r",
            encoding="utf-8"
        ) as file:
            history = json.load(file)

    except (
        FileNotFoundError,
        json.JSONDecodeError
    ):

        history = {}


    timestamp = time.time()

    for result in results:

        symbol = result["symbol"]

        history.setdefault(symbol, []).append({
            "timestamp": timestamp,
            "price": result["price"],
            "signal": result["signal"],
            "confidence": result["confidence"],
            "trend_1h": result["trend_1h"],
            "trend_4h": result["trend_4h"],
            "trend_1d": result["trend_1d"],
            "fast_structure": result["fast_structure"],
            "confirm_structure": result["confirm_structure"],
            "oi_change": result["oi_change"],
            "volume_strength": result["volume_strength"],
            "funding": result["funding"]
        })

        history[symbol] = history[symbol][-100:]

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            history,
            file,
            indent=2
        )


def clear_market_history():

    with open(
        HISTORY_FILE,
        "w",
        encoding="utf-8"
    ) as file:

        json.dump({}, file, indent=2)


# ============================================================
# SEND CONFIRMED TELEGRAM
# ============================================================

def send_confirmed_telegram(result):

    symbol = result["symbol"]

    signal = result["signal"]

    confidence = result["confidence"]


    # --------------------------------------------------------
    # Duplicate protection
    # --------------------------------------------------------

    key = (
        symbol,
        signal
    )


    previous = last_telegram_signal.get(
        symbol
    )


    if previous == signal:

        return


    # --------------------------------------------------------
    # Build message
    # --------------------------------------------------------

    message = telegram_message(
        result
    )


    if not message:

        return


    if send_telegram(message):

        last_telegram_signal[
            symbol
        ] = signal

        print(
            f"Telegram sent: "
            f"{symbol} {signal} "
            f"{confidence:.1f}%"
        )


# ============================================================
# ANALYZE SYMBOL
# ============================================================

def analyze_symbol(
    symbol,
    ticker,
    funding,
    all_time_low=None
):

    candles_5m = get_klines(
        symbol,
        FAST_TF,
        KLINE_LIMIT
    )


    candles_15m = get_klines(
        symbol,
        CONFIRM_TF,
        KLINE_LIMIT
    )


    candles_1h = get_klines(
        symbol,
        TREND_1H,
        KLINE_LIMIT
    )


    candles_4h = get_klines(
        symbol,
        TREND_4H,
        KLINE_LIMIT
    )


    candles_1d = get_klines(
        symbol,
        TREND_1D,
        KLINE_LIMIT
    )


    oi_history = get_oi_history(
        symbol,
        FAST_TF,
        20
    )


    if len(oi_history) < 2:

        return None


    funding_history = (
        get_funding_history(
            symbol,
            10
        )
    )


    price = candles_5m[-1]["close"]


    trend_1h = analyze_trend(
        candles_1h
    )

    trend_4h = analyze_trend(
        candles_4h
    )

    trend_1d = analyze_trend(
        candles_1d
    )


    fast_structure = (
        lower_structure(
            candles_5m
        )
    )


    confirm_structure = (
        lower_structure(
            candles_15m
        )
    )


    oi_change, oi_direction = (
        analyze_oi(
            oi_history
        )
    )


    volume = (
        volume_strength(
            candles_5m
        )
    )


    mom = momentum(
        candles_5m,
        3
    )


    supports_1h, resistances_1h = (
        swing_levels(
            candles_1h,
            SWING_LOOKBACK
        )
    )


    supports_4h, resistances_4h = (
        swing_levels(
            candles_4h,
            SWING_LOOKBACK
        )
    )


    support, resistance = (
        nearest_levels(

            price,

            supports_1h
            +
            supports_4h,

            resistances_1h
            +
            resistances_4h

        )
    )


    month_high, month_low = (
        thirty_day_levels(
            candles_1d
        )
    )


    loc = location_info(

        price,

        support,

        resistance,

        month_high,
        month_low,
        all_time_low

    )


    data = {

        "symbol":
            symbol,

        "price":
            price,

        "price_change":
            pct_change(
                price,
                candles_5m[-2]["close"]
            ),

        "momentum":
            mom,

        "volume_strength":
            volume,

        "oi_change":
            oi_change,

        "oi_direction":
            oi_direction,

        "funding":
            funding["funding"] * 100,

        "funding_history":
            funding_history,

        "trend_1h":
            trend_1h,

        "trend_4h":
            trend_4h,

        "trend_1d":
            trend_1d,

        "fast_structure":
            fast_structure,

        "confirm_structure":
            confirm_structure,

        "support":
            support,

        "resistance":
            resistance,

        "month_high":
            month_high,

        "month_low":
            month_low,

        "all_time_low":
            all_time_low,

        "location":
            loc

    }


    signal = generate_signal(
        data
    )


    result = {

        **data,

        **signal

    }

    result[
        "low_to_high_reversal"
    ] = (
        all_time_low is not None
        and loc["near_all_time_low"]
        and fast_structure == "BULLISH"
        and confirm_structure == "BULLISH"
        and mom > 0
        and (
            volume >= GOOD_VOLUME_PCT
            or oi_change > 0
        )
    )

    return result


# ============================================================
# PRINT SIGNAL
# ============================================================

def print_signal(r):

    icon = (
        "🟢"
        if r["signal"] == "LONG"
        else
        "🔴"
    )


    print()

    print(
        "=" * 80
    )


    print(
        f"{icon} "
        f"{r['symbol']} "
        f"{r['type']} "
        f"| "
        f"{r['confidence']:.1f}%"
    )


    print(
        f"CONFIRMED "
        f"{r.get('confirmation_count', 0)}/"
        f"{CONFIRMATION_SCANS}"
    )


    print(
        "-" * 80
    )


    print(
        f"Price:       "
        f"${format_price(r['price'])}"
    )


    print(
        f"1H:          {r['trend_1h']}"
    )

    print(
        f"4H:          {r['trend_4h']}"
    )

    print(
        f"1D:          {r['trend_1d']}"
    )


    print(
        f"5m:          {r['fast_structure']}"
    )

    print(
        f"15m:         {r['confirm_structure']}"
    )


    print()

    print(
        f"OI:          "
        f"{r['oi_change']:+.2f}% "
        f"{r['oi_direction']}"
    )


    print(
        f"Volume:      "
        f"{r['volume_strength']:+.1f}%"
    )


    print(
        f"Funding:     "
        f"{r['funding']:+.4f}%"
    )


    print()

    print(
        f"Support:     "
        f"${format_price(r['support'])}"
    )


    print(
        f"Resistance:  "
        f"${format_price(r['resistance'])}"
    )


    print(
        f"30D High:    "
        f"${format_price(r['month_high'])}"
    )


    print(
        f"30D Low:     "
        f"${format_price(r['month_low'])}"
    )


    plan = r.get(
        "trade_plan"
    )


    if plan:

        print()

        print(
            "TRADE PLAN"
        )


        print(
            f"Entry:       "
            f"${format_price(plan['entry'])}"
        )


        print(
            f"SL:          "
            f"${format_price(plan['sl'])} "
            f"({plan['risk_pct']:.2f}%)"
        )


        print(
            f"TP1:         "
            f"${format_price(plan['tp1'])} "
            f"(2R)"
        )


        print(
            f"TP2:         "
            f"${format_price(plan['tp2'])} "
            f"(3R)"
        )

        print(
            f"Projected:   "
            f"{plan['projected_return_pct']:+.2f}%"
        )

        print(
            f"At leverage: "
            f"2x {plan['return_at_2x_pct']:+.2f}% | "
            f"3x {plan['return_at_3x_pct']:+.2f}%"
        )

        if plan["twenty_percent_leverage"]:

            print(
                f"20% RETURN SETUP: "
                f"{plan['twenty_percent_leverage']} LEVERAGE "
                "(PROJECTED)"
            )

        if plan["higher_profit_setup"]:

            print(
                "HIGHER PROFIT SETUP: 30%+ AT 3X (PROJECTED)"
            )


        if plan["tp3"]:

            print(
                f"TP3:         "
                f"${format_price(plan['tp3'])}"
            )


        print(
            f"Leverage:    "
            f"{DEFAULT_LEVERAGE}"
        )


    print()

    print(
        "WHY:"
    )


    for reason in r["reasons"]:

        print(
            f"  ✓ {reason}"
        )


    if r["warnings"]:

        print()

        print(
            "WARNINGS:"
        )


        for warning in r["warnings"]:

            print(
                f"  ⚠ {warning}"
            )


    print(
        "=" * 80
    )


# ============================================================
# SCAN
# ============================================================

def scan(
    send_notifications=True,
    send_pending_notifications=True
):

    global confirmation_symbols
    global confirmation_low_symbols

    started = time.time()

    print(
        "Starting Binance API scan...",
        flush=True
    )

    print()

    print(
        "#" * 80
    )

    print(
        "BINANCE SIGNAL ENGINE"
    )

    print(
        datetime.now(
            timezone.utc
        ).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
    )

    print(
        "#" * 80
    )


    symbols = (
        get_usdt_perpetuals()
    )


    tickers = (
        get_24h_tickers()
    )


    funding = (
        get_current_funding()
    )


    # --------------------------------------------------------
    # Volume filter
    # --------------------------------------------------------

    symbols = [

        s

        for s in symbols

        if s in tickers

        and

        tickers[s]["volume"]
        >= MIN_24H_VOLUME

    ]


    symbols.sort(

        key=lambda s:
            tickers[s]["volume"],

        reverse=True

    )


    volume_symbols = symbols[
        :TOP_N
    ]

    low_symbols = [
        symbol
        for symbol in sorted(
            symbols,
            key=lambda item: tickers[item]["change"]
        )
        if symbol not in volume_symbols
    ][:LOW_CANDIDATE_N]

    selected_symbols = volume_symbols + low_symbols

    if RUN_ONCE:

        if confirmation_symbols is None:

            confirmation_symbols = selected_symbols
            confirmation_low_symbols = low_symbols

        else:

            print(
                "Reusing first-scan token universe for confirmation."
            )

            low_symbols = [
                symbol
                for symbol in confirmation_low_symbols
                if symbol in confirmation_symbols
            ]

        symbols = confirmation_symbols

    else:

        symbols = selected_symbols

    volume_symbols = [
        symbol
        for symbol in symbols
        if symbol not in low_symbols
    ]


    print(
        f"Scanning {len(volume_symbols)} volume leaders plus "
        f"{len(low_symbols)} low-watchlist symbols..."
    )


    results = []


    # --------------------------------------------------------
    # Analyze
    # --------------------------------------------------------

    for index, symbol in enumerate(
        symbols,
        1
    ):

        try:

            print(

                f"[{index}/{len(symbols)}] "
                f"{symbol:<15}",

                end="\r"

            )


            if symbol not in funding:

                continue


            all_time_low = (
                get_all_time_low(symbol)
                if symbol in low_symbols
                else None
            )


            result = analyze_symbol(

                symbol,

                tickers[symbol],

                funding[symbol],

                all_time_low

            )


            if result:

                results.append(
                    result
                )

                if (
                    symbol in low_symbols
                    and result["low_to_high_reversal"]
                ):

                    print()

                    print(
                        f"Low-to-high reversal watch: {symbol}"
                    )

                    if send_notifications:

                        send_low_to_high_reversal_telegram(
                            result
                        )


        except Exception as e:

            print()

            print(
                f"{symbol}: ERROR: {e}"
            )


    print()
    print()


    # --------------------------------------------------------
    # Confirmation
    # --------------------------------------------------------

    confirmed = []


    for result in results:

        if result["signal"] not in [
            "LONG",
            "SHORT"
        ]:

            continue


        if result["confidence"] < (
            MIN_CONFIDENCE
        ):

            continue


        result_confirmed = (
            confirm_signal(
                result
            )
        )


        if result_confirmed:

            plan = calculate_trade_plan(
                result_confirmed
            )


            if plan is None:

                print(
                    f"{result_confirmed['symbol']} "
                    f"signal rejected: "
                    f"SL distance too wide."
                )

                continue


            result_confirmed[
                "trade_plan"
            ] = plan


            confirmed.append(
                result_confirmed
            )


    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    confirmed.sort(

        key=lambda x:
            x["confidence"],

        reverse=True

    )


    # --------------------------------------------------------
    # Print
    # --------------------------------------------------------

    if confirmed:

        print(
            "#" * 80
        )

        print(
            "CONFIRMED SIGNALS"
        )

        print(
            "#" * 80
        )


        for result in confirmed[:10]:

            print_signal(
                result
            )


            if send_notifications:

                send_confirmed_telegram(
                    result
                )


    else:

        print(
            "No confirmed LONG/SHORT signals "
            "this scan."
        )


    # --------------------------------------------------------
    # Pending
    # --------------------------------------------------------

    pending = [

        r

        for r in results

        if r["signal"]
        in ["LONG", "SHORT"]

        and
        r["confidence"]
        >= MIN_CONFIDENCE

        and

        r["symbol"]
        in pending_signals
    ]


    if pending:

        print()

        print(
            "PENDING CONFIRMATION"
        )


        for r in sorted(

            pending,

            key=lambda x:
                x["confidence"],

            reverse=True

        )[:10]:

            state = (
                pending_signals[
                    r["symbol"]
                ]
            )


            print(

                f"🟡 "
                f"{r['symbol']} "
                f"{r['signal']} "
                f"{r['confidence']:.1f}% "
                f"— "
                f"{state['count']}/"
                f"{CONFIRMATION_SCANS}"

            )

            if send_notifications and send_pending_notifications:

                send_pending_telegram(r)


    # --------------------------------------------------------
    # Time
    # --------------------------------------------------------

    elapsed = (
        time.time()
        - started
    )


    print()

    print(
        f"Scan completed in "
        f"{elapsed:.1f}s",
        flush=True
    )

    return results


# ============================================================
# MAIN
# ============================================================

def main():

    print()

    print(
        "========================================"
    )

    print(
        " BINANCE SIGNAL ENGINE"
    )

    print(
        " Signal-only / No execution"
    )

    print(
        "========================================"
    )


    if TELEGRAM_ENABLED:

        if (
            TELEGRAM_BOT_TOKEN
            and
            TELEGRAM_CHAT_ID
        ):

            print(
                "Telegram: ENABLED"
            )

        else:

            print(
                "Telegram: NOT CONFIGURED"
            )

    else:

        print(
            "Telegram: DISABLED"
        )


    print()

    print(
        f"Confirmation: "
        f"{CONFIRMATION_SCANS} scans"
    )

    print(
        f"Scan interval: "
        f"{SCAN_INTERVAL // 60} minutes"
    )

    print(
        f"Universe: top "
        f"{TOP_N} by 24h volume"
    )


    print()

    if RUN_ONCE:

        try:

            print(
                "[1/2] Starting initial analysis...",
                flush=True
            )

            results = scan()

            print(
                "Initial analysis completed. "
                "Waiting 10 minutes for confirmation...",
                flush=True
            )

            time.sleep(CONFIRMATION_WAIT)

            print(
                "[2/2] Starting confirmation analysis...",
                flush=True
            )

            results = scan(
                send_pending_notifications=False
            )

            save_market_history(results)

            clear_market_history()

            print(
                "Confirmation analysis completed.",
                flush=True
            )

        except KeyboardInterrupt:

            print(
                "\nStopped."
            )

        except Exception as e:

            print(
                f"\nScanner error: {e}",
                flush=True
            )

            raise

        return


    while True:

        try:

            scan()


        except KeyboardInterrupt:

            print(
                "\nStopped."
            )

            break


        except Exception as e:

            print(
                f"\nScanner error: {e}"
            )

            print(
                "Will retry next cycle."
            )


        print()

        print(
            f"Next scan in "
            f"{SCAN_INTERVAL // 60} minutes..."
        )


        time.sleep(
            SCAN_INTERVAL
        )


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()