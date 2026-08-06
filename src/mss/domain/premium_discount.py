"""Premium and discount analysis result."""

from dataclasses import dataclass


@dataclass
class PremiumDiscount:
    swing_high: float | None = None
    swing_low: float | None = None
    premium_zone: tuple[float, float] | None = None
    discount_zone: tuple[float, float] | None = None
    equilibrium: float | None = None
    current_zone: str = "UNKNOWN"
    distance_to_equilibrium: float | None = None
    valid: bool = False
