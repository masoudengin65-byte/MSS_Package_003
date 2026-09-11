import json
from pathlib import Path

from mss.analysis.fibo_group_rejection_only_fragility_screen import screen_observations

ROOT = Path(__file__).resolve().parents[1]
INPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Signal_Observation_Stream_V1.json"
)
OUTPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Development_Rejection_Screen_V1.json"
)


if __name__ == "__main__":
    source = json.loads(INPUT.read_text(encoding="utf-8"))
    result = screen_observations(ROOT, source["observations"])
    result["input_scope"] = source["data_scope"]
    result["input_observation_stream_schema_version"] = source["schema_version"]
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_DEVELOPMENT_REJECTION_SCREEN_CREATED")
    print("OBSERVATION_COUNT", result["summary"]["observation_count"])
    print("REJECTED_COUNT", result["summary"]["rejected_count"])
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
