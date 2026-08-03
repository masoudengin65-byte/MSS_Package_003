"""
MT5 Tick Service
"""

from dataclasses import dataclass

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


@dataclass
class Tick:

    symbol: str
    bid: float
    ask: float
    last: float
    volume: int
    time: int


class TickService:

    def get(self, symbol: str):

        if mt5 is None:
            return None

        tick = mt5.symbol_info_tick(symbol)

        if tick is None:
            return None

        return Tick(
            symbol=symbol,
            bid=tick.bid,
            ask=tick.ask,
            last=tick.last,
            volume=tick.volume,
            time=tick.time,
        )