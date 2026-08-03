from datetime import datetime, timedelta

from mss.analysis.order_block_detector import OrderBlockDetector
from mss.analysis.bos_detector import BOS
from mss.domain.analysis_result import AnalysisResult
from mss.domain.candle import Candle
from mss.domain.displacement import Displacement
from mss.domain.liquidity import Liquidity
from mss.domain.market_context import MarketContext


def test_mitigated_order_block():

    t0 = datetime.now()

    candles = [

        Candle(t0,101,102,99,100,0,0,0),

        Candle(t0+timedelta(minutes=1),100,105,99,104,0,0,0),

        Candle(t0+timedelta(minutes=2),99,100,98,99,0,0,0),

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

        liquidity=Liquidity(sweep_low=True),

        displacement=Displacement(bullish=True),

        bos=BOS(

            direction="BULLISH",

            broken_level=100,

            break_price=104,

            break_time=None,

            reference_index=0,

        ),

        choch=None,

    )

    ob = OrderBlockDetector().detect(

        context,

        analysis,

    )

    assert ob.mitigated

    assert not ob.valid