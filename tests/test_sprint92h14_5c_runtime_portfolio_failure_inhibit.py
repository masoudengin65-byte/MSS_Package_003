import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(
    0,
    str(ROOT / "integration_tests"),
)

import run_sprint92h14_5c_shadow_live_safety_governor_session as runner


def test_runtime_portfolio_safety_error_preserves_reason_and_detail():
    exc = runner.RuntimePortfolioSafetyError(
        "MEMORY_STATE_INCONSISTENT",
        "TEST_DETAIL",
    )

    assert exc.reason == (
        "MEMORY_STATE_INCONSISTENT"
    )

    assert exc.detail == (
        "TEST_DETAIL"
    )

    assert str(exc) == (
        "MEMORY_STATE_INCONSISTENT:"
        "TEST_DETAIL"
    )


def test_memory_pair_mismatch_raises_typed_safety_error():
    fake_position = SimpleNamespace(
        position_id="TEST-POSITION",
    )

    with pytest.raises(
        runner.RuntimePortfolioSafetyError
    ) as captured:

        runner.refresh_runtime_portfolio_state(
            symbols=(),
            states={},
            position=fake_position,
            position_symbol=None,
        )

    assert captured.value.reason == (
        "MEMORY_STATE_INCONSISTENT"
    )

    assert (
        "RUNTIME_POSITION_MEMORY_STATE_INVALID"
        in captured.value.detail
    )


def test_typed_error_is_runtime_error_compatible():
    exc = runner.RuntimePortfolioSafetyError(
        "PORTFOLIO_RECOVERY_INVALID",
        "TEST_RECOVERY_FAILURE",
    )

    assert isinstance(
        exc,
        RuntimeError,
    )


def test_runner_contains_failsafe_refresh_catch_before_phase1():
    path = (
        ROOT
        / "integration_tests"
        / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
    )

    text = path.read_text(
        encoding="utf-8",
    )

    catch_index = text.index(
        "except RuntimePortfolioSafetyError as exc:"
    )

    inhibit_index = text.index(
        "GLOBAL_SESSION_ENTRY_INHIBIT",
        catch_index,
    )

    phase1_index = text.index(
        "# PHASE 1:",
        catch_index,
    )

    open_trade_index = text.index(
        ".open_trade("
    )

    assert (
        catch_index
        <
        inhibit_index
        <
        phase1_index
        <
        open_trade_index
    )


def test_refresh_failure_catch_continues_before_candidate_discovery():
    path = (
        ROOT
        / "integration_tests"
        / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
    )

    text = path.read_text(
        encoding="utf-8",
    )

    catch_index = text.index(
        "except RuntimePortfolioSafetyError as exc:"
    )

    phase1_index = text.index(
        "# PHASE 1:",
        catch_index,
    )

    segment = text[
        catch_index:phase1_index
    ]

    assert (
        "GLOBAL_SESSION_ENTRY_INHIBIT"
        in segment
    )

    assert (
        "GLOBAL_SESSION_SAFETY_DETAIL"
        in segment
    )

    assert (
        "continue"
        in segment
    )

    assert (
        ".open_trade("
        not in segment
    )


def test_report_contains_runtime_safety_reason_and_detail():
    path = (
        ROOT
        / "integration_tests"
        / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
    )

    text = path.read_text(
        encoding="utf-8",
    )

    assert (
        '"last_global_safety_reason"'
        in text
    )

    assert (
        '"last_global_safety_detail"'
        in text
    )
