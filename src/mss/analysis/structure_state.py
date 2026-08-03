"""
Market Structure State

Determines current market structure from validated swings.
"""

from dataclasses import dataclass
from enum import Enum


class StructureState(Enum):

    UNKNOWN = "UNKNOWN"

    UPTREND = "UPTREND"

    DOWNTREND = "DOWNTREND"

    RANGE = "RANGE"


@dataclass
class MarketStructure:

    state: StructureState

    last_high: float | None

    last_low: float | None


class StructureStateEngine:

    def detect(self, swings):

        if not swings:

            return MarketStructure(

                StructureState.UNKNOWN,

                None,

                None,

            )

        #
        # Compatible with both
        # Old Swing(kind)
        # New SwingPoint(is_high/is_low)
        #

        highs = []

        lows = []

        for s in swings:

            #
            # New SwingPoint
            #

            if hasattr(s, "is_high"):

                if s.is_high:

                    highs.append(s)

                if s.is_low:

                    lows.append(s)

                continue

            #
            # Legacy Swing
            #

            if hasattr(s, "kind"):

                if s.kind == "HIGH":

                    highs.append(s)

                elif s.kind == "LOW":

                    lows.append(s)

        if len(highs) < 2 or len(lows) < 2:

            return MarketStructure(

                StructureState.UNKNOWN,

                None,

                None,

            )

        h1 = highs[-2]

        h2 = highs[-1]

        l1 = lows[-2]

        l2 = lows[-1]

        #
        # Uptrend
        #

        if (

            h2.price > h1.price

            and

            l2.price > l1.price

        ):

            return MarketStructure(

                StructureState.UPTREND,

                h2.price,

                l2.price,

            )

        #
        # Downtrend
        #

        if (

            h2.price < h1.price

            and

            l2.price < l1.price

        ):

            return MarketStructure(

                StructureState.DOWNTREND,

                h2.price,

                l2.price,

            )

        #
        # Range
        #

        return MarketStructure(

            StructureState.RANGE,

            h2.price,

            l2.price,

        )