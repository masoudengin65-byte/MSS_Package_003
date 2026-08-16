from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_6_long_running_shadow_live_session.py"
)


def source():
    return RUNNER.read_text(
        encoding="utf-8"
    )


def test_crash_hook_is_explicitly_environment_gated():
    text = source()

    assert (
        "MSS_H14_6_TEST_CRASH_AFTER_HEARTBEAT"
        in text
    )

    assert (
        '"0"'
        in text
    )


def test_crash_hook_rejects_negative_threshold():
    text = source()

    assert (
        "runtime_test_crash_after_heartbeat < 0"
        in text
    )

    assert (
        "INVALID_H14_6_TEST_CRASH_AFTER_HEARTBEAT"
        in text
    )


def test_crash_hook_requires_healthy_supervisor_state():
    text = source()

    assert (
        "runtime_supervisor_decision.valid"
        in text
    )

    assert (
        "not runtime_supervisor_decision.hard_block"
        in text
    )


def test_crash_hook_waits_for_requested_heartbeat_sequence():
    text = source()

    assert (
        "runtime_heartbeat_sequence"
        in text
    )

    assert (
        "runtime_test_crash_after_heartbeat"
        in text
    )


def test_crash_hook_uses_explicit_process_exit_code():
    text = source()

    assert (
        "os._exit(86)"
        in text
    )


def test_crash_marker_is_flushed_before_process_exit():
    text = source()

    assert (
        "H14_6_TEST_PROCESS_CRASH_TRIGGER"
        in text
    )

    assert (
        "flush=True"
        in text
    )


def test_crash_hook_does_not_add_execution_paths():
    text = source()

    assert (
        text.count(
            ".open_trade("
        )
        == 1
    )

    assert (
        "mt5.order_send("
        not in text
    )

    assert (
        "mt5.order_check("
        not in text
    )


def test_crash_hook_does_not_mutate_journal_directly():
    text = source()

    marker_index = text.index(
        "H14_6_TEST_PROCESS_CRASH_TRIGGER"
    )

    nearby = text[
        max(0, marker_index - 1200):
        marker_index + 1200
    ]

    assert (
        "open_trade("
        not in nearby
    )

    assert (
        "close_trade("
        not in nearby
    )

    assert (
        "write_text("
        not in nearby
    )

    assert (
        "write_bytes("
        not in nearby
    )
