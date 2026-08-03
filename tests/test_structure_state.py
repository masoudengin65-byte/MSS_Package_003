from datetime import datetime

from mss.analysis.swing_detector import Swing
from mss.analysis.structure_state import (
    StructureState,
    StructureStateEngine,
)


def test_uptrend():

    swings = [

        Swing(1,"LOW",90,datetime.now()),

        Swing(2,"HIGH",100,datetime.now()),

        Swing(3,"LOW",95,datetime.now()),

        Swing(4,"HIGH",105,datetime.now()),

    ]

    state = StructureStateEngine().detect(swings)

    assert state.state == StructureState.UPTREND