"""Build the Sprint 92A audit from saved artifacts; never runs a replay."""

from __future__ import annotations

import json
from pathlib import Path

from mss.analysis.replay_integrity_audit import ReplayIntegrityAudit


ROOT = Path(__file__).resolve().parents[1]
REPLAY_PATH = ROOT / "reports/MSS_Multi_Asset_Historical_Replay_v1.json"
METADATA_PATH = ROOT / "reports/MSS_Multi_Asset_Data_Validation.json"
OUTPUT_PATH = ROOT / "reports/MSS_Sprint92A_Replay_Integrity_Audit.json"


def main():
    replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))
    metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    result = ReplayIntegrityAudit().audit(replay, metadata)
    OUTPUT_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"Wrote {OUTPUT_PATH}")
    print(f"status={result['overall_audit_status']}")
    print(f"code_defect_found={result['code_defect_found']}")


if __name__ == "__main__":
    main()
