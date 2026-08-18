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

def telegram_message(r):

    icon = (
        "🟢"
        if r["signal"] == "LONG"
        else
        "🔴"
    )


    plan = r.get(
        "trade_plan"
    )


    if plan is None:

        return None


    lines = []


    lines.append(
        f"{icon} <b>CONFIRMED "
        f"{r['signal']}</b>"
    )


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


def save_market_history(results):
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
