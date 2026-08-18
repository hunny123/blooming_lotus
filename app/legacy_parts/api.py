import time
import requests

from config import BASE_URL


session = requests.Session()
session.headers.update({
    "User-Agent": "Binance-Signal-Engine/5.0"
})


def api_get(endpoint, params=None):

    for attempt in range(3):

        try:

            response = session.get(

                BASE_URL + endpoint,

                params=params,

                timeout=15

            )


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

            return response.json()


        except Exception as e:

            print(
                f"API error: {e} "
                f"| retry {attempt + 1}/3"
            )

            if attempt == 2:

                raise

            time.sleep(2)


    raise RuntimeError(
        "Binance API request failed"
    )


# ============================================================
# TELEGRAM
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
