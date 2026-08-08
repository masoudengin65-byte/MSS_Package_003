"""Domain models for chronological historical paper backtests."""

from dataclasses import dataclass, field
from datetime import datetime

from mss.domain.trade_statistics import TradeStatistics
from mss.domain.context_snapshot import ContextSnapshot
from mss.domain.shadow_score import ShadowScore


@dataclass
class HistoricalBacktestConfig:
    warmup_candles: int = 200
    analysis_lookback: int = 500
    starting_balance: float = 10000.0
    risk_percent: float = 1.0
    reward_risk_ratio: float = 2.0
    spread_points: float | None = None
    commission_per_lot: float = 0.0
    slippage_points: float = 0.0
    ambiguous_policy: str = "STOP_LOSS_FIRST"


@dataclass
class BacktestSymbolMetadata:
    point: float | None = None
    digits: int | None = None
    tick_size: float | None = None
    tick_value: float | None = None
    contract_size: float | None = None
    volume_min: float | None = None
    volume_max: float | None = None
    volume_step: float | None = None
    spread_points: float = 0.0


@dataclass
class HistoricalTrade:
    trade_id: int = 0
    symbol: str = ""
    timeframe: str = ""
    direction: str = ""
    signal_time: datetime | None = None
    entry_time: datetime | None = None
    entry_price: float = 0.0
    stop_loss: float = 0.0
    take_profit: float = 0.0
    exit_time: datetime | None = None
    exit_price: float = 0.0
    exit_reason: str = ""
    spread: float = 0.0
    commission: float = 0.0
    slippage: float = 0.0
    volume: float = 0.0
    profit: float = 0.0
    r_multiple: float = 0.0
    score: int = 0
    confidence: float = 0.0
    legacy_score: int = 0
    legacy_confidence: float = 0.0
    shadow_score: int = 0
    shadow_confidence: float = 0.0
    shadow_score_breakdown: dict[str, int | str] = field(default_factory=dict)
    shadow_score_result: ShadowScore | None = None
    detector_states: dict = field(default_factory=dict)
    context_snapshot: ContextSnapshot | None = None
    status: str = "OPEN"


@dataclass
class BacktestDiagnostics:
    candles_loaded: int = 0
    candles_processed: int = 0
    data_start: datetime | None = None
    data_end: datetime | None = None
    warmup_candles: int = 0
    decisions_generated: int = 0
    buy_signals: int = 0
    sell_signals: int = 0
    wait_results: int = 0
    rejected_trades: int = 0
    rejection_reasons: dict[str, int] = field(default_factory=dict)
    opened_trades: int = 0
    closed_trades: int = 0
    unresolved_trades: int = 0
    skipped_invalid_candles: int = 0
    reordered_candles: int = 0
    runtime_seconds: float = 0.0


@dataclass
class HistoricalMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    average_r: float = 0.0
    maximum_drawdown: float = 0.0
    maximum_drawdown_percent: float = 0.0
    maximum_consecutive_wins: int = 0
    maximum_consecutive_losses: int = 0
    average_holding_minutes: float = 0.0
    ending_balance: float = 0.0
    return_percent: float = 0.0
    equity_curve: list[tuple[int, float]] = field(default_factory=list)


@dataclass
class HistoricalBacktestResult:
    symbol: str = ""
    timeframe: str = ""
    config: HistoricalBacktestConfig = field(default_factory=HistoricalBacktestConfig)
    metadata: BacktestSymbolMetadata = field(default_factory=BacktestSymbolMetadata)
    trades: list[HistoricalTrade] = field(default_factory=list)
    diagnostics: BacktestDiagnostics = field(default_factory=BacktestDiagnostics)
    statistics: TradeStatistics = field(default_factory=TradeStatistics)
    metrics: HistoricalMetrics = field(default_factory=HistoricalMetrics)
    valid: bool = False
