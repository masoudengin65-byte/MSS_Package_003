from datetime import datetime

from mss.analysis.bos_detector import BOS
from mss.analysis.choch_detector import CHoCHDetector
from mss.analysis.structure_state import (
    MarketStructure,
    StructureState,
)


def test_bearish_choch():

    structure = MarketStructure(

        StructureState.UPTREND,

        105,

        95,

    )

    bos = BOS(

        direction="BEARISH",

        broken_level=95,

        break_price=94,

        break_time=datetime.now(),

        reference_index=10,

    )

    choch = CHoCHDetector().detect(

        structure,

        bos,

    )

    assert choch is not None

    assert choch.direction == "BEARISH"