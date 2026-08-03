"""
MSS Position Manager
Version : 1.0
Sprint : 10.0
Compatible : v0.21
"""

from datetime import datetime

from mss.domain.position import Position


class PositionManager:

    def open_position(
        self,
        ticket: int,
        order,
    ) -> Position:

        position = Position()

        if order is None:
            return position

        if not order.valid:
            return position

        position.ticket = ticket

        position.symbol = order.symbol

        position.direction = order.direction

        position.volume = order.volume

        position.entry_price = order.entry

        position.stop_loss = order.stop_loss

        position.take_profit = order.take_profit_1

        position.open_time = datetime.now()

        position.status = "OPEN"

        position.valid = True

        return position

    def close_position(

        self,

        position: Position,

        close_price: float,

        profit: float,

    ) -> Position:

        if not position.valid:
            return position

        position.close_price = close_price

        position.profit = profit

        position.close_time = datetime.now()

        position.status = "CLOSED"

        return position