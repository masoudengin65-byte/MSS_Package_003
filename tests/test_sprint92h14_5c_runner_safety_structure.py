from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_5c_shadow_live_safety_governor_session.py"
)


def source_text():
    return RUNNER.read_text(
        encoding="utf-8"
    )


def test_h14_5c_runner_exists():
    assert RUNNER.is_file()


def test_h14_5c_identity_and_namespaces_are_isolated():
    text = source_text()

    assert "Sprint 92H.14.5c" in text

    assert (
        '/ "sprint92h14_5c"'
        in text
    )

    assert (
        '/ "sprint92h14_5b_1"'
        in text
    )

    assert (
        '/ "sprint92h14_5a"'
        not in text
    )


def test_exactly_one_shadow_open_trade_path_exists():
    text = source_text()

    assert text.count(
        ".open_trade("
    ) == 1


def test_no_direct_mt5_order_send_or_order_check():
    text = source_text()

    assert (
        "mt5.order_send("
        not in text
    )

    assert (
        "mt5.order_check("
        not in text
    )


def test_manual_kill_switch_uses_external_operator_control():
    text = source_text()

    assert (
        "MANUAL_KILL_SWITCH_PATH"
        in text
    )

    assert (
        "MSS_MANUAL_KILL_SWITCH"
        in text
    )

    assert (
        "def manual_kill_switch_requested()"
        in text
    )

    assert (
        "MANUAL_KILL_SWITCH_ACTIVE = False"
        not in text
    )


def test_entry_safety_helper_is_present():
    text = source_text()

    assert (
        "def evaluate_entry_safety("
        in text
    )

    assert (
        "ShadowLiveRuntimeSafetyAdapter"
        in text
    )

    assert (
        "ShadowLiveSafetyGovernor"
        in text
    )


def test_final_entry_safety_evaluation_precedes_open_trade():
    text = source_text()

    call_index = text.rfind(
        "evaluate_entry_safety("
    )

    open_index = text.index(
        ".open_trade("
    )

    assert call_index >= 0
    assert open_index >= 0
    assert call_index < open_index


def test_fresh_time_authority_is_consumed_by_final_safety_gate():
    text = source_text()

    call_index = text.rfind(
        "evaluate_entry_safety("
    )

    open_index = text.index(
        ".open_trade("
    )

    segment = text[
        call_index:open_index
    ]

    assert (
        "fresh_authority"
        in segment
    )

    assert (
        '"confirmed"'
        in segment
    )


def test_hard_block_occurs_before_open_trade_and_exits_path():
    text = source_text()

    hard_block_index = text.index(
        "GLOBAL_ENTRY_SAFETY_HARD_BLOCK"
    )

    open_index = text.index(
        ".open_trade("
    )

    assert (
        hard_block_index
        <
        open_index
    )

    segment = text[
        hard_block_index:open_index
    ]

    assert "continue" in segment


def test_safety_confirmation_occurs_before_open_trade():
    text = source_text()

    confirmed_index = text.index(
        "GLOBAL_ENTRY_SAFETY_CONFIRMED"
    )

    open_index = text.index(
        ".open_trade("
    )

    assert (
        confirmed_index
        <
        open_index
    )
