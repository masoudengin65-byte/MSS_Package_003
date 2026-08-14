from pathlib import Path


RUNNER = Path(
    r"integration_tests/"
    r"run_sprint92h14_5a_live_policy_multi_symbol_shadow_session.py"
)


def source():
    return RUNNER.read_text(
        encoding="utf-8-sig"
    )


def test_exactly_one_shadow_open_call():
    text = source()

    assert (
        text.count(".open_trade(")
        == 1
    )


def test_no_direct_real_execution_calls():
    text = source()

    assert "mt5.order_send(" not in text
    assert "mt5.order_check(" not in text


def test_execution_guards_remain_present():
    text = source()

    assert "make_execution_guard" in text

    assert (
        'api_name="order_send"'
        in text
    )

    assert (
        'api_name="order_check"'
        in text
    )


def test_deterministic_flow_precedes_shadow_open():
    text = source()

    analysis_index = text.index(
        "analysis_results = {}"
    )

    candidate_index = text.index(
        "policy_inputs = []"
    )

    policy_index = text.index(
        "MultiAssetShadowRiskPolicy"
        "\n                        .evaluate("
    )

    final_phase_index = text.index(
        "# PHASE 6:"
    )

    final_watch_index = text.index(
        "final_watch = ("
    )

    open_index = text.index(
        ".open_trade("
    )

    assert (
        analysis_index
        < candidate_index
        < policy_index
        < final_phase_index
        < final_watch_index
        < open_index
    )


def test_final_policy_revalidation_precedes_open():
    text = source()

    final_policy_index = text.index(
        "final_policy = ("
    )

    open_index = text.index(
        ".open_trade("
    )

    assert (
        final_policy_index
        < open_index
    )


def test_single_position_lock_precedes_policy():
    text = source()

    lock_index = text.index(
        "PORTFOLIO_LOCK_BLOCK"
    )

    policy_index = text.index(
        "MultiAssetShadowRiskPolicy"
        "\n                        .evaluate("
    )

    assert (
        lock_index
        < policy_index
    )


def test_h14_5a_identity_and_namespace():
    text = source()

    assert (
        '"sprint": "92H.14.5a"'
        in text
    )

    assert (
        '"sprint92h14_5a"'
        in text
    )

    assert (
        '"sprint92h14_4a_1"'
        not in text
    )


def test_true_oos_remains_disabled():
    text = source()

    assert (
        '"TRUE_OOS_ACCESS",'
        in text
    )

    assert (
        '"true_oos_data_accessed": False'
        in text
    )

    assert (
        '"true_oos_artifacts_modified": False'
        in text
    )
