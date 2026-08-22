# Trend Breakout Strategy

This strategy is a trend-following implementation that builds on the reusable shared logic.

## Purpose
- prefer strongly trending tokens
- confirm direction with short-term structure
- use volume and trend alignment as main filters

## Inputs
- symbol list from the scanner
- optional previous strategy result when layered composition is desired

## Typical behavior
This strategy may evaluate:
- higher timeframe trend
- short-term structure
- momentum
- volume confirmation
- risk filters

The actual analysis logic should live in the strategy implementation and can reuse shared helper modules.
