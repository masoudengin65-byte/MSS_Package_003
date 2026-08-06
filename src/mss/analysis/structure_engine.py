from mss.analysis.swing_detector import SwingDetector
from mss.analysis.swing_filter import SwingFilter
from mss.analysis.swing_validator import SwingValidator

from mss.analysis.structure_state import StructureStateEngine
from mss.analysis.liquidity_detector import LiquidityDetector
from mss.analysis.displacement_detector import DisplacementDetector
from mss.analysis.bos_detector import BOSDetector
from mss.analysis.choch_detector import CHoCHDetector
from mss.analysis.premium_discount_engine import PremiumDiscountEngine
from mss.analysis.order_block_detector import OrderBlockDetector
from mss.analysis.fvg_detector import FairValueGapDetector

from mss.domain.market_context import MarketContext
from mss.domain.analysis_result import AnalysisResult


class StructureEngine:

    def __init__(self):

        self.swing_detector = SwingDetector()

        self.swing_filter = SwingFilter()

        self.swing_validator = SwingValidator()

        self.structure_engine = StructureStateEngine()

        self.liquidity_detector = LiquidityDetector()

        self.displacement_detector = DisplacementDetector()

        self.bos_detector = BOSDetector()

        self.choch_detector = CHoCHDetector()

        self.premium_discount_engine = PremiumDiscountEngine()

        self.order_block_detector = OrderBlockDetector()

        self.fvg_detector = FairValueGapDetector()

    def analyze(

        self,

        symbol,

        timeframe,

        candles,

        swings=None,

    ):

        #
        # Empty candles
        #
        if not candles:

            return AnalysisResult(

                symbol=symbol,

                timeframe=timeframe,

            )

        #
        # Use external swings if Pipeline provides them.
        #
        if swings is None:

            swings = self.swing_detector.find(

                candles

            )

            swings = self.swing_filter.filter(

                swings

            )

            swings = self.swing_validator.validate(

                swings

            )

        #
        # Build market context
        #
        context = MarketContext(

            symbol=symbol,

            timeframe=timeframe,

            candles=candles,

            swings=swings,

            last_closed_candle=candles[-1],

        )

        #
        # Structure
        #
        structure = self.structure_engine.detect(

            swings

        )

        #
        # Liquidity
        #
        liquidity = self.liquidity_detector.detect(

            context

        )

        #
        # Displacement
        #
        displacement = self.displacement_detector.detect(

            context

        )

        #
        # BOS
        #
        bos = self.bos_detector.detect(

            context

        )

        #
        # CHOCH
        #
        choch = self.choch_detector.detect(

            structure,

            bos,

        )

        # Reuse the swings already supplied to the structure analysis.
        premium_discount = self.premium_discount_engine.calculate(

            swings,

            candles[-1].close,

        )

        #
        # Result
        #
        analysis = AnalysisResult(

            symbol=symbol,

            timeframe=timeframe,

            structure=structure,

            liquidity=liquidity,

            displacement=displacement,

            bos=bos,

            choch=choch,

            premium_discount=premium_discount,

        )

        # Connect completed detectors without changing their detection rules.
        analysis.order_block = self.order_block_detector.detect(

            context,

            analysis,

        )

        analysis.fair_value_gap = self.fvg_detector.detect(

            context,

            analysis,

        )

        return analysis
