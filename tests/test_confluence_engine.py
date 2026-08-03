from mss.analysis.confluence_engine import ConfluenceEngine
from mss.analysis.bos_detector import BOS

from mss.domain.analysis_result import AnalysisResult
from mss.domain.displacement import Displacement
from mss.domain.fair_value_gap import FairValueGap
from mss.domain.order_block import OrderBlock


def test_generate_buy_signal():

    analysis = AnalysisResult(

        structure=object(),

        bos=BOS(

            direction="BULLISH",

            broken_level=105,

            break_price=106,

            break_time=None,

            reference_index=0,

        ),

        displacement=Displacement(

            bullish=True,

        ),

        order_block=OrderBlock(

            direction="BULLISH",

            valid=True,

        ),

        fair_value_gap=FairValueGap(

            direction="BULLISH",

            valid=True,

        ),

    )

    signal = ConfluenceEngine().generate(

        analysis,

    )

    assert signal.valid

    assert signal.signal == "BUY"

    assert signal.confidence == 1.0


def test_generate_wait_signal():

    analysis = AnalysisResult()

    signal = ConfluenceEngine().generate(

        analysis,

    )

    assert not signal.valid

    assert signal.signal == "WAIT"