import json
from pathlib import Path

from mss.analysis.fibo_group_price_pattern_comparison import (
    BAR_SECONDS,
    MAPPINGS,
    _quantiles,
    build_comparison,
)


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _rate(timestamp: int, price: float, eligible: bool = True) -> dict[str, object]:
    return {
        "time": timestamp,
        "open": price,
        "high": price * 1.1,
        "low": price * 0.9,
        "close": price,
        "performance_eligible": eligible,
    }


def test_quantiles_are_deterministic():
    assert _quantiles([3, 1, 2]) == {"0.05": 1, "0.5": 2, "0.95": 3}
    assert _quantiles([]) is None


def test_comparison_uses_exact_timestamps_and_never_reports_performance(tmp_path):
    root = Path(__file__).resolve().parents[1]
    frozen, fibo = tmp_path / "frozen", tmp_path / "fibo"
    frozen.mkdir()
    fibo.mkdir()
    epochs = [900, 900 + BAR_SECONDS, 900 + (3 * BAR_SECONDS)]
    for frozen_symbol, fibo_symbol in MAPPINGS:
        _write(
            frozen / f"{frozen_symbol}_M15.jsonl",
            [_rate(epoch, 100 + index) for index, epoch in enumerate(epochs)]
            + [_rate(999999, 1, False)],
        )
        _write(
            fibo / f"{fibo_symbol}_M15.jsonl",
            [_rate(epoch, 200 + index) for index, epoch in enumerate(epochs)]
            + [_rate(777777, 1)],
        )
    result = build_comparison(root, frozen, fibo)
    first = result["symbols"][0]
    assert first["matched_timestamp_count"] == 3
    assert first["unmatched_frozen_timestamp_count"] == 0
    assert first["unmatched_fibo_timestamp_count"] == 1
    assert first["return_comparison_timestamp_count"] == 1
    assert first["shared_gap_boundary_count"] == 1
    assert result["safety"]["strategy_or_replay_run"] is False
    assert result["safety"]["order_send_called"] is False
