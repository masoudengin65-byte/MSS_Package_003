# MSS Smart Money Rules
Version : 1.0

This document defines every rule used by MSS.

These rules are the single source of truth.

No algorithm may violate these rules.

------------------------------------------------------------

# Rule 1 : Swing High

A Swing High is valid when:

- It is higher than neighboring highs.
- It survives Swing Filter.
- It survives Swing Validation.

------------------------------------------------------------

# Rule 2 : Swing Low

A Swing Low is valid when:

- It is lower than neighboring lows.
- It survives Swing Filter.
- It survives Swing Validation.

------------------------------------------------------------

# Rule 3 : Swing Filter

Two consecutive HIGH are forbidden.

Keep only the strongest HIGH.

Two consecutive LOW are forbidden.

Keep only the lowest LOW.

------------------------------------------------------------

# Rule 4 : Swing Validation

Reject weak swings.

Reject duplicated swings.

Reject insignificant movements.

Reject noisy swings.

------------------------------------------------------------

# Rule 5 : BOS

Bullish BOS

Close > Previous Swing High

Bearish BOS

Close < Previous Swing Low

Only VALIDATED swings may generate BOS.

------------------------------------------------------------

# Rule 6 : CHoCH

A CHoCH is valid only after an opposite BOS.

------------------------------------------------------------

# Rule 7 : Liquidity

Equal Highs

Equal Lows

Liquidity Sweep

will be implemented after BOS.

------------------------------------------------------------

# Rule 8 : Order Block

Only after a VALID BOS.

------------------------------------------------------------

# Rule 9 : Fair Value Gap

Only after BOS.

------------------------------------------------------------

End of Specification