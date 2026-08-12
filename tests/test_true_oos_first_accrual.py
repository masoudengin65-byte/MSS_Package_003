import json
from pathlib import Path

from mss.analysis.true_oos_first_accrual import (
    TrueOosFirstAccrual,
)


ROOT = Path(__file__).resolve().parents[1]


def load(name):
    return json.loads(
        (ROOT / "reports" / name).read_text(
            encoding="utf-8"
        )
    )


def genesis():
    return json.loads(
        (
            ROOT
            / "research_data/sprint92h_true_oos_v2/"
            "USDJPY_M15/manifest_000000.json"
        ).read_text(encoding="utf-8")
    )


def make_rows(count):
    start = 1786556700

    return [
        {
            "time": start + i * 900,
            "open": 147.0,
            "high": 147.1,
            "low": 146.9,
            "close": 147.0,
            "tick_volume": 100,
            "spread": 10,
            "real_volume": 0,
        }
        for i in range(count)
    ]


def build(count=4):
    return TrueOosFirstAccrual.build(
        load("MSS_Sprint92H10_One_Time_True_OOS_Anchor_Lock.json"),
        load("MSS_Sprint92H11_Append_Only_True_OOS_Ledger_Initialization.json"),
        load("MSS_Sprint92H11_1_MT5_Time_Authority_Audit.json"),
        genesis(),
        make_rows(count),
        1786556700 + count * 900,
        (
            "research_data/sprint92h_true_oos_v2/"
            "USDJPY_M15/chunks/chunk_000001.jsonl"
        ),
        "8fdbd541eee43aa140dc9819f4b2907851e847e801cce6be3caf9a1775d260ee",
    )


def test_h12_first_row_is_locked_raw_anchor():
    result = build()

    assert result["accrual"]["first_appended_epoch"] == 1786556700

    assert (
        result["time_contract"]["raw_mt5_time_field_is_execution_authority"]
        is True
    )


def test_h12_first_manifest_chains_to_genesis():
    result = build()

    assert result["next_manifest"]["manifest_sequence"] == 1

    assert (
        result["next_manifest"]["previous_manifest_sha256"]
        == "8fdbd541eee43aa140dc9819f4b2907851e847e801cce6be3caf9a1775d260ee"
    )


def test_h12_counts_rows_and_remaining():
    result = build(4)

    assert result["accrual"]["completed_rows_appended"] == 4
    assert result["accrual"]["remaining_rows"] == 9996

    assert result["next_manifest"]["row_count"] == 4
    assert result["next_manifest"]["chunk_count"] == 1


def test_h12_preserves_immutability():
    result = build()

    immutable = result["immutability"]

    assert immutable["genesis_manifest_modified"] is False
    assert immutable["chunk_000001_write_once"] is True
    assert immutable["manifest_000001_write_once"] is True
    assert immutable["broker_revision_overwrite_allowed"] is False


def test_h12_no_replay_or_outcome_access():
    result = build()

    audit = result["audit"]

    assert audit["strategy_replay_run"] is False
    assert audit["signals_generated"] is False
    assert audit["trades_generated"] is False
    assert audit["pnl_computed"] is False
    assert audit["outcomes_analyzed"] is False
    assert audit["orders_sent"] is False
