from types import SimpleNamespace

import MetaTrader5 as mt5

from mss.analysis.shadow_trade_engine import (
    ShadowTradeEngine,
)
from mss.analysis.shadow_trade_journal import (
    ShadowTradeJournal,
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
