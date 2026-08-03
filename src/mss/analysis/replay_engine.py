"""
MSS Replay Engine
Version : 2.0
Sprint : 29.0
Compatible : v0.30
"""

import time

from mss.analysis.market_analyzer import MarketAnalyzer
from mss.analysis.execution_pipeline import ExecutionPipeline

from mss.domain.market_context import MarketContext
from mss.domain.replay_result import ReplayResult


class ReplayEngine:

    def __init__(self):

        self.analyzer = MarketAnalyzer()

        self.execution = ExecutionPipeline()

    def replay(
        self,
        candles,
        symbol="REPLAY",
        timeframe=None,
        account_balance=10000.0,
        risk_percent=1.0,
    ) -> ReplayResult:

        result = ReplayResult()

        if candles is None:
            return result

        start = time.perf_counter()

        history = []

        ticket = 1

        for candle in candles:

            history.append(candle)

            context = MarketContext(

                symbol=symbol,

                timeframe=timeframe,

                candles=history.copy(),

                swings=[],

                last_closed_candle=candle,

            )

            analysis = self.analyzer.analyze(

                context,

            )

            result.analyses.append(

                analysis,

            )

            if analysis.trade_setup.valid:

                order, position = self.execution.execute(

                    symbol=symbol,

                    trade_setup=analysis.trade_setup,

                    account_balance=account_balance,

                    risk_percent=risk_percent,

                    ticket=ticket,

                )

                if order.valid:

                    result.orders.append(order)

                    result.executed_trades += 1

                if position.valid:

                    result.positions.append(position)

                    ticket += 1

            result.processed_candles += 1

        result.generated_signals = len(

            result.analyses,

        )

        result.elapsed_seconds = (

            time.perf_counter()

            -

            start

        )

        result.completed = True

        return result