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


def test_h14_6_runner_imports_runtime_supervisor():
    text = source()

    assert (
        "ShadowLiveRuntimeSupervisor"
        in text
    )

    assert (
        "ShadowLiveRuntimeSupervisorInput"
        in text
    )


def test_h14_6_runner_imports_runtime_telemetry():
    assert (
        "ShadowLiveRuntimeTelemetry"
        in source()
    )


def test_supervisor_occurs_after_position_lifecycle_monitoring():
    text = source()

    lifecycle = text.index(
        "Natural monitoring of the single"
    )

    supervisor = text.index(
        "H14.6 LONG-RUNNING RUNTIME SUPERVISOR"
    )

    assert lifecycle < supervisor


def test_supervisor_occurs_after_runtime_portfolio_refresh():
    text = source()

    refresh = text.index(
        "runtime authoritative portfolio"
    )

    supervisor = text.index(
        "H14.6 LONG-RUNNING RUNTIME SUPERVISOR"
    )

    assert refresh < supervisor


def test_supervisor_occurs_before_candidate_discovery():
    text = source()

    supervisor = text.index(
        "H14.6 LONG-RUNNING RUNTIME SUPERVISOR"
    )

    phase_1 = text.index(
        "# PHASE 1:"
    )

    assert supervisor < phase_1


def test_runtime_report_contains_telemetry():
    text = source()

    assert (
        '"runtime_telemetry"'
        in text
    )

    assert (
        '"heartbeat_count"'
        in text
    )

    assert (
        '"runtime_disconnect_count"'
        in text
    )


def test_h14_6_still_has_single_shadow_open_path():
    assert (
        source().count(
            ".open_trade("
        )
        == 1
    )


def test_h14_6_has_no_direct_real_execution_calls():
    text = source()

    assert (
        "mt5.order_send("
        not in text
    )

    assert (
        "mt5.order_check("
        not in text
    )
