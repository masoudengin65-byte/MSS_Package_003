from mss.engine.signal_engine import SignalEngine
from mss.domain.trade_context import TradeContext
from mss.domain.analysis_result import AnalysisResult
from mss.analysis.structure_state import (
    MarketStructure,
    StructureState,
)
from mss.analysis.bos_detector import BOS
from mss.domain.liquidity import Liquidity
from mss.domain.displacement import Displacement


def test_signal_from_bos():

    structure = MarketStructure(

        StructureState.UPTREND,

        105,

        95,

    )

    bos = BOS(

        direction="BULLISH",

        broken_level=105,

        break_price=106,

        break_time=None,

        reference_index=10,

    )

    analysis = AnalysisResult(

        symbol="TEST",

        timeframe=None,

        structure=structure,

        liquidity=Liquidity(),

        displacement=Displacement(),

        bos=bos,

        choch=None,

    )

    context = TradeContext(

        symbol="TEST",

        timeframe=None,

        analysis=analysis,

    )

    signal = SignalEngine().generate(context)

    assert signal.signal == "BULLISH"

    assert signal.reason == "BOS"