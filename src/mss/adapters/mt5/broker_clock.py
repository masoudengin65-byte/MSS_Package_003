"""Read broker/server time from the latest MT5 symbol tick."""

from datetime import datetime

from mss.adapters.mt5.tick import TickService


class BrokerClock:

    def __init__(self, tick_service=None):
        self.tick_service = tick_service or TickService()

    def now(self, symbol: str) -> datetime | None:
        tick = self.tick_service.get(symbol)

        if tick is None or not tick.time:
            return None

        return datetime.fromtimestamp(tick.time)
