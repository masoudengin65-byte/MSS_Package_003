"""Structured MT5 historical-candle load result."""

from dataclasses import dataclass, field

from mss.domain.candle import Candle


@dataclass
class HistoryResult:
    requested_symbol: str = ""
    resolved_symbol: str = ""
    timeframe: object = None
    start_position: int = 0
    requested_count: int = 0
    returned_count: int = 0
    attempts: int = 0
    symbol_selected: bool = False
    error_code: int = 0
    error_message: str = ""
    candles: list[Candle] = field(default_factory=list)
    success: bool = False

    @property
    def diagnostic(self) -> str:
        return (
            f"symbol={self.requested_symbol!r}, "
            f"resolved_symbol={self.resolved_symbol!r}, "
            f"timeframe={self.timeframe!r}, "
            f"start_position={self.start_position}, "
            f"requested_count={self.requested_count}, "
            f"returned_count={self.returned_count}, "
            f"attempts={self.attempts}, "
            f"symbol_selected={self.symbol_selected}, "
            f"last_error=({self.error_code}, {self.error_message!r})"
        )
