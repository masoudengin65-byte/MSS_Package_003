"""
Professional BOS Detector
Compatible with:
- Legacy Swing (kind)
- Real SwingPoint (is_high / is_low)
"""

from dataclasses import dataclass

from mss.domain.market_context import MarketContext


@dataclass
class BOS:

    direction: str

    broken_level: float

    break_price: float

    break_time: object

    reference_index: int


class BOSDetector:

    def detect(
        self,
        context: MarketContext,
    ):

        swings = context.swings

        if len(swings) < 4:
            return None

        close = context.last_closed_candle.close

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

        if len(highs) < 2:
            return None

        if len(lows) < 2:
            return None

        last_high = highs[-1]
        prev_high = highs[-2]

        last_low = lows[-1]
        prev_low = lows[-2]

        #
        # Bullish BOS
        #

        bullish_structure = (

            last_high.price > prev_high.price

            and

            last_low.price > prev_low.price

        )

        if bullish_structure:

            if close > last_high.price:

                return BOS(

                    direction="BULLISH",

                    broken_level=last_high.price,

                    break_price=close,

                    break_time=context.last_closed_candle.time,

                    reference_index=last_high.index,

                )

        #
        # Bearish BOS
        #

        bearish_structure = (

            last_high.price < prev_high.price

            and

            last_low.price < prev_low.price

        )

        if bearish_structure:

            if close < last_low.price:

                return BOS(

                    direction="BEARISH",

                    broken_level=last_low.price,

                    break_price=close,

                    break_time=context.last_closed_candle.time,

                    reference_index=last_low.index,

                )

        return None