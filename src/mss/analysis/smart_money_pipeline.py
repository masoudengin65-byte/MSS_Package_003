"""
MSS Smart Money Pipeline
Version : 4.1
Sprint : 54
"""

from mss.analysis.real_swing_engine import RealSwingEngine
from mss.analysis.setup_scoring_engine import SetupScoringEngine
from mss.analysis.structure_engine import StructureEngine
from mss.analysis.confluence_engine import ConfluenceEngine
from mss.domain.pipeline_result import PipelineResult


class SmartMoneyPipeline:

    def __init__(self):

        self.swing_engine = RealSwingEngine()

        self.structure_engine = StructureEngine()

        self.score_engine = SetupScoringEngine()

        self.confluence_engine = ConfluenceEngine()

    def run(
        self,
        symbol,
        timeframe,
        candles,
    ):

        result = PipelineResult(
            symbol=symbol,
            timeframe=timeframe,
        )

        #
        # Empty Data
        #

        if not candles:

            result.logs.append("No candles")

            result.valid = True

            result.recommendation = "WAIT"

            return result

        #
        # Swing Detection
        #

        swings = self.swing_engine.detect(candles)

        result.swing_count = len(swings)

        #
        # Structure Analysis
        #

        analysis = self.structure_engine.analyze(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            swings=swings,
        )

        # Capture the existing strict confluence contract without changing the
        # baseline recommendation or BOS decision path.
        confluence = self.confluence_engine.generate(analysis)
        result.confluence_valid = bool(confluence.valid)
        result.confluence_signal = confluence.signal
        result.confluence_reason = confluence.reason

        #
        # Structure
        #

        if analysis.structure is not None:

            result.structure_state = analysis.structure.state.value

        #
        # Debug Structure Levels
        #

        highs = [s for s in swings if getattr(s, "is_high", False)]

        lows = [s for s in swings if getattr(s, "is_low", False)]

        if len(highs) >= 2:

            result.previous_high = highs[-2].price

            result.last_high = highs[-1].price

        if len(lows) >= 2:

            result.previous_low = lows[-2].price

            result.last_low = lows[-1].price

        #
        # BOS Debug
        #

        result.current_close = candles[-1].close

        result.next_bos_level = None

        result.distance_to_bos = None

        result.distance_to_bos_pips = 0.0

        result.bos_progress = 0.0

        result.bos_status = "RANGE"
        if result.structure_state == "DOWNTREND":

            result.next_bos_level = result.last_low

        elif result.structure_state == "UPTREND":

            result.next_bos_level = result.last_high

        #
        # Calculate BOS Distance
        #

        if result.next_bos_level is not None and result.current_close is not None:

            result.distance_to_bos = abs(result.current_close - result.next_bos_level)

            result.distance_to_bos_pips = round(
                result.distance_to_bos * 10000,
                1,
            )

            result.bos_progress = max(
                0.0,
                min(
                    100.0,
                    (20.0 - result.distance_to_bos_pips) / 20.0 * 100.0,
                ),
            )

            if result.distance_to_bos_pips <= 2:

                result.bos_status = "BREAKING"

            elif result.distance_to_bos_pips <= 5:

                result.bos_status = "NEAR BOS"

            else:

                result.bos_status = "WAIT"

            #
            # Real BOS Detection
            #

            if result.structure_state == "UPTREND":

                if result.current_close > result.next_bos_level:

                    result.bos_detected = True

                    result.bos_direction = "BULLISH"

                    result.bos_status = "BROKEN"

            elif result.structure_state == "DOWNTREND":

                if result.current_close < result.next_bos_level:

                    result.bos_detected = True

                    result.bos_direction = "BEARISH"

                    result.bos_status = "BROKEN"

            result.bos_ready = result.bos_status in [
                "NEAR BOS",
                "BREAKING",
                "BROKEN",
            ]

            #
            # Real CHOCH Detection
            #

            if (
                result.structure_state == "DOWNTREND"
                and result.previous_high is not None
                and result.current_close > result.previous_high
            ):

                result.choch_detected = True
                result.choch_direction = "BULLISH"

            elif (
                result.structure_state == "UPTREND"
                and result.previous_low is not None
                and result.current_close < result.previous_low
            ):

                result.choch_detected = True
                result.choch_direction = "BEARISH"

            #
            # Liquidity Sweep Detection
            #

            result.liquidity_sweep = False

            if (
                result.last_high is not None
                and result.current_close > result.last_high
                and not result.bos_detected
            ):

                result.liquidity_sweep = True

                result.liquidity_side = "BUY"

            elif (
                result.last_low is not None
                and result.current_close < result.last_low
                and not result.bos_detected
            ):
                result.liquidity_sweep = True

                result.liquidity_side = "SELL"

        else:

            result.bos_status = "RANGE"

            result.bos_ready = False

        #
        # BOS
        #
        if analysis.bos is not None:

            result.bos_detected = True

            if hasattr(
                analysis.bos,
                "direction",
            ):

                result.bos_direction = analysis.bos.direction

        #
        # CHOCH
        #

        if analysis.choch is not None:

            result.choch_detected = True

            if hasattr(
                analysis.choch,
                "direction",
            ):

                result.choch_direction = analysis.choch.direction

        #
        # Log
        #

        result.logs.append(f"Swing Count : {result.swing_count}")

        result.logs.append(f"Structure : {result.structure_state}")

        result.logs.append(f"BOS : {result.bos_detected}")

        result.logs.append(f"BOS Status : {result.bos_status}")

        if result.distance_to_bos is None:

            result.logs.append("BOS Distance : -")

        else:
            result.logs.append(f"BOS Distance : {result.distance_to_bos_pips:.1f} pip")
        result.logs.append(f"CHOCH : {result.choch_detected}")

        if result.choch_detected:

            result.logs.append(f"CHOCH Direction : {result.choch_direction}")

        #
        # Score
        #

        score = self.score_engine.calculate(
            bos=result.bos_detected,
            choch=result.choch_detected,
        )

        result.score = score.score

        result.confidence = score.confidence

        #
        # Smart Recommendation Engine
        #

        if result.bos_detected:

            result.recommendation = "TRADE"

        elif result.choch_detected:

            result.recommendation = "WATCH"

        elif getattr(result, "liquidity_sweep", False):

            result.recommendation = "WATCH"

        elif result.bos_status == "BREAKING":

            result.recommendation = "WATCH"

        elif result.bos_status == "NEAR BOS":

            result.recommendation = "WATCH"

        elif result.score >= 80:

            result.recommendation = "BUY"

        elif result.score >= 45:

            result.recommendation = "WATCH"

        else:

            result.recommendation = "WAIT"
            #
            # Liquidity Sweep Log
            #

        if getattr(result, "liquidity_sweep", False):

            result.logs.append("Liquidity Sweep : True")

            result.logs.append(f"Liquidity Side : {result.liquidity_side}")

            if result.recommendation == "WAIT":

                result.recommendation = "WATCH"

        else:

            result.logs.append("Liquidity Sweep : False")

        #
        # Optional Analysis Results
        #

        if hasattr(analysis, "liquidity"):

            result.liquidity_detected = (
                analysis.liquidity.buy_side_liquidity
                or analysis.liquidity.sell_side_liquidity
            )

            if analysis.liquidity.buy_side_liquidity:

                result.liquidity_side = "BUY"

            elif analysis.liquidity.sell_side_liquidity:

                result.liquidity_side = "SELL"

        if hasattr(analysis, "order_block"):

            result.order_block_detected = analysis.order_block.valid

        if hasattr(analysis, "fair_value_gap"):

            result.fair_value_gap_detected = analysis.fair_value_gap.valid

        #
        # Final Log
        #

        result.logs.append(f"Score : {result.score}")

        result.logs.append(f"Confidence : {result.confidence:.2f}")

        result.logs.append(f"Recommendation : {result.recommendation}")

        #
        # Completed
        #

        result.valid = True

        return result
