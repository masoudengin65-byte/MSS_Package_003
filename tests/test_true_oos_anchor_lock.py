import json
from pathlib import Path

from mss.analysis.true_oos_anchor_lock import (
    TrueOosAnchorLock,
)


ROOT = Path(__file__).resolve().parents[1]

H9 = (
    ROOT
    / "reports"
    / "MSS_Sprint92H9_Raw_Immutable_True_OOS_Preregistration.json"
)


def protocol():
    return json.loads(
        H9.read_text(encoding="utf-8")
    )


def test_h10_deterministic():
    builder = TrueOosAnchorLock()
    h9 = protocol()

    anchor = 1786546800

    assert builder.build(h9, anchor) == builder.build(h9, anchor)


def test_h10_locks_new_boundary():
    result = TrueOosAnchorLock().build(
        protocol(),
        1786546800,
    )

    assert result["acceptance"]["new_boundary_locked"] is True

    assert (
        result["anchor"]["first_eligible_completed_candle_rule"]
        == (
            "CANDLE_OPEN_TIMESTAMP_GREATER_THAN_OR_EQUAL_TO_"
            "THE_LOCKED_H10_BOUNDARY"
        )
    )


def test_h10_rejects_non_m15_boundary():
    builder = TrueOosAnchorLock()

    try:
        builder.build(
            protocol(),
            1786546801,
        )
    except RuntimeError as exc:
        assert "15 minutes" in str(exc)
    else:
        raise AssertionError("non-M15 anchor was accepted")


def test_h10_writes_no_true_oos_rows():
    result = TrueOosAnchorLock().build(
        protocol(),
        1786546800,
    )

    assert (
        result["data_access"]
        ["completed_true_oos_candles_acquired"]
        == 0
    )

    assert (
        result["data_access"]["true_oos_ledger_rows_written"]
        == 0
    )


def test_h10_no_replay_or_outcome_access():
    result = TrueOosAnchorLock().build(
        protocol(),
        1786546800,
    )

    assert result["audit"]["strategy_replay_run"] is False
    assert result["audit"]["outcomes_analyzed"] is False
    assert result["audit"]["orders_sent"] is False

    assert (
        result["governance"]["anchor_replacement_prohibited"]
        is True
    )
