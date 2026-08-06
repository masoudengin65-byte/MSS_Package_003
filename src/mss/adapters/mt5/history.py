from datetime import datetime
from time import sleep

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None

from mss.domain.candle import Candle
from mss.domain.history_result import HistoryResult


class HistoryLoadError(RuntimeError):
    def __init__(self, result: HistoryResult):
        self.result = result
        super().__init__(f"MT5 history retrieval failed: {result.diagnostic}")


class HistoryService:

    TIMEFRAMES = {
        "M5": "TIMEFRAME_M5",
        "M15": "TIMEFRAME_M15",
        "H1": "TIMEFRAME_H1",
        "H4": "TIMEFRAME_H4",
    }

    def __init__(self, max_attempts=3, retry_delay=0.25):
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay = max(0.0, float(retry_delay))

    def last(self, symbol: str, timeframe, count: int = 100):

        result = self.load(symbol, timeframe, count)

        if not result.success:
            raise HistoryLoadError(result)

        return result.candles

    def load(
        self,
        symbol: str,
        timeframe,
        count: int = 100,
        start_position: int = 0,
    ) -> HistoryResult:

        resolved_timeframe = self._resolve_timeframe(timeframe)
        result = HistoryResult(
            requested_symbol=symbol,
            timeframe=resolved_timeframe,
            start_position=start_position,
            requested_count=count,
        )

        if mt5 is None:
            result.error_message = "MetaTrader5 package not installed"
            return result

        resolved_symbol = self._resolve_symbol(symbol)
        result.resolved_symbol = resolved_symbol or ""

        if resolved_symbol is None:
            self._set_last_error(result)
            if not result.error_message:
                result.error_message = "Symbol not found"
            return result

        result.symbol_selected = bool(mt5.symbol_select(resolved_symbol, True))
        if not result.symbol_selected:
            self._set_last_error(result)
            return result

        rates = None
        for attempt in range(1, self.max_attempts + 1):
            result.attempts = attempt
            rates = mt5.copy_rates_from_pos(
                resolved_symbol,
                resolved_timeframe,
                start_position,
                count,
            )

            if rates is not None and len(rates) > 0:
                break

            self._set_last_error(result)
            if attempt < self.max_attempts and self.retry_delay:
                sleep(self.retry_delay)

        if rates is None or len(rates) == 0:
            self._set_last_error(result)
            return result

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

        result.candles = candles
        result.returned_count = len(candles)
        result.success = True
        self._set_last_error(result)
        return result

    def _resolve_symbol(self, requested_symbol):
        if mt5.symbol_info(requested_symbol) is not None:
            return requested_symbol

        matches = mt5.symbols_get(group=f"*{requested_symbol}*") or []
        requested_upper = requested_symbol.upper()
        names = [item.name for item in matches]

        for name in names:
            if name.upper().startswith(requested_upper):
                return name

        return names[0] if names else None

    @classmethod
    def _resolve_timeframe(cls, timeframe):
        if not isinstance(timeframe, str):
            return timeframe

        attribute = cls.TIMEFRAMES.get(timeframe.upper())
        if attribute is None or mt5 is None:
            raise ValueError(f"Unsupported MT5 timeframe: {timeframe}")

        return getattr(mt5, attribute)

    @staticmethod
    def _set_last_error(result):
        error = mt5.last_error()
        if error is None:
            return
        result.error_code = int(error[0])
        result.error_message = str(error[1])
