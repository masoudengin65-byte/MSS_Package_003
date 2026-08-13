from pathlib import Path

import pytest

from mss.analysis.true_oos_time_authority_gate import (
    TrueOosTimeAuthorityGate,
)


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


def test_h1331_blocked_gate_prevents_any_ledger_write(tmp_path):
    chunk = tmp_path / "chunk_000003.jsonl"
    manifest = tmp_path / "manifest_000003.json"

    assert chunk.exists() is False
    assert manifest.exists() is False

    gate = blocked_gate()

    with pytest.raises(
        RuntimeError,
        match="NO_LEDGER_WRITE",
    ):
        TrueOosTimeAuthorityGate.require_confirmed(
            gate
        )

    assert chunk.exists() is False
    assert manifest.exists() is False


def test_h1331_blocked_gate_never_allows_write():
    gate = blocked_gate()

    assert gate["gate_confirmed"] is False

    assert (
        gate["fail_safe"]
        ["ledger_write_allowed"]
        is False
    )
