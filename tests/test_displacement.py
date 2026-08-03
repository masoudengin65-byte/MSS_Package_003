from datetime import datetime

from mss.analysis.displacement_detector import DisplacementDetector
from mss.domain.market_context import MarketContext
from mss.domain.candle import Candle


def candle(o, c):

    return Candle(

        datetime.now(),

        o,

        max(o, c),

        min(o, c),

        c,

        0,

        0,

        0,

    )


def test_displacement():

    candles = []

    for _ in range(20):

        candles.append(

            candle(100,100.4)

        )

    candles.append(

        candle(100,102)

    )

    context = MarketContext(

        symbol="TEST",

        timeframe=None,

        candles=candles,

        swings=[],

        last_closed_candle=candles[-1],

    )

    result = DisplacementDetector().detect(context)

    assert result.bullish

    assert result.ratio >= 2