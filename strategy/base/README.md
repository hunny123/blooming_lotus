# Base Strategy

The base strategy is the default implementation selected when the config does
not name another strategy. It is the modular equivalent of the decision logic
that previously lived in `app/core_engine.py`.

## Logical flow

1. Receive the initial token universe from `get_initial_tokens`.
2. Collect 24-hour ticker data and `5m`, `15m`, `1h`, `4h`, and `1d` candles.
3. Collect funding, open-interest history, and all-time extremes.
4. Save the first market snapshot.
5. Score every initial token and keep eligible tokens with a directional signal,
   valid trade plan, and confidence at or above `min_confidence`.
6. Wait `observation_scan_interval_seconds` from config.
7. Collect a second market snapshot only for eligible tokens.
8. Re-run the strategy for those tokens and calculate the observed changes.
9. Score LONG and SHORT evidence using:
	- EMA 20/50/200 higher-timeframe trend alignment
	- EMA 9/20 lower-timeframe structure and candle balance
	- short-term momentum
	- open-interest direction versus price movement
	- current volume versus the previous 20-candle average
	- funding bias
	- swing support and resistance
	- 30-day high/low location and reversal confirmation
8. Return `WAIT` when evidence is weak, conflicted, or crowded near a key level.
9. Create a trade plan only when risk is positive and stop distance is at most 5%.

## Technical contract

```python
result = strategy.run(tokens, client=binance_client)
```

Each result contains `selections`. Every selection contains:

- `token`, `signal`, `confidence`, and `type`
- `entry_range`, `sl_range`, and `tp_range`
- `trade_plan` with entry, stop, TP1, TP2, optional TP3, and risk percentage
- `indicators` with trend, structure, momentum, volume, OI, funding, and levels
- `reasons` and `warnings`
- a generic `label`

For tests or composition, pre-collected data can still be passed directly:

```python
result = strategy.run(tokens, market_data=market_data, previous_result=previous)
```

The strategy owns collection, eligibility, waiting, and history; the app runner
only selects the initial tokens, invokes the configured strategy, and forwards
its result to Telegram.
