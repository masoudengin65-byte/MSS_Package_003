import pytest

from mss.analysis.true_oos_time_authority_gate import (
    TrueOosTimeAuthorityGate,
)


def confirmed_gate():
    return {
        "gate_confirmed": True,
        "sync": {
            "status": "MT5_BAR_SYNCHRONIZED",
        },
        "authority": {
            "time_authority": {
                "status": "BROKER_TIME_DOMAIN_CONFIRMED",
            },
        },
        "fail_safe": {
            "ledger_write_allowed": True,
        },
    }


def blocked_gate():
    return {
        "gate_confirmed": False,
        "sync": {
            "status": "MT5_BAR_SYNC_TIMEOUT",
        },
        "authority": {
            "time_authority": {
                "status": (
                    "BROKER_BAR_SYNCHRONIZATION_UNRESOLVED"
                ),
            },
        },
        "fail_safe": {
            "ledger_write_allowed": False,
        },
    }


def test_h133_confirmed_gate_allows_accrual():
    gate = confirmed_gate()

    assert (
        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )
        is True
    )


def test_h133_blocked_gate_stops_accrual():
    gate = blocked_gate()

    with pytest.raises(
        RuntimeError,
        match="TRUE_OOS_TIME_AUTHORITY_GATE_BLOCKED",
    ):
        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )


def test_h133_blocked_gate_disallows_ledger_write():
    gate = blocked_gate()

    assert gate["gate_confirmed"] is False

    assert (
        gate["fail_safe"]
        ["ledger_write_allowed"]
        is False
    )


def test_h133_confirmed_gate_requires_sync():
    gate = confirmed_gate()

    assert (
        gate["sync"]["status"]
        == "MT5_BAR_SYNCHRONIZED"
    )


def test_h133_confirmed_gate_requires_time_authority():
    gate = confirmed_gate()

    assert (
        gate["authority"]
        ["time_authority"]
        ["status"]
        == "BROKER_TIME_DOMAIN_CONFIRMED"
    )


def test_h133_fail_safe_error_contains_no_ledger_write():
    gate = blocked_gate()

    with pytest.raises(
        RuntimeError,
        match="NO_LEDGER_WRITE",
    ):
        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )
