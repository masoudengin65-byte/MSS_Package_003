import json
from pathlib import Path

from mss.analysis.true_oos_ledger_initialization import (
    TrueOosLedgerInitialization,
)
from mss.analysis.true_oos_ledger_store import (
    TrueOosLedgerStore,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(
            encoding="utf-8"
        )
    )


def build():
    return TrueOosLedgerInitialization().build(
        load("MSS_Sprint92H9_Raw_Immutable_True_OOS_Preregistration.json"),
        load("MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"),
    )


def test_h11_deterministic():
    assert build() == build()


def test_h11_boundary_preserved():
    result = build()

    assert (
        result["ledger_identity"]["true_oos_boundary"]
        == "2026-08-12T17:45:00Z"
    )


def test_h11_empty_initial_state():
    result = build()

    state = result["initial_state"]

    assert state["chunk_count"] == 0
    assert state["row_count"] == 0
    assert state["chunks"] == []

    assert (
        state["aggregate_ledger_sha256"]
        == (
            "e3b0c44298fc1c149afbf4c8996fb924"
            "27ae41e4649b934ca495991b7852b855"
        )
    )


def test_h11_canonical_array_is_h9_format():
    row = {
        "time": 1786547100,
        "open": 147.1,
        "high": 147.2,
        "low": 147.0,
        "close": 147.15,
        "tick_volume": 100,
        "spread": 10,
        "real_volume": 0,
    }

    assert TrueOosLedgerStore.canonical_array(row) == [
        1786547100,
        147.1,
        147.2,
        147.0,
        147.15,
        100,
        10,
        0,
    ]

    assert (
        TrueOosLedgerStore.canonical_line(row)
        == (
            "[1786547100,147.1,147.2,147.0,"
            "147.15,100,10,0]\n"
        )
    )


def test_h11_no_market_or_outcome_access():
    result = build()

    audit = result["audit"]

    assert audit["mt5_accessed"] is False
    assert audit["market_data_acquired"] is False
    assert audit["completed_candles_acquired"] == 0
    assert audit["ledger_rows_written"] == 0
    assert audit["strategy_replay_run"] is False
    assert audit["outcomes_analyzed"] is False
