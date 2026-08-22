"""Reusable signal and trade-plan calculations."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from shared.indicators import ema


SR_PROXIMITY_PCT = 1.5
GOOD_VOLUME_PCT = 30.0
STRONG_VOLUME_PCT = 100.0
MAX_SL_DISTANCE_PCT = 5.0
TP1_R = 2.0
TP2_R = 3.0


def pct_change(current: float, previous: float) -> float:
    return ((current - previous) / previous) * 100 if previous else 0.0


def trend(candles: Sequence[Dict[str, float]]) -> str:
    if len(candles) < 200:
        return "UNKNOWN"
    closes = [item["close"] for item in candles]
    price = closes[-1]
    ema20 = ema(closes, 20)
    ema50 = ema(closes, 50)
    ema200 = ema(closes, 200)
    bullish = int(price > ema20) + int(price > ema50) + (2 if price > ema200 else 0)
    bearish = int(price <= ema20) + int(price <= ema50) + (2 if price <= ema200 else 0)
    if ema20 > ema50 > ema200:
        bullish += 2
    if ema20 < ema50 < ema200:
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


def lower_structure(candles: Sequence[Dict[str, float]]) -> str:
    if len(candles) < 30:
        return "UNKNOWN"
    closes = [item["close"] for item in candles]
    price = closes[-1]
    ema9 = ema(closes, 9)
    ema20 = ema(closes, 20)
    score = (1 if price > ema9 else -1) + (1 if price > ema20 else -1)
    score += 2 if ema9 > ema20 else -2
    recent = candles[-5:]
    green = sum(item["close"] > item["open"] for item in recent)
    red = sum(item["close"] < item["open"] for item in recent)
    score += 1 if green > red else -1 if red > green else 0
    return "BULLISH" if score >= 2 else "BEARISH" if score <= -2 else "NEUTRAL"


def momentum(candles: Sequence[Dict[str, float]], bars: int = 3) -> float:
    if len(candles) <= bars:
        return 0.0
    return pct_change(candles[-1]["close"], candles[-1 - bars]["close"])


def volume_strength(candles: Sequence[Dict[str, float]], lookback: int = 20) -> float:
    if len(candles) < lookback + 1:
        return 0.0
    current = candles[-1].get("quote_volume", candles[-1].get("volume", 0.0))
    previous = [item.get("quote_volume", item.get("volume", 0.0)) for item in candles[-lookback - 1:-1]]
    average = sum(previous) / len(previous) if previous else 0.0
    return pct_change(current, average) if average else 0.0


def oi_change(history: Sequence[float]) -> Tuple[float, str]:
    if len(history) < 2:
        return 0.0, "UNKNOWN"
    change = pct_change(history[-1], history[max(0, len(history) - 4)])
    return change, "RISING" if change > 0.5 else "FALLING" if change < -0.5 else "FLAT"


def swing_levels(candles: Sequence[Dict[str, float]], lookback: int = 5) -> Tuple[List[float], List[float]]:
    supports: List[float] = []
    resistances: List[float] = []
    for index in range(lookback, len(candles) - lookback):
        current = candles[index]
        neighbors = candles[index - lookback:index] + candles[index + 1:index + 1 + lookback]
        if current["low"] <= min(item["low"] for item in neighbors):
            supports.append(current["low"])
        if current["high"] >= max(item["high"] for item in neighbors):
            resistances.append(current["high"])
    return supports, resistances


def nearest_levels(price: float, supports: Iterable[float], resistances: Iterable[float]) -> Tuple[Optional[float], Optional[float]]:
    below = [level for level in supports if level < price]
    above = [level for level in resistances if level > price]
    return (max(below) if below else None, min(above) if above else None)


def location(price: float, support: Optional[float], resistance: Optional[float], month_high: Optional[float], month_low: Optional[float]) -> Dict[str, Any]:
    result = {"near_support": False, "near_resistance": False, "near_month_low": False, "near_month_high": False}
    if price <= 0:
        return result
    if support:
        distance = ((price - support) / price) * 100
        result["support_distance"] = distance
        result["near_support"] = 0 <= distance <= SR_PROXIMITY_PCT
    if resistance:
        distance = ((resistance - price) / price) * 100
        result["resistance_distance"] = distance
        result["near_resistance"] = 0 <= distance <= SR_PROXIMITY_PCT
    if month_low:
        distance = ((price - month_low) / price) * 100
        result["month_low_distance"] = distance
        result["near_month_low"] = 0 <= distance <= SR_PROXIMITY_PCT
    if month_high:
        distance = ((month_high - price) / price) * 100
        result["month_high_distance"] = distance
        result["near_month_high"] = 0 <= distance <= SR_PROXIMITY_PCT
    return result


def signal(data: Dict[str, Any]) -> Dict[str, Any]:
    mom = data["momentum"]
    volume = data["volume_strength"]
    oi = data["oi_change"]
    funding = data["funding"]
    fast = data["fast_structure"]
    confirm = data["confirm_structure"]
    trends = [data["trend_1h"], data["trend_4h"], data["trend_1d"]]
    loc = data["location"]
    long_score = 0.0
    short_score = 0.0
    long_reasons: List[str] = []
    short_reasons: List[str] = []
    warnings: List[str] = []
    bullish_htf = sum("BULLISH" in item for item in trends)
    bearish_htf = sum("BEARISH" in item for item in trends)
    long_crowded = funding > 0.08 and oi > 1.0 and mom > 0.50 and bullish_htf > 0
    short_crowded = funding < -0.08 and oi > 1.0 and mom < -0.50 and bearish_htf > 0
    if bullish_htf >= 2:
        long_score += 12; long_reasons.append("higher-timeframe trend supports LONG")
    if bearish_htf >= 2:
        short_score += 12; short_reasons.append("higher-timeframe trend supports SHORT")
    if fast == "BULLISH":
        long_score += 10; long_reasons.append("5m structure is bullish")
    elif fast == "BEARISH":
        short_score += 10; short_reasons.append("5m structure is bearish")
    if confirm == "BULLISH":
        long_score += 10; long_reasons.append("15m structure confirms buying")
    elif confirm == "BEARISH":
        short_score += 10; short_reasons.append("15m structure confirms selling")
    if mom > 0.30:
        long_score += 8; long_reasons.append("short-term momentum is positive")
    elif mom < -0.30:
        short_score += 8; short_reasons.append("short-term momentum is negative")
    if oi > 0.5 and mom > 0:
        long_score += 14; long_reasons.append("OI rising while price rises")
    elif oi > 0.5 and mom < 0:
        short_score += 14; short_reasons.append("OI rising while price falls")
    elif oi < -0.5 and mom > 0:
        long_score += 4; long_reasons.append("OI falling during price recovery")
    elif oi < -0.5 and mom < 0:
        short_score += 4; short_reasons.append("OI falling during price decline")
    volume_points = 14 if volume >= STRONG_VOLUME_PCT else 7 if volume >= GOOD_VOLUME_PCT else 0
    if volume_points and mom > 0:
        long_score += volume_points; long_reasons.append("volume supports buying")
    elif volume_points and mom < 0:
        short_score += volume_points; short_reasons.append("volume supports selling")
    if funding < -0.05:
        long_score += 8; long_reasons.append("negative funding supports LONG")
    elif funding > 0.05:
        short_score += 8; short_reasons.append("positive funding supports SHORT")
    if loc.get("near_support") and fast == "BULLISH" and mom > 0:
        long_score += 16; long_reasons.append("price is bouncing from support")
    if loc.get("near_resistance") and fast == "BEARISH" and mom < 0:
        short_score += 16; short_reasons.append("price is rejecting resistance")
    if loc.get("near_month_low") and fast == confirm == "BULLISH" and mom > 0 and volume >= GOOD_VOLUME_PCT:
        long_score += 24; long_reasons.append("confirmed reversal near 30D low")
    if loc.get("near_month_high") and fast == confirm == "BEARISH" and mom < 0 and volume >= GOOD_VOLUME_PCT:
        short_score += 24; short_reasons.append("confirmed reversal near 30D high")
    total = long_score + short_score
    if total <= 0 or abs(long_score - short_score) < 12:
        return {"signal": "WAIT", "confidence": round(max(long_score, short_score) / total * 100, 1) if total else 0.0, "type": "CONFLICTED" if total else "NO SETUP", "long_score": long_score, "short_score": short_score, "reasons": ["evidence is weak or conflicted"], "warnings": warnings}
    is_long = long_score > short_score
    crowded = long_crowded if is_long else short_crowded
    near_level = loc.get("near_resistance") if is_long else loc.get("near_support")
    if crowded and near_level:
        side = "LONG" if is_long else "SHORT"
        return {"signal": "WAIT", "confidence": round(max(long_score, short_score) / total * 100, 1), "type": f"CROWDED {side}", "long_score": long_score, "short_score": short_score, "reasons": [f"{side} rejected by crowding risk near a key level"], "warnings": [f"crowded {side.lower()} setup"]}
    signal_name = "LONG" if is_long else "SHORT"
    signal_type = "REVERSAL " + signal_name if (loc.get("near_month_low") if is_long else loc.get("near_month_high")) else "SUPPORT BOUNCE LONG" if is_long and loc.get("near_support") else "RESISTANCE REJECTION SHORT" if not is_long and loc.get("near_resistance") else "TREND " + signal_name
    return {"signal": signal_name, "confidence": round((long_score if is_long else short_score) / total * 100, 1), "type": signal_type, "long_score": long_score, "short_score": short_score, "reasons": long_reasons if is_long else short_reasons, "warnings": warnings}


def trade_plan(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if data.get("signal") not in {"LONG", "SHORT"}:
        return None
    entry = data["price"]
    support = data.get("support")
    resistance = data.get("resistance")
    long = data["signal"] == "LONG"
    stop = support * 0.997 if long and support else entry * 0.985 if long else resistance * 1.003 if resistance else entry * 1.015
    risk = entry - stop if long else stop - entry
    risk_pct = risk / entry * 100 if entry else 100.0
    if risk <= 0 or risk_pct > MAX_SL_DISTANCE_PCT:
        return None
    tp1 = entry + risk * TP1_R if long else entry - risk * TP1_R
    tp2 = entry + risk * TP2_R if long else entry - risk * TP2_R
    tp3 = resistance if long and resistance and resistance > tp2 else support if not long and support and support < tp2 else None
    target = tp3 or tp2
    projected = abs(target - entry) / entry * 100 if entry else 0.0
    return {"entry": entry, "sl": stop, "risk": risk, "risk_pct": risk_pct, "tp1": tp1, "tp2": tp2, "tp3": tp3, "projected_return_pct": projected, "direction": data["signal"]}
