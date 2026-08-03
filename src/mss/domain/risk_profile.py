"""
MSS Risk Profile
Version : 1.0
Sprint : 9.2
Compatible : v0.19
"""

from dataclasses import dataclass


@dataclass
class RiskProfile:

    account_balance: float = 0.0

    risk_percent: float = 1.0

    risk_amount: float = 0.0

    stop_distance: float = 0.0

    lot_size: float = 0.0

    valid: bool = False