import json
from pathlib import Path

from mss.analysis.immutable_development_replay import ImmutableDevelopmentReplay


ROOT = Path(__file__).resolve().parents[1]

PROTOCOL = ROOT / "reports/MSS_Sprint92H3_Immutable_Development_Replay_Preregistration.json"


def protocol():
    return json.loads(PROTOCOL.read_text(encoding="utf-8"))


def test_h4_all_immutable_sources_verify_without_mt5():
    engine = ImmutableDevelopmentReplay()

    histories, verification = engine.load_verified_sources(
        ROOT,
        protocol(),
    )

    assert len(histories) == 8
    assert len(verification) == 8
    assert sum(len(x) for x in histories.values()) == 240000

    for row in verification:
        assert row["file_sha256_match"] is True
        assert row["row_count_match"] is True
        assert row["first_epoch_match"] is True
        assert row["last_epoch_match"] is True
        assert row["ohlcv_sha256_match"] is True
        assert row["strictly_chronological"] is True


def test_h4_frozen_metadata_complete():
    engine = ImmutableDevelopmentReplay()
    metadata = engine.frozen_metadata(protocol())

    assert set(metadata) == set(engine.replay.SYMBOLS)

    for symbol, row in metadata.items():
        assert row.account_currency
        assert row.currency_profit
        assert row.contract_size > 0
        assert row.volume_min > 0
        assert row.volume_max >= row.volume_min
        assert row.volume_step > 0


def test_h4_configuration_matches_preregistration():
    engine = ImmutableDevelopmentReplay()
    cfg = engine.config()
    p = protocol()["strategy_contract"]

    assert cfg.warmup_candles == p["warmup_candles"]
    assert cfg.analysis_lookback == p["analysis_lookback"]
    assert cfg.starting_balance == p["starting_balance"]
    assert cfg.risk_percent == p["risk_percent"]
    assert cfg.reward_risk_ratio == p["reward_risk_ratio"]
    assert cfg.commission_per_lot == p["commission_per_lot"]
    assert cfg.slippage_points == p["slippage_points"]
    assert cfg.ambiguous_policy == p["ambiguous_policy"]
