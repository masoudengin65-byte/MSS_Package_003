"""Read-only FIBO demo-forward preflight with order APIs fail-closed."""

from __future__ import annotations

from pathlib import Path
from typing import Any

EXPECTED_SERVER = "FIBOGroup-MT5 Server"
SYMBOLS = ("EURUSD", "XAUUSD", "BTC", "ETH")


def run_preflight(terminal_path: Path, mt5: Any) -> dict[str, object]:
    if not terminal_path.is_file():
        raise FileNotFoundError(f"MT5 terminal is missing: {terminal_path}")

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("order-capable MT5 API call is forbidden during preflight")

    original_order_check = getattr(mt5, "order_check", None)
    original_order_send = getattr(mt5, "order_send", None)
    mt5.order_check = forbidden
    mt5.order_send = forbidden
    try:
        mt5.shutdown()
        if not mt5.initialize(path=str(terminal_path), timeout=120_000):
            raise RuntimeError(f"MT5 initialization failed: {mt5.last_error()}")
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None or terminal is None:
            raise RuntimeError("MT5 account or terminal information is unavailable")
        if getattr(account, "server", None) != EXPECTED_SERVER:
            raise RuntimeError(
                "active MT5 session is not the required FIBO demo server"
            )
        if getattr(account, "trade_mode", None) != getattr(
            mt5, "ACCOUNT_TRADE_MODE_DEMO"
        ):
            raise RuntimeError("non-demo MT5 account is blocked")
        if not getattr(terminal, "connected", False):
            raise RuntimeError("MT5 terminal is not connected")
        rows = []
        for symbol in SYMBOLS:
            if not mt5.symbol_select(symbol, True):
                raise RuntimeError(
                    f"FIBO symbol selection failed: {symbol}: {mt5.last_error()}"
                )
            info = mt5.symbol_info(symbol)
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 2)
            if info is None or rates is None or len(rates) < 2:
                raise RuntimeError(f"FIBO M15 preflight data unavailable: {symbol}")
            point = float(getattr(info, "point", 0.0) or 0.0)
            volume_min = float(getattr(info, "volume_min", 0.0) or 0.0)
            volume_step = float(getattr(info, "volume_step", 0.0) or 0.0)
            if point <= 0 or volume_min <= 0 or volume_step <= 0:
                raise RuntimeError(f"FIBO symbol contract metadata invalid: {symbol}")
            rows.append(
                {
                    "symbol": symbol,
                    "point": point,
                    "volume_min": volume_min,
                    "volume_step": volume_step,
                    "m15_bars_read": len(rates),
                }
            )
    finally:
        mt5.shutdown()
        mt5.order_check = original_order_check
        mt5.order_send = original_order_send
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_FORWARD_DEMO_PREFLIGHT_V1",
        "server": EXPECTED_SERVER,
        "account_is_demo": True,
        "terminal_connected": True,
        "symbols": rows,
        "forward_shadow_activation_eligible": False,
        "activation_blocker": "A separately published write-once activation manifest remains required",
        "safety": {
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
