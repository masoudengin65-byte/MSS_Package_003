"""
MSS Session Engine
Version : 1.1
Sprint : 14.0
Compatible : v0.29
"""

from datetime import datetime, time

from mss.domain.trading_session import TradingSession


class SessionEngine:

    ASIA_START = time(0, 0)
    ASIA_END = time(8, 0)

    LONDON_START = time(8, 0)
    LONDON_END = time(13, 0)

    NEWYORK_START = time(13, 0)
    NEWYORK_END = time(21, 0)

    def detect(
        self,
        current_time: datetime,
    ) -> TradingSession:

        session = TradingSession()

        if current_time is None:
            return session

        now = current_time.time()

        if self.ASIA_START <= now < self.ASIA_END:

            session.name = "ASIA"
            session.start = self.ASIA_START
            session.end = self.ASIA_END
            session.active = True

            return session

        if self.LONDON_START <= now < self.LONDON_END:

            session.name = "LONDON"
            session.start = self.LONDON_START
            session.end = self.LONDON_END
            session.active = True

            return session

        if self.NEWYORK_START <= now < self.NEWYORK_END:

            session.name = "NEWYORK"
            session.start = self.NEWYORK_START
            session.end = self.NEWYORK_END
            session.active = True

            return session

        return session