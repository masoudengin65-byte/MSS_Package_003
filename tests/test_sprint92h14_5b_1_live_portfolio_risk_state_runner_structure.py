from pathlib import Path


RUNNER = Path(
    r"integration_tests/"
    r"run_sprint92h14_5b_1_live_portfolio_risk_state_session.py"
)


def source():
    return RUNNER.read_text(
        encoding="utf-8-sig"
    )


def test_identity_and_namespace_are_h14_5b_1():
    text = source()

    assert "Sprint 92H.14.5b.1" in text
    assert '"sprint": "92H.14.5b.1"' in text
    assert '"sprint92h14_5b_1"' in text
    assert '"MSS_Sprint92H14_5b_1_"' in text


def test_predecessor_namespace_is_explicit_and_separate():
    text = source()

    assert '"sprint92h14_5a"' in text

    assert (
        text.count(
            '"sprint92h14_5a"'
        )
        == 1
    )

    assert (
        "def predecessor_journal_path_for("
        in text
    )


def test_single_position_limit_remains_frozen():
    text = source()

    assert (
        "MAX_OPEN_SHADOW_POSITIONS = 1"
        in text
    )


def test_no_direct_real_execution_calls():
    text = source()

    assert "mt5.order_send(" not in text
    assert "mt5.order_check(" not in text

    assert (
        text.count(
            ".open_trade("
        )
        == 1
    )


def test_portfolio_recovery_continuity_and_live_loop_order():
    text = source()

    current_recovery_index = text.index(
        "current_portfolio_sources ="
    )

    lifecycle_crosscheck_index = text.index(
        "PORTFOLIO_LIFECYCLE_CROSSCHECK_OK"
    )

    predecessor_recovery_index = text.index(
        "predecessor_sources ="
    )

    continuity_index = text.index(
        "ShadowPortfolioContinuityPolicy"
        "\n            .evaluate("
    )

    continuity_gate_index = text.index(
        "PORTFOLIO_CONTINUITY_GATE_OK"
    )

    start_index = text.index(
        "start_monotonic ="
    )

    live_loop_index = text.index(
        "with ThreadPoolExecutor("
    )

    assert (
        current_recovery_index
        < lifecycle_crosscheck_index
        < predecessor_recovery_index
        < continuity_index
        < continuity_gate_index
        < start_index
        < live_loop_index
    )


def test_predecessor_only_state_requires_import_and_blocks():
    text = source()

    assert (
        '== "IMPORT_REQUIRED"'
        in text
    )

    assert (
        "PREDECESSOR_H14_5A_"
        '"\n                "POSITION_IMPORT_REQUIRED:'
        in text
    )

    assert (
        "CURRENT_SUPERSEDES_PREDECESSOR"
        in text
    )


def test_continuity_gate_is_strict_allowlist():
    text = source()

    assert (
        '"CONTINUITY_CLEAR"'
        in text
    )

    assert (
        '"CURRENT_POSITION_ACTIVE"'
        in text
    )

    assert (
        '"CURRENT_SUPERSEDES_PREDECESSOR"'
        in text
    )

    assert (
        "UNEXPECTED_SHADOW_PORTFOLIO_"
        in text
    )

    assert (
        "SHADOW_PORTFOLIO_CONTINUITY_BLOCK:"
        in text
    )


def test_current_portfolio_is_converted_for_governor():
    text = source()

    recovery_index = text.index(
        "portfolio_risk_recovery = ("
    )

    conversion_index = text.index(
        "portfolio_governor_positions = (",
        recovery_index,
    )

    crosscheck_index = text.index(
        "PORTFOLIO_LIFECYCLE_CROSSCHECK_OK"
    )

    assert (
        recovery_index
        < conversion_index
        < crosscheck_index
    )


def test_consumption_inspector_runs_before_continuity_policy():
    text = source()

    inspector_index = text.index(
        ".inspect_consumption("
    )

    continuity_index = text.index(
        "ShadowPortfolioContinuityPolicy"
        "\n            .evaluate("
    )

    assert inspector_index < continuity_index

    assert (
        "PREDECESSOR_CONSUMPTION_VALID"
        in text
    )

    assert (
        "PREDECESSOR_CONSUMPTION_"
        '"\n                    "INSPECTION_FAILED:'
        in text
    )

    assert (
        "PREDECESSOR_CONSUMPTION_"
        '"\n                    "IDENTITY_MISMATCH'
        in text
    )


def test_consumption_evidence_is_passed_to_continuity():
    text = source()

    assert (
        "predecessor_consumed=("
        in text
    )

    assert (
        "predecessor_consumption_result"
        in text
    )

    assert (
        '"PREDECESSOR_POSITION_ALREADY_CONSUMED"'
        in text
    )

    assert (
        "expected_position_id=("
        in text
    )

    assert (
        "expected_symbol=("
        in text
    )


def test_runtime_portfolio_refresh_is_authoritative_and_crosschecked():
    text = source()

    assert (
        "def refresh_runtime_portfolio_state("
        in text
    )

    helper_start = text.index(
        "def refresh_runtime_portfolio_state("
    )

    helper_end = text.index(
        "\ndef new_stats():",
        helper_start,
    )

    helper = text[
        helper_start:helper_end
    ]

    assert (
        "ShadowPortfolioRiskAggregator"
        in helper
    )

    assert (
        "ShadowPositionRecovery"
        in helper
    )

    assert (
        "ShadowPortfolioRiskState"
        in helper
    )

    assert (
        "RUNTIME_PORTFOLIO_LIFECYCLE_"
        in helper
    )

    assert (
        "RUNTIME_PORTFOLIO_MEMORY_"
        in helper
    )

    assert (
        "MAX_OPEN_SHADOW_POSITIONS"
        in helper
    )


def test_both_policy_calls_receive_real_governor_positions():
    text = source()

    assert (
        "open_positions=(),"
        not in text
    )

    assert (
        text.count(
            "open_positions="
            "portfolio_governor_positions,"
        )
        == 2
    )


def test_runtime_refresh_occurs_after_close_before_policy_and_after_open():
    text = source()

    close_index = text.index(
        '"POSITION_CLOSED"'
    )

    phase_one_index = text.index(
        "# PHASE 1:",
        close_index,
    )

    refresh_after_lifecycle = (
        text.rfind(
            "refresh_runtime_portfolio_state(",
            close_index,
            phase_one_index,
        )
    )

    assert (
        refresh_after_lifecycle
        != -1
    )

    final_policy_index = text.index(
        "final_policy = ("
    )

    final_refresh_index = text.rfind(
        "refresh_runtime_portfolio_state(",
        phase_one_index,
        final_policy_index,
    )

    assert (
        final_refresh_index
        != -1
    )

    open_index = text.index(
        ".open_trade("
    )

    post_open_marker = text.index(
        "RUNTIME_PORTFOLIO_REFRESH_AFTER_OPEN",
        open_index,
    )

    post_open_refresh = text.rfind(
        "refresh_runtime_portfolio_state(",
        open_index,
        post_open_marker,
    )

    assert (
        post_open_refresh
        != -1
    )
