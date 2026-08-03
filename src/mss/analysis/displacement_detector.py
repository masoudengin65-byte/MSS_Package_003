"""
Professional Displacement Detector
"""

from mss.domain.displacement import Displacement


from mss.config.settings import (
    DISPLACEMENT_LOOKBACK,
    DISPLACEMENT_RATIO,
)


class DisplacementDetector:

    LOOKBACK = DISPLACEMENT_LOOKBACK

    RATIO = DISPLACEMENT_RATIO

    def detect(self, context):

        result = Displacement()

        candles = context.candles

        if len(candles) < self.LOOKBACK + 1:

            return result

        previous = candles[-self.LOOKBACK-1:-1]

        avg = sum(

            abs(c.close - c.open)

            for c in previous

        ) / len(previous)

        last = candles[-1]

        body = abs(last.close - last.open)

        result.body_size = body

        result.average_body = avg

        if avg == 0:

            return result

        result.ratio = body / avg

        bullish = (

            last.close > last.open

            and

            result.ratio >= self.RATIO

        )

        bearish = (

            last.close < last.open

            and

            result.ratio >= self.RATIO

        )

        result.bullish = bullish

        result.bearish = bearish

        return result