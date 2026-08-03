from datetime import datetime, timedelta

from mss.analysis.fvg_validator import FairValueGapValidator
from mss.analysis.bos_detector import BOS

from mss.domain.analysis_result import AnalysisResult
from mss.domain.candle import Candle
from mss.domain.displacement import Displacement
from mss.domain.fair_value_gap import FairValueGap
from mss.domain.liquidity import Liquidity
from mss.domain.market_context import MarketContext
from mss.domain.order_block import OrderBlock


def test_valid_bullish_fvg():

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
            103,
            101,
            102,
            0,
            0,
            0,
        ),

        Candle(
            t + timedelta(minutes=2),
            104,
            105,
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

        liquidity=Liquidity(
            sweep_low=True,
        ),

        displacement=Displacement(
            bullish=True,
        ),

        bos=BOS(

            direction="BULLISH",

            broken_level=101,

            break_price=105,

            break_time=None,

            reference_index=0,

        ),

        order_block=OrderBlock(

            direction="BULLISH",

            valid=True,

        ),

    )

    fvg = FairValueGap(

        direction="BULLISH",

        low=101,

        high=104,

        candle_time=candles[1].time,

        valid=True,

    )

    result = FairValueGapValidator().validate(

        context,

        analysis,

        fvg,

    )

    assert result.valid

    assert not result.filled