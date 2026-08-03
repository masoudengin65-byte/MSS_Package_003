from dataclasses import dataclass, field

from mss.analysis.structure_state import MarketStructure
from mss.analysis.bos_detector import BOS
from mss.analysis.choch_detector import CHoCH

from mss.domain.liquidity import Liquidity
from mss.domain.displacement import Displacement
from mss.domain.order_block import OrderBlock
from mss.domain.fair_value_gap import FairValueGap
from mss.domain.trade_setup import TradeSetup


@dataclass
class AnalysisResult:

    symbol: str = ""

    timeframe: object = None

    structure: MarketStructure | None = None

    liquidity: Liquidity = field(default_factory=Liquidity)

    displacement: Displacement = field(default_factory=Displacement)

    bos: BOS | None = None

    choch: CHoCH | None = None

    order_block: OrderBlock = field(default_factory=OrderBlock)

    fair_value_gap: FairValueGap = field(default_factory=FairValueGap)

    trade_setup: TradeSetup = field(
        default_factory=TradeSetup
    )