import json

from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


def test_empty_journal_is_valid(tmp_path):
    path = (
        tmp_path
        / "shadow_events.jsonl"
    )

    result = (
        ShadowTradeJournal.verify(
            path
        )
    )

    assert result["valid"] is True
    assert result["event_count"] == 0
    assert (
        result["last_event_sha256"]
        == ShadowTradeJournal.GENESIS_SHA256
    )


def test_append_builds_valid_hash_chain(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_events.jsonl"
    )

    first = (
        ShadowTradeJournal.append_event(
            path=path,
            event_type="POSITION_OPENED",
            position_id="SHADOW-1",
            broker_epoch=1000,
            payload={
                "symbol": "USDJPY",
                "direction": "BUY",
            },
        )
    )

    second = (
        ShadowTradeJournal.append_event(
            path=path,
            event_type="POSITION_CLOSED",
            position_id="SHADOW-1",
            broker_epoch=1100,
            payload={
                "exit_reason": (
                    "TAKE_PROFIT"
                ),
                "pnl": 100.0,
            },
        )
    )

    assert (
        second[
            "previous_event_sha256"
        ]
        == first["event_sha256"]
    )

    verification = (
        ShadowTradeJournal.verify(
            path
        )
    )

    assert verification["valid"] is True
    assert verification["event_count"] == 2
    assert (
        verification[
            "last_event_sha256"
        ]
        == second["event_sha256"]
    )


def test_tampering_is_detected(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_events.jsonl"
    )

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_OPENED",
        position_id="SHADOW-2",
        broker_epoch=1000,
        payload={
            "symbol": "USDJPY",
            "volume": 0.10,
        },
    )

    lines = path.read_text(
        encoding="utf-8"
    ).splitlines()

    event = json.loads(
        lines[0]
    )

    event["payload"]["volume"] = (
        99.99
    )

    path.write_text(
        json.dumps(
            event,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )

    verification = (
        ShadowTradeJournal.verify(
            path
        )
    )

    assert verification["valid"] is False
    assert (
        verification["reason"]
        == "EVENT_HASH_MISMATCH"
    )


def test_shadow_audit_prohibits_execution(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_events.jsonl"
    )

    event = (
        ShadowTradeJournal.append_event(
            path=path,
            event_type="POSITION_OPENED",
            position_id="SHADOW-3",
            broker_epoch=1000,
            payload={
                "symbol": "USDJPY",
            },
        )
    )

    audit = event["audit"]

    assert audit["shadow_only"] is True

    assert (
        audit[
            "real_order_send_allowed"
        ]
        is False
    )

    assert (
        audit["order_send_called"]
        is False
    )

    assert (
        audit[
            "true_oos_data_accessed"
        ]
        is False
    )

    assert (
        audit[
            "true_oos_artifacts_modified"
        ]
        is False
    )
