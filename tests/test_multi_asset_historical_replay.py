from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
from pathlib import Path

import pytest

from mss.analysis.historical_backtest_engine import HistoricalBacktestEngine
from mss.analysis.multi_asset_historical_replay import MultiAssetHistoricalReplay
from mss.domain.candle import Candle
from mss.domain.historical_backtest import HistoricalBacktestConfig
from mss.domain.pipeline_result import PipelineResult


START = datetime(2026, 1, 1)


class PipelineStub:
    def __init__(self, signal_calls=(1,)):
        self.signal_calls = set(signal_calls)
        self.calls = []

    def run(self, symbol, timeframe, candles):
        self.calls.append(tuple(candle.time for candle in candles))
        if len(self.calls) in self.signal_calls:
            return PipelineResult(
                symbol=symbol,
                timeframe=timeframe,
                valid=True,
                bos_detected=True,
                bos_direction="BULLISH",
                last_low=99.0,
                structure_state="UPTREND",
                score=80,
                confidence=75.0,
                recommendation="TRADE",
            )
        return PipelineResult(
            symbol=symbol,
            timeframe=timeframe,
            valid=True,
            recommendation="WAIT",
        )


def config():
    return HistoricalBacktestConfig(
        warmup_candles=2,
        analysis_lookback=10,
        starting_balance=10000.0,
        risk_percent=1.0,
        reward_risk_ratio=2.0,
        spread_points=0,
        commission_per_lot=0.0,
        slippage_points=0.0,
        ambiguous_policy="STOP_LOSS_FIRST",
    )


def candle(index):
    return Candle(
        time=START + timedelta(minutes=15 * index),
        open=100.0,
        high=103.0,
        low=99.5,
        close=101.0,
        tick_volume=100,
        spread=0,
        real_volume=0,
    )


def inputs(count=6):
    replay = MultiAssetHistoricalReplay()
    aliases = {"BTCUSD": "BITCOIN", "ETHUSD": "ETHEREUM"}
    history = {}
    metadata = {}
    for definition in replay.universe:
        canonical = definition.canonical_symbol
        broker_symbol = aliases.get(canonical, canonical)
        candles = [candle(index) for index in range(count)]
        history[canonical] = {
            "resolved_symbol": broker_symbol,
            "requested_count": count,
            "returned_count": count,
            "attempts": 1,
            "error_code": 1,
            "error_message": "Success",
            "candles": candles,
        }
        metadata[canonical] = {
            "broker_symbol": broker_symbol,
            "digits": 5,
            "point": 0.01,
            "trade_tick_size": 0.01,
            "trade_tick_value": 1.0,
            "trade_contract_size": 100.0,
            "volume_min": 0.01,
            "volume_max": 100.0,
            "volume_step": 0.01,
            "spread": 0,
        }
    as_of = START + timedelta(minutes=15 * count)
    return history, metadata, as_of


def engine_factory(signal_calls=(1,)):
    return lambda: HistoricalBacktestEngine(PipelineStub(signal_calls))


def test_reuses_historical_engine_for_complete_registered_universe():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    result = replay.replay(
        history, metadata, as_of, config(), target_count=6,
        engine_factory=engine_factory(),
    ).to_dict()

    assert result["schema_version"] == replay.VERSION
    assert result["replay_configuration"]["common_candle_count"] == 6
    assert result["diagnostics"]["symbol_count"] == 8
    assert result["diagnostics"]["closed_trade_count"] == 8
    assert result["diagnostics"]["unresolved_trade_count"] == 0
    assert result["diagnostics"]["context_snapshot_count"] == 8
    by_symbol = {row["canonical_symbol"]: row for row in result["per_symbol_results"]}
    assert by_symbol["BTCUSD"]["broker_symbol"] == "BITCOIN"
    assert by_symbol["ETHUSD"]["broker_symbol"] == "ETHEREUM"
    assert all(row["source_candles"] == 6 for row in by_symbol.values())


def test_replay_is_immutable_deterministic_and_does_not_mutate_inputs():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    history_before = deepcopy(history)
    metadata_before = deepcopy(metadata)
    first = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    )
    second = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    )

    assert first.payload_json == second.payload_json
    assert first.sha256 == second.sha256
    assert history == history_before
    assert metadata == metadata_before
    with pytest.raises(TypeError):
        first["trades"] = []
    extracted = first.to_dict()
    extracted["trades"].clear()
    assert first.to_dict()["trades"]


def test_future_completed_candle_is_rejected_before_replay():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    history["EURUSD"]["candles"].append(candle(6))
    history["EURUSD"]["returned_count"] += 1
    with pytest.raises(ValueError, match="Future candle rejected"):
        replay.replay(
            history, metadata, as_of, config(), 6, engine_factory(),
        )


def test_common_count_is_reduced_for_every_symbol_not_only_partial_symbol():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    history["ETHUSD"]["candles"] = history["ETHUSD"]["candles"][-5:]
    history["ETHUSD"]["returned_count"] = 5
    result = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    ).to_dict()

    assert result["replay_configuration"]["common_candle_count"] == 5
    assert {row["source_candles"] for row in result["per_symbol_results"]} == {5}
    assert {row["selected_count"] for row in result["history_availability"]} == {5}


def test_missing_symbol_history_stops_the_comparable_replay():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    history["XAUUSD"]["candles"] = []
    history["XAUUSD"]["returned_count"] = 0
    with pytest.raises(ValueError, match="history unavailable"):
        replay.replay(
            history, metadata, as_of, config(), 6, engine_factory(),
        )


def test_unresolved_trades_are_preserved_but_excluded_from_outcome_metrics():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    for payload in history.values():
        payload["candles"][-1].high = 101.0
        payload["candles"][-1].low = 99.5
    result = replay.replay(
        history, metadata, as_of, config(), 6,
        engine_factory(signal_calls=(4,)),
    ).to_dict()

    assert result["diagnostics"]["closed_trade_count"] == 0
    assert result["diagnostics"]["unresolved_trade_count"] == 8
    assert result["combined_independent_results"]["closed_trades"] == 0
    assert result["combined_independent_results"]["unresolved_trades"] == 8
    assert all(row["outcome"] == "UNRESOLVED" for row in result["trades"])
    assert result["audit"]["unresolved_trades_excluded_from_outcome_metrics"] is True


def test_asset_class_and_combined_balances_are_sums_of_independent_results():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    result = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    ).to_dict()

    symbol_ending = sum(row["ending_balance"] for row in result["per_symbol_results"])
    combined = result["combined_independent_results"]
    assert combined["starting_balance"] == 80000.0
    assert combined["ending_balance"] == symbol_ending
    assert combined["true_shared_capital_portfolio"] is False
    class_starting = sum(row["starting_balance"] for row in result["asset_class_results"])
    assert class_starting == combined["starting_balance"]


def test_required_broker_metadata_is_captured_and_validated():
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    result = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    ).to_dict()
    btc = next(row for row in result["broker_metadata"] if row["canonical_symbol"] == "BTCUSD")
    assert btc == {
        "canonical_symbol": "BTCUSD",
        "broker_symbol": "BITCOIN",
        "asset_class": "CRYPTO",
        "digits": 5,
        "point": 0.01,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "contract_size": 100.0,
        "volume_min": 0.01,
        "volume_max": 100.0,
        "volume_step": 0.01,
        "spread_points": 0.0,
        "spread_price": 0.0,
    }
    metadata["BTCUSD"]["volume_step"] = 0
    with pytest.raises(ValueError, match="volume_step"):
        replay.replay(
            history, metadata, as_of, config(), 6, engine_factory(),
        )


def test_schema_and_json_serialization_are_reproducible(tmp_path):
    replay = MultiAssetHistoricalReplay()
    history, metadata, as_of = inputs()
    snapshot = replay.replay(
        history, metadata, as_of, config(), 6, engine_factory(),
    )
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    replay.write_json(snapshot.to_dict(), first)
    replay.write_json(snapshot.to_dict(), second)

    assert hashlib.sha256(first.read_bytes()).digest() == hashlib.sha256(second.read_bytes()).digest()
    result = snapshot.to_dict()
    assert set(result) == set(replay.RESULT_KEYS)
    assert result["diagnostics"]["future_candle_count"] == 0
    assert result["diagnostics"]["lookahead_violation_count"] == 0
    assert result["production_change_justified"] is False


def test_production_paths_do_not_import_sprint_91_layer():
    root = Path(__file__).resolve().parents[1]
    production_files = (
        root / "src/mss/analysis/smart_money_pipeline.py",
        root / "src/mss/analysis/structure_engine.py",
        root / "src/mss/engine/signal_engine.py",
        root / "src/mss/analysis/risk_engine.py",
        root / "src/mss/analysis/execution_pipeline.py",
        root / "src/mss/execution/mt5_executor.py",
    )
    for path in production_files:
        content = path.read_text(encoding="utf-8").lower()
        assert "multi_asset_historical_replay" not in content
        assert "multi_asset_replay_result" not in content
