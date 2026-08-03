"""
Institutional Fair Value Gap Validator
Version 1.0
"""

from mss.domain.fair_value_gap import FairValueGap


class FairValueGapValidator:

    def validate(
        self,
        context,
        analysis,
        fvg: FairValueGap,
    ) -> FairValueGap:

        # -----------------------------
        # Gap must exist
        # -----------------------------

        if not fvg.valid:
            return fvg

        # -----------------------------
        # BOS required
        # -----------------------------

        if analysis.bos is None:
            fvg.valid = False
            return fvg

        # -----------------------------
        # Order Block required
        # -----------------------------

        if analysis.order_block is None:
            fvg.valid = False
            return fvg

        if not analysis.order_block.valid:
            fvg.valid = False
            return fvg

        # -----------------------------
        # Displacement required
        # -----------------------------

        if analysis.displacement is None:
            fvg.valid = False
            return fvg

        if fvg.direction == "BULLISH":

            if not analysis.displacement.bullish:
                fvg.valid = False
                return fvg

        if fvg.direction == "BEARISH":

            if not analysis.displacement.bearish:
                fvg.valid = False
                return fvg

        # -----------------------------
        # Filled Gap Validation
        # -----------------------------

        candles = context.candles

        for candle in candles:

            if fvg.candle_time is None:
                break

            if candle.time <= fvg.candle_time:
                continue

            if fvg.direction == "BULLISH":

                if candle.close <= fvg.low:

                    fvg.filled = True
                    fvg.valid = False

                    return fvg

            if fvg.direction == "BEARISH":

                if candle.close >= fvg.high:

                    fvg.filled = True
                    fvg.valid = False

                    return fvg

        return fvg