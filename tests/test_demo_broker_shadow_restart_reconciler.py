from dataclasses import replace

import pytest

from mss.analysis.demo_broker_shadow_restart_reconciler import (
    DemoBrokerPositionSnapshot,
    DemoBrokerShadowRestartReconciler,
)
from mss.analysis.virtual_position_engine import VirtualPositionEngine


@pytest.fixture
def broker():
    return DemoBrokerPositionSnapshot(
        ticket=11, identifier=12, magic=920146, symbol="EURGBP",
        direction="SELL", volume=0.01, entry_price=0.85698,
        stop_loss=0.85760, take_profit=0.85553,
        open_broker_epoch=1787240705, point=0.00001, volume_step=0.01,
    )


@pytest.fixture
def shadow():
    return VirtualPositionEngine.open_position(
        position_id="p1", symbol="EURGBP", direction="SELL", volume=0.01,
        entry_price=0.85698, stop_loss=0.85760, take_profit=0.85553,
        broker_epoch=1787240705,
    )


def reconcile(broker, shadow, pending=0):
    return DemoBrokerShadowRestartReconciler.reconcile(
        broker_positions=broker if isinstance(broker, tuple) else (broker,),
        pending_order_count=pending,
        shadow_positions=shadow if isinstance(shadow, tuple) else (shadow,),
    )


def test_exact_match_resumes_without_send(broker, shadow):
    result = reconcile(broker, shadow)
    assert result.valid and result.resume_allowed
    assert result.reason == "BROKER_SHADOW_RESTART_MATCH_CONFIRMED"
    assert result.real_order_send_allowed is False


@pytest.mark.parametrize(("field", "value", "reason"), [
    ("magic", 1, "BROKER_MAGIC_MISMATCH"),
    ("symbol", "GBPUSD", "BROKER_SHADOW_SYMBOL_MISMATCH"),
    ("direction", "BUY", "BROKER_SHADOW_DIRECTION_MISMATCH"),
    ("volume", 0.02, "BROKER_SHADOW_VOLUME_MISMATCH"),
    ("entry_price", 0.85710, "BROKER_SHADOW_ENTRY_MISMATCH"),
    ("stop_loss", 0.85780, "BROKER_SHADOW_SL_MISMATCH"),
    ("take_profit", 0.85530, "BROKER_SHADOW_TP_MISMATCH"),
    ("open_broker_epoch", 1787240700, "BROKER_SHADOW_OPEN_EPOCH_MISMATCH"),
    ("ticket", 0, "INVALID_BROKER_POSITION_METADATA"),
])
def test_broker_mismatch_blocks(broker, shadow, field, value, reason):
    result = reconcile(replace(broker, **{field: value}), shadow)
    assert not result.resume_allowed
    assert result.reason == reason
    assert result.real_order_send_allowed is False


def test_missing_or_invalid_shadow_blocks(broker, shadow):
    missing = reconcile(broker, ())
    invalid = reconcile(broker, replace(shadow, status="CLOSED"))
    assert missing.reason == "BROKER_OPEN_POSITION_WITHOUT_SHADOW_EXPOSURE"
    assert invalid.reason == "INVALID_OPEN_SHADOW_POSITION"


def test_point_level_normalization_is_accepted(broker, shadow):
    normalized = replace(
        broker, entry_price=shadow.entry_price + broker.point,
        stop_loss=shadow.stop_loss - broker.point,
        take_profit=shadow.take_profit + broker.point,
        volume=shadow.volume + broker.volume_step / 2.0,
    )
    assert reconcile(normalized, shadow).resume_allowed


def test_historical_pre_authoritative_position_remains_blocked(broker, shadow):
    historical_shadow = replace(
        shadow,
        entry_price=0.8569100000000001,
        open_broker_epoch=1787240700,
    )
    result = reconcile(broker, historical_shadow)
    assert not result.resume_allowed
    assert result.reason == "BROKER_SHADOW_ENTRY_MISMATCH"


def test_ambiguous_counts_and_pending_orders_block(broker, shadow):
    assert reconcile((broker, broker), shadow).reason == "MULTIPLE_MSS_BROKER_POSITIONS"
    assert reconcile(broker, (shadow, shadow)).reason == "MULTIPLE_OPEN_SHADOW_POSITIONS"
    assert reconcile(broker, shadow, pending=1).reason == "MSS_PENDING_ORDER_PRESENT"
    assert reconcile((), shadow).reason == "SHADOW_OPEN_POSITION_WITHOUT_BROKER_EXPOSURE"


def test_no_exposure_is_valid_without_resume_send(broker, shadow):
    result = reconcile((), ())
    assert result.valid and not result.resume_allowed
    assert result.real_order_send_allowed is False
