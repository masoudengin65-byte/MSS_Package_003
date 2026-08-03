"""
MSS Performance Analyzer
Version : 2.0
Sprint : 33.0
Compatible : v0.31
"""

from mss.domain.trade_statistics import TradeStatistics


class PerformanceAnalyzer:

    def calculate(
        self,
        positions,
    ) -> TradeStatistics:

        stats = TradeStatistics()

        if positions is None:
            return stats

        if len(positions) == 0:
            return stats

        stats.total_trades = len(positions)

        profits = []

        losses = []

        equity = 0.0

        peak = 0.0

        max_dd = 0.0

        for position in positions:

            p = position.profit

            equity += p

            #
            # Equity Curve
            #
            stats.equity_curve.append(
                equity
            )

            if equity > peak:

                peak = equity

            dd = peak - equity

            if dd > max_dd:

                max_dd = dd

            if p > 0:

                stats.winning_trades += 1

                stats.gross_profit += p

                profits.append(p)

            elif p < 0:

                stats.losing_trades += 1

                stats.gross_loss += abs(p)

                losses.append(abs(p))

            else:

                stats.breakeven_trades += 1

        stats.net_profit = (

            stats.gross_profit

            -

            stats.gross_loss

        )

        if stats.total_trades > 0:

            stats.win_rate = (

                stats.winning_trades

                /

                stats.total_trades

            ) * 100.0

        if stats.gross_loss > 0:

            stats.profit_factor = (

                stats.gross_profit

                /

                stats.gross_loss

            )

        if profits:

            stats.average_profit = (

                sum(profits)

                /

                len(profits)

            )

        if losses:

            stats.average_loss = (

                sum(losses)

                /

                len(losses)

            )

        if stats.total_trades > 0:

            stats.expectancy = (

                stats.net_profit

                /

                stats.total_trades

            )

        stats.max_drawdown = max_dd

        #
        # Balance Curve
        #
        stats.balance_curve = (

            stats.equity_curve.copy()

        )

        stats.valid = True

        return stats