"""
MSS Backtest Engine
Version : 2.0
Sprint : 20.1
Compatible : v0.30
"""

import time

from mss.analysis.performance_analyzer import PerformanceAnalyzer
from mss.domain.backtest_result import BacktestResult


class BacktestEngine:

    def run(
        self,
        positions,
        replay_result=None,
    ) -> BacktestResult:

        result = BacktestResult()

        start = time.perf_counter()

        #
        # اطلاعات Replay (اختیاری)
        #
        if replay_result is not None:

            result.processed_candles = (
                replay_result.processed_candles
            )

            result.generated_signals = (
                len(replay_result.analyses)
            )

        else:

            result.processed_candles = 0

        #
        # نسخه قدیمی همچنان پشتیبانی می‌شود
        #
        if positions is None:
            return result

        #
        # اگر Replay وجود نداشت،
        # تعداد سیگنال‌ها همان تعداد معاملات است.
        #
        if replay_result is None:

            result.generated_signals = len(positions)

        result.executed_trades = len(positions)

        result.statistics = (
            PerformanceAnalyzer().calculate(
                positions
            )
        )

        result.execution_time = (
            time.perf_counter()
            -
            start
        )

        result.valid = (
            result.statistics.valid
        )

        return result