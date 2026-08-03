from pathlib import Path

from mss.data.csv_replay_reader import CSVReplayReader


def test_load_csv(tmp_path: Path):

    csv_file = tmp_path / "sample.csv"

    csv_file.write_text(
        "\n".join(
            [
                "time,open,high,low,close,tick_volume,spread,real_volume",
                "2026-01-01T00:00:00,100,105,99,104,1000,10,1000",
                "2026-01-01T00:01:00,104,106,103,105,1200,10,1200",
            ]
        ),
        encoding="utf-8",
    )

    candles = CSVReplayReader().load(

        str(csv_file),

    )

    assert len(candles) == 2

    assert candles[0].open == 100.0

    assert candles[0].high == 105.0

    assert candles[0].low == 99.0

    assert candles[0].close == 104.0

    assert candles[1].close == 105.0


def test_empty_csv(tmp_path: Path):

    csv_file = tmp_path / "empty.csv"

    csv_file.write_text(

        "time,open,high,low,close,tick_volume,spread,real_volume\n",

        encoding="utf-8",

    )

    candles = CSVReplayReader().load(

        str(csv_file),

    )

    assert candles == []
    