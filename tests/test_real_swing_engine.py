from datetime import datetime

from mss.analysis.real_swing_engine import RealSwingEngine


class Candle:

    def __init__(
        self,
        high,
        low,
    ):

        self.high = high

        self.low = low

        self.time = datetime.now()


def build_candles():

    values = [

        (10, 5),
        (11, 6),
        (13, 7),
        (18, 8),   # Swing High
        (14, 7),
        (12, 6),
        (11, 5),
        (12, 4),   # Swing Low
        (14, 5),
        (16, 6),
        (15, 7),

    ]

    candles = []

    for high, low in values:

        candles.append(

            Candle(

                high,

                low,

            )

        )

    return candles


def test_detect_swings():

    swings = RealSwingEngine().detect(

        build_candles(),

    )

    assert len(swings) >= 2

    highs = [

        s for s in swings

        if s.is_high

    ]

    lows = [

        s for s in swings

        if s.is_low

    ]

    assert len(highs) >= 1

    assert len(lows) >= 1

    assert all(

        s.valid

        for s in swings

    )


def test_empty():

    swings = RealSwingEngine().detect(

        [],

    )

    assert swings == []


def test_none():

    swings = RealSwingEngine().detect(

        None,

    )

    assert swings == []