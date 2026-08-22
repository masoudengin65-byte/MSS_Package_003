from types import SimpleNamespace

import MetaTrader5 as mt5

from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
)
from mss.analysis.shadow_position_recovery import (
    ShadowPositionRecovery,
)


def install_broker_stubs(
    monkeypatch,
):
    info = SimpleNamespace(
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
    )

    monkeypatch.setattr(
        mt5,
        "symbol_info",
        lambda symbol: info,
    )

    def fake_calc(
        order_type,
        symbol,
        volume,
        open_price,
        close_price,
    ):
        if order_type == mt5.ORDER_TYPE_BUY:
            direction = 1.0
        else:
            direction = -1.0

        return (
            (close_price - open_price)
            * direction
            * 1000.0
            * volume
        )

    monkeypatch.setattr(
        mt5,
        "order_calc_profit",
        fake_calc,
    )


def test_broker_identity_persists_from_open_through_recovery(
    tmp_path, monkeypatch
):
    install_broker_stubs(monkeypatch)
    journal = tmp_path / "identity.jsonl"
    opened = ShadowTradeEngine.open_trade(
        journal_path=journal,
        position_id="SHADOW-ID-1",
        symbol="USDJPY",
        direction="BUY",
        balance=10000.0,
        risk_percent=1.0,
        entry_price=159.0,
        stop_loss=158.5,
        take_profit=160.0,
        broker_epoch=1000,
        broker_position_ticket=12345,
        broker_position_identifier=67890,
    )
    assert opened.valid
    assert opened.journal_event["payload"]["broker_position_ticket"] == 12345
    assert (
        opened.journal_event["payload"]["broker_position_identifier"]
        == 67890
    )
    recovered = ShadowPositionRecovery.recover(journal).position
    assert recovered.broker_position_ticket == 12345
    assert recovered.broker_position_identifier == 67890


def test_full_buy_lifecycle(
    tmp_path,
    monkeypatch,
):
    install_broker_stubs(
        monkeypatch
    )

    journal = (
        tmp_path
        / "shadow"
        / "USDJPY"
        / "events.jsonl"
    )

    opened = (
        ShadowTradeEngine.open_trade(
            journal_path=journal,
            position_id="SHADOW-000001",
            symbol="USDJPY",
            direction="BUY",
            balance=10000.0,
            risk_percent=1.0,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    assert opened.valid is True
    assert (
        opened.action
        == "POSITION_OPENED"
    )
    assert opened.position.valid is True
    assert (
        opened.real_order_send_allowed
        is False
    )
    assert (
        opened.order_send_called
        is False
    )

    held = (
        ShadowTradeEngine.update_trade(
            journal_path=journal,
            position=opened.position,
            bid=159.200,
            ask=159.210,
            broker_epoch=1050,
        )
    )

    assert held.valid is True
    assert (
        held.action
        == "POSITION_HELD"
    )
    assert (
        held.position.status
        == "OPEN"
    )

    closed = (
        ShadowTradeEngine.update_trade(
            journal_path=journal,
            position=opened.position,
            bid=160.010,
            ask=160.020,
            broker_epoch=1100,
        )
    )

    assert closed.valid is True
    assert (
        closed.action
        == "POSITION_CLOSED"
    )
    assert (
        closed.reason
        == "TAKE_PROFIT"
    )
    assert (
        closed.position.status
        == "CLOSED"
    )
    assert (
        closed.position
        .pnl_account_currency
        > 0
    )
    assert (
        closed.position.r_multiple
        > 2.0
    )

    verification = (
        ShadowTradeJournal.verify(
            journal
        )
    )

    assert verification["valid"] is True
    assert verification["event_count"] == 2


def test_full_sell_stop_lifecycle(
    tmp_path,
    monkeypatch,
):
    install_broker_stubs(
        monkeypatch
    )

    journal = (
        tmp_path
        / "sell_events.jsonl"
    )

    opened = (
        ShadowTradeEngine.open_trade(
            journal_path=journal,
            position_id="SHADOW-000002",
            symbol="USDJPY",
            direction="SELL",
            balance=10000.0,
            risk_percent=1.0,
            entry_price=159.000,
            stop_loss=159.500,
            take_profit=158.000,
            broker_epoch=1000,
        )
    )

    assert opened.valid is True

    closed = (
        ShadowTradeEngine.update_trade(
            journal_path=journal,
            position=opened.position,
            bid=159.500,
            ask=159.510,
            broker_epoch=1100,
        )
    )

    assert closed.valid is True
    assert closed.reason == "STOP_LOSS"
    assert (
        closed.position
        .pnl_account_currency
        < 0
    )
    assert closed.position.r_multiple < -1.0


def test_true_oos_namespace_is_blocked(
    tmp_path,
):
    path = (
        tmp_path
        / "sprint92h_true_oos_v2"
        / "events.jsonl"
    )

    try:
        ShadowTradeEngine.open_trade(
            journal_path=path,
            position_id="SHADOW-X",
            symbol="USDJPY",
            direction="BUY",
            balance=10000.0,
            risk_percent=1.0,
            entry_price=159.0,
            stop_loss=158.5,
            take_profit=160.0,
            broker_epoch=1000,
        )

    except RuntimeError as exc:
        assert (
            "SHADOW_TRUE_OOS_NAMESPACE_COLLISION"
            in str(exc)
        )

    else:
        raise AssertionError(
            "True-OOS namespace must be blocked"
        )


def test_engine_has_no_real_execution_methods():
    methods = set(
        dir(ShadowTradeEngine)
    )

    prohibited = {
        "send_order",
        "order_send",
        "order_check",
        "modify_order",
        "modify_position",
        "close_real_position",
    }

    assert not (
        methods
        & prohibited
    )


def test_volume_override_downsizes_position_and_recalculates_risk(
    tmp_path,
    monkeypatch,
):
    install_broker_stubs(
        monkeypatch
    )

    journal = (
        tmp_path
        / "volume_override_events.jsonl"
    )

    opened = (
        ShadowTradeEngine.open_trade(
            journal_path=journal,
            position_id=(
                "SHADOW-VOLUME-OVERRIDE-1"
            ),
            symbol="USDJPY",
            direction="BUY",
            balance=10000.0,
            risk_percent=1.0,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
            volume_override=0.01,
        )
    )

    assert opened.valid is True
    assert (
        opened.action
        == "POSITION_OPENED"
    )

    assert opened.position.valid is True
    assert opened.position.volume == 0.01

    assert (
        opened.risk.normalized_volume
        == 0.01
    )

    # Stub loss for one lot:
    # abs(159.000 - 158.500) * 1000
    # = 500 account-currency units.
    #
    # Therefore 0.01 lot carries actual risk:
    # 500 * 0.01 = 5.00
    #
    # On a 10,000 balance:
    # 5 / 10,000 * 100 = 0.05%
    assert (
        abs(
            opened.risk.risk_amount
            - 5.0
        )
        < 1e-12
    )

    assert (
        abs(
            opened.risk.risk_percent
            - 0.05
        )
        < 1e-12
    )

    event = opened.journal_event

    assert (
        event["event_type"]
        == "POSITION_OPENED"
    )

    payload = event["payload"]

    assert payload["volume"] == 0.01

    assert (
        payload["normalized_volume"]
        == 0.01
    )

    assert (
        abs(
            payload["risk_amount"]
            - 5.0
        )
        < 1e-12
    )

    assert (
        abs(
            payload["risk_percent"]
            - 0.05
        )
        < 1e-12
    )

    verification = (
        ShadowTradeJournal.verify(
            journal
        )
    )

    assert verification["valid"] is True
    assert (
        verification["event_count"]
        == 1
    )


def test_volume_override_above_risk_volume_is_blocked(
    tmp_path,
    monkeypatch,
):
    install_broker_stubs(
        monkeypatch
    )

    journal = (
        tmp_path
        / "volume_override_blocked.jsonl"
    )

    blocked = (
        ShadowTradeEngine.open_trade(
            journal_path=journal,
            position_id=(
                "SHADOW-VOLUME-OVERRIDE-2"
            ),
            symbol="USDJPY",
            direction="BUY",
            balance=10000.0,
            risk_percent=1.0,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
            volume_override=0.21,
        )
    )

    # Normal calculated risk volume is 0.20.
    # An override may downsize exposure, but it
    # must never increase exposure above the
    # risk-calculated normalized volume.
    assert blocked.valid is False

    assert (
        blocked.action
        == "OPEN_BLOCKED"
    )

    assert (
        blocked.reason
        ==
        "VOLUME_OVERRIDE_EXCEEDS_"
        "RISK_NORMALIZED_VOLUME"
    )

    assert journal.exists() is False
