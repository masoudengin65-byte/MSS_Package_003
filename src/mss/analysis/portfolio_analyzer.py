"""
MSS Portfolio Analyzer
Version : 1.0
Sprint : 38.0
Compatible : v0.31
"""

from mss.domain.portfolio_statistics import PortfolioStatistics
from mss.domain.trade_statistics import TradeStatistics


class PortfolioAnalyzer:

    def calculate(
        self,
        statistics: dict[str, TradeStatistics],
    ) -> PortfolioStatistics:

        portfolio = PortfolioStatistics()

        if statistics is None:

            return portfolio

        if len(statistics) == 0:

            return portfolio

        portfolio.reports = statistics

        portfolio.symbols = list(

            statistics.keys()

        )

        portfolio.total_symbols = len(

            portfolio.symbols

        )

        win_rate_sum = 0.0

        pf_sum = 0.0

        for symbol, stat in statistics.items():

            portfolio.total_trades += (

                stat.total_trades

            )

            portfolio.total_profit += (

                stat.gross_profit

            )

            portfolio.total_loss += (

                stat.gross_loss

            )

            portfolio.net_profit += (

                stat.net_profit

            )

            win_rate_sum += (

                stat.win_rate

            )

            pf_sum += (

                stat.profit_factor

            )

        portfolio.average_win_rate = (

            win_rate_sum

            /

            portfolio.total_symbols

        )

        portfolio.average_profit_factor = (

            pf_sum

            /

            portfolio.total_symbols

        )

        portfolio.valid = True

        return portfolio