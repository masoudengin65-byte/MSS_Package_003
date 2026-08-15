import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "integration_tests"),
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
    manual=False,
    mt5_connected=True,
    terminal=True,
    account=True,
    portfolio_recovery=None,
    risk_snapshot=None,
):
    if portfolio_recovery is None:
        portfolio_recovery = recovery()

    if risk_snapshot is None:
        risk_snapshot = snapshot()

    return runner.evaluate_session_runtime_health(
        manual_kill_switch_active=manual,
        mt5_connected=mt5_connected,
        terminal_available=terminal,
        account_available=account,
        runtime_portfolio_risk_recovery=(
            portfolio_recovery
        ),
        current_risk_snapshot=(
            risk_snapshot
        ),
    )


def test_healthy_runtime_has_no_kill_conditions():
    result = evaluate()

    assert result == ()


def test_manual_kill_blocks_runtime_entry_discovery():
    result = evaluate(
        manual=True,
    )

    assert result[0] == (
        "MANUAL_KILL_SWITCH_ACTIVE"
    )


def test_mt5_disconnect_blocks_runtime_entry_discovery():
    result = evaluate(
        mt5_connected=False,
    )

    assert (
        "MT5_NOT_CONNECTED"
        in result
    )


def test_terminal_loss_blocks_runtime_entry_discovery():
    result = evaluate(
        terminal=False,
    )

    assert (
        "MT5_TERMINAL_UNAVAILABLE"
        in result
    )


def test_account_loss_blocks_runtime_entry_discovery():
    result = evaluate(
        account=False,
    )

    assert (
        "MT5_ACCOUNT_UNAVAILABLE"
        in result
    )


def test_invalid_portfolio_recovery_blocks_runtime():
    result = evaluate(
        portfolio_recovery=recovery(
            valid=False,
        ),
    )

    assert (
        "PORTFOLIO_RECOVERY_INVALID"
        in result
    )

    assert (
        "PORTFOLIO_LIMITS_INVALID"
        in result
    )


def test_missing_portfolio_snapshot_blocks_runtime():
    result = runner.evaluate_session_runtime_health(
        manual_kill_switch_active=False,
        mt5_connected=True,
        terminal_available=True,
        account_available=True,
        runtime_portfolio_risk_recovery=(
            recovery()
        ),
        current_risk_snapshot=None,
    )

    assert (
        "PORTFOLIO_SNAPSHOT_MISSING"
        in result
    )

    assert (
        "PORTFOLIO_LIMITS_INVALID"
        in result
    )


def test_position_count_above_runner_limit_blocks():
    result = evaluate(
        portfolio_recovery=recovery(
            open_position_count=(
                runner.MAX_OPEN_SHADOW_POSITIONS
                + 1
            ),
        ),
    )

    assert (
        "PORTFOLIO_LIMITS_INVALID"
        in result
    )


def test_total_risk_above_governor_limit_blocks():
    result = evaluate(
        risk_snapshot=snapshot(
            total_risk_percent=(
                runner.PortfolioRiskGovernor
                .MAX_TOTAL_OPEN_RISK_PERCENT
                + 0.01
            ),
        ),
    )

    assert (
        "PORTFOLIO_LIMITS_INVALID"
        in result
    )


def test_nan_risk_is_fail_safe_blocked():
    result = evaluate(
        risk_snapshot=snapshot(
            total_risk_percent=float("nan"),
        ),
    )

    assert (
        "PORTFOLIO_LIMITS_INVALID"
        in result
    )


def test_multiple_failures_are_reported_deterministically():
    result = evaluate(
        manual=True,
        mt5_connected=False,
        terminal=False,
        account=False,
        portfolio_recovery=recovery(
            valid=False,
        ),
    )

    assert result == (
        "MANUAL_KILL_SWITCH_ACTIVE",
        "MT5_NOT_CONNECTED",
        "MT5_TERMINAL_UNAVAILABLE",
        "MT5_ACCOUNT_UNAVAILABLE",
        "PORTFOLIO_RECOVERY_INVALID",
        "PORTFOLIO_LIMITS_INVALID",
    )
