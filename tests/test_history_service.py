from types import SimpleNamespace

import pytest

import mss.adapters.mt5.history as history_module
from mss.adapters.mt5.history import HistoryLoadError, HistoryService


def rate(timestamp=1785960000):
    return {
        "time": timestamp,
        "open": 1.1,
        "high": 1.2,
        "low": 1.0,
        "close": 1.15,
        "tick_volume": 100,
        "spread": 2,
        "real_volume": 50,
    }


class MT5Stub:
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_H1 = 16385
    TIMEFRAME_H4 = 16388

    def __init__(self, responses, exact_symbol=True):
        self.responses = list(responses)
        self.exact_symbol = exact_symbol
        self.requests = []
        self.select_requests = []
        self.error = (1, "Success")

    def symbol_info(self, symbol):
        return SimpleNamespace(name=symbol) if self.exact_symbol else None

    def symbols_get(self, group):
        return [SimpleNamespace(name="EURUSD.a")]

    def symbol_select(self, symbol, selected):
        self.select_requests.append((symbol, selected))
        return True

    def copy_rates_from_pos(self, symbol, timeframe, start, count):
        self.requests.append((symbol, timeframe, start, count))
        response = self.responses.pop(0)
        if response is None:
            self.error = (-1, "Terminal: Call failed")
        else:
            self.error = (1, "Success")
        return response

    def last_error(self):
        return self.error


def test_load_selects_symbol_and_returns_diagnostic_result(monkeypatch):
    mt5 = MT5Stub([[rate()]])
    monkeypatch.setattr(history_module, "mt5", mt5)

    result = HistoryService(retry_delay=0).load("EURUSD", "M15", 500)

    assert result.success
    assert result.resolved_symbol == "EURUSD"
    assert result.symbol_selected
    assert result.requested_count == 500
    assert result.returned_count == 1
    assert mt5.select_requests == [("EURUSD", True)]
    assert mt5.requests == [("EURUSD", 15, 0, 500)]


def test_load_retries_bounded_terminal_failure(monkeypatch):
    mt5 = MT5Stub([None, None, [rate()]])
    monkeypatch.setattr(history_module, "mt5", mt5)

    result = HistoryService(max_attempts=3, retry_delay=0).load(
        "EURUSD", "M15", 500
    )

    assert result.success
    assert result.attempts == 3
    assert len(mt5.requests) == 3


def test_load_resolves_broker_symbol_suffix(monkeypatch):
    mt5 = MT5Stub([[rate()]], exact_symbol=False)
    monkeypatch.setattr(history_module, "mt5", mt5)

    result = HistoryService(retry_delay=0).load("EURUSD", "M15", 500)

    assert result.success
    assert result.resolved_symbol == "EURUSD.a"
    assert mt5.requests[0][0] == "EURUSD.a"


def test_last_raises_clear_diagnostic_instead_of_empty_list(monkeypatch):
    mt5 = MT5Stub([None, None])
    monkeypatch.setattr(history_module, "mt5", mt5)

    with pytest.raises(HistoryLoadError) as error:
        HistoryService(max_attempts=2, retry_delay=0).last(
            "EURUSD", "M15", 500
        )

    result = error.value.result
    assert not result.success
    assert result.attempts == 2
    assert result.error_code == -1
    assert result.error_message == "Terminal: Call failed"
    assert "requested_count=500" in str(error.value)
