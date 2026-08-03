from datetime import datetime, timedelta

from mss.analysis.fvg_detector import FairValueGapDetector
from mss.analysis.bos_detector import BOS

from mss.domain.analysis_result import AnalysisResult
from mss.domain.market_context import MarketContext
from mss.domain.candle import Candle
from mss.domain.displacement import Displacement
from mss.domain.order_block import OrderBlock


def test_detect_bullish_fvg():

    t = datetime.now()

    candles = [

        Candle(
            t,
            100,
            101,
            99,
            100,
            0,
            0,
            0,
        ),

        Candle(
            t + timedelta(minutes=1),
            101,
            104,
            101,
            103,
            0,
            0,
            0,
        ),

        Candle(
            t + timedelta(minutes=2),
            105,
            106,
            104,
            105,
            0,
            0,
            0,
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

        bos=BOS(

            direction="BULLISH",

            broken_level=100,

            break_price=105,

            break_time=None,

            reference_index=0,

        ),

        displacement=Displacement(

            bullish=True,

        ),

        order_block=OrderBlock(

            valid=True,

            direction="BULLISH",

        ),

    )

    fvg = FairValueGapDetector().detect(

        context,

        analysis,

    )

    assert fvg is not None

    assert fvg.valid

    assert fvg.direction == "BULLISH"

    assert fvg.low == 101

    assert fvg.high == 104