"""Runtime fact adapter for the shadow-live safety governor.

Sprint 92H.14.5c.2

Pure adapter layer:
- no MT5 calls
- no journal reads or writes
- no order_send
- no order_check
- no duplicated recovery logic
- deterministic and fail-safe

It converts already-established runtime facts into the
ShadowLiveSafetyState consumed by ShadowLiveSafetyGovernor.
"""

from __future__ import annotations

from dataclasses import dataclass
import math

from mss.analysis.shadow_live_safety_governor import (
    ShadowLiveSafetyState,
)


@dataclass(frozen=True)
class ShadowLiveRuntimeSafetyFacts:
    manual_kill_switch_active: bool

    mt5_initialized: bool
    terminal_available: bool
    account_available: bool

    time_authority_confirmed: bool

    portfolio_recovery_valid: bool
    portfolio_snapshot_present: bool
    lifecycle_state_valid: bool
    memory_state_consistent: bool
    governor_state_consistent: bool

    open_position_count: int
    total_open_risk_percent: float

    max_open_positions: int
    max_total_open_risk_percent: float


class ShadowLiveRuntimeSafetyAdapter:
    """Convert validated runtime facts into global safety state."""

    @staticmethod
    def _portfolio_limits_valid(
        *,
        open_position_count: int,
        total_open_risk_percent: float,
        max_open_positions: int,
        max_total_open_risk_percent: float,
    ) -> bool:

        try:
            count = int(open_position_count)
            risk = float(total_open_risk_percent)
            max_count = int(max_open_positions)
            max_risk = float(
                max_total_open_risk_percent
            )
        except (
            TypeError,
            ValueError,
            OverflowError,
        ):
            return False

        if count < 0:
            return False

        if max_count < 0:
            return False

        if not math.isfinite(risk):
            return False

        if not math.isfinite(max_risk):
            return False

        if risk < 0.0:
            return False

        if max_risk < 0.0:
            return False

        if count > max_count:
            return False

        if risk > max_risk:
            return False

        return True

    @classmethod
    def build(
        cls,
        facts: ShadowLiveRuntimeSafetyFacts,
    ) -> ShadowLiveSafetyState:

        if not isinstance(
            facts,
            ShadowLiveRuntimeSafetyFacts,
        ):
            return ShadowLiveSafetyState(
                manual_kill_switch_active=True,
                mt5_connected=False,
                terminal_available=False,
                account_available=False,
                time_authority_confirmed=False,
                portfolio_recovery_valid=False,
                portfolio_snapshot_present=False,
                lifecycle_state_valid=False,
                memory_state_consistent=False,
                governor_state_consistent=False,
                portfolio_limits_valid=False,
            )

        portfolio_limits_valid = (
            cls._portfolio_limits_valid(
                open_position_count=(
                    facts.open_position_count
                ),
                total_open_risk_percent=(
                    facts.total_open_risk_percent
                ),
                max_open_positions=(
                    facts.max_open_positions
                ),
                max_total_open_risk_percent=(
                    facts.max_total_open_risk_percent
                ),
            )
        )

        return ShadowLiveSafetyState(
            manual_kill_switch_active=bool(
                facts.manual_kill_switch_active
            ),
            mt5_connected=bool(
                facts.mt5_initialized
            ),
            terminal_available=bool(
                facts.terminal_available
            ),
            account_available=bool(
                facts.account_available
            ),
            time_authority_confirmed=bool(
                facts.time_authority_confirmed
            ),
            portfolio_recovery_valid=bool(
                facts.portfolio_recovery_valid
            ),
            portfolio_snapshot_present=bool(
                facts.portfolio_snapshot_present
            ),
            lifecycle_state_valid=bool(
                facts.lifecycle_state_valid
            ),
            memory_state_consistent=bool(
                facts.memory_state_consistent
            ),
            governor_state_consistent=bool(
                facts.governor_state_consistent
            ),
            portfolio_limits_valid=(
                portfolio_limits_valid
            ),
        )
