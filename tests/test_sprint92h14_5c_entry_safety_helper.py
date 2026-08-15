import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
INTEGRATION_TESTS = ROOT / "integration_tests"

if str(INTEGRATION_TESTS) not in sys.path:
    sys.path.insert(
        0,
        str(INTEGRATION_TESTS),
    )


import run_sprint92h14_5c_shadow_live_safety_governor_session as runner


def recovery(
    *,
    valid=True,
    open_position_count=0,
):
    return SimpleNamespace(
        valid=valid,
        open_position_count=open_position_count,
    )


def snapshot(
    *,
    total_risk_percent=0.0,
):
    return SimpleNamespace(
        total_risk_percent=total_risk_percent,
    )


def evaluate(
    *,
    manual_kill_switch_active=False,
    mt5_initialized=True,
    terminal_available=True,
    account_available=True,
    time_authority_confirmed=True,
    portfolio_recovery=None,
    risk_snapshot=None,
):
    if portfolio_recovery is None:
        portfolio_recovery = recovery()

    if risk_snapshot is None:
        risk_snapshot = snapshot()

    return runner.evaluate_entry_safety(
        manual_kill_switch_active=(
            manual_kill_switch_active
        ),
        mt5_initialized=mt5_initialized,
        terminal_available=terminal_available,
        account_available=account_available,
        time_authority_confirmed=(
            time_authority_confirmed
        ),
        runtime_portfolio_risk_recovery=(
            portfolio_recovery
        ),
        current_risk_snapshot=(
            risk_snapshot
        ),
    )


def test_healthy_entry_safety_allows():
    result = evaluate()

    assert result.trading_allowed is True
    assert result.hard_block is False
    assert result.reason == (
        "GLOBAL_SAFETY_CONFIRMED"
    )
    assert result.kill_conditions == ()


def test_manual_kill_switch_blocks_entry():
    result = evaluate(
        manual_kill_switch_active=True,
    )

    assert result.trading_allowed is False
    assert result.hard_block is True
    assert result.reason == (
        "MANUAL_KILL_SWITCH_ACTIVE"
    )


def test_mt5_not_initialized_blocks_entry():
    result = evaluate(
        mt5_initialized=False,
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_NOT_CONNECTED"
    )


def test_terminal_unavailable_blocks_entry():
    result = evaluate(
        terminal_available=False,
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_TERMINAL_UNAVAILABLE"
    )


def test_account_unavailable_blocks_entry():
    result = evaluate(
        account_available=False,
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "MT5_ACCOUNT_UNAVAILABLE"
    )


def test_time_authority_failure_blocks_entry():
    result = evaluate(
        time_authority_confirmed=False,
    )

    assert result.trading_allowed is False
    assert result.reason == (
        "TIME_AUTHORITY_NOT_CONFIRMED"
    )


def test_invalid_portfolio_recovery_blocks_entry():
    result = evaluate(
        portfolio_recovery=recovery(
            valid=False,
        ),
    )

    assert result.trading_allowed is False
    assert result.hard_block is True

    assert (
        "PORTFOLIO_RECOVERY_INVALID"
        in result.kill_conditions
    )

    assert (
        "LIFECYCLE_STATE_INVALID"
        in result.kill_conditions
    )

    assert (
        "MEMORY_STATE_INCONSISTENT"
        in result.kill_conditions
    )

    assert (
        "GOVERNOR_STATE_INCONSISTENT"
        in result.kill_conditions
    )


def test_runtime_risk_above_hard_limit_blocks_entry():
    result = evaluate(
        portfolio_recovery=recovery(
            valid=True,
            open_position_count=1,
        ),
        risk_snapshot=snapshot(
            total_risk_percent=2.01,
        ),
    )

    assert result.trading_allowed is False
    assert result.hard_block is True
    assert result.reason == (
        "PORTFOLIO_LIMITS_INVALID"
    )
