"""
Change Of Character Detector
"""

from dataclasses import dataclass

from mss.analysis.bos_detector import BOS
from mss.analysis.structure_state import (
    MarketStructure,
    StructureState,
)


@dataclass
class CHoCH:

    direction: str

    break_time: object

    level: float


class CHoCHDetector:

    def detect(

        self,

        structure: MarketStructure,

        bos: BOS | None,

    ):

        if bos is None:

            return None

        if (

            structure.state == StructureState.UPTREND

            and

            bos.direction == "BEARISH"

        ):

            return CHoCH(

                direction="BEARISH",

                break_time=bos.break_time,

                level=bos.broken_level,

            )

        if (

            structure.state == StructureState.DOWNTREND

            and

            bos.direction == "BULLISH"

        ):

            return CHoCH(

                direction="BULLISH",

                break_time=bos.break_time,

                level=bos.broken_level,

            )

        return None