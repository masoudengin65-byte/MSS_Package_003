"""
MSS Walk Forward Analyzer
Version : 1.0
Sprint : 39.0
Compatible : v0.31
"""

from mss.domain.walk_forward_result import WalkForwardResult
from mss.domain.trade_statistics import TradeStatistics


class WalkForwardAnalyzer:

    def calculate(
        self,
        reports: list[TradeStatistics],
    ) -> WalkForwardResult:

        result = WalkForwardResult()

        if reports is None:

            return result

        if len(reports) == 0:

            return result

        result.reports = reports

        result.training_windows = len(reports)

        result.testing_windows = len(reports)

        for report in reports:

            result.average_profit += (

                report.net_profit

            )

            result.average_win_rate += (

                report.win_rate

            )

            result.average_profit_factor += (

                report.profit_factor

            )

            result.average_drawdown += (

                report.max_drawdown

            )

        count = len(reports)

        result.average_profit /= count

        result.average_win_rate /= count

        result.average_profit_factor /= count

        result.average_drawdown /= count

        result.valid = True

        return result