from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

RUNNER = (
    ROOT
    / "integration_tests"
    / "run_sprint92h14_7_demo_forward_session.py"
)

ADAPTER = (
    ROOT
    / "src"
    / "mss"
    / "analysis"
    / "demo_broker_execution_adapter.py"
)


def _runner_text():
    return RUNNER.read_text(
        encoding="utf-8"
    )


def _adapter_text():
    return ADAPTER.read_text(
        encoding="utf-8"
    )


def test_demo_forward_requires_explicit_flag():
    text = _runner_text()

    assert '"--demo-forward"' in text
    assert "action=\"store_true\"" in text


def test_default_demo_forward_state_is_no_send():
    text = _runner_text()

    assert (
        "DEMO_FORWARD_EXECUTION_ENABLED"
        in text
    )

    assert (
        "if not args.demo_forward"
        in text
    )


def test_runner_has_no_direct_mt5_order_send_call():
    text = _runner_text()

    assert "mt5.order_send(" not in text


def test_runner_has_no_direct_mt5_order_check_call():
    text = _runner_text()

    assert "mt5.order_check(" not in text


def test_runner_uses_demo_execution_adapter():
    text = _runner_text()

    assert (
        "DemoBrokerExecutionAdapter"
        in text
    )

    assert (
        ".execute_market_order("
        in text
    )


def test_runner_uses_broker_risk_calculator():
    text = _runner_text()

    assert "ShadowRiskCalculator" in text
    assert ".calculate(" in text


def test_original_order_send_is_injected_only():
    text = _runner_text()

    assert (
        "order_send_callable=("
        in text
    )

    assert "original_order_send" in text


def test_original_order_check_is_injected_only():
    text = _runner_text()

    assert (
        "order_check_callable=("
        in text
    )

    assert "original_order_check" in text


def test_h14_7_has_independent_journal_namespace():
    text = _runner_text()

    assert (
        '"sprint92h14_7_shadow_observation"'
        in text
    )

    assert (
        '"sprint92h14_7_demo_broker_execution"'
        in text
    )

    assert (
        '"sprint92h14_7_demo_forward"'
        not in text
    )

    assert '"sprint92h14_6"' not in text
    assert '"sprint92h14_5c"' not in text



def test_h14_7_report_has_demo_forward_telemetry():
    text = _runner_text()

    assert (
        '"demo_forward_execution"'
        in text
    )

    assert '"attempt_count"' in text
    assert '"success_count"' in text
    assert '"blocked_count"' in text
    assert '"last_order_ticket"' in text
    assert '"last_deal_ticket"' in text


def test_adapter_supports_injected_check_callable():
    text = _adapter_text()

    assert (
        "order_check_callable=None"
        in text
    )

    assert (
        "check_fn = ("
        in text
    )


def test_adapter_supports_injected_send_callable():
    text = _adapter_text()

    assert (
        "order_send_callable=None"
        in text
    )

    assert (
        "send_fn = ("
        in text
    )


def test_adapter_still_blocks_non_demo_accounts():
    text = _adapter_text()

    assert (
        "NON_DEMO_ACCOUNT_BLOCKED"
        in text
    )


def test_adapter_checks_duplicate_positions():
    text = _adapter_text()

    assert (
        "DUPLICATE_SYMBOL_POSITION_BLOCKED"
        in text
    )


def test_adapter_checks_duplicate_orders():
    text = _adapter_text()

    assert (
        "DUPLICATE_SYMBOL_ORDER_BLOCKED"
        in text
    )


def test_adapter_checks_before_send():
    text = _adapter_text()

    check_pos = text.find(
        "check = check_fn("
    )

    send_pos = text.find(
        "result = send_fn("
    )

    assert check_pos >= 0
    assert send_pos >= 0
    assert check_pos < send_pos


def test_true_oos_is_declared_unaccessed():
    text = _runner_text()

    assert (
        '"true_oos_data_accessed": False'
        in text
    )

    assert (
        '"true_oos_artifacts_modified": False'
        in text
    )


def test_demo_broker_execution_precedes_shadow_open():
    text = _runner_text()

    start = text.find(
        '"GLOBAL_ENTRY_SAFETY_CONFIRMED"'
    )

    broker_pos = text.find(
        ".execute_market_order(",
        start,
    )

    shadow_pos = text.find(
        ".open_trade(",
        start,
    )

    assert start >= 0
    assert broker_pos >= 0
    assert shadow_pos >= 0
    assert broker_pos < shadow_pos


def test_broker_failure_cannot_open_shadow_position():
    text = _runner_text()

    assert (
        "shadow_open_permitted = ("
        in text
    )

    assert (
        "shadow_open_permitted = True"
        in text
    )

    assert (
        "if shadow_open_permitted:"
        in text
    )


def test_demo_mirror_failure_is_fatal_after_broker_confirmation():
    text = _runner_text()

    assert (
        "DEMO_BROKER_POSITION_WITHOUT_SHADOW_MIRROR"
        in text
    )

    assert (
        "DEMO_BROKER_CONFIRMED_"
        in text
    )

    assert (
        "SHADOW_MIRROR_FAILED:"
        in text
    )


def test_main_global_stats_contains_demo_execution_counters():
    from pathlib import Path

    text = Path(
        "integration_tests/"
        "run_sprint92h14_7_demo_forward_session.py"
    ).read_text(
        encoding="utf-8"
    )

    anchor = text.index(
        "    global_stats = {"
    )

    end = text.index(
        "    initialized = False",
        anchor,
    )

    main_stats_block = text[
        anchor:end
    ]

    assert '"demo_execution_attempts": 0' in main_stats_block
    assert '"demo_execution_successes": 0' in main_stats_block
    assert '"demo_execution_blocks": 0' in main_stats_block


def test_expanded_demo_probe_isolated_symbol_universe():
    from pathlib import Path

    text = Path(
        "integration_tests/"
        "run_sprint92h14_7_demo_forward_session.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "EXPANDED_DEMO_PROBE_SYMBOLS" in text
    assert "--demo-probe-expanded-symbols" in text
    assert "EXPANDED_DEMO_PROBE_REQUIRES_DEMO_FORWARD" in text
    assert "DEMO_PROBE_EXPANDED_SYMBOL_COUNT" in text

    expected = [
        "AUDUSD",
        "USDCAD",
        "USDCHF",
        "NZDUSD",
        "EURJPY",
        "GBPJPY",
        "EURGBP",
        "AUDJPY",
        "CADJPY",
        "CHFJPY",
        "EURAUD",
        "EURNZD",
        "EURCAD",
        "EURCHF",
        "GBPAUD",
        "GBPCAD",
        "GBPCHF",
        "COPPER",
        "NAS100",
        "US30",
        "NETH25",
        "SPN35",
        "BITCOIN CASH",
        "SOLANA",
    ]

    for symbol in expected:
        assert f'"{symbol}"' in text


def test_expanded_demo_probe_contains_exactly_32_symbols():
    import ast
    from pathlib import Path

    text = Path(
        "integration_tests/"
        "run_sprint92h14_7_demo_forward_session.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    tree = ast.parse(text)

    expanded = None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and
                    target.id
                    == "EXPANDED_DEMO_PROBE_SYMBOLS"
                ):
                    expanded = ast.literal_eval(
                        node.value
                    )

    assert expanded is not None
    assert len(expanded) == 32
    assert len(set(expanded)) == 32


def test_demo_shadow_mirror_uses_broker_confirmed_volume():
    runner = Path(
        "integration_tests/"
        "run_sprint92h14_7_demo_forward_session.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "volume_override=(" in runner
    assert "float(demo_result.volume)" in runner
    assert "and demo_result.valid" in runner


def test_demo_post_send_uncertain_exposure_fail_stops():
    runner = Path(
        "integration_tests/"
        "run_sprint92h14_7_demo_forward_session.py"
    ).read_text(
        encoding="utf-8-sig"
    )

    assert "order_send_performed" in runner
    assert "DEMO_POST_SEND_FAIL_STOP" in runner
    assert '"DEMO_POST_SEND_"' in runner
    assert '"REQUIRES_MANUAL_"' in runner
    assert '"RECONCILIATION:"' in runner

def test_demo_mirror_uses_broker_confirmed_entry_and_epoch():
    text = _runner_text()

    assert "demo_result" in text
    assert ".fill_price" in text

    assert (
        ".position_open_broker_epoch"
        in text
    )


def test_demo_attempt_limit_preserves_open_position_monitoring():
    text = _runner_text()

    assert (
        text.count(
            '"DEMO_EXECUTION_ATTEMPT_"'
        )
        >= 1
    )

    gate = text.index(
        "# H14.7 controlled Demo session limits."
    )

    window = text[
        gate:
        gate + 1600
    ]

    assert "if position is None:" in window
    assert "args.max_demo_attempts > 0" in window


def test_session_deadline_does_not_abandon_open_position():
    text = _runner_text()

    first_status = text.index(
        '"SESSION_MAX_SECONDS_REACHED"'
    )

    window = text[
        max(
            0,
            first_status - 500,
        ):
        first_status
    ]

    assert "position is None" in window


def test_existing_single_broker_position_reaches_shadow_recovery():
    text = _runner_text()
    snapshot = text.index("demo_mss_positions = tuple(")
    recovery = text.index("ShadowPositionRecovery", snapshot)
    reconciliation = text.index(
        "DemoBrokerShadowRestartReconciler.reconcile", recovery
    )
    assert snapshot < recovery < reconciliation
    assert "DEMO_BROKER_EXPOSURE_REQUIRES_RECONCILIATION" not in text


def test_restart_reconciliation_precedes_candidate_execution():
    text = _runner_text()
    reconciliation = text.index(
        "DemoBrokerShadowRestartReconciler.reconcile"
    )
    candidate = text.index("candidate_context = {}", reconciliation)
    adapter = text.index(".execute_market_order(", reconciliation)
    assert reconciliation < candidate < adapter


def test_restart_resume_uses_existing_recovery_without_duplicate_open():
    text = _runner_text()
    reconciliation = text.index(
        "DemoBrokerShadowRestartReconciler.reconcile"
    )
    restore = text.index(") = recovered[0]", reconciliation)
    open_trade = text.index(".open_trade(", restore)
    assert reconciliation < restore < open_trade
    assert "DEMO_BROKER_SHADOW_RESTART_RESUME_ALLOWED" in text
    assert 'print("REAL_ORDER_SENT", False)' in text


def test_restart_reconciler_receives_global_pending_and_shadow_counts():
    text = _runner_text()
    assert "pending_order_count=len(demo_mss_orders)" in text
    assert "shadow_positions=tuple(item[1] for item in recovered)" in text


def test_case_d_uses_position_scoped_deal_history_before_candidates():
    text = _runner_text()
    history = text.index("mt5.history_deals_get(")
    reconcile = text.index(
        "DemoBrokerOfflineClosureReconciler.reconcile", history
    )
    apply_close = text.index(
        "DemoBrokerOfflineClosureJournalApplier.apply", reconcile
    )
    candidate = text.index("candidate_context = {}", apply_close)
    assert history < reconcile < apply_close < candidate
    assert "position=(" in text[history:reconcile]


def test_offline_close_requires_post_recovery_and_broker_verification():
    text = _runner_text()
    start = text.index("DemoBrokerOfflineClosureJournalApplier.apply")
    end = text.index("# Read-only predecessor safety guard", start)
    block = text[start:end]
    assert "ShadowPositionRecovery.recover(" in block
    assert "ShadowPortfolioRiskAggregator.recover(" in block
    assert "post_broker_positions = mt5.positions_get()" in block
    assert "post_broker_orders = mt5.orders_get()" in block
    assert "OFFLINE_CLOSURE_POST_BROKER_" in block
    assert '"EXPOSURE_PRESENT"' in block
    assert '"PENDING_ORDER_PRESENT"' in block


def test_demo_mirror_persists_broker_position_identity():
    text = _runner_text()
    assert "broker_position_ticket=(" in text
    assert "int(demo_result.position_ticket)" in text
    assert "broker_position_identifier=(" in text
    assert "int(demo_result.position_identifier)" in text
