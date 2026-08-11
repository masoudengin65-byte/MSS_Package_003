"""Build Sprint 92B.2 from the frozen v2 replay artifact only."""

import json
from pathlib import Path

from mss.analysis.bootstrap_robustness_audit import BootstrapRobustnessAudit


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "reports" / "MSS_Multi_Asset_Historical_Replay_v2.json"
TEMPORAL = ROOT / "reports" / "MSS_Sprint92B1_Temporal_Stability_Audit.json"
OUTPUT = ROOT / "reports" / "MSS_Sprint92B2_Cross_Asset_Robustness_Bootstrap.json"


def canonical_json(payload):
    return json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"


def main():
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    temporal = json.loads(TEMPORAL.read_text(encoding="utf-8"))
    audit = BootstrapRobustnessAudit()
    first = audit.build(source, temporal)
    second = audit.build(source, temporal)
    first["validation"]["deterministic_rebuild"] = canonical_json(first) == canonical_json(second)
    if not first["validation"]["closed_trade_count_matches"]:
        raise RuntimeError("Frozen closed-trade count did not reconcile to 821")
    if not first["validation"]["all_per_symbol_reconciled"]:
        raise RuntimeError("Per-symbol frozen trade reconciliation failed")
    if not first["validation"]["deterministic_rebuild"]:
        raise RuntimeError("Bootstrap artifact rebuild was not deterministic")
    OUTPUT.write_text(canonical_json(first), encoding="utf-8")
    print(f"WROTE={OUTPUT}")
    print(f"CLOSED_TRADES={first['source']['frozen_closed_trade_count']}")
    print(f"SEED={first['methodology']['random_seed']}")
    print(f"RESAMPLES={first['methodology']['resample_count']}")
    print(f"CLASSIFICATIONS={first['final_classifications']}")


if __name__ == "__main__":
    main()
