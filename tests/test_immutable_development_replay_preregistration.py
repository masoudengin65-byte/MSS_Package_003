import hashlib
import json
from pathlib import Path

from mss.analysis.immutable_development_replay_preregistration import (
    ImmutableDevelopmentReplayPreregistration,
)


ROOT = Path(__file__).resolve().parents[1]

H1 = ROOT / "reports/MSS_Sprint92H1_Immutable_Research_Data_Preregistration.json"
H2 = ROOT / "reports/MSS_Sprint92H2_Immutable_Research_Data_Manifest.json"
V2 = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v2.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    h1 = json.loads(H1.read_text(encoding="utf-8"))
    h2 = json.loads(H2.read_text(encoding="utf-8"))
    v2 = json.loads(V2.read_text(encoding="utf-8"))

    builder = ImmutableDevelopmentReplayPreregistration()

    return builder.build(
        h1,
        h2,
        v2,
        h1_file_sha256=sha(H1),
        h2_file_sha256=sha(H2),
        v2_file_sha256=sha(V2),
    )


def test_h3_preregistration_is_deterministic():
    assert build() == build()


def test_h3_scope_is_development_only_and_exact():
    result = build()

    assert result["dataset_contract"]["symbol_count"] == 8
    assert result["dataset_contract"]["candles_per_symbol"] == 30000
    assert result["dataset_contract"]["total_candles"] == 240000

    assert result["execution_policy"]["validation_access_prohibited"] is True
    assert result["execution_policy"]["external_history_access_prohibited"] is True
    assert result["execution_policy"]["true_future_oos_access_prohibited"] is True
    assert result["execution_policy"]["fresh_mt5_history_access_prohibited"] is True


def test_h3_freezes_metadata_and_forbids_live_fallback():
    result = build()

    metadata = result["broker_metadata_contract"]["symbols"]

    assert len(metadata) == 8
    assert {x["canonical_symbol"] for x in metadata} == {
        "EURUSD",
        "GBPUSD",
        "USDJPY",
        "AUDUSD",
        "USDCAD",
        "XAUUSD",
        "BTCUSD",
        "ETHUSD",
    }

    assert result["broker_metadata_contract"]["metadata_is_frozen"] is True
    assert result["broker_metadata_contract"]["current_mt5_symbol_info_access_prohibited"] is True
    assert result["source_verification_contract"]["mt5_fallback_prohibited"] is True

    assert result["audit"]["strategy_replay_run"] is False
    assert result["audit"]["outcomes_analyzed"] is False
    assert result["audit"]["mt5_accessed"] is False
