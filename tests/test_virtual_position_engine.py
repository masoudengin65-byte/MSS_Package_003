from mss.analysis.virtual_position_engine import (
    VirtualPositionEngine,
)


def test_buy_position_opens_valid():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-1",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    assert position.valid is True
    assert position.status == "OPEN"
    assert position.initial_risk_price == 0.5
    assert (
        position.real_order_send_allowed
        is False
    )


def test_sell_position_opens_valid():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-2",
            symbol="USDJPY",
            direction="SELL",
            volume=0.10,
            entry_price=159.000,
            stop_loss=159.500,
            take_profit=158.000,
            broker_epoch=1000,
        )
    )

    assert position.valid is True
    assert position.status == "OPEN"


def test_invalid_buy_geometry_is_blocked():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-3",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=159.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    assert position.valid is False


def test_buy_uses_bid_for_stop_loss():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-4",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    update = (
        VirtualPositionEngine
        .update_from_tick(
            position=position,
            bid=158.490,
            ask=158.500,
            broker_epoch=1100,
        )
    )

    assert update.closed is True
    assert update.reason == "STOP_LOSS"
    assert (
        update.position.close_price
        == 158.490
    )
    assert update.position.r_multiple < -1.0


def test_buy_uses_bid_for_take_profit():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-5",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    update = (
        VirtualPositionEngine
        .update_from_tick(
            position=position,
            bid=160.010,
            ask=160.020,
            broker_epoch=1100,
        )
    )

    assert update.closed is True
    assert update.reason == "TAKE_PROFIT"
    assert update.position.r_multiple > 2.0


def test_sell_uses_ask_for_stop_loss():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-6",
            symbol="USDJPY",
            direction="SELL",
            volume=0.10,
            entry_price=159.000,
            stop_loss=159.500,
            take_profit=158.000,
            broker_epoch=1000,
        )
    )

    update = (
        VirtualPositionEngine
        .update_from_tick(
            position=position,
            bid=159.490,
            ask=159.510,
            broker_epoch=1100,
        )
    )

    assert update.closed is True
    assert update.reason == "STOP_LOSS"
    assert (
        update.position.close_price
        == 159.510
    )


def test_sell_uses_ask_for_take_profit():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-7",
            symbol="USDJPY",
            direction="SELL",
            volume=0.10,
            entry_price=159.000,
            stop_loss=159.500,
            take_profit=158.000,
            broker_epoch=1000,
        )
    )

    update = (
        VirtualPositionEngine
        .update_from_tick(
            position=position,
            bid=157.980,
            ask=157.990,
            broker_epoch=1100,
        )
    )

    assert update.closed is True
    assert update.reason == "TAKE_PROFIT"
    assert update.position.r_multiple > 2.0


def test_position_remains_open_between_sl_tp():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-8",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    update = (
        VirtualPositionEngine
        .update_from_tick(
            position=position,
            bid=159.250,
            ask=159.260,
            broker_epoch=1100,
        )
    )

    assert update.closed is False
    assert update.reason == "POSITION_REMAINS_OPEN"
    assert update.position.status == "OPEN"


def test_closed_position_is_not_closed_twice():
    position = (
        VirtualPositionEngine
        .open_position(
            position_id="SHADOW-9",
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            stop_loss=158.500,
            take_profit=160.000,
            broker_epoch=1000,
        )
    )

    closed = (
        VirtualPositionEngine
        .close_position(
            position=position,
            close_price=160.000,
            broker_epoch=1100,
            reason="TAKE_PROFIT",
        )
    )

    second = (
        VirtualPositionEngine
        .close_position(
            position=closed,
            close_price=158.000,
            broker_epoch=1200,
            reason="STOP_LOSS",
        )
    )

    assert second == closed
    assert second.exit_reason == "TAKE_PROFIT"
