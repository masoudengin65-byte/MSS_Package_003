"""
MSS Swing Point
Version : 1.0
Sprint : 46.0
Compatible : v0.46
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class SwingPoint:

    index: int = 0

    price: float = 0.0

    time: datetime | None = None

    is_high: bool = False

    is_low: bool = False

    strength: int = 0

    valid: bool = False