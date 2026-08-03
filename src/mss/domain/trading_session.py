"""
MSS Trading Session
Version : 1.0
Sprint : 14.0
Compatible : v0.25
"""

from dataclasses import dataclass
from datetime import time


@dataclass
class TradingSession:

    name: str = ""

    start: time | None = None

    end: time | None = None

    active: bool = False