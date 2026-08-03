"""
MSS Kill Zone Engine
Version : 1.0
Sprint : 15.0
Compatible : v0.26
"""

from datetime import datetime
from datetime import time

from mss.domain.kill_zone import KillZone


class KillZoneEngine:

    LONDON_OPEN_START = time(7, 0)
    LONDON_OPEN_END = time(10, 0)

    NEWYORK_OPEN_START = time(12, 0)
    NEWYORK_OPEN_END = time(15, 0)

    NEWYORK_CLOSE_START = time(18, 0)
    NEWYORK_CLOSE_END = time(20, 0)

    def detect(
        self,
        current_time: datetime,
    ) -> KillZone:

        zone = KillZone()

        if current_time is None:
            return zone

        now = current_time.time()

        if self.LONDON_OPEN_START <= now < self.LONDON_OPEN_END:

            zone.name = "LONDON_OPEN"

            zone.session = "LONDON"

            zone.start = self.LONDON_OPEN_START

            zone.end = self.LONDON_OPEN_END

            zone.description = "London Open Kill Zone"

            zone.active = True

            return zone

        if self.NEWYORK_OPEN_START <= now < self.NEWYORK_OPEN_END:

            zone.name = "NEWYORK_OPEN"

            zone.session = "NEWYORK"

            zone.start = self.NEWYORK_OPEN_START

            zone.end = self.NEWYORK_OPEN_END

            zone.description = "New York Open Kill Zone"

            zone.active = True

            return zone

        if self.NEWYORK_CLOSE_START <= now < self.NEWYORK_CLOSE_END:

            zone.name = "NEWYORK_CLOSE"

            zone.session = "NEWYORK"

            zone.start = self.NEWYORK_CLOSE_START

            zone.end = self.NEWYORK_CLOSE_END

            zone.description = "New York Close Kill Zone"

            zone.active = True

            return zone

        return zone