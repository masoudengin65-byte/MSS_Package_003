"""
MSS MT5 Executor
Version : 2.0
Sprint : 40.0
Compatible : v0.40
"""

import MetaTrader5 as mt5

from mss.domain.execution_result import ExecutionResult


class MT5Executor:

    def initialize(
        self,
    ) -> bool:

        return mt5.initialize()

    def shutdown(
        self,
    ):

        mt5.shutdown()

    def terminal_info(
        self,
    ):

        return mt5.terminal_info()

    def account_info(
        self,
    ):

        return mt5.account_info()

    def symbol_info(
        self,
        symbol,
    ):

        return mt5.symbol_info(symbol)

    def symbol_tick(
        self,
        symbol,
    ):

        return mt5.symbol_info_tick(symbol)

    def positions(
        self,
        symbol=None,
    ):

        if symbol is None:

            return mt5.positions_get()

        return mt5.positions_get(

            symbol=symbol,

        )

    def orders(
        self,
        symbol=None,
    ):

        if symbol is None:

            return mt5.orders_get()

        return mt5.orders_get(

            symbol=symbol,

        )

    def send_order(
        self,
        order,
    ) -> ExecutionResult:

        result = ExecutionResult()

        if order is None:

            result.comment = "Order is None"

            return result

        if not order.valid:

            result.comment = "Invalid Order"

            return result

        tick = self.symbol_tick(

            order.symbol,

        )

        if tick is None:

            result.comment = "Symbol Tick Not Found"

            return result

        if order.direction == "BUY":

            order_type = mt5.ORDER_TYPE_BUY

            price = tick.ask

        else:

            order_type = mt5.ORDER_TYPE_SELL

            price = tick.bid

        request = {

            "action": mt5.TRADE_ACTION_DEAL,

            "symbol": order.symbol,

            "volume": order.volume,

            "type": order_type,

            "price": price,

            "sl": order.stop_loss,

            "tp": order.take_profit_1,

            "deviation": 20,

            "magic": 777777,

            "comment": order.comment,

            "type_time": mt5.ORDER_TIME_GTC,

            "type_filling": mt5.ORDER_FILLING_IOC,

        }

        mt5_result = mt5.order_send(

            request,

        )

        if mt5_result is None:

            result.comment = "order_send failed"

            return result

        result.raw_result = mt5_result

        result.retcode = mt5_result.retcode

        result.comment = mt5_result.comment

        if mt5_result.retcode == mt5.TRADE_RETCODE_DONE:

            result.success = True

            result.order = mt5_result.order

            result.deal = mt5_result.deal

            result.volume = mt5_result.volume

            result.price = mt5_result.price

        return result