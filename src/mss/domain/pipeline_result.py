"""
MSS Smart Money Pipeline Result
Sprint 51
"""

from dataclasses import dataclass, field


@dataclass
class PipelineResult:

    #
    # General
    #

    symbol: str = ""

    timeframe: str = ""

    valid: bool = False

    #
    # Swing
    #

    swing_count: int = 0

    previous_high: float | None = None

    last_high: float | None = None

    previous_low: float | None = None

    last_low: float | None = None

    #
    # Structure
    #

    structure_state: str = "UNKNOWN"

    #
    # BOS
    #

    bos_detected: bool = False

    bos_direction: str = ""

    #
    # BOS Debug
    #

    next_bos_level: float | None = None

    current_close: float | None = None

    distance_to_bos: float | None = None

    distance_to_bos_pips: float = 0.0

    bos_status: str = "WAIT"

    bos_progress: float = 0.0

    bos_ready: bool = False

    #
    # CHOCH
    #

    choch_detected: bool = False

    choch_direction: str = ""

    #
    # Liquidity
    #

    liquidity_detected: bool = False

    liquidity_side: str = ""

    #
    # Order Block
    #

    order_block_detected: bool = False

    #
    # Fair Value Gap
    #

    fair_value_gap_detected: bool = False

    #
    # Score
    #

    score: int = 0

    confidence: float = 0.0

    recommendation: str = "WAIT"

    #
    # Debug
    #

    logs: list[str] = field(default_factory=list)

    