import json
from pathlib import Path

from mss.analysis.fibo_group_forward_shadow_preregistration import (
    FiboGroupForwardShadowPreregistration,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint93_3F_FIBO_Group_Forward_Shadow_Preregistration_V1.json"
)


if __name__ == "__main__":
    result = FiboGroupForwardShadowPreregistration.build(ROOT)
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_FORWARD_SHADOW_PREREGISTRATION_CREATED")
    print("PROTOCOL_STATE", result["protocol_state"])
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
