"""
MSS Confluence Engine
Version : 1.0
Sprint : 8
Compatible : v0.17
"""

from mss.domain.trade_signal import TradeSignal


class ConfluenceEngine:

    def generate(
        self,
        analysis,
    ) -> TradeSignal:

        signal = TradeSignal()

        # ---------------------------------
        # Structure Required
        # ---------------------------------

        if analysis.structure is None:
            return signal

        # ---------------------------------
        # BOS Required
        # ---------------------------------

        if analysis.bos is None:
            return signal

        # ---------------------------------
        # Order Block Required
        # ---------------------------------

        if analysis.order_block is None:
            return signal

        if not analysis.order_block.valid:
            return signal

        # ---------------------------------
        # Fair Value Gap Required
        # ---------------------------------

        if analysis.fair_value_gap is None:
            return signal

        if not analysis.fair_value_gap.valid:
            return signal

        # ---------------------------------
        # BUY
        # ---------------------------------

        if (

            analysis.bos.direction == "BULLISH"

            and

            analysis.displacement.bullish

            and

            analysis.order_block.direction == "BULLISH"

            and

            analysis.fair_value_gap.direction == "BULLISH"

        ):

            signal.signal = "BUY"

            signal.valid = True

            signal.confidence = 1.0

            signal.reason = (
                "Bullish BOS + "
                "Displacement + "
                "Order Block + "
                "Fair Value Gap"
            )

            return signal

        # ---------------------------------
        # SELL
        # ---------------------------------

        if (

            analysis.bos.direction == "BEARISH"

            and

            analysis.displacement.bearish

            and

            analysis.order_block.direction == "BEARISH"

            and

            analysis.fair_value_gap.direction == "BEARISH"

        ):

            signal.signal = "SELL"

            signal.valid = True

            signal.confidence = 1.0

            signal.reason = (
                "Bearish BOS + "
                "Displacement + "
                "Order Block + "
                "Fair Value Gap"
            )

            return signal

        return signal