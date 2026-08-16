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


def test_runtime_stall_hook_is_explicitly_environment_gated():
    text = source()

    assert (
        "MSS_H14_6_TEST_RUNTIME_STALL_SECONDS"
        in text
    )

    assert (
        '"0"'
        in text
    )


def test_runtime_stall_is_one_shot():
    text = source()

    assert (
        "runtime_test_stall_injected = False"
        in text
    )

    assert (
        "not runtime_test_stall_injected"
        in text
    )


def test_runtime_stall_occurs_only_after_healthy_supervisor_decision():
    text = source()

    healthy_check = text.index(
        "not runtime_supervisor_decision.hard_block"
    )

    stall = text.index(
        "H14_6_TEST_RUNTIME_STALL_BEGIN"
    )

    assert healthy_check < stall


def test_runtime_stall_does_not_add_execution_paths():
    text = source()

    assert text.count(
        ".open_trade("
    ) == 1

    assert (
        "mt5.order_send("
        not in text
    )

    assert (
        "mt5.order_check("
        not in text
    )
