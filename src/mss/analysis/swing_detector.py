"""
MSS Swing Detector

Detects valid swing highs and swing lows from OHLC candles.
"""

from dataclasses import dataclass
from typing import List

from mss.domain.candle import Candle


@dataclass
class Swing:

    index: int
    kind: str
    price: float
    time: object


class SwingDetector:

    def __init__(self, fractal_size: int = 2):

        if fractal_size < 1:
            raise ValueError("fractal_size must be >= 1")

        self.fractal = fractal_size

    def find(self, candles: List[Candle]) -> List[Swing]:

        swings: List[Swing] = []

        left = self.fractal
        right = self.fractal

        if len(candles) < left + right + 1:
            return swings

        for i in range(left, len(candles) - right):

            c = candles[i]

            high_ok = True
            low_ok = True

            for j in range(1, left + 1):

                if c.high <= candles[i - j].high:
                    high_ok = False

                if c.low >= candles[i - j].low:
                    low_ok = False

            for j in range(1, right + 1):

                if c.high <= candles[i + j].high:
                    high_ok = False

                if c.low >= candles[i + j].low:
                    low_ok = False

            if high_ok:

                swings.append(
                    Swing(
                        index=i,
                        kind="HIGH",
                        price=c.high,
                        time=c.time,
                    )
                )

            elif low_ok:

                swings.append(
                    Swing(
                        index=i,
                        kind="LOW",
                        price=c.low,
                        time=c.time,
                    )
                )

        return swings