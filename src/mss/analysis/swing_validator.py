"""
MSS Swing Validator

Removes weak market structure swings.
"""

from typing import List

from mss.analysis.swing_detector import Swing


class SwingValidator:

    def __init__(
        self,
        min_price_distance=1.0,
        min_bar_distance=3,
    ):

        self.min_price_distance = min_price_distance

        self.min_bar_distance = min_bar_distance

    def validate(
        self,
        swings: List[Swing],
    ) -> List[Swing]:

        if len(swings) < 2:

            return swings

        valid = [swings[0]]

        for current in swings[1:]:

            last = valid[-1]

            price_distance = abs(
                current.price - last.price
            )

            bar_distance = (
                current.index - last.index
            )

            if (
                price_distance
                < self.min_price_distance
            ):
                continue

            if (
                bar_distance
                < self.min_bar_distance
            ):
                continue

            valid.append(current)

        return valid