"""
MSS Setup Score
Version : 1.0
Sprint : 45.0
Compatible : v0.45
"""

from dataclasses import dataclass


@dataclass
class SetupScore:

    bos: int = 0

    choch: int = 0

    order_block: int = 0

    fair_value_gap: int = 0

    liquidity: int = 0

    kill_zone: int = 0

    higher_timeframe: int = 0

    score: int = 0

    confidence: float = 0.0

    stars: int = 0

    valid: bool = False