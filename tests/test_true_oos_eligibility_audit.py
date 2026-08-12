import json
from pathlib import Path

from mss.analysis.true_oos_eligibility_audit import (
    TrueOosEligibilityAudit,
)


ROOT = Path(__file__).resolve().parents[1]

PROTOCOL = (
    ROOT
    / "reports"
    / "MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"
)


def protocol():
    return json.loads(
        PROTOCOL.read_text(encoding="utf-8")
    )


def make_rows(count):
    start = TrueOosEligibilityAudit.LOCKED_BOUNDARY_EPOCH

    rows = []

    for index in range(count):
        timestamp = start + index * 900

        rows.append(
            {
                "time": timestamp,
                "open": 150.0,
                "high": 150.1,
                "low": 149.9,
                "close": 150.0,
                "tick_volume": 100,
                "spread": 10,
                "real_volume": 0,
            }
        )

    return rows


def test_h8_1_completed_filter_uses_locked_boundary():
    rows = make_rows(10)

    current_boundary = (
        TrueOosEligibilityAudit.LOCKED_BOUNDARY_EPOCH
        + 10 * 900
    )

    eligible = TrueOosEligibilityAudit.eligible_completed(
        rows,
        current_boundary,
    )

    assert len(eligible) == 10

    assert (
        int(eligible[0]["time"])
        == TrueOosEligibilityAudit.LOCKED_BOUNDARY_EPOCH
    )


def test_h8_1_fewer_than_227_cannot_pass_prefix():
    result = TrueOosEligibilityAudit.prefix_audit(
        make_rows(100)
    )

    assert result["available"] is False
    assert result["match"] is False


def test_h8_1_protocol_contract_locked():
    p = protocol()

    assert (
        p["source_lineage"]["true_oos_boundary"]["timestamp"]
        == TrueOosEligibilityAudit.LOCKED_BOUNDARY_ISO
    )

    assert (
        p["immutable_snapshot_contract"]
        ["required_completed_candles"]
        == TrueOosEligibilityAudit.REQUIRED_CANDLES
    )


def test_h8_1_does_not_authorize_replay_from_protocol():
    p = protocol()

    assert (
        p["authoritative_execution_contract"]
        ["eligibility_check_runs_after_h7_commit_only"]
        is True
    )

    assert (
        p["data_governance"]["true_oos_current_status"]
        == "SEALED"
    )
