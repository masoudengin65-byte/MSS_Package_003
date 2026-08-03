"""
MSS Kill Zone
Version : 1.0
Sprint : 15.0
Compatible : v0.26
"""

from dataclasses import dataclass
from datetime import time


@dataclass
class KillZone:

    name: str = ""

    start: time | None = None

    end: time | None = None

    active: bool = False

    session: str = ""

    description: str = ""