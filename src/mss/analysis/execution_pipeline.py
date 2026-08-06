"""
MSS Execution Pipeline
Version : 2.0
Sprint : 32.0
Compatible : v0.31
"""

from mss.analysis.risk_engine import RiskEngine
from mss.analysis.order_builder import OrderBuilder
from mss.analysis.position_manager import PositionManager

from mss.domain.trade_order import TradeOrder
from mss.domain.position import Position


class ExecutionPipeline:
    """
    TradeSetup
        ↓
    RiskEngine
        ↓
    RiskProfile
        ↓
    OrderBuilder
        ↓
    TradeOrder
        ↓
    PositionManager
        ↓
    Position
    """

    def __init__(self):

        self.risk_engine = RiskEngine()

        self.order_builder = OrderBuilder()

        self.position_manager = PositionManager()

    def execute(
        self,
        symbol,
        trade_setup,
        account_balance,
        risk_percent,
        ticket=1,
        news_risk_status=None,
        portfolio_exposure=None,
    ):

        order = TradeOrder()

        position = Position()

        if trade_setup is None:

            return order, position

        if not trade_setup.valid:

            return order, position

        stop_distance = abs(

            trade_setup.entry

            -

            trade_setup.stop_loss

        )

        risk_profile = self.risk_engine.calculate(

            balance=account_balance,

            risk_percent=risk_percent,

            stop_distance=stop_distance,

            news_risk_status=news_risk_status,

            portfolio_exposure=portfolio_exposure,

        )

        if not risk_profile.valid:

            return order, position

        order = self.order_builder.build(

            symbol,

            trade_setup,

            risk_profile,

        )

        if not order.valid:

            return order, position

        position = self.position_manager.open_position(

            ticket,

            order,

        )

        return order, position
