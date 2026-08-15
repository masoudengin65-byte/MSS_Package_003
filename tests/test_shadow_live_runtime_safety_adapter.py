from dataclasses import replace

from mss.analysis.shadow_live_runtime_safety_adapter import (
    ShadowLiveRuntimeSafetyAdapter,
    ShadowLiveRuntimeSafetyFacts,
)
from mss.analysis.shadow_live_safety_governor import (
    ShadowLiveSafetyGovernor,
)


def healthy_facts():
    return ShadowLiveRuntimeSafetyFacts(
        manual_kill_switch_active=False,
        mt5_initialized=True,
        terminal_available=True,
        account_available=True,
        time_authority_confirmed=True,
        portfolio_recovery_valid=True,
        portfolio_snapshot_present=True,
        lifecycle_state_valid=True,
        memory_state_consistent=True,
        governor_state_consistent=True,
        open_position_count=1,
        total_open_risk_percent=1.0,
        max_open_positions=1,
        max_total_open_risk_percent=2.0,
    )


def test_healthy_runtime_facts_build_healthy_state():
    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            healthy_facts()
        )
    )

    assert state.manual_kill_switch_active is False
    assert state.mt5_connected is True
    assert state.terminal_available is True
    assert state.account_available is True
    assert state.time_authority_confirmed is True
    assert state.portfolio_recovery_valid is True
    assert state.portfolio_snapshot_present is True
    assert state.lifecycle_state_valid is True
    assert state.memory_state_consistent is True
    assert state.governor_state_consistent is True
    assert state.portfolio_limits_valid is True


def test_healthy_adapter_state_allows_global_safety():
    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            healthy_facts()
        )
    )

    decision = (
        ShadowLiveSafetyGovernor.evaluate(
            state
        )
    )

    assert decision.trading_allowed is True
    assert decision.hard_block is False
    assert decision.reason == (
        "GLOBAL_SAFETY_CONFIRMED"
    )


def test_manual_kill_switch_is_preserved():
    facts = replace(
        healthy_facts(),
        manual_kill_switch_active=True,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.manual_kill_switch_active is True

    decision = (
        ShadowLiveSafetyGovernor.evaluate(
            state
        )
    )

    assert decision.trading_allowed is False
    assert decision.reason == (
        "MANUAL_KILL_SWITCH_ACTIVE"
    )


def test_mt5_initialization_state_is_preserved():
    facts = replace(
        healthy_facts(),
        mt5_initialized=False,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.mt5_connected is False


def test_time_authority_state_is_preserved():
    facts = replace(
        healthy_facts(),
        time_authority_confirmed=False,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.time_authority_confirmed is False


def test_portfolio_validation_states_are_preserved():
    facts = replace(
        healthy_facts(),
        portfolio_recovery_valid=False,
        portfolio_snapshot_present=False,
        lifecycle_state_valid=False,
        memory_state_consistent=False,
        governor_state_consistent=False,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_recovery_valid is False
    assert state.portfolio_snapshot_present is False
    assert state.lifecycle_state_valid is False
    assert state.memory_state_consistent is False
    assert state.governor_state_consistent is False


def test_position_count_at_limit_is_valid():
    facts = replace(
        healthy_facts(),
        open_position_count=1,
        max_open_positions=1,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is True


def test_position_count_above_limit_is_invalid():
    facts = replace(
        healthy_facts(),
        open_position_count=2,
        max_open_positions=1,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_risk_at_limit_is_valid():
    facts = replace(
        healthy_facts(),
        total_open_risk_percent=2.0,
        max_total_open_risk_percent=2.0,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is True


def test_risk_above_limit_is_invalid():
    facts = replace(
        healthy_facts(),
        total_open_risk_percent=2.01,
        max_total_open_risk_percent=2.0,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_negative_position_count_fails_safe():
    facts = replace(
        healthy_facts(),
        open_position_count=-1,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_negative_risk_fails_safe():
    facts = replace(
        healthy_facts(),
        total_open_risk_percent=-0.01,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_non_finite_risk_fails_safe():
    facts = replace(
        healthy_facts(),
        total_open_risk_percent=float("nan"),
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_non_finite_max_risk_fails_safe():
    facts = replace(
        healthy_facts(),
        max_total_open_risk_percent=float(
            "inf"
        ),
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    assert state.portfolio_limits_valid is False


def test_invalid_adapter_input_builds_killed_state():
    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            None
        )
    )

    decision = (
        ShadowLiveSafetyGovernor.evaluate(
            state
        )
    )

    assert decision.trading_allowed is False
    assert decision.hard_block is True
    assert (
        state.manual_kill_switch_active
        is True
    )
    assert (
        state.portfolio_limits_valid
        is False
    )


def test_limit_violation_reaches_global_governor():
    facts = replace(
        healthy_facts(),
        open_position_count=2,
        max_open_positions=1,
    )

    state = (
        ShadowLiveRuntimeSafetyAdapter.build(
            facts
        )
    )

    decision = (
        ShadowLiveSafetyGovernor.evaluate(
            state
        )
    )

    assert decision.trading_allowed is False
    assert decision.hard_block is True
    assert decision.reason == (
        "PORTFOLIO_LIMITS_INVALID"
    )
