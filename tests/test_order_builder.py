from mss.analysis.order_builder import OrderBuilder

from mss.domain.trade_setup import TradeSetup
from mss.domain.risk_profile import RiskProfile


def test_build_order():

    setup = TradeSetup(

        direction="BUY",

        entry=4048.20,

        stop_loss=4044.80,

        take_profit_1=4055.00,

        take_profit_2=4062.00,

        rr=3.0,

        valid=True,

    )

    risk = RiskProfile(

        account_balance=10000,

        risk_percent=1,

        risk_amount=100,

        stop_distance=3.4,

        lot_size=0.27,

        valid=True,

    )

    order = OrderBuilder().build(

        "XAUUSD",

        setup,

        risk,

    )

    assert order.valid

    assert order.symbol == "XAUUSD"

    assert order.direction == "BUY"

    assert order.volume == 0.27

    assert order.entry == 4048.20

    assert order.stop_loss == 4044.80

    assert order.take_profit_1 == 4055.00

    assert order.take_profit_2 == 4062.00

    assert order.rr == 3.0


def test_invalid_setup():

    setup = TradeSetup()

    risk = RiskProfile(valid=True)

    order = OrderBuilder().build(

        "XAUUSD",

        setup,

        risk,

    )

    assert not order.valid


def test_invalid_risk():

    setup = TradeSetup(valid=True)

    risk = RiskProfile()

    order = OrderBuilder().build(

        "XAUUSD",

        setup,

        risk,

    )

    assert not order.valid