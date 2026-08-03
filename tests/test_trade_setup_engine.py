from mss.analysis.trade_setup_engine import TradeSetupEngine
from mss.analysis.bos_detector import BOS

from mss.domain.analysis_result import AnalysisResult
from mss.domain.displacement import Displacement
from mss.domain.fair_value_gap import FairValueGap
from mss.domain.order_block import OrderBlock


def test_build_buy_trade_setup():

    analysis = AnalysisResult(

        structure=object(),

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

            direction="BULLISH",

            high=100,

            low=95,

            valid=True,

        ),

        fair_value_gap=FairValueGap(

            direction="BULLISH",

            valid=True,

        ),

    )

    setup = TradeSetupEngine().build(

        analysis,

    )

    assert setup.valid

    assert setup.direction == "BUY"

    assert setup.entry == 100

    assert setup.stop_loss == 95

    assert setup.take_profit_1 == 110

    assert setup.take_profit_2 == 115

    assert setup.rr == 3.0


def test_build_wait_setup():

    analysis = AnalysisResult()

    setup = TradeSetupEngine().build(

        analysis,

    )

    assert not setup.valid