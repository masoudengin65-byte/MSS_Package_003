from dataclasses import replace

from mss.analysis.shadow_live_safety_governor import (
    ShadowLiveSafetyDecision,
    ShadowLiveSafetyGovernor,
    ShadowLiveSafetyState,
)


def healthy_state():
    return ShadowLiveSafetyState(
        manual_kill_switch_active=False,
        mt5_connected=True,
        terminal_available=True,
        account_available=True,
        time_authority_confirmed=True,
        portfolio_recovery_valid=True,
        portfolio_snapshot_present=True,
        lifecycle_state_valid=True,
        memory_state_consistent=True,
        governor_state_consistent=True,
        portfolio_limits_valid=True,
    )


def test_healthy_state_allows_trading():
    result = ShadowLiveSafetyGovernor.evaluate(
        healthy_state()
    )

    assert isinstance(
        result,
        ShadowLiveSafetyDecision,
    )
    assert result.trading_allowed is True
    assert result.hard_block is False
    assert result.reason == (
        "GLOBAL_SAFETY_CONFIRMED"
    )
    assert result.kill_conditions == ()


def test_manual_kill_switch_hard_blocks():
    state = replace(
        healthy_state(),
        manual_kill_switch_active=True,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.hard_block is True
    assert result.reason == (
        "MANUAL_KILL_SWITCH_ACTIVE"
    )
    assert result.kill_conditions == (
        "MANUAL_KILL_SWITCH_ACTIVE",
    )


def test_mt5_disconnect_hard_blocks():
    state = replace(
        healthy_state(),
        mt5_connected=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_NOT_CONNECTED"
    )


def test_terminal_unavailable_hard_blocks():
    state = replace(
        healthy_state(),
        terminal_available=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_TERMINAL_UNAVAILABLE"
    )


def test_account_unavailable_hard_blocks():
    state = replace(
        healthy_state(),
        account_available=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_ACCOUNT_UNAVAILABLE"
    )


def test_unconfirmed_time_authority_hard_blocks():
    state = replace(
        healthy_state(),
        time_authority_confirmed=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "TIME_AUTHORITY_NOT_CONFIRMED"
    )


def test_invalid_portfolio_recovery_hard_blocks():
    state = replace(
        healthy_state(),
        portfolio_recovery_valid=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "PORTFOLIO_RECOVERY_INVALID"
    )


def test_missing_portfolio_snapshot_hard_blocks():
    state = replace(
        healthy_state(),
        portfolio_snapshot_present=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "PORTFOLIO_SNAPSHOT_MISSING"
    )


def test_invalid_lifecycle_state_hard_blocks():
    state = replace(
        healthy_state(),
        lifecycle_state_valid=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "LIFECYCLE_STATE_INVALID"
    )


def test_memory_inconsistency_hard_blocks():
    state = replace(
        healthy_state(),
        memory_state_consistent=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MEMORY_STATE_INCONSISTENT"
    )


def test_governor_state_inconsistency_hard_blocks():
    state = replace(
        healthy_state(),
        governor_state_consistent=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "GOVERNOR_STATE_INCONSISTENT"
    )


def test_portfolio_limit_failure_hard_blocks():
    state = replace(
        healthy_state(),
        portfolio_limits_valid=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "PORTFOLIO_LIMITS_INVALID"
    )


def test_multiple_failures_are_all_preserved():
    state = replace(
        healthy_state(),
        mt5_connected=False,
        time_authority_confirmed=False,
        portfolio_recovery_valid=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.trading_allowed is False
    assert result.hard_block is True

    assert result.reason == (
        "MT5_NOT_CONNECTED"
    )

    assert result.kill_conditions == (
        "MT5_NOT_CONNECTED",
        "TIME_AUTHORITY_NOT_CONFIRMED",
        "PORTFOLIO_RECOVERY_INVALID",
    )


def test_failure_priority_is_deterministic():
    state = replace(
        healthy_state(),
        manual_kill_switch_active=True,
        mt5_connected=False,
        terminal_available=False,
    )

    result = ShadowLiveSafetyGovernor.evaluate(
        state
    )

    assert result.reason == (
        "MANUAL_KILL_SWITCH_ACTIVE"
    )

    assert result.kill_conditions == (
        "MANUAL_KILL_SWITCH_ACTIVE",
        "MT5_NOT_CONNECTED",
        "MT5_TERMINAL_UNAVAILABLE",
    )


def test_invalid_input_fails_safe():
    result = ShadowLiveSafetyGovernor.evaluate(
        None
    )

    assert result.trading_allowed is False
    assert result.hard_block is True
    assert result.reason == (
        "INVALID_SAFETY_STATE_INPUT"
    )
    assert result.kill_conditions == (
        "INVALID_SAFETY_STATE_INPUT",
    )
