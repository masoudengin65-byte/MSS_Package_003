from __future__ import annotations

from dataclasses import dataclass, replace
import math
from typing import Optional


@dataclass(frozen=True)
class ShadowLiveRuntimeTelemetryState:
    session_started_monotonic: float

    heartbeat_sequence: int = 0
    heartbeat_count: int = 0
    stale_heartbeat_count: int = 0

    global_safety_block_count: int = 0
    runtime_disconnect_count: int = 0
    portfolio_recovery_failure_count: int = 0

    last_heartbeat_monotonic: Optional[float] = None
    last_runtime_reason: Optional[str] = None
    last_runtime_detail: Optional[str] = None


@dataclass(frozen=True)
class ShadowLiveRuntimeTelemetrySnapshot:
    valid: bool
    reason: str

    uptime_seconds: float

    heartbeat_sequence: int
    heartbeat_count: int
    stale_heartbeat_count: int

    global_safety_block_count: int
    runtime_disconnect_count: int
    portfolio_recovery_failure_count: int

    last_runtime_reason: Optional[str]
    last_runtime_detail: Optional[str]


class ShadowLiveRuntimeTelemetry:
    REASON_OK = (
        "RUNTIME_TELEMETRY_OK"
    )

    REASON_INVALID = (
        "INVALID_RUNTIME_TELEMETRY_STATE"
    )

    @classmethod
    def initialize(
        cls,
        *,
        started_monotonic: float,
    ) -> ShadowLiveRuntimeTelemetryState:
        if (
            not isinstance(
                started_monotonic,
                (int, float),
            )
            or
            not math.isfinite(
                float(started_monotonic)
            )
            or
            float(started_monotonic) < 0.0
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        return ShadowLiveRuntimeTelemetryState(
            session_started_monotonic=float(
                started_monotonic
            )
        )

    @classmethod
    def record_heartbeat(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        *,
        now_monotonic: float,
        heartbeat_sequence: int,
        stale: bool,
        reason: str,
        detail: Optional[str] = None,
    ) -> ShadowLiveRuntimeTelemetryState:
        cls._validate_state(
            state
        )

        cls._validate_now(
            state,
            now_monotonic,
        )

        if (
            not isinstance(
                heartbeat_sequence,
                int,
            )
            or
            isinstance(
                heartbeat_sequence,
                bool,
            )
            or
            heartbeat_sequence <= 0
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        if (
            heartbeat_sequence
            <=
            state.heartbeat_sequence
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        if not isinstance(
            stale,
            bool,
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        cls._validate_reason(
            reason
        )

        return replace(
            state,
            heartbeat_sequence=(
                heartbeat_sequence
            ),
            heartbeat_count=(
                state.heartbeat_count
                + 1
            ),
            stale_heartbeat_count=(
                state.stale_heartbeat_count
                + (1 if stale else 0)
            ),
            last_heartbeat_monotonic=float(
                now_monotonic
            ),
            last_runtime_reason=reason,
            last_runtime_detail=detail,
        )

    @classmethod
    def record_safety_block(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        *,
        reason: str,
        detail: Optional[str] = None,
    ) -> ShadowLiveRuntimeTelemetryState:
        cls._validate_state(
            state
        )

        cls._validate_reason(
            reason
        )

        return replace(
            state,
            global_safety_block_count=(
                state.global_safety_block_count
                + 1
            ),
            last_runtime_reason=reason,
            last_runtime_detail=detail,
        )

    @classmethod
    def record_disconnect(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        *,
        reason: str,
        detail: Optional[str] = None,
    ) -> ShadowLiveRuntimeTelemetryState:
        cls._validate_state(
            state
        )

        cls._validate_reason(
            reason
        )

        return replace(
            state,
            runtime_disconnect_count=(
                state.runtime_disconnect_count
                + 1
            ),
            last_runtime_reason=reason,
            last_runtime_detail=detail,
        )

    @classmethod
    def record_portfolio_recovery_failure(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        *,
        reason: str,
        detail: Optional[str] = None,
    ) -> ShadowLiveRuntimeTelemetryState:
        cls._validate_state(
            state
        )

        cls._validate_reason(
            reason
        )

        return replace(
            state,
            portfolio_recovery_failure_count=(
                state.portfolio_recovery_failure_count
                + 1
            ),
            last_runtime_reason=reason,
            last_runtime_detail=detail,
        )

    @classmethod
    def snapshot(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        *,
        now_monotonic: float,
    ) -> ShadowLiveRuntimeTelemetrySnapshot:
        try:
            cls._validate_state(
                state
            )

            cls._validate_now(
                state,
                now_monotonic,
            )

        except ValueError:
            return (
                ShadowLiveRuntimeTelemetrySnapshot(
                    valid=False,
                    reason=cls.REASON_INVALID,
                    uptime_seconds=0.0,
                    heartbeat_sequence=0,
                    heartbeat_count=0,
                    stale_heartbeat_count=0,
                    global_safety_block_count=0,
                    runtime_disconnect_count=0,
                    portfolio_recovery_failure_count=0,
                    last_runtime_reason=None,
                    last_runtime_detail=None,
                )
            )

        return ShadowLiveRuntimeTelemetrySnapshot(
            valid=True,
            reason=cls.REASON_OK,
            uptime_seconds=(
                float(now_monotonic)
                -
                state.session_started_monotonic
            ),
            heartbeat_sequence=(
                state.heartbeat_sequence
            ),
            heartbeat_count=(
                state.heartbeat_count
            ),
            stale_heartbeat_count=(
                state.stale_heartbeat_count
            ),
            global_safety_block_count=(
                state.global_safety_block_count
            ),
            runtime_disconnect_count=(
                state.runtime_disconnect_count
            ),
            portfolio_recovery_failure_count=(
                state.portfolio_recovery_failure_count
            ),
            last_runtime_reason=(
                state.last_runtime_reason
            ),
            last_runtime_detail=(
                state.last_runtime_detail
            ),
        )

    @classmethod
    def _validate_state(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
    ) -> None:
        if not isinstance(
            state,
            ShadowLiveRuntimeTelemetryState,
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        numeric_counters = (
            state.heartbeat_sequence,
            state.heartbeat_count,
            state.stale_heartbeat_count,
            state.global_safety_block_count,
            state.runtime_disconnect_count,
            state.portfolio_recovery_failure_count,
        )

        if any(
            (
                not isinstance(value, int)
                or isinstance(value, bool)
                or value < 0
            )
            for value in numeric_counters
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        started = (
            state.session_started_monotonic
        )

        if (
            not isinstance(
                started,
                (int, float),
            )
            or
            not math.isfinite(
                float(started)
            )
            or
            float(started) < 0.0
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        if (
            state.last_heartbeat_monotonic
            is not None
        ):
            last = (
                state.last_heartbeat_monotonic
            )

            if (
                not isinstance(
                    last,
                    (int, float),
                )
                or
                not math.isfinite(
                    float(last)
                )
                or
                float(last)
                <
                float(started)
            ):
                raise ValueError(
                    cls.REASON_INVALID
                )

    @classmethod
    def _validate_now(
        cls,
        state: ShadowLiveRuntimeTelemetryState,
        now_monotonic: float,
    ) -> None:
        if (
            not isinstance(
                now_monotonic,
                (int, float),
            )
            or
            not math.isfinite(
                float(now_monotonic)
            )
            or
            float(now_monotonic)
            <
            state.session_started_monotonic
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

        if (
            state.last_heartbeat_monotonic
            is not None
            and
            float(now_monotonic)
            <
            state.last_heartbeat_monotonic
        ):
            raise ValueError(
                cls.REASON_INVALID
            )

    @classmethod
    def _validate_reason(
        cls,
        reason: str,
    ) -> None:
        if (
            not isinstance(
                reason,
                str,
            )
            or
            not reason.strip()
        ):
            raise ValueError(
                cls.REASON_INVALID
            )
