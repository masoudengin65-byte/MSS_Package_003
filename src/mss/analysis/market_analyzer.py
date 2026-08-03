"""
MSS Market Analyzer
Version : 2.1
Sprint : 31.1
Compatible : v0.31
"""

from mss.analysis.structure_engine import StructureEngine
from mss.analysis.trade_setup_engine import TradeSetupEngine

from mss.domain.analysis_result import AnalysisResult


class MarketAnalyzer:

    def __init__(self):

        self.structure_engine = StructureEngine()

        self.trade_setup_engine = TradeSetupEngine()

    def analyze(
        self,
        context,
    ) -> AnalysisResult:

        #
        # Safe Guard
        #
        if context is None:

            return AnalysisResult()

        #
        # Structure Analysis
        #
        analysis = self.structure_engine.analyze(

            symbol=context.symbol,

            timeframe=context.timeframe,

            candles=context.candles,

        )

        #
        # Build Trade Setup
        #
        analysis.trade_setup = self.trade_setup_engine.build(

            analysis

        )

        return analysis