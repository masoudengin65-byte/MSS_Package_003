from dataclasses import dataclass

from mss.domain.analysis_result import AnalysisResult


@dataclass
class TradeContext:

    symbol: str

    timeframe: object

    analysis: AnalysisResult