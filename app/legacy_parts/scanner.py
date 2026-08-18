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
def analyze_symbol(
    symbol,
    ticker,
    funding
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

        month_low

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

        "location":
            loc

    }


    signal = generate_signal(
        data
    )


    return {

        **data,

        **signal

    }


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

def scan(send_notifications=True):

    started = time.time()


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


    symbols = symbols[
        :TOP_N
    ]


    print(
        f"Scanning {len(symbols)} symbols..."
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


            result = analyze_symbol(

                symbol,

                tickers[symbol],

                funding[symbol]

            )


            if result:

                results.append(
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

            if send_notifications:

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
        f"{elapsed:.1f}s"
    )

    return results


# ============================================================
# MAIN
