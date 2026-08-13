from types import SimpleNamespace


from mss.analysis.live_market_observer import (
    LiveMarketObserver,
)


def test_symbol_metadata_contains_execution_constraints():
    info = SimpleNamespace(
        name="EURUSD",
        description="Euro vs US Dollar",
        visible=True,
        digits=5,
        point=0.00001,
        spread=12,
        trade_mode=4,
        trade_contract_size=100000.0,
        volume_min=0.01,
        volume_max=100.0,
        volume_step=0.01,
        volume_limit=0.0,
        trade_stops_level=10,
        trade_freeze_level=0,
    )

    result = (
        LiveMarketObserver._symbol_metadata(
            info
        )
    )

    assert result["digits"] == 5
    assert result["point"] == 0.00001
    assert result["volume_min"] == 0.01
    assert result["volume_step"] == 0.01
    assert (
        result["trade_contract_size"]
        == 100000.0
    )
    assert result["trade_stops_level"] == 10


def test_tick_spread_is_calculated_from_bid_ask():
    tick = SimpleNamespace(
        time=1000,
        time_msc=1000000,
        bid=1.10000,
        ask=1.10012,
        last=0.0,
        volume=0.0,
    )

    result = (
        LiveMarketObserver._tick_payload(
            tick,
            0.00001,
        )
    )

    assert abs(
        result["spread_price"]
        - 0.00012
    ) < 1e-12

    assert abs(
        result["spread_points_observed"]
        - 12.0
    ) < 1e-8


def test_account_metadata_does_not_expose_login():
    account = SimpleNamespace(
        login=12345678,
        server="Broker-Demo",
        currency="USD",
        company="Broker",
        trade_allowed=True,
        trade_expert=True,
    )

    result = (
        LiveMarketObserver._safe_account_metadata(
            account
        )
    )

    assert "login" not in result
    assert result["server"] == "Broker-Demo"


def test_shadow_contract_hard_disables_real_execution():
    assert (
        "order_send"
        in LiveMarketObserver.PROHIBITED_API
    )

    assert (
        "order_check"
        in LiveMarketObserver.PROHIBITED_API
    )

    assert (
        "order_send"
        not in LiveMarketObserver.READ_ONLY_API
    )


def test_current_design_has_no_execution_method():
    prohibited_methods = {
        "send_order",
        "execute_order",
        "place_order",
        "modify_order",
        "close_position",
    }

    observer_methods = set(
        dir(LiveMarketObserver)
    )

    assert not (
        prohibited_methods
        & observer_methods
    )
