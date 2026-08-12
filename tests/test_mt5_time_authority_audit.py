import json
from pathlib import Path

from mss.analysis.mt5_time_authority_audit import (
    Mt5TimeAuthorityAudit,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(
            encoding="utf-8"
        )
    )


def build(offset=10800):
    windows = 1786549800
    tick = windows + offset
    bar = (tick // 900) * 900

    return Mt5TimeAuthorityAudit().build(
        load("MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"),
        load("MSS_Sprint92H11_Append_Only_True_OOS_Ledger_Initialization.json"),
        windows,
        tick,
        bar,
    )


def test_h11_1_confirms_three_hour_domain():
    result = build()

    assert (
        result["time_authority"]["status"]
        == "BROKER_TIME_DOMAIN_CONFIRMED"
    )


def test_h11_1_raw_broker_epoch_is_execution_authority():
    result = build()

    authority = result["time_authority"]

    assert (
        authority["execution_time_domain"]
        == "RAW_MT5_BROKER_EPOCH_DOMAIN"
    )

    assert (
        authority["do_not_treat_raw_mt5_epoch_as_true_utc"]
        is True
    )


def test_h11_1_preserves_h10_and_h11():
    result = build()

    assert (
        result["h10_anchor_interpretation"]
        ["h10_anchor_replacement_required"]
        is False
    )

    assert (
        result["h11_ledger_interpretation"]
        ["ledger_reinitialization_required"]
        is False
    )


def test_h11_1_rejects_large_offset_drift():
    result = build(offset=7200)

    assert (
        result["time_authority"]["status"]
        == "BROKER_OFFSET_UNRESOLVED"
    )


def test_h11_1_no_ledger_or_outcome_mutation():
    result = build()

    assert result["audit"]["completed_true_oos_rows_written"] == 0
    assert result["audit"]["ledger_modified"] is False
    assert result["audit"]["strategy_replay_run"] is False
    assert result["audit"]["outcomes_analyzed"] is False
