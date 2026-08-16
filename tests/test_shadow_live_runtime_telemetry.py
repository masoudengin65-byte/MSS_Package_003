import math

import pytest

from mss.analysis.shadow_live_runtime_telemetry import (
    ShadowLiveRuntimeTelemetry,
    ShadowLiveRuntimeTelemetryState,
)


def new_state():
    return (
        ShadowLiveRuntimeTelemetry
        .initialize(
            started_monotonic=100.0
        )
    )


def test_initialize_creates_clean_runtime_state():
    state = new_state()

    assert (
        state.session_started_monotonic
        == 100.0
    )

    assert state.heartbeat_sequence == 0
    assert state.heartbeat_count == 0
    assert state.stale_heartbeat_count == 0
    assert state.global_safety_block_count == 0
    assert state.runtime_disconnect_count == 0


def test_initialize_rejects_invalid_monotonic_start():
    for value in (
        -1.0,
        math.nan,
        math.inf,
        -math.inf,
    ):
        with pytest.raises(
            ValueError
        ):
            (
                ShadowLiveRuntimeTelemetry
                .initialize(
                    started_monotonic=value
                )
            )


def test_healthy_heartbeat_advances_sequence_and_count():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_heartbeat(
            state,
            now_monotonic=101.0,
            heartbeat_sequence=1,
            stale=False,
            reason="RUNTIME_HEARTBEAT_HEALTHY",
        )
    )

    assert state.heartbeat_sequence == 1
    assert state.heartbeat_count == 1
    assert state.stale_heartbeat_count == 0

    assert (
        state.last_heartbeat_monotonic
        == 101.0
    )


def test_stale_heartbeat_increments_stale_counter():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_heartbeat(
            state,
            now_monotonic=110.0,
            heartbeat_sequence=1,
            stale=True,
            reason="RUNTIME_HEARTBEAT_STALE",
        )
    )

    assert state.heartbeat_count == 1
    assert state.stale_heartbeat_count == 1


def test_heartbeat_sequence_must_move_forward():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_heartbeat(
            state,
            now_monotonic=101.0,
            heartbeat_sequence=1,
            stale=False,
            reason="OK",
        )
    )

    with pytest.raises(
        ValueError
    ):
        (
            ShadowLiveRuntimeTelemetry
            .record_heartbeat(
                state,
                now_monotonic=102.0,
                heartbeat_sequence=1,
                stale=False,
                reason="OK",
            )
        )


def test_safety_block_counter_is_monotonic():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_safety_block(
            state,
            reason="MANUAL_KILL_SWITCH_ACTIVE",
        )
    )

    state = (
        ShadowLiveRuntimeTelemetry
        .record_safety_block(
            state,
            reason="MT5_NOT_CONNECTED",
        )
    )

    assert (
        state.global_safety_block_count
        == 2
    )

    assert (
        state.last_runtime_reason
        == "MT5_NOT_CONNECTED"
    )


def test_disconnect_counter_is_independent():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_disconnect(
            state,
            reason="MT5_NOT_CONNECTED",
        )
    )

    assert (
        state.runtime_disconnect_count
        == 1
    )

    assert (
        state.global_safety_block_count
        == 0
    )


def test_portfolio_recovery_failure_counter_is_independent():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_portfolio_recovery_failure(
            state,
            reason="PORTFOLIO_RECOVERY_INVALID",
            detail="TEST_DETAIL",
        )
    )

    assert (
        state.portfolio_recovery_failure_count
        == 1
    )

    assert (
        state.last_runtime_detail
        == "TEST_DETAIL"
    )


def test_snapshot_reports_uptime_and_counters():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_heartbeat(
            state,
            now_monotonic=101.0,
            heartbeat_sequence=1,
            stale=False,
            reason="OK",
        )
    )

    state = (
        ShadowLiveRuntimeTelemetry
        .record_safety_block(
            state,
            reason="TEST_BLOCK",
        )
    )

    snapshot = (
        ShadowLiveRuntimeTelemetry
        .snapshot(
            state,
            now_monotonic=110.0,
        )
    )

    assert snapshot.valid

    assert snapshot.reason == (
        "RUNTIME_TELEMETRY_OK"
    )

    assert snapshot.uptime_seconds == 10.0
    assert snapshot.heartbeat_count == 1

    assert (
        snapshot.global_safety_block_count
        == 1
    )


def test_snapshot_rejects_clock_regression():
    state = new_state()

    state = (
        ShadowLiveRuntimeTelemetry
        .record_heartbeat(
            state,
            now_monotonic=105.0,
            heartbeat_sequence=1,
            stale=False,
            reason="OK",
        )
    )

    snapshot = (
        ShadowLiveRuntimeTelemetry
        .snapshot(
            state,
            now_monotonic=104.0,
        )
    )

    assert not snapshot.valid

    assert snapshot.reason == (
        "INVALID_RUNTIME_TELEMETRY_STATE"
    )


def test_empty_reason_is_rejected():
    state = new_state()

    with pytest.raises(
        ValueError
    ):
        (
            ShadowLiveRuntimeTelemetry
            .record_safety_block(
                state,
                reason="",
            )
        )


def test_state_is_immutable():
    state = new_state()

    with pytest.raises(
        Exception
    ):
        state.heartbeat_count = 99


def test_invalid_state_counter_is_fail_safe():
    state = (
        ShadowLiveRuntimeTelemetryState(
            session_started_monotonic=100.0,
            heartbeat_count=-1,
        )
    )

    snapshot = (
        ShadowLiveRuntimeTelemetry
        .snapshot(
            state,
            now_monotonic=101.0,
        )
    )

    assert not snapshot.valid


def test_runtime_telemetry_has_no_wall_clock_dependency():
    import inspect
    import mss.analysis.shadow_live_runtime_telemetry as module

    source = inspect.getsource(
        module
    )

    assert "time.time(" not in source
    assert "datetime" not in source
    assert "timezone" not in source
    assert "MT5" not in source
