import json
from pathlib import Path

from mss.analysis.fibo_group_signal_observation_stream import (
    load_verified_fibo_development_data,
    observe_histories,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "reports" / "MSS_Sprint93_3F_FIBO_Group_Signal_Observation_Stream_V1.json"
)


if __name__ == "__main__":
    histories, source_hashes = load_verified_fibo_development_data(ROOT)
    result = observe_histories(histories, source_hashes)
    OUTPUT.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print("FIBO_SIGNAL_OBSERVATION_STREAM_CREATED")
    print("OBSERVATION_COUNT", result["summary"]["observation_count"])
    print("ORDER_SEND_CALLED", result["safety"]["order_send_called"])
