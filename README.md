# Binance Signal Engine

A signal-only Binance Futures scanner. It analyzes USDT-margined perpetual contracts and sends LONG or SHORT alerts to Telegram. It does not place Binance orders.

## Strategy

### 1. Market selection

Each scan:

- Loads Binance Futures public market data.
- Keeps trading USDT perpetual contracts only.
- Filters symbols with at least `$20,000,000` 24-hour quote volume.
- Scans the top 50 symbols by 24-hour volume, plus up to 20 additional symbols
	with the largest negative 24-hour price change.

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
- Position crowding risk from funding, open interest, and price momentum.

A signal is rejected as `WAIT` when evidence is too weak or LONG and SHORT scores are too balanced. The minimum signal confidence is 60%.

Crowding protection also rejects a LONG when positive funding, rising open interest,
and positive momentum occur near resistance. It rejects a SHORT when negative
funding, rising open interest, and negative momentum occur near support. These
conditions can indicate that leveraged traders are positioned too heavily in one
direction and that a reversal or liquidation move is possible.

## Bot V2 Plan

Bot V2 will be developed as a separate strategy and will not change the current
bot's signal logic. It will use a staged analysis pipeline:

1. Shortlist liquid and active tokens using the market data API.
	The Bot V2 shortlist is capped at the top 30 candidates.
2. Run a 30-minute observation session for each shortlisted token, taking a
	checkpoint every 5 minutes and comparing each checkpoint with the previous
	one.
3. Identify the broad trend using BTC, related parent coins, and the token's
	1D, 4H, and 1H structure.
4. Identify important 1D and 4H support and resistance zones.
5. Use the 5-minute checkpoints to confirm short-term trend direction and
	detect whether price breaks through or rejects the higher-timeframe zones.
6. Detect critical bounce and rejection areas.
7. Review funding-rate and open-interest history.
8. Confirm order-flow conditions such as volume, order-book imbalance, and
	liquidation activity when available.
9. Check correlation with BTC and the token's related sector or parent coin.
10. Produce a final signal only after entry, stop-loss, and reward-to-risk checks.

For a higher-timeframe level, V2 should distinguish between:

- **Confirmed break:** a 5-minute candle closes beyond the 4H or 1D zone and
  follow-up checkpoints hold beyond it.
- **Rejection:** price enters the zone but closes back away from it, with later
  5-minute checkpoints confirming the reversal.
- **Unconfirmed touch:** price reaches the zone without enough follow-up data;
  this should not create a signal by itself.

Liquidity is a mandatory V2 criterion. A token must pass minimum quote volume,
recent trading activity, and basic market-quality checks before deeper analysis.
Distance from the all-time high and all-time low is also a mandatory criterion
for every shortlisted token. V2 should record whether price is near, between, or
breaking away from these historical extremes; this is context for the signal,
not an automatic LONG or SHORT decision.

Bot V2 should use hard filters for liquidity, major trend conflict, and poor
risk-to-reward setups. Other measurements should contribute evidence to the
final score rather than all being mandatory filters. Correlated measurements
should not be counted as fully independent confirmations.

Bot V2 results remain separate from the current bot and are currently printed
to stdout for review. Telegram delivery can be added without changing the V2
analysis pipeline.

### Bot V2 implementation

Bot V2 is available as a separate signal-only script. It selects the V2
universe, filters the liquid candidates for current 15-minute activity, then
observes only the survivors through 6 five-minute checkpoints and prints the
final signal and trade plan:

```powershell
C:/Python313/python.exe bot_v2.py
```

The script uses the public Binance Futures API only and never places orders.
Each observed candidate takes approximately 30 minutes. The liquid candidate
pool is capped at 30, but inactive candidates are rejected before observation.
Set `BINANCE_BASE_URL` when a different Binance Futures host is required. All
qualified candidates run in parallel by default; set `V2_WORKERS` to use a
smaller worker count if Binance rate limits the requests.

### 4. Confirmation flow

When `RUN_ONCE=true`, one observation session does two scans:

1. Scan 1 analyzes the market and sends a pending/initial Telegram message.
2. The process waits 10 minutes.
3. Scan 2 analyzes the same token universe selected during Scan 1, so newly
	appearing tokens cannot enter only because of the confirmation scan.
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

To run one confirmed observation session every four hours on Linux or WSL:

```bash
chmod +x run_every_4_hours.sh
./run_every_4_hours.sh
```

Set `PYTHON_BIN` when the Python executable is not `python3`, for example:

```bash
PYTHON_BIN="$PWD/.venv/bin/python" ./run_every_4_hours.sh
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
