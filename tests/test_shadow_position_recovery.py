from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)


def append_open(
    path,
    *,
    position_id="SHADOW-1",
):
    return (
        ShadowTradeJournal.append_event(
            path=path,
            event_type="POSITION_OPENED",
            position_id=position_id,
            broker_epoch=1000,
            payload={
                "symbol": "USDJPY",
                "direction": "BUY",
                "volume": 0.10,
                "entry_price": 159.0,
                "stop_loss": 158.5,
                "take_profit": 160.0,
                "initial_risk_price": 0.5,
            },
        )
    )


def test_missing_journal_has_no_open_position(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    result = (
        ShadowPositionRecovery.recover(
            path
        )
    )

    assert result.valid is True

    assert (
        result.reason
        == "NO_OPEN_SHADOW_POSITION"
    )

    assert (
        result.open_position_count
        == 0
    )


def test_open_position_is_recovered(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    append_open(path)

    result = (
        ShadowPositionRecovery.recover(
            path
        )
    )

    assert result.valid is True

    assert (
        result.reason
        == "OPEN_SHADOW_POSITION_RECOVERED"
    )

    assert (
        result.open_position_count
        == 1
    )

    position = result.position

    assert position.valid is True
    assert position.status == "OPEN"

    assert (
        position.position_id
        == "SHADOW-1"
    )

    assert position.symbol == "USDJPY"
    assert position.direction == "BUY"

    assert position.volume == 0.10
    assert position.entry_price == 159.0
    assert position.stop_loss == 158.5
    assert position.take_profit == 160.0

    assert (
        position.open_broker_epoch
        == 1000
    )

    assert (
        position.real_order_send_allowed
        is False
    )


def test_closed_position_is_not_recovered(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    append_open(path)

    ShadowTradeJournal.append_event(
        path=path,
        event_type="POSITION_CLOSED",
        position_id="SHADOW-1",
        broker_epoch=1100,
        payload={
            "symbol": "USDJPY",
            "exit_reason": "TAKE_PROFIT",
            "close_price": 160.0,
        },
    )

    result = (
        ShadowPositionRecovery.recover(
            path
        )
    )

    assert result.valid is True

    assert (
        result.open_position_count
        == 0
    )

    assert result.position is None


def test_multiple_open_positions_fail_safe(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    append_open(
        path,
        position_id="SHADOW-1",
    )

    append_open(
        path,
        position_id="SHADOW-2",
    )

    result = (
        ShadowPositionRecovery.recover(
            path
        )
    )

    assert result.valid is False

    assert (
        result.reason
        == "MULTIPLE_OPEN_SHADOW_POSITIONS"
    )

    assert (
        result.open_position_count
        == 2
    )


def test_tampered_journal_is_blocked(
    tmp_path,
):
    path = (
        tmp_path
        / "events.jsonl"
    )

    append_open(path)

    text = path.read_text(
        encoding="utf-8"
    )

    text = text.replace(
        '"volume":0.1',
        '"volume":9.9',
    )

    path.write_text(
        text,
        encoding="utf-8",
    )

    result = (
        ShadowPositionRecovery.recover(
            path
        )
    )

    assert result.valid is False

    assert (
        result.reason
        == "SHADOW_JOURNAL_INTEGRITY_FAILURE"
    )
