from pathlib import Path

import pytest

from mss.analysis.fibo_group_paired_forward_runtime import (
    FiboBoundarySnapshot,
    FiboGroupPairedForwardRuntime,
    FiboVerifiedActivation,
    _FIBO_VERIFIED_ACTIVATION_MARKER,
)
from mss.analysis.shadow_trade_journal import ShadowTradeJournal


def _rates():
    return [
        {
            "time": index * 900,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.0,
            "tick_volume": 1,
            "spread": 1,
            "real_volume": 0,
        }
        for index in range(1, 502)
    ]


def _snapshots():
    rates = _rates()
    return tuple(
        FiboBoundarySnapshot(
            canonical_symbol=canonical,
            broker_symbol=broker,
            account_server="FIBOGroup-MT5 Server",
            current_bar_epoch=501 * 900,
            rates=rates,
        )
        for canonical, broker in (("BTCUSD", "BTC"), ("ETHUSD", "ETH"))
    )


def _activation():
    return FiboVerifiedActivation(
        manifest_sha256="a" * 64,
        first_eligible_epoch=500 * 900,
        exclusive_end_epoch=600 * 900,
        _verification_marker=_FIBO_VERIFIED_ACTIVATION_MARKER,
    )


def test_runtime_evaluates_same_boundary_without_order_capability():
    result = FiboGroupPairedForwardRuntime().evaluate_pair(_snapshots())
    assert result["boundary_epoch"] == 501 * 900
    assert tuple(result["branches"]) == ("BTCUSD", "ETHUSD")
    assert result["safety"]["order_send_called"] is False


def test_commit_is_hash_chained_and_duplicate_boundary_fails(tmp_path: Path):
    runtime = FiboGroupPairedForwardRuntime()
    evaluated = runtime.evaluate_pair(_snapshots())
    journal = tmp_path / "fibo.jsonl"
    runtime.commit_pair(
        activation=_activation(), journal_path=journal, evaluated=evaluated
    )
    assert ShadowTradeJournal.verify(journal)["valid"] is True
    with pytest.raises(RuntimeError, match="duplicate"):
        runtime.commit_pair(
            activation=_activation(), journal_path=journal, evaluated=evaluated
        )


def test_commit_rejects_unverified_activation(tmp_path: Path):
    runtime = FiboGroupPairedForwardRuntime()
    evaluated = runtime.evaluate_pair(_snapshots())
    unverified = FiboVerifiedActivation("a" * 64, 500 * 900, 600 * 900, object())
    with pytest.raises(RuntimeError, match="verified"):
        runtime.commit_pair(
            activation=unverified,
            journal_path=tmp_path / "fibo.jsonl",
            evaluated=evaluated,
        )
