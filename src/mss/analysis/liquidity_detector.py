"""
Professional Liquidity Detector
Compatible with:
- Legacy Swing (kind)
- Real SwingPoint (is_high / is_low)
"""

from mss.domain.liquidity import Liquidity

from mss.config.settings import (
    LIQUIDITY_TOLERANCE,
)


class LiquidityDetector:

    TOLERANCE = LIQUIDITY_TOLERANCE

    def detect(self, context):

        result = Liquidity()

        swings = context.swings

        candles = context.candles

        if len(swings) < 2:

            return result

        highs = []

        lows = []

        #
        # Compatible with both Swing models
        #

        for s in swings:

            if hasattr(s, "is_high"):

                if s.is_high:

                    highs.append(s)

                if s.is_low:

                    lows.append(s)

                continue

            if hasattr(s, "kind"):

                if s.kind == "HIGH":

                    highs.append(s)

                elif s.kind == "LOW":

                    lows.append(s)

        if not candles:

            return result

        last = candles[-1]

        #
        # Equal High
        #

        if len(highs) >= 2:

            h1 = highs[-2]

            h2 = highs[-1]

            if abs(h1.price - h2.price) <= self.TOLERANCE:

                result.equal_high = True

                result.buy_side_liquidity = True

                result.level = h2.price

                if (

                    last.high > h2.price

                    and

                    last.close < h2.price

                ):

                    result.sweep_high = True

        #
        # Equal Low
        #

        if len(lows) >= 2:

            l1 = lows[-2]

            l2 = lows[-1]

            if abs(l1.price - l2.price) <= self.TOLERANCE:

                result.equal_low = True

                result.sell_side_liquidity = True

                result.level = l2.price

                if (

                    last.low < l2.price

                    and

                    last.close > l2.price

                ):

                    result.sweep_low = True

        return result