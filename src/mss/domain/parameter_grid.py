"""
MSS Parameter Grid
Version : 1.0
Sprint : 43.0
Compatible : v0.43
"""

from dataclasses import dataclass, field


@dataclass
class ParameterRange:

    name: str = ""

    start: float = 0.0

    stop: float = 0.0

    step: float = 1.0


@dataclass
class ParameterGrid:

    ranges: list[ParameterRange] = field(

        default_factory=list

    )

    combinations: list[dict] = field(

        default_factory=list

    )

    total_combinations: int = 0

    valid: bool = False