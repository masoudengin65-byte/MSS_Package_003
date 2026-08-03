from datetime import datetime

from mss.analysis.bos_detector import BOSDetector
from mss.analysis.swing_detector import Swing
from mss.domain.market_context import MarketContext
from mss.domain.candle import Candle


def test_bullish_bos():

    swings = [

        Swing(1, "LOW", 90, datetime.now()),

        Swing(2, "HIGH", 100, datetime.now()),

        Swing(3, "LOW", 95, datetime.now()),

        Swing(4, "HIGH", 105, datetime.now()),

    ]

    candle = Candle(

        datetime.now(),

        104,

        106,

        103,

        106,

        0,

        0,

        0,
    )

    context = MarketContext(

        symbol="TEST",

        timeframe=None,

        candles=[candle],

        swings=swings,

        last_closed_candle=candle,
    )

    bos = BOSDetector().detect(context)

    assert bos is not None

    assert bos.direction == "BULLISH"

    assert bos.break_price == 106