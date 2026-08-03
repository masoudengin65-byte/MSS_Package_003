# MSS Fair Value Gap Specification v1.0

## Purpose

Detect Institutional Fair Value Gaps.

---

## Bullish FVG

Three consecutive candles.

Condition:

High(Candle 1)

<

Low(Candle 3)

Gap exists.

---

## Additional MSS Rules

A Bullish FVG is VALID only if:

1.
Bullish Order Block exists.

2.
Bullish BOS exists.

3.
Bullish Displacement exists.

4.
Gap is NOT filled.

---

Filled Gap

If price closes inside the gap,

↓

Gap becomes invalid.

---

Priority

Liquidity

↓

Displacement

↓

BOS

↓

Order Block

↓

Fair Value Gap