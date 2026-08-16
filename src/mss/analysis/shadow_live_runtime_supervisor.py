from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from mss.analysis.shadow_live_runtime_heartbeat import (
    ShadowLiveHeartbeatInput,
    ShadowLiveRuntimeHeartbeat,
)

from mss.analysis.shadow_live_runtime_telemetry import (
    ShadowLiveRuntimeTelemetry,
    ShadowLiveRuntimeTelemetryState,
)


@dataclass(frozen=True)
class ShadowLiveRuntimeSupervisorInput:
    started_monotonic: float
    now_monotonic: float

    last_heartbeat_monotonic: Optional[float]
    heartbeat_sequence: int
    max_heartbeat_gap_seconds: float

    mt5_connected: bool
    terminal_available: bool
    account_available: bool
    portfolio_recovery_valid: bool


@dataclass(frozen=True)
class ShadowLiveRuntimeSupervisorDecision:
    valid: bool
    healthy: bool
    hard_block: bool

    reason: str
    detail: Optional[str]

    next_last_heartbeat_monotonic: float
    next_heartbeat_sequence: int

    telemetry_state: ShadowLiveRuntimeTelemetryState


class ShadowLiveRuntimeSupervisor:
    REASON_RUNTIME_HEALTHY = (
        "RUNTIME_SUPERVISOR_HEALTHY"
    )

    REASON_MT5_DISCONNECTED = (
        "MT5_NOT_CONNECTED"
    )

    REASON_TERMINAL_UNAVAILABLE = (
        "MT5_TERMINAL_UNAVAILABLE"
    )

    REASON_ACCOUNT_UNAVAILABLE = (
        "MT5_ACCOUNT_UNAVAILABLE"
    )

    REASON_PORTFOLIO_RECOVERY_INVALID = (
        "PORTFOLIO_RECOVERY_INVALID"
    )

    REASON_INVALID_INPUT = (
        "INVALID_RUNTIME_SUPERVISOR_INPUT"
    )

    @classmethod
    def evaluate(
        cls,
        *,
        supervisor: ShadowLiveRuntimeSupervisorInput,
        telemetry_state: ShadowLiveRuntimeTelemetryState,
    ) -> ShadowLiveRuntimeSupervisorDecision:

        if not isinstance(
            supervisor,
            ShadowLiveRuntimeSupervisorInput,
        ):
            return cls._invalid(
                telemetry_state
            )

        boolean_values = (
            supervisor.mt5_connected,
            supervisor.terminal_available,
            supervisor.account_available,
            supervisor.portfolio_recovery_valid,
        )

        if not all(
            isinstance(value, bool)
            for value in boolean_values
        ):
            return cls._invalid(
                telemetry_state
            )

        heartbeat = (
            ShadowLiveRuntimeHeartbeat
            .evaluate(
                ShadowLiveHeartbeatInput(
                    started_monotonic=(
                        supervisor.started_monotonic
                    ),
                    now_monotonic=(
                        supervisor.now_monotonic
                    ),
                    last_heartbeat_monotonic=(
                        supervisor
                        .last_heartbeat_monotonic
                    ),
                    heartbeat_sequence=(
                        supervisor
                        .heartbeat_sequence
                    ),
                    max_heartbeat_gap_seconds=(
                        supervisor
                        .max_heartbeat_gap_seconds
                    ),
                )
            )
        )

        if not heartbeat.valid:
            return cls._invalid(
                telemetry_state
            )

        try:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_heartbeat(
                    telemetry_state,
                    now_monotonic=(
                        supervisor.now_monotonic
                    ),
                    heartbeat_sequence=(
                        heartbeat
                        .next_heartbeat_sequence
                    ),
                    stale=(
                        heartbeat.hard_block
                    ),
                    reason=heartbeat.reason,
                    detail=None,
                )
            )
        except ValueError:
            return cls._invalid(
                telemetry_state
            )

        if heartbeat.hard_block:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_safety_block(
                    telemetry_state,
                    reason=heartbeat.reason,
                    detail=(
                        f"heartbeat_gap_seconds="
                        f"{heartbeat.heartbeat_gap_seconds}"
                    ),
                )
            )

            return cls._decision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=heartbeat.reason,
                detail=(
                    f"heartbeat_gap_seconds="
                    f"{heartbeat.heartbeat_gap_seconds}"
                ),
                heartbeat=heartbeat,
                telemetry_state=telemetry_state,
            )

        if not supervisor.mt5_connected:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_disconnect(
                    telemetry_state,
                    reason=(
                        cls.REASON_MT5_DISCONNECTED
                    ),
                )
            )

            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_safety_block(
                    telemetry_state,
                    reason=(
                        cls.REASON_MT5_DISCONNECTED
                    ),
                )
            )

            return cls._decision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=(
                    cls.REASON_MT5_DISCONNECTED
                ),
                detail=None,
                heartbeat=heartbeat,
                telemetry_state=telemetry_state,
            )

        if not supervisor.terminal_available:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_disconnect(
                    telemetry_state,
                    reason=(
                        cls.REASON_TERMINAL_UNAVAILABLE
                    ),
                )
            )

            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_safety_block(
                    telemetry_state,
                    reason=(
                        cls.REASON_TERMINAL_UNAVAILABLE
                    ),
                )
            )

            return cls._decision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=(
                    cls.REASON_TERMINAL_UNAVAILABLE
                ),
                detail=None,
                heartbeat=heartbeat,
                telemetry_state=telemetry_state,
            )

        if not supervisor.account_available:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_disconnect(
                    telemetry_state,
                    reason=(
                        cls.REASON_ACCOUNT_UNAVAILABLE
                    ),
                )
            )

            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_safety_block(
                    telemetry_state,
                    reason=(
                        cls.REASON_ACCOUNT_UNAVAILABLE
                    ),
                )
            )

            return cls._decision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=(
                    cls.REASON_ACCOUNT_UNAVAILABLE
                ),
                detail=None,
                heartbeat=heartbeat,
                telemetry_state=telemetry_state,
            )

        if not supervisor.portfolio_recovery_valid:
            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_portfolio_recovery_failure(
                    telemetry_state,
                    reason=(
                        cls.REASON_PORTFOLIO_RECOVERY_INVALID
                    ),
                )
            )

            telemetry_state = (
                ShadowLiveRuntimeTelemetry
                .record_safety_block(
                    telemetry_state,
                    reason=(
                        cls.REASON_PORTFOLIO_RECOVERY_INVALID
                    ),
                )
            )

            return cls._decision(
                valid=True,
                healthy=False,
                hard_block=True,
                reason=(
                    cls.REASON_PORTFOLIO_RECOVERY_INVALID
                ),
                detail=None,
                heartbeat=heartbeat,
                telemetry_state=telemetry_state,
            )

        return cls._decision(
            valid=True,
            healthy=True,
            hard_block=False,
            reason=cls.REASON_RUNTIME_HEALTHY,
            detail=None,
            heartbeat=heartbeat,
            telemetry_state=telemetry_state,
        )

    @classmethod
    def _decision(
        cls,
        *,
        valid,
        healthy,
        hard_block,
        reason,
        detail,
        heartbeat,
        telemetry_state,
    ):
        return ShadowLiveRuntimeSupervisorDecision(
            valid=valid,
            healthy=healthy,
            hard_block=hard_block,
            reason=reason,
            detail=detail,
            next_last_heartbeat_monotonic=(
                heartbeat
                .next_last_heartbeat_monotonic
            ),
            next_heartbeat_sequence=(
                heartbeat
                .next_heartbeat_sequence
            ),
            telemetry_state=telemetry_state,
        )

    @classmethod
    def _invalid(
        cls,
        telemetry_state,
    ):
        return ShadowLiveRuntimeSupervisorDecision(
            valid=False,
            healthy=False,
            hard_block=True,
            reason=cls.REASON_INVALID_INPUT,
            detail=None,
            next_last_heartbeat_monotonic=0.0,
            next_heartbeat_sequence=0,
            telemetry_state=telemetry_state,
        )
