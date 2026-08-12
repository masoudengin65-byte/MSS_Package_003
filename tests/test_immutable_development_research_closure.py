import json
from pathlib import Path

from mss.analysis.immutable_development_research_closure import (
    ImmutableDevelopmentResearchClosure,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(encoding="utf-8")
    )


def build():
    return ImmutableDevelopmentResearchClosure().build(
        load("MSS_Sprint92H5_Immutable_Development_Outcome_Analysis.json"),
        load("MSS_Sprint92C6_Research_Closure_True_OOS_Preregistration.json"),
        load("MSS_Sprint92E8_External_Historical_Validation_Closure.json"),
        load("MSS_Sprint92G5_Confluence_Gate_Research_Closure.json"),
    )


def test_h6_deterministic():
    assert build() == build()


def test_h6_preserves_true_oos_seal():
    result = build()

    assert (
        result["future_experiment_governance"]["true_future_oos_status"]
        == "SEALED"
    )
    assert (
        result["legacy_true_oos_protocol"]
        ["automatic_execution_authorized_by_h6"]
        is False
    )
    assert (
        result["legacy_true_oos_protocol"]
        ["eligibility_check_authorized_by_h6"]
        is False
    )


def test_h6_respects_h5_usdjpy_status():
    result = build()

    assert (
        result["immutable_development_closure"]
        ["final_classifications"]["USDJPY"]
        == "DEVELOPMENT_PROMISING_NOT_CONFIRMED"
    )

    assert (
        result["production_governance"]
        ["symbol_filter_change_authorized"]
        is False
    )


def test_h6_requires_distinct_future_preregistration():
    result = build()

    governance = result["future_experiment_governance"]

    assert governance["next_experiment_requires_new_preregistration"] is True
    assert governance["next_experiment_must_be_distinct"] is True
    assert governance["new_execution_id_required"] is True

    assert result["audit"]["strategy_replay_run"] is False
    assert result["audit"]["mt5_accessed"] is False
    assert result["audit"]["validation_accessed"] is False
    assert result["audit"]["true_future_oos_used"] is False
