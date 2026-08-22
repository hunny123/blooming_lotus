# Risk Controlled Strategy

This strategy is a conservative variant of the base strategy.

## Purpose
- same token-list entry contract as other strategies
- more conservative checks for risk and confirmation
- useful as a secondary or layered strategy

## Inputs
- symbol list
- optional previous strategy result

## Typical behavior
It may use:
- tighter stop validation
- stricter trend or structure confirmation
- stronger risk rejection for crowded or conflicted setups

This strategy should reuse shared helpers rather than duplicating core market logic.
