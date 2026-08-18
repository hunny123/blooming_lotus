# Binance Signal Engine

A signal-only Binance Futures scanner. It analyzes USDT-margined perpetual contracts and sends LONG or SHORT alerts to Telegram. It does not place Binance orders.

## Strategy

### 1. Market selection

Each scan:

- Loads Binance Futures public market data.
- Keeps trading USDT perpetual contracts only.
- Filters symbols with at least `$20,000,000` 24-hour quote volume.
- Scans the top 30 symbols by 24-hour volume.

### 2. Timeframes

| Purpose | Timeframe |
| --- | --- |
| Fast structure | 5m |
| Confirmation structure | 15m |
| Trend | 1h, 4h, 1d |

The trend calculation uses EMA 20, EMA 50, and EMA 200. The lower-timeframe structure uses EMA 9, EMA 20, and the recent candle balance.

### 3. Signal inputs

The strategy scores LONG and SHORT evidence from:

- Higher-timeframe trend alignment.
- 5-minute and 15-minute market structure.
- Short-term momentum.
- Open-interest direction compared with price movement.
- Volume compared with the previous 20-candle average.
- Funding-rate crowding.
- Swing support and resistance.
- Distance from the 30-day high or low.
- Confirmed reversals near 30-day extremes.

A signal is rejected as `WAIT` when evidence is too weak or LONG and SHORT scores are too balanced. The minimum signal confidence is 60%.

### 4. Confirmation flow

When `RUN_ONCE=true`, one observation session does two scans:

1. Scan 1 analyzes the market and sends a pending/initial Telegram message.
2. The process waits 10 minutes.
3. Scan 2 analyzes the market again.
4. If the same LONG or SHORT direction remains valid and passes confirmation, a confirmed Telegram message is sent with the trade plan.

The normal GitHub Actions schedule starts a new observation session every 3 hours. Scheduled jobs use UTC times.

## Trade plan

For a LONG:

- Entry is the current analyzed price.
- Stop loss is below nearby support, or 1.5% below price when support is unavailable.
- TP1 is 2R.
- TP2 is 3R.
- An optional TP3 uses the next resistance beyond TP2.

For a SHORT, the calculations are mirrored around resistance and support.

Signals are rejected when the calculated stop-loss distance exceeds 5%. Suggested leverage is informational only and does not execute an order.

## Telegram configuration

Create `blooming_lotus/.env.local` locally:

```env
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Do not commit this file. GitHub Actions reads the equivalent values from repository secrets named:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

If either value is missing, the scanner continues but Telegram delivery is unavailable.

## Run locally

From the `blooming_lotus` directory:

```powershell
C:/Python313/python.exe deployment\build.py

$env:RUN_ONCE="true"
C:/Python313/python.exe dist\signal_engine.pyz
```

A full one-session run takes at least 10 minutes because of the confirmation wait.

For the normal continuous process:

```powershell
C:/Python313/python.exe main.py
```

## Deployment build

The build script creates an executable Python zipapp:

```text
dist/signal_engine.pyz
```

GitHub Actions builds and runs this artifact. The deployable code is organized as:

```text
app/          Core engine and service classes
config/       Configuration modules
deployment/   Build tooling
utils/        Shared utilities
main.py       Runtime entry point
```

## Data and limitations

`market_history.json` stores the latest scan data during a session and is cleaned after the final confirmation. GitHub Actions uploads the file as an artifact before the job ends.

This project is for market observation and alerts only. It is not financial advice, and signals can be wrong or delayed. Validate every signal independently before taking any action.
