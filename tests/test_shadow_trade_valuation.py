import MetaTrader5 as mt5

from mss.analysis.shadow_trade_valuation import (
    ShadowTradeValuation,
)


def test_buy_profit_uses_mt5_order_calc_profit(
    monkeypatch,
):
    calls = []

    def fake_calc(
        order_type,
        symbol,
        volume,
        entry,
        close,
    ):
        calls.append(
            (
                order_type,
                symbol,
                volume,
                entry,
                close,
            )
        )

        return 125.50

    monkeypatch.setattr(
        mt5,
        "order_calc_profit",
        fake_calc,
    )

    result = (
        ShadowTradeValuation.calculate(
            symbol="USDJPY",
            direction="BUY",
            volume=0.10,
            entry_price=159.000,
            close_price=159.500,
        )
    )

    assert result.valid is True
    assert (
        result.pnl_account_currency
        == 125.50
    )
    assert (
        result.order_calc_profit_used
        is True
    )
    assert (
        result.real_order_send_allowed
        is False
    )
    assert result.order_send_called is False

    assert len(calls) == 1
    assert (
        calls[0][0]
        == mt5.ORDER_TYPE_BUY
    )


def test_sell_loss_is_preserved(
    monkeypatch,
):
    monkeypatch.setattr(
        mt5,
        "order_calc_profit",
        lambda *args: -75.25,
    )

    result = (
        ShadowTradeValuation.calculate(
            symbol="USDJPY",
            direction="SELL",
            volume=0.10,
            entry_price=159.000,
            close_price=159.300,
        )
    )

    assert result.valid is True
    assert (
        result.pnl_account_currency
        == -75.25
    )


def test_invalid_direction_blocks_valuation():
    result = (
        ShadowTradeValuation.calculate(
            symbol="USDJPY",
            direction="WAIT",
            volume=0.10,
            entry_price=159.000,
            close_price=159.100,
        )
    )

    assert result.valid is False
    assert (
        result.reason
        == "INVALID_DIRECTION"
    )
