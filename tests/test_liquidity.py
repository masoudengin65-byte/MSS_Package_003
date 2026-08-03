from datetime import datetime

from mss.analysis.liquidity_detector import LiquidityDetector
from mss.analysis.swing_detector import Swing

from mss.domain.market_context import MarketContext
from mss.domain.candle import Candle


def test_equal_high():

    swings = [

        Swing(1,"HIGH",100,datetime.now()),

        Swing(2,"LOW",90,datetime.now()),

        Swing(3,"HIGH",100.05,datetime.now()),

    ]

    candle = Candle(

        datetime.now(),

        99,

        100.20,

        98,

        99.80,

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

    result = LiquidityDetector().detect(context)

    assert result.equal_high

    assert result.buy_side_liquidity

    assert result.sweep_high