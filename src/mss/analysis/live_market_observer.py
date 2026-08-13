"""Read-only live MT5 market observer for MSS Shadow Live."""

from __future__ import annotations

import time
from typing import Any

import MetaTrader5 as mt5

from mss.analysis.global_time_authority import (
    GlobalTimeAuthority,
)


class LiveMarketObserver:
    """
    Sprint 92H.14.1

    Strictly read-only MT5 observation layer.

    This component must never:
    - send an order
    - modify an order
    - modify a position
    - close a position
    """

    VERSION = (
        "MSS_SPRINT92H14_1_LIVE_MARKET_OBSERVER_V1"
    )

    TIMEFRAME = mt5.TIMEFRAME_M15
    TIMEFRAME_SECONDS = 900

    # Same mature synchronization policy validated in H13.
    SYNC_TIMEOUT_SECONDS = 15.0
    SYNC_POLL_SECONDS = 0.25

    READ_ONLY_API = (
        "initialize",
        "terminal_info",
        "account_info",
        "symbol_info",
        "symbol_info_tick",
        "copy_rates_from_pos",
        "positions_get",
        "orders_get",
        "last_error",
        "shutdown",
    )

    PROHIBITED_API = (
        "order_send",
        "order_check",
    )

    @staticmethod
    def _get(
        obj: Any,
        name: str,
        default=None,
    ):
        if obj is None:
            return default

        return getattr(
            obj,
            name,
            default,
        )

    @staticmethod
    def _safe_account_metadata(
        account,
    ) -> dict[str, Any]:
        """
        Deliberately excludes login/account number.
        """

        return {
            "server": LiveMarketObserver._get(
                account,
                "server",
            ),
            "currency": LiveMarketObserver._get(
                account,
                "currency",
            ),
            "company": LiveMarketObserver._get(
                account,
                "company",
            ),
            "trade_allowed": bool(
                LiveMarketObserver._get(
                    account,
                    "trade_allowed",
                    False,
                )
            ),
            "trade_expert": bool(
                LiveMarketObserver._get(
                    account,
                    "trade_expert",
                    False,
                )
            ),
        }

    @staticmethod
    def _symbol_metadata(
        info,
    ) -> dict[str, Any]:
        return {
            "name": LiveMarketObserver._get(
                info,
                "name",
            ),
            "description": LiveMarketObserver._get(
                info,
                "description",
            ),
            "visible": bool(
                LiveMarketObserver._get(
                    info,
                    "visible",
                    False,
                )
            ),
            "digits": LiveMarketObserver._get(
                info,
                "digits",
            ),
            "point": LiveMarketObserver._get(
                info,
                "point",
            ),
            "spread_points_reported": (
                LiveMarketObserver._get(
                    info,
                    "spread",
                )
            ),
            "trade_mode": LiveMarketObserver._get(
                info,
                "trade_mode",
            ),
            "trade_contract_size": (
                LiveMarketObserver._get(
                    info,
                    "trade_contract_size",
                )
            ),
            "volume_min": LiveMarketObserver._get(
                info,
                "volume_min",
            ),
            "volume_max": LiveMarketObserver._get(
                info,
                "volume_max",
            ),
            "volume_step": LiveMarketObserver._get(
                info,
                "volume_step",
            ),
            "volume_limit": LiveMarketObserver._get(
                info,
                "volume_limit",
            ),
            "trade_stops_level": (
                LiveMarketObserver._get(
                    info,
                    "trade_stops_level",
                )
            ),
            "trade_freeze_level": (
                LiveMarketObserver._get(
                    info,
                    "trade_freeze_level",
                )
            ),
        }

    @staticmethod
    def _tick_payload(
        tick,
        point,
    ) -> dict[str, Any]:
        bid = float(
            LiveMarketObserver._get(
                tick,
                "bid",
                0.0,
            )
        )

        ask = float(
            LiveMarketObserver._get(
                tick,
                "ask",
                0.0,
            )
        )

        spread_price = ask - bid

        spread_points = None

        if point not in (
            None,
            0,
            0.0,
        ):
            spread_points = (
                spread_price
                / float(point)
            )

        return {
            "time": int(
                LiveMarketObserver._get(
                    tick,
                    "time",
                    0,
                )
            ),
            "time_msc": LiveMarketObserver._get(
                tick,
                "time_msc",
            ),
            "bid": bid,
            "ask": ask,
            "last": LiveMarketObserver._get(
                tick,
                "last",
            ),
            "volume": LiveMarketObserver._get(
                tick,
                "volume",
            ),
            "spread_price": spread_price,
            "spread_points_observed": (
                spread_points
            ),
        }

    @classmethod
    def observe(
        cls,
        *,
        symbol: str,
        previous_broker_offset_seconds=None,
    ) -> dict[str, Any]:

        if not symbol:
            raise ValueError(
                "symbol is required"
            )

        initialized = False

        try:
            initialized = bool(
                mt5.initialize()
            )

            if not initialized:
                raise RuntimeError(
                    "MT5_INITIALIZE_FAILED: "
                    f"{mt5.last_error()}"
                )

            terminal = mt5.terminal_info()
            account = mt5.account_info()

            if terminal is None:
                raise RuntimeError(
                    "MT5_TERMINAL_INFO_UNAVAILABLE"
                )

            if account is None:
                raise RuntimeError(
                    "MT5_ACCOUNT_INFO_UNAVAILABLE"
                )

            info = mt5.symbol_info(
                symbol
            )

            if info is None:
                raise RuntimeError(
                    f"MT5_SYMBOL_INFO_UNAVAILABLE: {symbol}"
                )

            if not bool(
                cls._get(
                    info,
                    "visible",
                    False,
                )
            ):
                selected = mt5.symbol_select(
                    symbol,
                    True,
                )

                if not selected:
                    raise RuntimeError(
                        "MT5_SYMBOL_SELECT_FAILED: "
                        f"{symbol}"
                    )

                info = mt5.symbol_info(
                    symbol
                )

                if info is None:
                    raise RuntimeError(
                        "MT5_SYMBOL_INFO_UNAVAILABLE_AFTER_SELECT"
                    )

            sync_started = time.monotonic()
            sync_attempts = 0
            first_sync_observation = None
            final_sync_observation = None

            while True:
                sync_attempts += 1

                utc_before = time.time()

                tick = mt5.symbol_info_tick(
                    symbol
                )

                rates = mt5.copy_rates_from_pos(
                    symbol,
                    cls.TIMEFRAME,
                    0,
                    3,
                )

                utc_after = time.time()

                if tick is None:
                    raise RuntimeError(
                        "MT5_TICK_UNAVAILABLE"
                    )

                if rates is None or len(rates) < 1:
                    raise RuntimeError(
                        "MT5_M15_BAR_UNAVAILABLE"
                    )

                tick_epoch = int(
                    tick.time
                )

                expected_bar_epoch = (
                    tick_epoch
                    // cls.TIMEFRAME_SECONDS
                ) * cls.TIMEFRAME_SECONDS

                returned_epochs = [
                    int(row["time"])
                    for row in rates
                ]

                current_bar_epoch = max(
                    returned_epochs
                )

                sync_observation = {
                    "attempt": sync_attempts,
                    "tick_epoch": tick_epoch,
                    "expected_current_bar_epoch": (
                        expected_bar_epoch
                    ),
                    "returned_bar_epochs": (
                        returned_epochs
                    ),
                    "selected_current_bar_epoch": (
                        current_bar_epoch
                    ),
                    "bar_lag_seconds": (
                        expected_bar_epoch
                        - current_bar_epoch
                    ),
                }

                if first_sync_observation is None:
                    first_sync_observation = dict(
                        sync_observation
                    )

                final_sync_observation = dict(
                    sync_observation
                )

                synchronized = (
                    current_bar_epoch
                    == expected_bar_epoch
                )

                sync_elapsed = (
                    time.monotonic()
                    - sync_started
                )

                if synchronized:
                    sync_status = (
                        "MT5_BAR_SYNCHRONIZED"
                    )
                    break

                if (
                    sync_elapsed
                    >= cls.SYNC_TIMEOUT_SECONDS
                ):
                    sync_status = (
                        "MT5_BAR_SYNC_TIMEOUT"
                    )
                    break

                time.sleep(
                    cls.SYNC_POLL_SECONDS
                )

            current_bar = max(
                rates,
                key=lambda row: int(
                    row["time"]
                ),
            )

            authority = (
                GlobalTimeAuthority().build(
                    utc_epoch_before_tick=(
                        utc_before
                    ),
                    utc_epoch_after_tick=(
                        utc_after
                    ),
                    tick_epoch=tick_epoch,
                    current_bar_epoch=(
                        current_bar_epoch
                    ),
                    previous_broker_offset_seconds=(
                        previous_broker_offset_seconds
                    ),
                )
            )

            if (
                sync_status
                != "MT5_BAR_SYNCHRONIZED"
            ):
                authority[
                    "time_authority"
                ]["status"] = (
                    "BROKER_BAR_SYNCHRONIZATION_UNRESOLVED"
                )

                authority[
                    "time_authority"
                ]["confirmed"] = False

                authority[
                    "fail_safe"
                ][
                    "trading_allowed_by_time_authority"
                ] = False

            symbol_metadata = (
                cls._symbol_metadata(
                    info
                )
            )

            tick_payload = (
                cls._tick_payload(
                    tick,
                    symbol_metadata["point"],
                )
            )

            positions = (
                mt5.positions_get(
                    symbol=symbol
                )
                or ()
            )

            pending_orders = (
                mt5.orders_get(
                    symbol=symbol
                )
                or ()
            )

            time_confirmed = bool(
                authority[
                    "time_authority"
                ][
                    "confirmed"
                ]
            )

            market_data_valid = (
                tick_payload["bid"] > 0
                and tick_payload["ask"] > 0
                and tick_payload["ask"]
                >= tick_payload["bid"]
                and current_bar_epoch > 0
            )

            observation_allowed = (
                time_confirmed
                and market_data_valid
                and sync_status
                == "MT5_BAR_SYNCHRONIZED"
            )

            return {
                "schema_version": (
                    cls.VERSION
                ),

                "mode": (
                    "SHADOW_LIVE_READ_ONLY"
                ),

                "symbol": symbol,

                "terminal": {
                    "company": cls._get(
                        terminal,
                        "company",
                    ),
                    "name": cls._get(
                        terminal,
                        "name",
                    ),
                    "connected": bool(
                        cls._get(
                            terminal,
                            "connected",
                            True,
                        )
                    ),
                    "trade_allowed_terminal": bool(
                        cls._get(
                            terminal,
                            "trade_allowed",
                            False,
                        )
                    ),
                },

                "account": (
                    cls._safe_account_metadata(
                        account
                    )
                ),

                "symbol_info": (
                    symbol_metadata
                ),

                "tick": tick_payload,

                "current_m15_bar": {
                    "time": (
                        current_bar_epoch
                    ),
                    "open": float(
                        current_bar["open"]
                    ),
                    "high": float(
                        current_bar["high"]
                    ),
                    "low": float(
                        current_bar["low"]
                    ),
                    "close": float(
                        current_bar["close"]
                    ),
                    "tick_volume": int(
                        current_bar[
                            "tick_volume"
                        ]
                    ),
                    "spread": int(
                        current_bar[
                            "spread"
                        ]
                    ),
                    "real_volume": int(
                        current_bar[
                            "real_volume"
                        ]
                    ),
                },

                "exposure_observation": {
                    "open_position_count": (
                        len(positions)
                    ),
                    "pending_order_count": (
                        len(pending_orders)
                    ),
                },

                "time_synchronization": {
                    "status": sync_status,
                    "attempts": sync_attempts,
                    "elapsed_seconds": (
                        sync_elapsed
                    ),
                    "timeout_seconds": (
                        cls.SYNC_TIMEOUT_SECONDS
                    ),
                    "poll_seconds": (
                        cls.SYNC_POLL_SECONDS
                    ),
                    "first_observation": (
                        first_sync_observation
                    ),
                    "final_observation": (
                        final_sync_observation
                    ),
                },

                "time_authority": (
                    authority
                ),

                "safety": {
                    "market_data_valid": (
                        market_data_valid
                    ),
                    "time_authority_confirmed": (
                        time_confirmed
                    ),
                    "shadow_observation_allowed": (
                        observation_allowed
                    ),

                    "real_order_send_allowed": False,
                    "virtual_order_send_allowed": False,

                    "order_send_called": False,
                    "order_check_called": False,

                    "position_modification_allowed": False,
                    "pending_order_modification_allowed": False,

                    "read_only_mode": True,
                },

                "audit": {
                    "strategy_signal_generated": False,
                    "virtual_trade_generated": False,
                    "real_trade_generated": False,
                    "order_send_called": False,
                    "order_check_called": False,
                    "orders_sent": False,
                    "positions_modified": False,
                    "true_oos_data_accessed": False,
                    "true_oos_artifacts_modified": False,
                },
            }

        finally:
            if initialized:
                mt5.shutdown()
