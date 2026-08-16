from mss.analysis.shadow_live_runtime_supervisor import (
    ShadowLiveRuntimeSupervisor,
    ShadowLiveRuntimeSupervisorInput,
)

from mss.analysis.shadow_live_runtime_telemetry import (
    ShadowLiveRuntimeTelemetry,
)


def telemetry():
    return (
        ShadowLiveRuntimeTelemetry
        .initialize(
            started_monotonic=100.0
        )
    )


def supervisor(
    *,
    now=100.0,
    last=None,
    sequence=0,
    max_gap=5.0,
    mt5_connected=True,
    terminal_available=True,
    account_available=True,
    portfolio_recovery_valid=True,
):
    return ShadowLiveRuntimeSupervisorInput(
        started_monotonic=100.0,
        now_monotonic=now,
        last_heartbeat_monotonic=last,
        heartbeat_sequence=sequence,
        max_heartbeat_gap_seconds=max_gap,
        mt5_connected=mt5_connected,
        terminal_available=terminal_available,
        account_available=account_available,
        portfolio_recovery_valid=portfolio_recovery_valid,
    )


def test_initial_runtime_health_is_allowed():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(),
            telemetry_state=telemetry(),
        )
    )

    assert result.valid
    assert result.healthy
    assert not result.hard_block

    assert result.reason == (
        "RUNTIME_SUPERVISOR_HEALTHY"
    )

    assert (
        result.next_heartbeat_sequence
        == 1
    )


def test_normal_followup_runtime_health_is_allowed():
    first = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(),
            telemetry_state=telemetry(),
        )
    )

    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                now=103.0,
                last=(
                    first
                    .next_last_heartbeat_monotonic
                ),
                sequence=(
                    first
                    .next_heartbeat_sequence
                ),
            ),
            telemetry_state=(
                first.telemetry_state
            ),
        )
    )

    assert result.valid
    assert result.healthy
    assert not result.hard_block

    assert (
        result.telemetry_state
        .heartbeat_count
        == 2
    )


def test_stale_heartbeat_hard_blocks():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                now=110.0,
                last=100.0,
                sequence=1,
                max_gap=5.0,
            ),
            telemetry_state=telemetry(),
        )
    )

    assert result.valid
    assert not result.healthy
    assert result.hard_block

    assert result.reason == (
        "RUNTIME_HEARTBEAT_STALE"
    )

    assert (
        result.telemetry_state
        .stale_heartbeat_count
        == 1
    )

    assert (
        result.telemetry_state
        .global_safety_block_count
        == 1
    )


def test_mt5_disconnect_hard_blocks_and_counts_disconnect():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                mt5_connected=False
            ),
            telemetry_state=telemetry(),
        )
    )

    assert result.hard_block

    assert result.reason == (
        "MT5_NOT_CONNECTED"
    )

    assert (
        result.telemetry_state
        .runtime_disconnect_count
        == 1
    )

    assert (
        result.telemetry_state
        .global_safety_block_count
        == 1
    )


def test_terminal_unavailable_hard_blocks():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                terminal_available=False
            ),
            telemetry_state=telemetry(),
        )
    )

    assert result.hard_block

    assert result.reason == (
        "MT5_TERMINAL_UNAVAILABLE"
    )


def test_account_unavailable_hard_blocks():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                account_available=False
            ),
            telemetry_state=telemetry(),
        )
    )

    assert result.hard_block

    assert result.reason == (
        "MT5_ACCOUNT_UNAVAILABLE"
    )


def test_portfolio_recovery_failure_hard_blocks_and_counts():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=supervisor(
                portfolio_recovery_valid=False
            ),
            telemetry_state=telemetry(),
        )
    )

    assert result.hard_block

    assert result.reason == (
        "PORTFOLIO_RECOVERY_INVALID"
    )

    assert (
        result.telemetry_state
        .portfolio_recovery_failure_count
        == 1
    )

    assert (
        result.telemetry_state
        .global_safety_block_count
        == 1
    )


def test_invalid_supervisor_input_is_fail_safe():
    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=None,
            telemetry_state=telemetry(),
        )
    )

    assert not result.valid
    assert not result.healthy
    assert result.hard_block

    assert result.reason == (
        "INVALID_RUNTIME_SUPERVISOR_INPUT"
    )


def test_non_boolean_runtime_flag_is_rejected():
    bad = supervisor()

    bad = (
        ShadowLiveRuntimeSupervisorInput(
            started_monotonic=(
                bad.started_monotonic
            ),
            now_monotonic=(
                bad.now_monotonic
            ),
            last_heartbeat_monotonic=(
                bad.last_heartbeat_monotonic
            ),
            heartbeat_sequence=(
                bad.heartbeat_sequence
            ),
            max_heartbeat_gap_seconds=(
                bad.max_heartbeat_gap_seconds
            ),
            mt5_connected=1,
            terminal_available=True,
            account_available=True,
            portfolio_recovery_valid=True,
        )
    )

    result = (
        ShadowLiveRuntimeSupervisor
        .evaluate(
            supervisor=bad,
            telemetry_state=telemetry(),
        )
    )

    assert not result.valid
    assert result.hard_block


def test_supervisor_has_no_direct_mt5_dependency():
    import inspect
    import mss.analysis.shadow_live_runtime_supervisor as module

    source = inspect.getsource(
        module
    )

    assert "MetaTrader5" not in source
    assert "mt5." not in source
    assert "order_send(" not in source
    assert "order_check(" not in source


def test_supervisor_has_no_wall_clock_dependency():
    import inspect
    import mss.analysis.shadow_live_runtime_supervisor as module

    source = inspect.getsource(
        module
    )

    assert "time.time(" not in source
    assert "datetime" not in source
    assert "timezone" not in source
