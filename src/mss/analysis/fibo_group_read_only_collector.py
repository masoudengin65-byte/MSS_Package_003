"""Acquire preregistered FIBO demo bars with no order-capable MT5 calls."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


MANIFEST_NAME = "MSS_Sprint93_3F_FIBO_Group_Price_Comparison_Acquisition_Manifest_V1.json"
EXPECTED_SERVER = "FIBOGroup-MT5 Server"
RATE_FIELDS = ("time", "open", "high", "low", "close")


def _value(row: Any, name: str) -> Any:
    names = getattr(getattr(row, "dtype", None), "names", None)
    if names and name in names:
        return row[name].item() if hasattr(row[name], "item") else row[name]
    if isinstance(row, dict):
        return row[name]
    return getattr(row, name)


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _serialise_rates(rates: Any) -> list[dict[str, float | int]]:
    result = []
    previous_time = None
    for row in rates:
        item = {name: _value(row, name) for name in RATE_FIELDS}
        item["time"] = int(item["time"])
        for name in RATE_FIELDS[1:]:
            item[name] = float(item[name])
        if previous_time is not None and item["time"] <= previous_time:
            raise ValueError("Broker rates must be strictly increasing")
        if not item["low"] <= min(item["open"], item["close"]) <= max(item["open"], item["close"]) <= item["high"]:
            raise ValueError("Broker rates contain invalid OHLC")
        previous_time = item["time"]
        result.append(item)
    if not result:
        raise ValueError("Broker returned no rates")
    return result


def _write_once(path: Path, payload: list[dict[str, float | int]]) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            for item in payload:
                handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise FileExistsError(f"Refusing to overwrite evidence: {path}") from error
    finally:
        temporary.unlink(missing_ok=True)


def collect(root: Path, terminal_path: Path, mt5: Any, output_root: Path | None = None) -> dict[str, object]:
    manifest = json.loads((root / "reports" / MANIFEST_NAME).read_text(encoding="utf-8"))
    quality = json.loads((root / "reports" / "MSS_Sprint93_3A_Data_Quality_V1.json").read_text(encoding="utf-8"))
    gates = manifest["pre_acquisition_gates"]
    if not gates["all_required_gates_pass"]:
        raise RuntimeError("FIBO pre-acquisition gates are not all passed")
    if manifest["safety"]["candidate_data_acquired"]:
        raise RuntimeError("Candidate data was already acquired; refusing duplicate collection")
    if not terminal_path.is_file():
        raise FileNotFoundError(f"MT5 terminal missing: {terminal_path}")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Order-capable MT5 API call is forbidden during FIBO collection")

    original_order_check = getattr(mt5, "order_check", None)
    original_order_send = getattr(mt5, "order_send", None)
    mt5.order_check = forbidden
    mt5.order_send = forbidden
    captured: dict[str, list[dict[str, float | int]]] = {}
    try:
        mt5.shutdown()
        if not mt5.initialize(path=str(terminal_path), timeout=120_000):
            raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
        account = mt5.account_info()
        if account is None or getattr(account, "server", None) != EXPECTED_SERVER:
            raise RuntimeError("Active MT5 session is not the preregistered FIBO demo server")
        start = _utc(quality["window"]["start_utc_inclusive"])
        end = _utc(quality["window"]["end_utc_exclusive"]) - timedelta(seconds=1)
        for mapping in manifest["symbol_mappings"]:
            symbol = mapping["fibo_group_symbol"]
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(f"FIBO symbol unavailable: {symbol}: {mt5.last_error()}")
            rates = mt5.copy_rates_range(symbol, mt5.TIMEFRAME_M15, start, end)
            captured[symbol] = _serialise_rates(rates)
    finally:
        mt5.shutdown()
        mt5.order_check = original_order_check
        mt5.order_send = original_order_send

    output_root = output_root or root / "historical_data" / "sprint93_3f_fibo_candidate"
    for symbol in captured:
        if (output_root / f"{symbol}_M15.jsonl").exists():
            raise FileExistsError("FIBO candidate evidence destination already exists")
    for symbol, rates in captured.items():
        _write_once(output_root / f"{symbol}_M15.jsonl", rates)
    return {
        "server": EXPECTED_SERVER,
        "symbols": {symbol: len(rates) for symbol, rates in captured.items()},
        "order_check_called": False,
        "order_send_called": False,
        "raw_output_root": str(output_root),
    }
