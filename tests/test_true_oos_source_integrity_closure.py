import json
from pathlib import Path

from mss.analysis.true_oos_source_integrity_closure import (
    TrueOosSourceIntegrityClosure,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(encoding="utf-8")
    )


def build():
    return TrueOosSourceIntegrityClosure().build(
        load("MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"),
        load("MSS_Sprint92H8_1_True_OOS_Eligibility_Audit.json"),
    )


def test_h8_2_deterministic():
    assert build() == build()


def test_h8_2_closes_legacy_experiment_as_data_integrity_blocked():
    result = build()

    assert (
        result["closed_experiment"]["status"]
        == "DATA_INTEGRITY_BLOCKED"
    )

    assert (
        result["closed_experiment"]["strategy_outcome_status"]
        == "NOT_EVALUATED"
    )


def test_h8_2_preserves_no_outcome_inference():
    result = build()

    science = result["scientific_interpretation"]

    assert science["strategy_failure_claimed"] is False
    assert science["strategy_success_claimed"] is False
    assert science["true_oos_performance_claimed"] is False
    assert science["h7_confirmation_test_completed"] is False


def test_h8_2_requires_new_protocol_and_raw_immutability():
    result = build()

    nxt = result["next_experiment_requirements"]

    assert nxt["new_execution_id_required"] is True
    assert nxt["new_preregistration_required"] is True
    assert nxt["new_true_oos_boundary_required"] is True
    assert nxt["raw_candle_immutability_required"] is True
    assert nxt["write_once_snapshot_storage_required"] is True


def test_h8_2_no_mt5_replay_or_production_change():
    result = build()

    audit = result["audit"]

    assert audit["mt5_accessed"] is False
    assert audit["strategy_replay_run"] is False
    assert audit["outcomes_analyzed"] is False
    assert audit["production_behavior_changed"] is False
