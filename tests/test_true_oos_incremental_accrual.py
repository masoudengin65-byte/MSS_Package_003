import hashlib
import json
from pathlib import Path

from mss.analysis.true_oos_incremental_accrual import (
    TrueOosIncrementalAccrual,
)


ROOT = Path(__file__).resolve().parents[1]

MANIFEST = (
    ROOT
    / "research_data"
    / "sprint92h_true_oos_v2"
    / "USDJPY_M15"
    / "manifest_000001.json"
)


def manifest():
    return json.loads(
        MANIFEST.read_text(
            encoding="utf-8"
        )
    )


def ledger_audit():
    return (
        TrueOosIncrementalAccrual
        .verify_existing_ledger(
            ROOT,
            manifest(),
        )
    )


def make_new_rows():
    return [
        {
            "time": 1786561200,
            "open": 147.0,
            "high": 147.1,
            "low": 146.9,
            "close": 147.0,
            "tick_volume": 100,
            "spread": 10,
            "real_volume": 0,
        },
        {
            "time": 1786562100,
            "open": 147.0,
            "high": 147.1,
            "low": 146.9,
            "close": 147.0,
            "tick_volume": 100,
            "spread": 10,
            "real_volume": 0,
        },
    ]


def build():
    current_manifest = manifest()

    previous_sha = hashlib.sha256(
        MANIFEST.read_bytes()
    ).hexdigest()

    return TrueOosIncrementalAccrual.build(
        current_manifest,
        previous_sha,
        ledger_audit(),
        make_new_rows(),
        1786563000,
        (
            "research_data/sprint92h_true_oos_v2/"
            "USDJPY_M15/chunks/chunk_000002.jsonl"
        ),
    )


def test_h13_existing_ledger_verifies():
    audit = ledger_audit()

    assert audit["verified"] is True
    assert len(audit["rows"]) == 5

    assert (
        audit["aggregate_sha256"]
        == (
            "8d4f85675d0f5ef46b4e951515b3ca2c"
            "f01ad6268a93e7696715c126437bf8d1"
        )
    )


def test_h13_only_appends_after_last_frozen_epoch():
    result = build()

    assert (
        result["accrual"]
        ["previous_last_epoch"]
        == 1786560300
    )

    assert (
        result["accrual"]
        ["first_new_epoch"]
        == 1786561200
    )


def test_h13_advances_manifest_chain():
    result = build()

    assert (
        result["next_manifest"]
        ["manifest_sequence"]
        == 2
    )

    assert (
        result["next_manifest"]
        ["chunk_count"]
        == 2
    )

    assert (
        result["next_manifest"]
        ["row_count"]
        == 7
    )

    assert (
        result["next_manifest"]
        ["previous_manifest_sha256"]
        == hashlib.sha256(
            MANIFEST.read_bytes()
        ).hexdigest()
    )


def test_h13_broker_drift_does_not_overwrite():
    frozen = ledger_audit()["rows"]

    broker = [
        dict(row)
        for row in frozen
    ]

    broker[0]["close"] += 0.01

    audit = (
        TrueOosIncrementalAccrual
        .broker_drift_audit(
            frozen,
            broker,
        )
    )

    assert audit["drift_detected"] is True
    assert audit["drifted_timestamp_count"] == 1
    assert audit["frozen_rows_modified"] is False

    assert (
        audit["evidence"][0]
        ["changed_fields"][0]["field"]
        == "close"
    )


def test_h13_no_replay_or_outcome_access():
    result = build()

    assert (
        result["audit"]
        ["strategy_replay_run"]
        is False
    )

    assert (
        result["audit"]
        ["outcomes_analyzed"]
        is False
    )

    assert (
        result["audit"]
        ["orders_sent"]
        is False
    )
