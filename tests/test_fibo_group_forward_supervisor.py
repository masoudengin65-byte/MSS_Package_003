from dataclasses import dataclass
from pathlib import Path

import pytest

from mss.analysis.fibo_group_forward_activation import (
    FiboVerifiedActivation,
    _FIBO_VERIFIED_ACTIVATION_MARKER,
)
from mss.analysis.fibo_group_forward_supervisor import (
    EXPECTED_SERVER,
    FiboMt5ReadOnlySession,
    RELEASE_CYCLE,
    run_fibo_forward_supervisor,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal


def _rates(current: int):
    return [
        {
            "time": current - (500 - index) * 900,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "tick_volume": 1,
            "spread": 1,
            "real_volume": 0,
        }
        for index in range(501)
    ]


@dataclass
class _Terminal:
    connected: bool = True


@dataclass
class _Account:
    server: str = EXPECTED_SERVER
    trade_mode: int = 0


@dataclass
class _Info:
    point: float = 0.01


class _FakeMt5:
    TIMEFRAME_M15 = 15
    ACCOUNT_TRADE_MODE_DEMO = 0

    def __init__(self, server=EXPECTED_SERVER):
        self.server = server
        self.initialized = False
        self.shutdown_called = False
        self.selected = []

    def initialize(self, **_kwargs):
        self.initialized = True
        return True

    def shutdown(self):
        self.shutdown_called = True

    def terminal_info(self):
        return _Terminal()

    def account_info(self):
        return _Account(server=self.server)

    def symbol_select(self, symbol, _selected):
        self.selected.append(symbol)
        return True

    def symbol_info(self, _symbol):
        return _Info()

    def copy_rates_from_pos(self, _symbol, _timeframe, _start, _count):
        return _rates(501 * 900)


def test_fibo_session_requires_connected_demo_server():
    fake = _FakeMt5(server="Alpari-Demo")
    with pytest.raises(RuntimeError, match="required FIBO demo server"):
        with FiboMt5ReadOnlySession(mt5_module=fake):
            pass
    assert fake.shutdown_called


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return None

    def capture_pair(self, boundary):
        from mss.analysis.fibo_group_paired_forward_runtime import FiboBoundarySnapshot

        rates = _rates(boundary)
        return tuple(
            FiboBoundarySnapshot(
                canonical_symbol=canonical,
                broker_symbol=broker,
                account_server=EXPECTED_SERVER,
                current_bar_epoch=boundary,
                rates=rates,
            )
            for canonical, broker in (("BTCUSD", "BTC"), ("ETHUSD", "ETH"))
        )


def test_supervisor_writes_one_shadow_boundary_and_never_resumes(tmp_path: Path):
    assert RELEASE_CYCLE == "S93.3F-FIBO-FORWARD-REFREEZE-20260916D"
    start = 501 * 900
    clock = {"value": float(start - 1)}

    def now():
        return clock["value"]

    def sleep(seconds):
        clock["value"] += seconds

    activation = FiboVerifiedActivation(
        manifest_sha256="a" * 64,
        first_eligible_epoch=start,
        exclusive_end_epoch=start + 900,
        _verification_marker=_FIBO_VERIFIED_ACTIVATION_MARKER,
    )
    journal = tmp_path / "fibo.jsonl"
    result = run_fibo_forward_supervisor(
        activation=activation,
        journal_path=journal,
        session_factory=_FakeSession,
        utc_now=now,
        sleep=sleep,
    )

    assert result["completed_boundaries"] == 1
    assert result["real_order_send_allowed"] is False
    assert ShadowTradeJournal.verify(journal)["valid"] is True
    clock["value"] = float(start - 1)
    with pytest.raises(RuntimeError, match="pristine journals"):
        run_fibo_forward_supervisor(
            activation=activation,
            journal_path=journal,
            session_factory=_FakeSession,
            utc_now=now,
            sleep=sleep,
        )
