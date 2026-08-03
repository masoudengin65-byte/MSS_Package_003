from mss.analysis.position_manager import PositionManager

from mss.domain.trade_order import TradeOrder


def test_open_position():

    order = TradeOrder(

        symbol="XAUUSD",

        direction="BUY",

        volume=0.25,

        entry=4048.20,

        stop_loss=4044.80,

        take_profit_1=4055.00,

        valid=True,

    )

    position = PositionManager().open_position(

        ticket=123456,

        order=order,

    )

    assert position.valid

    assert position.ticket == 123456

    assert position.symbol == "XAUUSD"

    assert position.direction == "BUY"

    assert position.volume == 0.25

    assert position.status == "OPEN"


def test_close_position():

    order = TradeOrder(

        symbol="XAUUSD",

        direction="BUY",

        volume=0.25,

        entry=4048.20,

        stop_loss=4044.80,

        take_profit_1=4055.00,

        valid=True,

    )

    manager = PositionManager()

    position = manager.open_position(

        ticket=1,

        order=order,

    )

    position = manager.close_position(

        position,

        close_price=4056.00,

        profit=195.50,

    )

    assert position.status == "CLOSED"

    assert position.close_price == 4056.00

    assert position.profit == 195.50

    assert position.close_time is not None


def test_invalid_order():

    order = TradeOrder()

    position = PositionManager().open_position(

        ticket=1,

        order=order,

    )

    assert not position.valid