import hashlib
import json
from pathlib import Path

import pytest

from mss.analysis.sprint93_confluence_gate_v2_preregistration import (
    Sprint93ConfluenceGateV2Preregistration,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads((ROOT / "reports" / name).read_text(encoding="utf-8"))


def execution_hashes(builder):
    return {
        relative: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
        for relative in builder.REQUIRED_EXECUTION_FILES
    }


def inputs():
    return (
        load("MSS_Sprint92G5_Confluence_Gate_Research_Closure.json"),
        load("MSS_Sprint92H6_Immutable_Development_Research_Closure.json"),
        load("MSS_Sprint92C2_Extended_Dataset_Manifest.json"),
    )


def build():
    builder = Sprint93ConfluenceGateV2Preregistration()
    return builder.build(*inputs(), execution_hashes(builder))


def test_sprint93_2a_is_deterministic_and_distinct_from_g1_g3():
    first = build()
    second = build()
    assert first == second
    assert first["execution_id"] == (
        "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V1"
    )
    identity = first["experiment_identity"]
    assert identity["distinct_hypothesis_version"] is True
    assert identity["distinct_execution_id"] is True
    assert identity["g3_rerun"] is False
    assert first["acceptance"]["g3_failure_preserved"] is True


def test_sprint93_2a_excludes_all_consumed_and_pre_protocol_data():
    result = build()
    source = result["source_governance"]
    assert source["first_eligible_candle_open_utc"] == (
        "2026-08-23T20:15:00Z"
    )
    assert source["historical_backfill"] is False
    assert source["development_reuse"] is False
    assert source["validation_reuse"] is False
    assert source["research_quarantine_reuse"] is False
    assert source["pre_protocol_true_oos_prefix_reuse"] is False
    assert len(source["prior_unanalyzed_prefixes_excluded"]) == 2
    assert all(
        row["eligible_for_sprint93_outcomes"] is False
        for row in source["prior_unanalyzed_prefixes_excluded"]
    )


def test_sprint93_2a_locks_one_strategy_change_only():
    result = build()
    contract = result["candidate_contract"]
    assert contract["no_symbol_specific_rule"] is True
    assert contract["no_direction_filter"] is True
    assert contract["no_score_threshold"] is True
    assert contract["parameter_optimization"] is False
    assert contract["production_pipeline_replacement"] is False
    assert contract["single_change"] == (
        "ENTRY_ELIGIBLE_ONLY_WHEN_EXISTING_CONFLUENCE_ENGINE_"
        "RETURNS_VALID_DIRECTION_MATCHING_BOS"
    )


def test_sprint93_2a_is_paired_forward_shadow_only():
    result = build()
    contract = result["paired_forward_shadow_contract"]
    assert [row["broker_symbol"] for row in contract["symbols"]] == [
        "BITCOIN",
        "ETHEREUM",
    ]
    assert contract["same_completed_candles"] is True
    assert contract["same_decision_timestamps"] is True
    assert contract["order_check_allowed"] is False
    assert contract["order_send_allowed"] is False
    assert contract["real_order_allowed"] is False


def test_sprint93_2a_has_a_non_extendable_research_gate():
    result = build()
    shadow = result["paired_forward_shadow_contract"]
    gate = result["research_evaluation_gate"]
    assert shadow["timebox_calendar_days"] == 45
    assert shadow["extension_after_timebox"] is False
    assert gate["minimum_candidate_closed_trades_pooled"] == 50
    assert gate["minimum_candidate_closed_trades_per_symbol"] == 15
    assert gate["target_candidate_profit_factor"] == 1.10
    assert gate["target_candidate_win_rate"] == 0.36
    assert gate["decision_if_sample_insufficient_at_timebox"] == (
        "CLOSE_INCONCLUSIVE_NO_EXTENSION_NO_PRODUCTION_CHANGE"
    )


def test_sprint93_2a_freezes_execution_and_changes_no_runtime_behavior():
    result = build()
    identity = result["execution_identity"]
    assert set(identity["execution_file_sha256"]) == set(
        Sprint93ConfluenceGateV2Preregistration.REQUIRED_EXECUTION_FILES
    )
    assert all(len(value) == 64 for value in identity["execution_file_sha256"].values())
    assert result["audit"]["mt5_accessed"] is False
    assert result["audit"]["strategy_replay_run"] is False
    assert result["audit"]["outcomes_analyzed"] is False
    assert result["audit"]["production_behavior_changed"] is False
    assert result["audit"]["order_check_called"] is False
    assert result["audit"]["order_send_called"] is False
    assert result["future_release_gate_not_authorized_here"]["real_money_authorized"] is False


def test_sprint93_2a_rejects_attempt_to_relabel_g3_as_authorized():
    g5, h6, c2 = inputs()
    g5["governance"]["g3_rerun_authorized"] = True
    builder = Sprint93ConfluenceGateV2Preregistration()
    with pytest.raises(RuntimeError, match="G3 rerun"):
        builder.build(g5, h6, c2, execution_hashes(builder))


def test_sprint93_2a_rejects_incomplete_execution_identity():
    g5, h6, c2 = inputs()
    builder = Sprint93ConfluenceGateV2Preregistration()
    hashes = execution_hashes(builder)
    hashes.pop("src/mss/analysis/confluence_engine.py")
    with pytest.raises(RuntimeError, match="file universe"):
        builder.build(g5, h6, c2, hashes)


def test_sprint93_2a_committed_report_preserves_outcome_blind_audit():
    report = load("MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration.json")
    assert report["schema_version"] == (
        Sprint93ConfluenceGateV2Preregistration.VERSION
    )
    assert report["audit"]["deterministic_rebuild"] is True
    assert report["audit"]["mt5_accessed"] is False
    assert report["audit"]["outcomes_analyzed"] is False
    assert report["audit"]["order_send_called"] is False
    assert set(report["source_file_sha256"]) == {"g5", "h6", "c2"}
