from datetime import datetime

from mss.domain.liquidity import Liquidity
from mss.domain.displacement import Displacement


def test_order_block_requirements():

    liquidity = Liquidity(

        sweep_low=True,

    )

    displacement = Displacement(

        bullish=True,

    )

    assert liquidity.sweep_low

    assert displacement.bullish