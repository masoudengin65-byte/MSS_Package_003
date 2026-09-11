"""Freeze current FIBO cost inputs for research-only conservative scenarios."""

from __future__ import annotations

from datetime import UTC, datetime

EXPECTED_SERVER = "FIBOGroup-MT5 Server"
SYMBOLS = ("EURUSD", "XAUUSD", "BTC", "ETH")
FIELDS = (
    "point",
    "digits",
    "spread",
    "swap_long",
    "swap_short",
    "swap_mode",
    "swap_rollover3days",
    "trade_contract_size",
    "trade_tick_size",
    "trade_tick_value",
    "volume_min",
    "volume_step",
    "trade_mode",
    "currency_profit",
    "currency_margin",
)


def collect_snapshot(mt5, collected_at_utc: str | None = None) -> dict[str, object]:
    """Read current symbol metadata only; caller owns the MT5 lifecycle."""
    account = mt5.account_info()
    if account is None or account.server != EXPECTED_SERVER:
        raise ValueError("Active MT5 account is not the expected FIBO demo server")
    symbols = []
    for name in SYMBOLS:
        info = mt5.symbol_info(name)
        if info is None:
            raise ValueError(f"Required FIBO symbol is unavailable: {name}")
        symbols.append(
            {"symbol": name, **{field: getattr(info, field) for field in FIELDS}}
        )
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_CURRENT_COST_SNAPSHOT_V1",
        "source": {
            "provider": "FIBO Group",
            "mt5_server": account.server,
            "account_class": "demo",
        },
        "collected_at_utc": collected_at_utc or datetime.now(UTC).isoformat(),
        "symbols": symbols,
        "commission": {
            "status": "UNAVAILABLE_FROM_MT5_SYMBOL_INFO",
            "rule": "No commission value is inferred or substituted from a different account type or date",
        },
        "safety": {
            "read_only_mt5_calls": [
                "initialize",
                "account_info",
                "symbol_info",
                "shutdown",
            ],
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }


def build_protocol(snapshot: dict[str, object]) -> dict[str, object]:
    if snapshot["source"]["mt5_server"] != EXPECTED_SERVER:
        raise ValueError("Cost protocol requires a verified FIBO snapshot")
    scenarios = []
    for name, spread_multiplier, slippage_share, swap_multiplier in (
        ("BASELINE_CURRENT_REFERENCE", 1.0, 0.25, 1.0),
        ("CONSERVATIVE", 1.5, 0.50, 1.5),
        ("STRESSED", 2.0, 1.00, 2.0),
    ):
        inputs = []
        for symbol in snapshot["symbols"]:
            spread_points = float(symbol["spread"])
            inputs.append(
                {
                    "symbol": symbol["symbol"],
                    "spread_points": spread_points * spread_multiplier,
                    "slippage_points_per_side": max(
                        1.0, spread_points * slippage_share
                    ),
                    "swap_long_current_reference": float(symbol["swap_long"])
                    * swap_multiplier,
                    "swap_short_current_reference": float(symbol["swap_short"])
                    * swap_multiplier,
                    "swap_mode": symbol["swap_mode"],
                    "commission_per_lot": None,
                }
            )
        scenarios.append({"name": name, "inputs": inputs})
    return {
        "schema_version": "MSS_SPRINT93_3F_FIBO_GROUP_COST_SCENARIO_PROTOCOL_V1",
        "purpose": "Freeze current-reference cost scenarios for a future rejection-only research screen",
        "source_snapshot": snapshot,
        "scenarios": scenarios,
        "research_boundary": {
            "current_snapshot_is_historical_fact": False,
            "historical_net_profit_replay_eligible": False,
            "allowed_conclusion": "A candidate may be rejected as fragile under declared hypothetical costs",
            "forbidden_conclusions": [
                "broker-accurate historical net profit",
                "execution quality",
                "production readiness",
            ],
        },
        "release_blocker": "Commission remains unavailable; no net-profit result may be calculated or reported",
        "safety": {
            "raw_data_modified": False,
            "strategy_or_replay_run": False,
            "order_check_called": False,
            "order_send_called": False,
            "real_order_send_allowed": False,
            "production_execution_enabled": False,
        },
    }
