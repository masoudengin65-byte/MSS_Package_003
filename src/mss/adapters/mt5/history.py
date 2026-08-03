from datetime import datetime

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from mss.domain.candle import Candle


class HistoryService:

    def last(self, symbol: str, timeframe, count: int = 100):

        if mt5 is None:
            return []

        rates = mt5.copy_rates_from_pos(
            symbol,
            timeframe,
            0,
            count
        )

        if rates is None:
            return []

        candles = []

        for r in rates:

            candles.append(
                Candle(
                    time=datetime.fromtimestamp(r["time"]),
                    open=r["open"],
                    high=r["high"],
                    low=r["low"],
                    close=r["close"],
                    tick_volume=r["tick_volume"],
                    spread=r["spread"],
                    real_volume=r["real_volume"],
                )
            )

        return candles