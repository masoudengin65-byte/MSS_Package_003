import json
from pathlib import Path

from mss.analysis.fibo_group_signal_observation_publication_summary import build_summary

ROOT = Path(__file__).resolve().parents[1]
OBSERVATIONS = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Signal_Observation_Stream_V1.json"
)
SCREEN = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Development_Rejection_Screen_V1.json"
)
OUTPUT = (
    ROOT
    / "reports"
    / "MSS_Sprint93_3F_FIBO_Group_Signal_Screen_Publication_Summary_V1.json"
)


if __name__ == "__main__":
    result = build_summary(
        json.loads(OBSERVATIONS.read_text(encoding="utf-8")),
        json.loads(SCREEN.read_text(encoding="utf-8")),
    )
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_SIGNAL_SCREEN_PUBLICATION_SUMMARY_CREATED")
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
