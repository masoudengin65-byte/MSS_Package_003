"""
MSS CSV Replay Reader
Version : 1.0
Sprint : 16.0
Compatible : v0.27
"""

import csv
from datetime import datetime

from mss.domain.replay_candle import ReplayCandle


class CSVReplayReader:

    def load(
        self,
        filename: str,
    ) -> list[ReplayCandle]:

        candles = []

        with open(
            filename,
            "r",
            newline="",
            encoding="utf-8-sig",
        ) as file:

            reader = csv.DictReader(file)

            for row in reader:

                candle = ReplayCandle(

                    time=datetime.fromisoformat(
                        row["time"]
                    ),

                    open=float(row["open"]),

                    high=float(row["high"]),

                    low=float(row["low"]),

                    close=float(row["close"]),

                    tick_volume=int(
                        row.get(
                            "tick_volume",
                            0,
                        )
                    ),

                    spread=int(
                        row.get(
                            "spread",
                            0,
                        )
                    ),

                    real_volume=int(
                        row.get(
                            "real_volume",
                            0,
                        )
                    ),

                )

                candles.append(
                    candle
                )

        return candles