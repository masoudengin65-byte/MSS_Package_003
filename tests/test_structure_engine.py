from datetime import datetime

from mss.analysis.structure_engine import StructureEngine
from mss.domain.replay_candle import ReplayCandle


def test_structure_engine_returns_analysis():

    candles = [

        ReplayCandle(
            time=datetime.now(),
            open=100,
            high=105,
            low=99,
            close=104,
        ),

        ReplayCandle(
            time=datetime.now(),
            open=104,
            high=108,
            low=103,
            close=107,
        ),

        ReplayCandle(
            time=datetime.now(),
            open=107,
            high=110,
            low=106,
            close=109,
        ),

    ]

    analysis = StructureEngine().analyze(

        symbol="TEST",

        timeframe="M5",

        candles=candles,

    )

    assert analysis is not None

    assert analysis.symbol == "TEST"

    assert analysis.timeframe == "M5"

    assert analysis.structure is not None