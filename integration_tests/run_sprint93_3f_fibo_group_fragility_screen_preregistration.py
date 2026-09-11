import json
from pathlib import Path

from mss.analysis.fibo_group_fragility_screen_preregistration import (
    build_preregistration,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint93_3F_FIBO_Group_Fragility_Screen_Preregistration_V1.json"
)

if __name__ == "__main__":
    result = build_preregistration(ROOT)
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_FRAGILITY_SCREEN_PREREGISTRATION_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
