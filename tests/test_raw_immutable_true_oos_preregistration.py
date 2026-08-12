import json
from pathlib import Path

from mss.analysis.raw_immutable_true_oos_preregistration import (
    RawImmutableTrueOosPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(encoding="utf-8")
    )


def build():
    return RawImmutableTrueOosPreregistration().build(
        load("MSS_Sprint92H7_Distinct_Future_True_OOS_Preregistration.json"),
        load("MSS_Sprint92H8_2_True_OOS_Source_Integrity_Closure.json"),
    )


def test_h9_deterministic():
    assert build() == build()


def test_h9_uses_new_execution_identity():
    result = build()

    assert (
        result["execution_id"]
        == "MSS_92H9_USDJPY_RAW_IMMUTABLE_TRUE_OOS_V2"
    )

    assert result["legacy_experiment"]["reuse_prohibited"] is True


def test_h9_boundary_must_be_after_preregistration():
    result = build()

    boundary = result["new_boundary_contract"]

    assert boundary["exact_timestamp_locked_in_h9"] is False

    assert (
        boundary["exact_timestamp_must_be_created_after_h9_commit"]
        is True
    )

    assert boundary["h81_observed_candles_eligible"] is False


def test_h9_requires_raw_write_once_accrual():
    result = build()

    contract = result["immutable_accrual_contract"]

    assert contract["required_completed_candles"] == 10000
    assert contract["write_once"] is True
    assert contract["append_only"] is True
    assert contract["overwrite_prohibited"] is True
    assert contract["per_record_sha256_required"] is True
    assert contract["chunk_sha256_required"] is True
    assert contract["ledger_sha256_required"] is True


def test_h9_no_market_or_outcome_access():
    result = build()

    audit = result["audit"]

    assert audit["mt5_accessed"] is False
    assert audit["market_data_acquired"] is False
    assert audit["true_oos_rows_written"] == 0
    assert audit["strategy_replay_run"] is False
    assert audit["outcomes_analyzed"] is False
    assert audit["orders_sent"] is False
