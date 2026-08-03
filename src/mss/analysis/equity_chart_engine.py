"""
MSS Equity Chart Engine
Version : 1.0
Sprint : 37.0
Compatible : v0.31
"""

from pathlib import Path

import matplotlib.pyplot as plt

from mss.domain.report import Report


class EquityChartEngine:

    def build(
        self,
        report: Report,
        output_folder="reports",
    ) -> str:

        folder = Path(output_folder)

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = folder / "Equity_Curve.png"

        equity = report.statistics.equity_curve

        plt.figure(figsize=(10, 5))

        plt.plot(
            range(1, len(equity) + 1),
            equity,
            linewidth=2,
        )

        plt.title("MSS Equity Curve")

        plt.xlabel("Trades")

        plt.ylabel("Equity")

        plt.grid(True)

        plt.tight_layout()

        plt.savefig(filename)

        plt.close()

        return str(filename)