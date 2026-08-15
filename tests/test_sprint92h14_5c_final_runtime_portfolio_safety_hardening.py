import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]

RUNNER_PATH = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
)

sys.path.insert(
    0,
    str(ROOT / "integration_tests"),
)

import run_sprint92h14_5c_shadow_live_safety_governor_session as runner


def source_text():
    return RUNNER_PATH.read_text(
        encoding="utf-8"
    )


def test_post_open_portfolio_safety_stop_preserves_reason_and_detail():
    exc = runner.PostOpenPortfolioSafetyStop(
        "MEMORY_STATE_INCONSISTENT",
        "POST_OPEN_TEST_DETAIL",
    )

    assert exc.reason == (
        "MEMORY_STATE_INCONSISTENT"
    )

    assert exc.detail == (
        "POST_OPEN_TEST_DETAIL"
    )

    assert str(exc) == (
        "MEMORY_STATE_INCONSISTENT:"
        "POST_OPEN_TEST_DETAIL"
    )


def test_post_open_portfolio_safety_stop_is_runtime_error_compatible():
    exc = runner.PostOpenPortfolioSafetyStop(
        "PORTFOLIO_RECOVERY_INVALID",
        "TEST_DETAIL",
    )

    assert isinstance(
        exc,
        RuntimeError,
    )


def test_final_pre_open_refresh_failure_hard_blocks_before_open_trade():
    text = source_text()

    final_quote_index = text.index(
        "final_quote_fresh = bool("
    )

    open_index = text.index(
        ".open_trade(",
        final_quote_index,
    )

    segment = text[
        final_quote_index:open_index
    ]

    refresh_index = segment.index(
        "refresh_runtime_portfolio_state("
    )

    catch_index = segment.index(
        "except RuntimePortfolioSafetyError as exc:",
        refresh_index,
    )

    block_index = segment.index(
        "GLOBAL_ENTRY_SAFETY_HARD_BLOCK",
        catch_index,
    )

    detail_index = segment.index(
        "GLOBAL_ENTRY_SAFETY_DETAIL",
        catch_index,
    )

    continue_index = segment.index(
        "continue",
        catch_index,
    )

    assert (
        refresh_index
        <
        catch_index
        <
        block_index
        <
        continue_index
    )

    assert (
        catch_index
        <
        detail_index
        <
        continue_index
    )


def test_final_pre_open_refresh_failure_updates_global_safety_state():
    text = source_text()

    start = text.index(
        "final_quote_fresh = bool("
    )

    end = text.index(
        "final_policy = (",
        start,
    )

    segment = text[
        start:end
    ]

    catch_index = segment.index(
        "except RuntimePortfolioSafetyError as exc:"
    )

    catch_segment = segment[
        catch_index:
    ]

    assert (
        '"last_global_safety_reason"'
        in catch_segment
    )

    assert (
        '"last_global_safety_detail"'
        in catch_segment
    )

    assert (
        '"global_safety_blocks"'
        in catch_segment
    )

    assert (
        '"policy_blocks"'
        in catch_segment
    )

    assert (
        ".open_trade("
        not in catch_segment
    )


def test_post_open_refresh_failure_raises_dedicated_controlled_stop():
    text = source_text()

    opened_index = text.index(
        '"SHADOW_POSITION_OPENED"'
    )

    success_refresh_index = text.index(
        '"RUNTIME_PORTFOLIO_REFRESH_AFTER_OPEN"',
        opened_index,
    )

    segment = text[
        opened_index:
        success_refresh_index
    ]

    refresh_index = segment.index(
        "refresh_runtime_portfolio_state("
    )

    catch_index = segment.index(
        "except RuntimePortfolioSafetyError as exc:",
        refresh_index,
    )

    failure_index = segment.index(
        "POST_OPEN_PORTFOLIO_SAFETY_FAILURE",
        catch_index,
    )

    raise_index = segment.index(
        "raise PostOpenPortfolioSafetyStop(",
        catch_index,
    )

    assert (
        refresh_index
        <
        catch_index
        <
        failure_index
        <
        raise_index
    )

    assert (
        '"last_global_safety_reason"'
        in segment[
            catch_index:raise_index
        ]
    )

    assert (
        '"last_global_safety_detail"'
        in segment[
            catch_index:raise_index
        ]
    )

    assert (
        '"global_safety_blocks"'
        in segment[
            catch_index:raise_index
        ]
    )


def test_post_open_safety_stop_has_dedicated_outer_session_handler():
    text = source_text()

    handler_index = text.index(
        "except PostOpenPortfolioSafetyStop as exc:"
    )

    keyboard_index = text.index(
        "except KeyboardInterrupt:",
        handler_index,
    )

    segment = text[
        handler_index:
        keyboard_index
    ]

    assert (
        "SESSION_STOPPED_POST_OPEN_"
        in segment
    )

    assert (
        "PORTFOLIO_SAFETY_FAILURE"
        in segment
    )

    assert (
        "POST_OPEN_PORTFOLIO_SAFETY_REASON"
        in segment
    )

    assert (
        "POST_OPEN_PORTFOLIO_SAFETY_DETAIL"
        in segment
    )

    assert (
        "final_status"
        in segment
    )
