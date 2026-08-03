# MSS Order Block Specification v1.0

## Purpose

Detect Institutional Order Blocks based on Smart Money Concepts (ICT).

---

# Bullish Order Block

A Bullish Order Block is VALID only if ALL conditions are satisfied.

## Rule 1

Sell Side Liquidity must be taken.

(Equal Low or Sell Side Sweep)

↓

## Rule 2

Bullish Displacement must occur.

Large bullish impulse.

↓

## Rule 3

Bullish BOS must occur.

Break by CLOSE.

↓

## Rule 4

The Order Block is the LAST bearish candle
before the bullish displacement.

↓

## Rule 5

The Order Block must remain UNMITIGATED.

If price fully trades through the candle body,
the Order Block becomes invalid.

---

# Bearish Order Block

Exactly opposite.

Buy Side Liquidity

↓

Bearish Displacement

↓

Bearish BOS

↓

Last Bullish Candle

↓

Unmitigated

---

# Validation Rules

An Order Block is rejected if:

- No Liquidity Sweep
- Weak displacement
- No BOS
- Already mitigated

---

# MSS Priority

Liquidity

↓

Displacement

↓

BOS

↓

Order Block
