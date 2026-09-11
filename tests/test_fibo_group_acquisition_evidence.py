import json
from pathlib import Path

from mss.analysis.fibo_group_acquisition_evidence import build_evidence


def write_rates(path: Path, epochs: list[int]) -> None:
    path.write_text("".join(json.dumps({"time": epoch, "open": 1, "high": 2, "low": 0, "close": 1}) + "\n" for epoch in epochs), encoding="utf-8")


def test_evidence_inventory_is_deterministic_and_non_performance(tmp_path):
    root = Path(__file__).resolve().parents[1]
    evidence = tmp_path / "candidate"
    evidence.mkdir()
    for symbol in ("EURUSD", "XAUUSD", "BTC", "ETH"):
        write_rates(evidence / f"{symbol}_M15.jsonl", [900, 1800])
    result = build_evidence(root, evidence)
    assert result == build_evidence(root, evidence)
    assert [item["fibo_group_symbol"] for item in result["symbols"]] == ["EURUSD", "XAUUSD", "BTC", "ETH"]
    assert result["safety"]["comparison_run"] is False
    assert result["safety"]["order_send_called"] is False
