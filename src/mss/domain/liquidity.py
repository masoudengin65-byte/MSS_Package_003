from dataclasses import dataclass


@dataclass
class Liquidity:

    equal_high: bool = False

    equal_low: bool = False

    buy_side_liquidity: bool = False

    sell_side_liquidity: bool = False

    sweep_high: bool = False

    sweep_low: bool = False

    level: float | None = None