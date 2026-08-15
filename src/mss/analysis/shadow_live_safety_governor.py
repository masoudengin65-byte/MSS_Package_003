"""Global shadow-live safety governor.

Sprint 92H.14.5c.1

Pure decision layer:
- no MT5 calls
- no journal reads or writes
- no order_send
- no order_check
- deterministic
- fail-safe by default

The governor consumes already-validated runtime facts.
It does not duplicate portfolio recovery, time authority,
or market eligibility logic.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ShadowLiveSafetyState:
    manual_kill_switch_active: bool

    mt5_connected: bool
    terminal_available: bool
    account_available: bool

    time_authority_confirmed: bool

    portfolio_recovery_valid: bool
    portfolio_snapshot_present: bool
    lifecycle_state_valid: bool
    memory_state_consistent: bool
    governor_state_consistent: bool

    portfolio_limits_valid: bool


@dataclass(frozen=True)
class ShadowLiveSafetyDecision:
    trading_allowed: bool
    hard_block: bool
    reason: str
    kill_conditions: tuple[str, ...]


class ShadowLiveSafetyGovernor:
    """Deterministic global session safety decision."""

    _CHECKS = (
        (
            "MANUAL_KILL_SWITCH_ACTIVE",
            lambda state: state.manual_kill_switch_active,
        ),
        (
            "MT5_NOT_CONNECTED",
            lambda state: not state.mt5_connected,
        ),
        (
            "MT5_TERMINAL_UNAVAILABLE",
            lambda state: not state.terminal_available,
        ),
        (
            "MT5_ACCOUNT_UNAVAILABLE",
            lambda state: not state.account_available,
        ),
        (
            "TIME_AUTHORITY_NOT_CONFIRMED",
            lambda state: not state.time_authority_confirmed,
        ),
        (
            "PORTFOLIO_RECOVERY_INVALID",
            lambda state: not state.portfolio_recovery_valid,
        ),
        (
            "PORTFOLIO_SNAPSHOT_MISSING",
            lambda state: not state.portfolio_snapshot_present,
        ),
        (
            "LIFECYCLE_STATE_INVALID",
            lambda state: not state.lifecycle_state_valid,
        ),
        (
            "MEMORY_STATE_INCONSISTENT",
            lambda state: not state.memory_state_consistent,
        ),
        (
            "GOVERNOR_STATE_INCONSISTENT",
            lambda state: not state.governor_state_consistent,
        ),
        (
            "PORTFOLIO_LIMITS_INVALID",
            lambda state: not state.portfolio_limits_valid,
        ),
    )

    @classmethod
    def evaluate(
        cls,
        state: ShadowLiveSafetyState,
    ) -> ShadowLiveSafetyDecision:

        if not isinstance(
            state,
            ShadowLiveSafetyState,
        ):
            return ShadowLiveSafetyDecision(
                trading_allowed=False,
                hard_block=True,
                reason="INVALID_SAFETY_STATE_INPUT",
                kill_conditions=(
                    "INVALID_SAFETY_STATE_INPUT",
                ),
            )

        kill_conditions = tuple(
            reason
            for reason, predicate in cls._CHECKS
            if predicate(state)
        )

        if kill_conditions:
            return ShadowLiveSafetyDecision(
                trading_allowed=False,
                hard_block=True,
                reason=kill_conditions[0],
                kill_conditions=kill_conditions,
            )

        return ShadowLiveSafetyDecision(
            trading_allowed=True,
            hard_block=False,
            reason="GLOBAL_SAFETY_CONFIRMED",
            kill_conditions=(),
        )
