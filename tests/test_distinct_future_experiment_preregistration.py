import hashlib
import json
from pathlib import Path

from mss.analysis.distinct_future_experiment_preregistration import (
    DistinctFutureExperimentPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(encoding="utf-8")
    )


def execution_hashes(builder):
    return {
        relative: hashlib.sha256(
            (ROOT / relative).read_bytes()
        ).hexdigest()
        for relative in builder.REQUIRED_EXECUTION_FILES
    }


def build():
    builder = DistinctFutureExperimentPreregistration()

    return builder.build(
        load("MSS_Sprint92H6_Immutable_Development_Research_Closure.json"),
        load("MSS_Sprint92C2_Extended_Dataset_Manifest.json"),
        execution_hashes(builder),
    )


def test_h7_deterministic():
    assert build() == build()


def test_h7_true_oos_boundary_and_snapshot_locked():
    result = build()

    assert (
        result["source_lineage"]["true_oos_boundary"]["timestamp"]
        == "2026-08-07T17:00:00Z"
    )

    snapshot = result["immutable_snapshot_contract"]

    assert snapshot["required_completed_candles"] == 10000
    assert snapshot["interim_peeking"] is False
    assert snapshot["partial_snapshot_outcome_analysis"] is False
    assert snapshot["write_once"] is True


def test_h7_existing_227_prefix_remains_unanalyzed():
    result = build()

    prefix = result["source_lineage"]["existing_frozen_unanalyzed_prefix"]

    assert prefix["candles"] == 227
    assert prefix["status"] == "FROZEN_NO_ANALYSIS"
    assert prefix["may_form_prefix_of_future_snapshot"] is True

    assert result["audit"]["eligibility_checked"] is False
    assert result["audit"]["outcomes_analyzed"] is False
    assert result["audit"]["true_oos_used"] is False


def test_h7_execution_identity_frozen():
    result = build()

    identity = result["execution_identity"]

    assert identity["baseline_commit"] == "6f2189c"
    assert identity["legacy_c6_binary_identity_claimed"] is False
    assert len(identity["execution_file_sha256"]) == 10

    assert (
        identity["execution_file_sha256"]
        ["src/mss/analysis/smart_money_pipeline.py"]
        == "4d7e87f4e16f1f913098534fe88b80851487f738afa059e09b6575ecff2febc6"
    )

    assert (
        identity["execution_file_sha256"]
        ["src/mss/analysis/confluence_engine.py"]
        == "2c9cfb1598055d0966b691203af4e5990bd5f34607c0cfe89b5f2936d9a92356"
    )


def test_h7_no_consumed_data_can_be_confirmatory():
    result = build()

    governance = result["data_governance"]

    assert governance["development_reuse_for_selection"] is False
    assert governance["validation_reuse_for_confirmation"] is False
    assert governance["research_quarantine_reuse_for_confirmation"] is False
    assert governance["external_history_reuse_for_confirmation"] is False
    assert governance["true_oos_current_status"] == "SEALED"
