from copy import deepcopy

from mss.analysis.replay_integrity_audit import ReplayIntegrityAudit


def fixture_payload():
    symbols = ReplayIntegrityAudit.SYMBOLS
    trades = []
    summaries = []
    metadata = []
    references = []
    for symbol in symbols:
        profits = [200.0, -100.0]
        for trade_id, profit in enumerate(profits, 1):
            trades.append({
                "canonical_symbol": symbol, "status": "CLOSED", "trade_id": trade_id,
                "direction": "BUY", "entry_time": f"2026-01-0{trade_id}T00:00:00",
                "exit_time": f"2026-01-0{trade_id}T01:00:00",
                "exit_reason": "TAKE_PROFIT" if profit > 0 else "STOP_LOSS",
                "entry_price": 100.0, "stop_loss": 99.9, "exit_price": 100.2 if profit > 0 else 99.9,
                "profit": profit, "volume": 0.01, "spread": 0.0,
                "slippage": 0.0, "commission": 0.0,
            })
        summaries.append({
            "canonical_symbol": symbol, "starting_balance": 10000.0,
            "ending_balance": 10100.0, "gross_profit": 200.0, "gross_loss": 100.0,
            "net_profit": 100.0, "maximum_drawdown": 100.0,
            "maximum_drawdown_percent": 100.0 / 10200.0 * 100.0,
            "total_return_percent": 1.0, "closed_trades": 2, "wins": 1, "losses": 1,
        })
        metadata.append({
            "canonical_symbol": symbol, "broker_symbol": symbol, "asset_class": "FOREX",
            "point": 0.00001, "digits": 5, "contract_size": 100000.0,
            "volume_min": 0.01, "volume_max": 100.0, "volume_step": 0.01,
        })
        references.append({
            "canonical_symbol": symbol, "point": 0.00001, "digits": 5,
            "trade_contract_size": 100000.0, "trade_tick_size": 0.00001,
            "trade_tick_value": 1.0,
        })
    return {
        "schema_version": "test", "generated_as_of": "2026-01-03T00:00:00",
        "replay_configuration": {"risk_percent": 1.0},
        "per_symbol_results": summaries, "broker_metadata": metadata, "trades": trades,
    }, {"trading_conditions": references}


def test_reconciles_saved_trade_rows_without_replay():
    replay, reference = fixture_payload()
    result = ReplayIntegrityAudit().audit(replay, reference)

    assert result["overall_audit_status"] == "PASS"
    assert all(row["status"] == "PASS" for row in result["per_symbol_reconciliation"].values())
    assert result["conclusions"]["summary_fields_reconcile"] is True


def test_flags_summary_mismatch_independently():
    replay, reference = fixture_payload()
    replay["per_symbol_results"][0]["net_profit"] = 999.0
    result = ReplayIntegrityAudit().audit(replay, reference)

    check = result["per_symbol_reconciliation"]["EURUSD"]
    assert check["status"] == "FAIL"
    assert check["comparisons"]["net_profit"]["recomputed"] == 100.0


def test_flags_tick_value_unit_defect_without_fixing_it():
    replay, reference = fixture_payload()
    usd = next(row for row in reference["trading_conditions"] if row["canonical_symbol"] == "USDJPY")
    usd["trade_tick_size"] = 0.001
    usd["trade_tick_value"] = 0.6312334301224594
    replay_usd = next(row for row in replay["broker_metadata"] if row["canonical_symbol"] == "USDJPY")
    replay_usd.update({"point": 0.001, "digits": 3})

    result = ReplayIntegrityAudit().audit(deepcopy(replay), reference)
    check = result["metadata_checks"]["USDJPY"]

    assert result["overall_audit_status"] == "DEFECT_FOUND"
    assert result["code_defect_found"] is True
    assert check["engine_value_per_tick_per_lot_matches_reference"] is False
    assert check["engine_to_reference_tick_value_ratio"] > 150
    tick_risk = result["per_symbol_risk_consistency"]["USDJPY"]["tick_value_aware_loss_distribution"]
    assert tick_risk["maximum_losing_trade_percent"] < 0.01
    assert result["conclusions"]["production_fix_applied"] is False


def test_nearest_rank_risk_diagnostics_and_drawdown_sequence():
    replay, reference = fixture_payload()
    result = ReplayIntegrityAudit().audit(replay, reference)
    risk = result["per_symbol_risk_consistency"]["EURUSD"]
    drawdown = result["usd_jpy_drawdown_audit"]

    assert risk["median_losing_trade_percent"] == round(100 / 10200 * 100, 4)
    assert risk["p90_losing_trade_percent"] == risk["maximum_losing_trade_percent"]
    assert drawdown["prior_equity_peak"] == 10200.0
    assert drawdown["trough_equity"] == 10100.0
    assert drawdown["trades_peak_to_trough"] == 1
    assert drawdown["peak_to_trough_trade_ids"] == [2]
