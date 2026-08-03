from datetime import datetime

from mss.analysis.order_block_detector import OrderBlockDetector
from mss.analysis.bos_detector import BOS
from mss.domain.analysis_result import AnalysisResult
from mss.domain.displacement import Displacement
from mss.domain.liquidity import Liquidity
from mss.domain.market_context import MarketContext
from mss.domain.candle import Candle


def test_detector_returns_bullish_order_block():

    candles = [

        Candle(
            datetime.now(),
            101,
            102,
            99,
            100,
            0,0,0
        ),

        Candle(
            datetime.now(),
            100,
            105,
            99,
            104,
            0,0,0
        ),

    ]

    context = MarketContext(

        symbol="TEST",

        timeframe=None,

        candles=candles,

        swings=[],

        last_closed_candle=candles[-1],

    )

    analysis = AnalysisResult(

        symbol="TEST",

        timeframe=None,

        structure=None,

        liquidity=Liquidity(
    sweep_low=True,
),

         
        displacement=Displacement(bullish=True),

        bos=BOS(

            direction="BULLISH",

            broken_level=100,

            break_price=104,

            break_time=None,

            reference_index=1,

        ),

        choch=None,

    )

    ob = OrderBlockDetector().detect(

        context,

        analysis,

    )

    assert ob.valid

    assert ob.direction == "BULLISH"

    assert ob.close < ob.open