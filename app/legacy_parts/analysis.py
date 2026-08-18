import time

from config import (
    CONFIRMATION_SCANS,
    DEFAULT_LEVERAGE,
    EXTREME_ZONE_PCT,
    GOOD_VOLUME_PCT,
    MAX_SL_DISTANCE_PCT,
    MIN_CONFIRMATION_CONFIDENCE,
    SR_PROXIMITY_PCT,
    STRONG_VOLUME_PCT,
    TP1_R,
    TP2_R,
    VOLUME_LOOKBACK,
)


pending_signals = {}


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
    month_low
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
            None

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
