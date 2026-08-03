"""
MSS Trade Setup Engine
Version : 1.0
Sprint : 9.1
Compatible : v0.18
"""

from mss.domain.trade_setup import TradeSetup


class TradeSetupEngine:

    RR_1 = 2.0
    RR_2 = 3.0

    def build(
        self,
        analysis,
    ) -> TradeSetup:

        setup = TradeSetup()

        if analysis is None:
            return setup

        if analysis.bos is None:
            return setup

        if analysis.order_block is None:
            return setup

        if not analysis.order_block.valid:
            return setup

        if analysis.fair_value_gap is None:
            return setup

        if not analysis.fair_value_gap.valid:
            return setup

        # ==========================================
        # BUY
        # ==========================================

        if analysis.bos.direction == "BULLISH":

            setup.direction = "BUY"

            setup.entry = analysis.order_block.high

            setup.stop_loss = analysis.order_block.low

            setup.risk = abs(

                setup.entry -

                setup.stop_loss

            )

            setup.take_profit_1 = (

                setup.entry +

                setup.risk * self.RR_1

            )

            setup.take_profit_2 = (

                setup.entry +

                setup.risk * self.RR_2

            )

            setup.reward = (

                setup.take_profit_2 -

                setup.entry

            )

            if setup.risk > 0:

                setup.rr = (

                    setup.reward /

                    setup.risk

                )

            setup.valid = True

            setup.reason = (

                "Bullish Trade Setup"

            )

            return setup

        # ==========================================
        # SELL
        # ==========================================

        if analysis.bos.direction == "BEARISH":

            setup.direction = "SELL"

            setup.entry = analysis.order_block.low

            setup.stop_loss = analysis.order_block.high

            setup.risk = abs(

                setup.stop_loss -

                setup.entry

            )

            setup.take_profit_1 = (

                setup.entry -

                setup.risk * self.RR_1

            )

            setup.take_profit_2 = (

                setup.entry -

                setup.risk * self.RR_2

            )

            setup.reward = (

                setup.entry -

                setup.take_profit_2

            )

            if setup.risk > 0:

                setup.rr = (

                    setup.reward /

                    setup.risk

                )

            setup.valid = True

            setup.reason = (

                "Bearish Trade Setup"

            )

            return setup

        return setup