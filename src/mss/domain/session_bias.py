"""Session bias result derived from existing analysis outputs."""

from dataclasses import dataclass


@dataclass
class SessionBias:
    current_session: str = "NONE"
    bias: str = "Neutral"
    strength: float = 0.0
    confidence: float = 0.0
    bullish_timeframes: int = 0
    bearish_timeframes: int = 0
    neutral_timeframes: int = 0
    valid: bool = False
