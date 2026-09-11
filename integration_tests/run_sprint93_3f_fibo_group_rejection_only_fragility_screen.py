import json
from pathlib import Path

from mss.analysis.fibo_group_rejection_only_fragility_screen import screen_observations

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint93_3F_FIBO_Group_Rejection_Only_Fragility_Screen_V1.json"
)


if __name__ == "__main__":
    result = screen_observations(ROOT, observations=())
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_REJECTION_ONLY_FRAGILITY_SCREEN_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
