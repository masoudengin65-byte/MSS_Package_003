"""Correlation and portfolio exposure result."""

from dataclasses import dataclass, field


@dataclass
class PortfolioExposure:
    portfolio_exposure: float = 0.0
    currency_exposure: dict[str, float] = field(default_factory=dict)
    asset_exposure: dict[str, float] = field(default_factory=dict)
    correlation_level: str = "LOW"
    correlation_percent: float = 0.0
    portfolio_risk_score: float = 0.0
    risk_level: str = "LOW"
    open_positions: int = 0
    valid: bool = False
