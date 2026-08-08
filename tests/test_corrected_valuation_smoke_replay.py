from datetime import datetime, timedelta
from types import SimpleNamespace

from mss.analysis.corrected_valuation_smoke_replay import CorrectedValuationSmokeReplay
from mss.domain.historical_backtest import (
    BacktestDiagnostics, BacktestSymbolMetadata, HistoricalBacktestConfig,
    HistoricalMetrics, HistoricalTrade,
)


def metadata(symbol):
    values = {
        "USDJPY": (0.001, 0.6312334301224594, 100000.0, 3),
        "USDCAD": (0.00001, 0.7135161361674194, 100000.0, 5),
        "XAUUSD": (0.01, 0.1, 100.0, 2),
    }
    tick_size, tick_value, contract_size, digits = values[symbol]
    return BacktestSymbolMetadata(
        point=tick_size, digits=digits, tick_size=tick_size,
        tick_value=tick_value, contract_size=contract_size,
        volume_min=0.01, volume_max=100.0, volume_step=0.01,
        spread_points=0.0,
    )


def replay_row(symbol):
    meta = metadata(symbol)
    stop_distance = 100.0 / meta.tick_value * meta.tick_size
    start = datetime(2026, 1, 1)
    trades = [
        HistoricalTrade(
            trade_id=1, direction="BUY", entry_time=start,
            exit_time=start + timedelta(minutes=15), entry_price=100.0,
            stop_loss=100.0 - stop_distance, exit_price=100.0 - stop_distance,
            volume=1.0, profit=-100.0, r_multiple=-1.0,
            exit_reason="STOP_LOSS", status="CLOSED",
        ),
        HistoricalTrade(
            trade_id=2, direction="BUY", entry_time=start + timedelta(minutes=30),
            exit_time=start + timedelta(minutes=45), entry_price=100.0,
            stop_loss=100.0 - stop_distance, exit_price=100.0 + 2 * stop_distance,
            volume=0.99, profit=198.0, r_multiple=2.0,
            exit_reason="TAKE_PROFIT", status="CLOSED",
        ),
    ]
    return {
        "canonical_symbol": symbol,
        "historical_window": {
            "candle_count": 10000,
            "first_candle_open_time": "2026-01-01T00:00:00",
            "last_candle_open_time": "2026-04-15T00:00:00",
        },
        "metadata": meta,
        "result": SimpleNamespace(
            trades=trades,
            config=HistoricalBacktestConfig(),
            diagnostics=BacktestDiagnostics(
                opened_trades=2, closed_trades=2, rejected_trades=1,
                rejection_reasons={"NO_NEXT_CANDLE": 1},
            ),
            metrics=HistoricalMetrics(
                total_trades=2, winning_trades=1, losing_trades=1,
                win_rate=50.0, net_profit=98.0, profit_factor=1.98,
                expectancy=49.0, average_r=0.5,
                maximum_drawdown_percent=1.0, return_percent=0.98,
            ),
        ),
    }


def v1_payload():
    return {"per_symbol_results": [
        {
            "canonical_symbol": symbol, "opened_trades": 2,
            "closed_trades": 2, "rejected_trades": 1,
            "win_rate_percent": 50.0, "net_profit": 0.0,
            "profit_factor": 1.0, "expectancy": 0.0, "average_r": 0.0,
            "maximum_drawdown_percent": 10.0, "total_return_percent": 0.0,
        }
        for symbol in CorrectedValuationSmokeReplay.SYMBOLS
    ]}


def audit_payload():
    return {"per_symbol_risk_consistency": {
        symbol: {
            "median_losing_trade_percent": 2.0,
            "p90_losing_trade_percent": 2.0,
            "maximum_losing_trade_percent": 2.0,
            "losses_above_1_25_percent": 1,
            "losses_above_1_50_percent": 1,
            "losses_above_2_00_percent": 0,
        }
        for symbol in CorrectedValuationSmokeReplay.SYMBOLS
    }}


def test_builds_exact_three_symbol_comparison_and_passes_acceptance():
    rows = [replay_row(symbol) for symbol in CorrectedValuationSmokeReplay.SYMBOLS]
    report = CorrectedValuationSmokeReplay().build_report(
        rows, v1_payload(), audit_payload(),
    )

    assert report["overall_status"] == "PASS"
    assert set(report["symbols"]) == set(CorrectedValuationSmokeReplay.SYMBOLS)
    assert report["full_eight_symbol_replay_run"] is False
    assert report["real_orders_sent"] is False
    for row in report["symbols"].values():
        assert row["valuation_check"]["corrected_to_broker_ratio"] == 1.0
        assert row["corrected_loss_risk_distribution"]["median_losing_trade_percent"] == 1.0
        assert row["minimum_volume"]["oversized_minimum_volume_trade_count"] == 0


def test_rejects_incomplete_or_extra_symbol_scope():
    smoke = CorrectedValuationSmokeReplay()
    rows = [replay_row("USDJPY"), replay_row("USDCAD")]
    try:
        smoke.build_report(rows, v1_payload(), audit_payload())
    except ValueError as error:
        assert "exactly" in str(error)
    else:
        raise AssertionError("Expected incomplete smoke scope to fail")
