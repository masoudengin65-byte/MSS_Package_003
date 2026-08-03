"""
Institutional Order Block Detector
Version 0.3
"""

from mss.domain.order_block import OrderBlock


class OrderBlockDetector:

    def detect(
        self,
        context,
        analysis,
    ):

        ob = OrderBlock()

        # ---------------------------------
        # Preconditions
        # ---------------------------------

        if analysis.bos is None:
            return ob

        if analysis.liquidity is None:
            return ob

        if analysis.displacement is None:
            return ob

        if not (
            analysis.liquidity.sweep_low
            or
            analysis.liquidity.sweep_high
        ):
            return ob

        if not (
            analysis.displacement.bullish
            or
            analysis.displacement.bearish
        ):
            return ob

        candles = context.candles

        if len(candles) < 2:
            return ob

        # =====================================================
        # BULLISH ORDER BLOCK
        # =====================================================

        if analysis.bos.direction == "BULLISH":

            for candle in reversed(candles[:-1]):

                # آخرین کندل نزولی
                if candle.close < candle.open:

                    ob.direction = "BULLISH"
                    ob.open = candle.open
                    ob.close = candle.close
                    ob.high = candle.high
                    ob.low = candle.low
                    ob.candle_time = candle.time

                    # -------------------------
                    # Mitigation Validation
                    # -------------------------

                    body_low = min(ob.open, ob.close)

                    for index, c in enumerate(candles):

                        if c.time <= ob.candle_time:
                            continue

                        if c.close <= body_low:

                            ob.valid = False
                            ob.mitigated = True
                            ob.mitigation_index = index

                            return ob

                    ob.valid = True
                    ob.validated = True

                    return ob

        # =====================================================
        # BEARISH ORDER BLOCK
        # =====================================================

        if analysis.bos.direction == "BEARISH":

            for candle in reversed(candles[:-1]):

                # آخرین کندل صعودی
                if candle.close > candle.open:

                    ob.direction = "BEARISH"
                    ob.open = candle.open
                    ob.close = candle.close
                    ob.high = candle.high
                    ob.low = candle.low
                    ob.candle_time = candle.time

                    # -------------------------
                    # Mitigation Validation
                    # -------------------------

                    body_high = max(ob.open, ob.close)

                    for index, c in enumerate(candles):

                        if c.time <= ob.candle_time:
                            continue

                        if c.close >= body_high:

                            ob.valid = False
                            ob.mitigated = True
                            ob.mitigation_index = index

                            return ob

                    ob.valid = True
                    ob.validated = True

                    return ob

        return ob