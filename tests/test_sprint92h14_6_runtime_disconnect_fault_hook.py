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


def test_disconnect_hook_is_explicitly_environment_gated():
    text = source()

    assert (
        "MSS_H14_6_TEST_MT5_DISCONNECT_CYCLES"
        in text
    )

    assert (
        '"0"'
        in text
    )


def test_disconnect_hook_defaults_to_zero_cycles():
    text = source()

    assert (
        "runtime_test_disconnect_cycles = int("
        in text
    )

    assert (
        "runtime_test_disconnect_cycles_remaining = ("
        in text
    )


def test_disconnect_hook_cannot_use_negative_cycles():
    text = source()

    assert (
        "runtime_test_disconnect_cycles < 0"
        in text
    )

    assert (
        "INVALID_H14_6_TEST_MT5_DISCONNECT_CYCLES"
        in text
    )


def test_disconnect_injection_uses_effective_connection_only():
    text = source()

    assert (
        "effective_terminal_connected = ("
        in text
    )

    assert (
        "effective_terminal_connected = False"
        in text
    )


def test_disconnect_cycles_are_consumed():
    text = source()

    assert (
        "runtime_test_disconnect_cycles_remaining -= 1"
        in text
    )


def test_disconnect_evidence_is_reported():
    text = source()

    assert (
        '"test_disconnect_cycles"'
        in text
    )

    assert (
        '"test_disconnect_cycles_remaining"'
        in text
    )

    assert (
        '"test_disconnect_observed"'
        in text
    )


def test_disconnect_hook_does_not_add_shadow_execution_paths():
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


def test_disconnect_hook_does_not_shutdown_mt5():
    text = source()

    marker = (
        "H14_6_TEST_MT5_DISCONNECT_ACTIVE"
    )

    index = text.index(
        marker
    )

    nearby = text[
        max(0, index - 1500):
        index + 1500
    ]

    assert (
        "mt5.shutdown()"
        not in nearby
    )
