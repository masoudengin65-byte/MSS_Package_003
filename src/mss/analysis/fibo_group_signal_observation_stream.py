"""Extract frozen strategy observations without orders, positions, or outcomes."""

from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Iterable

from mss.analysis.smart_money_pipeline import SmartMoneyPipeline
from mss.domain.candle import Candle

DATA_MANIFEST_NAME = "MSS_Sprint92H2_Immutable_Research_Data_Manifest.json"
SCOPE = ("EURUSD", "XAUUSD", "BTCUSD", "ETHUSD")
TIMEFRAME_SECONDS = 15 * 60
WARMUP_CANDLES = 200
ANALYSIS_LOOKBACK = 500


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_candles(path: Path) -> list[Candle]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [
        Candle(
            time=datetime.fromtimestamp(row["time_epoch_seconds"], tz=UTC),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            tick_volume=int(row["tick_volume"]),
            spread=int(row["spread"]),
            real_volume=int(row["real_volume"]),
        )
        for row in rows
    ]


def load_verified_fibo_development_data(
    root: Path,
) -> tuple[dict[str, list[Candle]], dict[str, str]]:
    manifest_path = root / "reports" / DATA_MANIFEST_NAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    by_symbol = {row["canonical_symbol"]: row for row in manifest["symbols"]}
    histories: dict[str, list[Candle]] = {}
    source_hashes: dict[str, str] = {}
    for symbol in SCOPE:
        source = by_symbol[symbol]
        path = root / source["relative_path"]
        actual = _sha256(path)
        if actual != source["file_sha256"]:
            raise ValueError(f"immutable development data hash mismatch for {symbol}")
        candles = _load_candles(path)
        if len(candles) != source["row_count"]:
            raise ValueError(
                f"immutable development data row count mismatch for {symbol}"
            )
        if any(
            candles[index].time >= candles[index + 1].time
            for index in range(len(candles) - 1)
        ):
            raise ValueError(
                f"immutable development timestamps are not strictly increasing for {symbol}"
            )
        histories[symbol] = candles
        source_hashes[symbol] = actual
    return histories, source_hashes


def _direction(result: object) -> str | None:
    if not getattr(result, "valid", False) or not getattr(
        result, "bos_detected", False
    ):
        return None
    return {"BULLISH": "BUY", "BEARISH": "SELL"}.get(
        getattr(result, "bos_direction", None)
    )


def _crosses_gap(candles: list[Candle], start: int, end: int) -> bool:
    return any(
        (candles[index + 1].time - candles[index].time).total_seconds()
        != TIMEFRAME_SECONDS
        for index in range(start, end)
    )


def observe_histories(
    histories: dict[str, list[Candle]], source_hashes: dict[str, str]
) -> dict[str, object]:
    """Emit signal observations only; no trade, size, price outcome, or P&L fields."""
    if tuple(histories) != SCOPE:
        raise ValueError("observation histories must use exactly the frozen FIBO scope")
    observations: list[dict[str, object]] = []
    for symbol in SCOPE:
        candles = histories[symbol]
        pipeline = SmartMoneyPipeline()
        for index in range(WARMUP_CANDLES - 1, len(candles) - 1):
            start = max(0, index + 1 - ANALYSIS_LOOKBACK)
            direction = _direction(
                pipeline.run(symbol, "M15", candles[start : index + 1])
            )
            if direction is None:
                continue
            observations.append(
                {
                    "candidate_id": f"{symbol}:{int(candles[index].time.timestamp())}:{direction}",
                    "symbol": symbol,
                    "signal_time_utc": candles[index]
                    .time.isoformat()
                    .replace("+00:00", "Z"),
                    "entry_bar_time_utc": candles[index + 1]
                    .time.isoformat()
                    .replace("+00:00", "Z"),
                    "direction": direction,
                    "observed_spread_points": candles[index + 1].spread,
                    "lookback_crosses_unadjudicated_gap": _crosses_gap(
                        candles, start, index
                    ),
                    "position_carries_across_unadjudicated_gap": False,
                }
            )
    if len({row["candidate_id"] for row in observations}) != len(observations):
        raise ValueError("candidate observation identifiers are not unique")
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_SIGNAL_OBSERVATION_STREAM_V1",
        "purpose": "Extract historical strategy observations without simulating or valuing trades",
        "data_scope": "IMMUTABLE_DEVELOPMENT_ONLY_PREVIOUSLY_ANALYZED_NOT_TRUE_FUTURE_OOS",
        "configuration": {
            "symbols": list(SCOPE),
            "timeframe": "M15",
            "warmup_candles": WARMUP_CANDLES,
            "analysis_lookback": ANALYSIS_LOOKBACK,
            "entry_policy": "NEXT_CANDLE_OPEN_TIME_RECORDED_ONLY_NO_ORDER_OR_PRICE_SIMULATION",
        },
        "source_hashes": source_hashes,
        "observations": observations,
        "summary": {"observation_count": len(observations)},
        "outcome_boundary": {
            "entry_price_emitted": False,
            "position_created": False,
            "exit_observed": False,
            "net_profit_metric_emitted": False,
            "return_metric_emitted": False,
            "drawdown_metric_emitted": False,
        },
        "safety": {
            "raw_data_modified": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
