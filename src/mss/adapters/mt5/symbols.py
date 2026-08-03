"""
MT5 Symbol Service
"""

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from mss.domain.symbol import Symbol


class SymbolService:

    def all(self):

        if mt5 is None:
            return []

        symbols = mt5.symbols_get()

        if symbols is None:
            return []

        result = []

        for s in symbols:

            result.append(
                Symbol(
                    name=s.name,
                    description=s.description,
                    path=s.path,
                    digits=s.digits,
                    spread=s.spread,
                    trade_mode=s.trade_mode,
                    visible=s.visible,
                )
            )

        return result