from dataclasses import dataclass
from typing import List

from mss.domain.candle import Candle
from mss.analysis.swing_detector import Swing


@dataclass
class MarketContext:

    symbol: str

    timeframe: object

    candles: List[Candle]

    swings: List[Swing]

    last_closed_candle: Candle