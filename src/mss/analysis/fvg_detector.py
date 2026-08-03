"""
Professional Fair Value Gap Detector
Version 1.0
"""

from mss.domain.fair_value_gap import FairValueGap
from mss.analysis.fvg_validator import FairValueGapValidator


class FairValueGapDetector:

    def detect(
        self,
        context,
        analysis,
    ) -> FairValueGap:

        fvg = FairValueGap()

        candles = context.candles

        # ---------------------------------
        # Need at least three candles
        # ---------------------------------

        if len(candles) < 3:
            return fvg

        c1 = candles[-3]
        c2 = candles[-2]
        c3 = candles[-1]

        # ==========================================
        # Bullish Fair Value Gap
        # ==========================================

        if c1.high < c3.low:

            fvg.direction = "BULLISH"

            fvg.low = c1.high
            fvg.high = c3.low

            fvg.candle_time = c2.time

            fvg.valid = True

            return FairValueGapValidator().validate(
                context,
                analysis,
                fvg,
            )

        # ==========================================
        # Bearish Fair Value Gap
        # ==========================================

        if c1.low > c3.high:

            fvg.direction = "BEARISH"

            fvg.low = c3.high
            fvg.high = c1.low

            fvg.candle_time = c2.time

            fvg.valid = True

            return FairValueGapValidator().validate(
                context,
                analysis,
                fvg,
            )

        return fvg