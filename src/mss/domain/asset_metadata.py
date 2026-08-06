"""Immutable diagnostic metadata for a research-universe instrument."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AssetDefinition:
    """Canonical identity of an instrument in the Sprint 89 research universe."""

    canonical_symbol: str
    asset_class: str
    base_asset: str
    quote_asset: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class AssetMetadata:
    """Immutable broker metadata captured without affecting trading behavior."""

    canonical_symbol: str
    asset_class: str
    base_asset: str
    quote_asset: str
    broker_symbol: str
    resolved_symbol: str
    resolution_status: str
    description: object
    broker_path: object
    digits: object
    point: object
    spread_points: object
    spread_price: object
    trade_mode: object
    trade_mode_name: object
    trade_allowed: object
    visible: object
    selected: object
    volume_min: object
    volume_max: object
    volume_step: object
    volume_limit: object
    trade_contract_size: object
    trade_tick_size: object
    trade_tick_value: object
    trade_stops_level: object
    trade_freeze_level: object
    filling_mode: object
    order_mode: object
    swap_mode: object
    swap_long: object
    swap_short: object
    currency_base: object
    currency_profit: object
    currency_margin: object

    def to_dict(self) -> dict:
        return asdict(self)
