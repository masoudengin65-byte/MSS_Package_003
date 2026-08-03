"""
MSS Real Swing Engine
Version : 1.0
Sprint : 46.0
Compatible : v0.46
"""

from mss.domain.swing_point import SwingPoint


class RealSwingEngine:

    def detect(
        self,
        candles,
        left=2,
        right=2,
    ):

        swings = []

        if candles is None:

            return swings

        if len(candles) < (left + right + 1):

            return swings

        #
        # Swing High / Low Detection
        #
        for i in range(

            left,

            len(candles) - right,

        ):

            current = candles[i]

            #
            # Swing High
            #
            high = True

            for j in range(

                i - left,

                i + right + 1,

            ):

                if j == i:

                    continue

                if candles[j].high >= current.high:

                    high = False

                    break

            if high:

                point = SwingPoint()

                point.index = i

                point.price = current.high

                point.time = current.time

                point.is_high = True

                point.strength = left + right

                point.valid = True

                swings.append(

                    point

                )

                continue

            #
            # Swing Low
            #
            low = True

            for j in range(

                i - left,

                i + right + 1,

            ):

                if j == i:

                    continue

                if candles[j].low <= current.low:

                    low = False

                    break

            if low:

                point = SwingPoint()

                point.index = i

                point.price = current.low

                point.time = current.time

                point.is_low = True

                point.strength = left + right

                point.valid = True

                swings.append(

                    point

                )

        return swings