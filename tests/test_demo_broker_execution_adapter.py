from types import SimpleNamespace

import pytest

import mss.analysis.demo_broker_execution_adapter as module

from mss.analysis.demo_broker_execution_adapter import (
    DemoBrokerExecutionAdapter,
)


class FakeMT5:
    ORDER_TYPE_BUY = 0
    ORDER_TYPE_SELL = 1

    ACCOUNT_TRADE_MODE_DEMO = 0

    TRADE_ACTION_DEAL = 1

    ORDER_TIME_GTC = 0

    ORDER_FILLING_FOK = 0
    ORDER_FILLING_IOC = 1
    ORDER_FILLING_RETURN = 2

    SYMBOL_FILLING_FOK = 1
    SYMBOL_FILLING_IOC = 2

    SYMBOL_TRADE_EXECUTION_MARKET = 2

    TRADE_RETCODE_DONE = 10009
    TRADE_RETCODE_DONE_PARTIAL = 10010

    def __init__(self):
        self.calls = []

        self.account = SimpleNamespace(
            trade_mode=self.ACCOUNT_TRADE_MODE_DEMO
        )

        self.terminal = SimpleNamespace(
            connected=True
        )

        self.info = SimpleNamespace(
            filling_mode=self.SYMBOL_FILLING_IOC,
            trade_exemode=0,
        )

        self.tick = SimpleNamespace(
            bid=1.1000,
            ask=1.1002,
        )

        self.positions_before = ()
        self.positions_after = (
            SimpleNamespace(
                magic=DemoBrokerExecutionAdapter.MAGIC
            ),
        )

        self.orders = ()

        self.check_result = SimpleNamespace(
            retcode=0
        )

        self.send_result = SimpleNamespace(
            retcode=self.TRADE_RETCODE_DONE,
            order=12345,
            deal=67890,
            price=1.1002,
        )

        self._position_calls = 0

    def account_info(self):
        self.calls.append("account_info")
        return self.account

    def terminal_info(self):
        self.calls.append("terminal_info")
        return self.terminal

    def symbol_info(self, symbol):
        self.calls.append(
            ("symbol_info", symbol)
        )
        return self.info

    def positions_get(self, *, symbol):
        self.calls.append(
            ("positions_get", symbol)
        )

        self._position_calls += 1

        if self._position_calls == 1:
            return self.positions_before

        return self.positions_after

    def orders_get(self, *, symbol):
        self.calls.append(
            ("orders_get", symbol)
        )
        return self.orders

    def symbol_info_tick(self, symbol):
        self.calls.append(
            ("symbol_info_tick", symbol)
        )
        return self.tick

    def order_check(self, request):
        self.calls.append(
            ("order_check", request)
        )
        return self.check_result

    def order_send(self, request):
        self.calls.append(
            ("order_send", request)
        )
        return self.send_result


@pytest.fixture
def fake_mt5(monkeypatch):
    fake = FakeMT5()

    monkeypatch.setattr(
        module,
        "mt5",
        fake,
    )

    return fake


def execute(**overrides):
    args = {
        "enabled": True,
        "symbol": "EURUSD",
        "direction": "BUY",
        "volume": 0.10,
        "stop_loss": 1.0950,
        "take_profit": 1.1100,
        "deviation_points": 20,
    }

    args.update(overrides)

    return (
        DemoBrokerExecutionAdapter
        .execute_market_order(
            **args
        )
    )


def test_disabled_mode_is_fail_safe(
    fake_mt5,
):
    result = execute(
        enabled=False
    )

    assert not result.valid
    assert (
        result.reason
        == "DEMO_EXECUTION_NOT_ENABLED"
    )

    assert fake_mt5.calls == []


def test_non_demo_account_is_blocked(
    fake_mt5,
):
    fake_mt5.account = SimpleNamespace(
        trade_mode=99
    )

    result = execute()

    assert not result.valid
    assert (
        result.reason
        == "NON_DEMO_ACCOUNT_BLOCKED"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_duplicate_position_blocks_execution(
    fake_mt5,
):
    fake_mt5.positions_before = (
        SimpleNamespace(
            magic=999
        ),
    )

    result = execute()

    assert not result.valid

    assert (
        result.reason
        == "DUPLICATE_SYMBOL_POSITION_BLOCKED"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_check"
        for call in fake_mt5.calls
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_duplicate_pending_order_blocks_execution(
    fake_mt5,
):
    fake_mt5.orders = (
        SimpleNamespace(
            ticket=100
        ),
    )

    result = execute()

    assert not result.valid

    assert (
        result.reason
        == "DUPLICATE_SYMBOL_ORDER_BLOCKED"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_positions_get_failure_is_fail_safe(
    fake_mt5,
):
    def unavailable(*, symbol):
        fake_mt5.calls.append(
            ("positions_get", symbol)
        )
        return None

    fake_mt5.positions_get = unavailable

    result = execute()

    assert not result.valid

    assert (
        result.reason
        == "POSITIONS_GET_UNAVAILABLE"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_orders_get_failure_is_fail_safe(
    fake_mt5,
):
    def unavailable(*, symbol):
        fake_mt5.calls.append(
            ("orders_get", symbol)
        )
        return None

    fake_mt5.orders_get = unavailable

    result = execute()

    assert not result.valid

    assert (
        result.reason
        == "ORDERS_GET_UNAVAILABLE"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_order_check_rejection_prevents_send(
    fake_mt5,
):
    fake_mt5.check_result = (
        SimpleNamespace(
            retcode=10016
        )
    )

    result = execute()

    assert not result.valid
    assert (
        result.reason
        == "ORDER_CHECK_REJECTED"
    )

    assert (
        result.order_check_performed
        is True
    )

    assert (
        result.order_send_performed
        is False
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )


def test_order_check_must_precede_order_send(
    fake_mt5,
):
    result = execute()

    assert result.valid

    names = [
        call[0]
        if isinstance(call, tuple)
        else call
        for call in fake_mt5.calls
    ]

    assert (
        names.index("order_check")
        <
        names.index("order_send")
    )


def test_successful_demo_order_is_confirmed(
    fake_mt5,
):
    result = execute()

    assert result.valid
    assert (
        result.reason
        == "DEMO_ORDER_EXECUTED"
    )

    assert result.order_check_performed
    assert result.order_send_performed
    assert result.position_confirmed

    assert result.order_ticket == 12345
    assert result.deal_ticket == 67890

    assert result.requested_price == pytest.approx(
        1.1002
    )

    assert result.fill_price == pytest.approx(
        1.1002
    )


def test_post_send_position_must_match_magic(
    fake_mt5,
):
    fake_mt5.positions_after = (
        SimpleNamespace(
            magic=999999
        ),
    )

    result = execute()

    assert not result.valid

    assert (
        result.reason
        ==
        "POST_SEND_POSITION_NOT_CONFIRMED"
    )

    assert result.order_send_performed


def test_buy_uses_ask_price(
    fake_mt5,
):
    result = execute(
        direction="BUY"
    )

    assert result.valid

    assert result.requested_price == pytest.approx(
        fake_mt5.tick.ask
    )


def test_sell_uses_bid_price(
    fake_mt5,
):
    fake_mt5.send_result = (
        SimpleNamespace(
            retcode=(
                fake_mt5
                .TRADE_RETCODE_DONE
            ),
            order=12346,
            deal=67891,
            price=1.1000,
        )
    )

    result = execute(
        direction="SELL",
        stop_loss=1.1050,
        take_profit=1.0900,
    )

    assert result.valid

    assert result.requested_price == pytest.approx(
        fake_mt5.tick.bid
    )


def test_ioc_filling_mode_is_selected(
    fake_mt5,
):
    result = execute()

    assert result.valid

    check_call = next(
        call
        for call in fake_mt5.calls
        if (
            isinstance(call, tuple)
            and call[0] == "order_check"
        )
    )

    request = check_call[1]

    assert (
        request["type_filling"]
        ==
        fake_mt5.ORDER_FILLING_IOC
    )


def test_fok_filling_mode_is_supported(
    fake_mt5,
):
    fake_mt5.info = SimpleNamespace(
        filling_mode=(
            fake_mt5
            .SYMBOL_FILLING_FOK
        ),
        trade_exemode=0,
    )

    result = execute()

    assert result.valid

    check_call = next(
        call
        for call in fake_mt5.calls
        if (
            isinstance(call, tuple)
            and call[0] == "order_check"
        )
    )

    assert (
        check_call[1]["type_filling"]
        ==
        fake_mt5.ORDER_FILLING_FOK
    )


def test_market_execution_without_supported_fill_blocks(
    fake_mt5,
):
    fake_mt5.info = SimpleNamespace(
        filling_mode=0,
        trade_exemode=(
            fake_mt5
            .SYMBOL_TRADE_EXECUTION_MARKET
        ),
    )

    result = execute()

    assert not result.valid

    assert (
        result.reason
        ==
        "SUPPORTED_FILLING_MODE_UNAVAILABLE"
    )

    assert not any(
        isinstance(call, tuple)
        and call[0] == "order_send"
        for call in fake_mt5.calls
    )
