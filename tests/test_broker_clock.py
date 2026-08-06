from types import SimpleNamespace
from datetime import datetime

from mss.adapters.mt5.broker_clock import BrokerClock


class TickServiceStub:
    def __init__(self, tick):
        self.tick = tick

    def get(self, symbol):
        assert symbol == "EURUSD"
        return self.tick


def test_broker_clock_reads_tick_timestamp():
    timestamp = 1767268800
    clock = BrokerClock(TickServiceStub(SimpleNamespace(time=timestamp)))

    assert clock.now("EURUSD") == datetime.fromtimestamp(timestamp)


def test_broker_clock_handles_missing_tick():
    clock = BrokerClock(TickServiceStub(None))

    assert clock.now("EURUSD") is None
