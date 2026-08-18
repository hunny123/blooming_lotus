import os
from dotenv import load_dotenv


load_dotenv(
    os.path.join(
        os.path.dirname(__file__),
        ".env.local"
    )
)


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


# ------------------------------------------------------------
# Scanner
# ------------------------------------------------------------

TOP_N = 30

MIN_24H_VOLUME = 20_000_000

SCAN_INTERVAL = 300
# 5 minutes


# ------------------------------------------------------------
# Confirmation
# ------------------------------------------------------------

CONFIRMATION_SCANS = 2

MIN_CONFIDENCE = 60

MIN_CONFIRMATION_CONFIDENCE = 60


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

DEFAULT_LEVERAGE = "2x-3x"


# ------------------------------------------------------------
# Telegram
# ------------------------------------------------------------

TELEGRAM_ENABLED = True

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RUN_ONCE = os.getenv("RUN_ONCE", "false").lower() == "true"

CONFIRMATION_WAIT = 300

TREND_RECHECK_WAIT = 1800

HISTORY_FILE = os.path.join(
    os.path.dirname(__file__),
    "market_history.json"
)



