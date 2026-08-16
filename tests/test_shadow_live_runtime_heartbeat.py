import math

from mss.analysis.shadow_live_runtime_heartbeat import (
    ShadowLiveHeartbeatInput,
    ShadowLiveRuntimeHeartbeat,
)


def evaluate(
    *,
    started=100.0,
    now=100.0,
    last=None,
    sequence=0,
    max_gap=5.0,
):
    return (
        ShadowLiveRuntimeHeartbeat
        .evaluate(
            ShadowLiveHeartbeatInput(
                started_monotonic=started,
                now_monotonic=now,
                last_heartbeat_monotonic=last,
                heartbeat_sequence=sequence,
                max_heartbeat_gap_seconds=max_gap,
            )
        )
    )


def test_first_heartbeat_initializes_liveness():
    result = evaluate()

    assert result.valid
    assert result.healthy
    assert not result.hard_block

    assert result.reason == (
        "RUNTIME_HEARTBEAT_INITIALIZED"
    )

    assert (
        result.next_heartbeat_sequence
        == 1
    )

    assert (
        result.next_last_heartbeat_monotonic
        == 100.0
    )


def test_normal_heartbeat_is_healthy():
    result = evaluate(
        now=103.0,
        last=100.0,
        sequence=1,
    )

    assert result.valid
    assert result.healthy
    assert not result.hard_block

    assert result.reason == (
        "RUNTIME_HEARTBEAT_HEALTHY"
    )

    assert result.heartbeat_gap_seconds == 3.0
    assert result.uptime_seconds == 3.0
    assert result.next_heartbeat_sequence == 2


def test_exact_maximum_gap_is_still_healthy():
    result = evaluate(
        now=105.0,
        last=100.0,
        sequence=1,
        max_gap=5.0,
    )

    assert result.healthy
    assert not result.hard_block
    assert result.heartbeat_gap_seconds == 5.0


def test_gap_above_limit_is_hard_block():
    result = evaluate(
        now=105.001,
        last=100.0,
        sequence=1,
        max_gap=5.0,
    )

    assert result.valid
    assert not result.healthy
    assert result.hard_block

    assert result.reason == (
        "RUNTIME_HEARTBEAT_STALE"
    )


def test_stale_heartbeat_still_advances_observation_state():
    result = evaluate(
        now=110.0,
        last=100.0,
        sequence=7,
        max_gap=5.0,
    )

    assert result.hard_block

    assert (
        result.next_last_heartbeat_monotonic
        == 110.0
    )

    assert (
        result.next_heartbeat_sequence
        == 8
    )


def test_monotonic_clock_cannot_move_before_start():
    result = evaluate(
        started=100.0,
        now=99.0,
    )

    assert not result.valid
    assert not result.healthy
    assert result.hard_block

    assert result.reason == (
        "INVALID_RUNTIME_HEARTBEAT_INPUT"
    )


def test_last_heartbeat_cannot_be_in_future():
    result = evaluate(
        started=100.0,
        now=110.0,
        last=111.0,
        sequence=1,
    )

    assert not result.valid
    assert result.hard_block


def test_last_heartbeat_cannot_predate_session_start():
    result = evaluate(
        started=100.0,
        now=110.0,
        last=99.0,
        sequence=1,
    )

    assert not result.valid
    assert result.hard_block


def test_nonzero_sequence_requires_existing_heartbeat():
    result = evaluate(
        last=None,
        sequence=1,
    )

    assert not result.valid
    assert result.hard_block


def test_existing_heartbeat_requires_positive_sequence():
    result = evaluate(
        now=101.0,
        last=100.0,
        sequence=0,
    )

    assert not result.valid
    assert result.hard_block


def test_invalid_gap_limit_is_fail_safe():
    for max_gap in (
        0.0,
        -1.0,
        math.nan,
        math.inf,
    ):
        result = evaluate(
            max_gap=max_gap,
        )

        assert not result.valid
        assert result.hard_block


def test_nonfinite_monotonic_values_are_fail_safe():
    for value in (
        math.nan,
        math.inf,
        -math.inf,
    ):
        result = evaluate(
            now=value,
        )

        assert not result.valid
        assert result.hard_block


def test_boolean_sequence_is_rejected():
    result = evaluate(
        sequence=False,
    )

    assert not result.valid
    assert result.hard_block


def test_heartbeat_contract_has_no_wall_clock_dependency():
    import inspect
    import mss.analysis.shadow_live_runtime_heartbeat as module

    source = inspect.getsource(
        module
    )

    assert "time.time(" not in source
    assert "datetime" not in source
    assert "timezone" not in source
    assert "MT5" not in source
