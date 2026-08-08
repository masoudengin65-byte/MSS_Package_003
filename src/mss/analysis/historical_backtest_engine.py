"""Chronological, no-look-ahead historical paper backtest engine."""

import time

from mss.analysis.order_builder import OrderBuilder
from mss.analysis.performance_analyzer import PerformanceAnalyzer
from mss.analysis.position_manager import PositionManager
from mss.analysis.risk_engine import RiskEngine
from mss.analysis.historical_valuation import HistoricalValuation
from mss.analysis.smart_money_pipeline import SmartMoneyPipeline
from mss.analysis.context_capture_engine import ContextCaptureEngine
from mss.analysis.score_engine import ScoreEngine
from mss.domain.historical_backtest import (
    BacktestDiagnostics,
    BacktestSymbolMetadata,
    HistoricalBacktestConfig,
    HistoricalBacktestResult,
    HistoricalMetrics,
    HistoricalTrade,
)
from mss.domain.trade_setup import TradeSetup


class HistoricalBacktestEngine:

    def __init__(self, pipeline=None):
        self.pipeline = pipeline or SmartMoneyPipeline()
        self.risk_engine = RiskEngine()
        self.order_builder = OrderBuilder()
        self.position_manager = PositionManager()
        self.context_capture_engine = ContextCaptureEngine()
        self.shadow_score_engine = ScoreEngine()

    def run(
        self,
        symbol,
        timeframe,
        candles,
        config=None,
        metadata=None,
    ) -> HistoricalBacktestResult:
        config = config or HistoricalBacktestConfig()
        metadata = metadata or BacktestSymbolMetadata()
        result = HistoricalBacktestResult(
            symbol=symbol,
            timeframe=timeframe,
            config=config,
            metadata=metadata,
            diagnostics=BacktestDiagnostics(warmup_candles=config.warmup_candles),
        )
        started = time.perf_counter()
        history = self._prepare_candles(candles, result.diagnostics)
        result.diagnostics.candles_loaded = len(history)
        if history:
            result.diagnostics.data_start = history[0].time
            result.diagnostics.data_end = history[-1].time

        if len(history) <= config.warmup_candles:
            result.diagnostics.runtime_seconds = time.perf_counter() - started
            result.metrics.ending_balance = config.starting_balance
            return result

        balance = config.starting_balance
        pending = None
        active_trade = None
        active_position = None
        closed_positions = []

        for index, candle in enumerate(history):
            result.diagnostics.candles_processed += 1

            if pending is not None:
                if active_trade is None:
                    opened = self._open_pending(
                        pending,
                        candle,
                        balance,
                        config,
                        metadata,
                        result,
                    )
                    if opened is not None:
                        active_trade, active_position = opened
                        result.trades.append(active_trade)
                        result.diagnostics.opened_trades += 1
                else:
                    self._reject(result.diagnostics, "POSITION_ALREADY_OPEN")
                pending = None

            if active_trade is not None:
                exit_data = self._detect_exit(
                    active_trade,
                    candle,
                    config,
                )
                if exit_data is not None:
                    exit_price, exit_reason = exit_data
                    balance = self._close_trade(
                        active_trade,
                        active_position,
                        candle,
                        exit_price,
                        exit_reason,
                        balance,
                        metadata,
                        closed_positions,
                    )
                    result.diagnostics.closed_trades += 1
                    active_trade = None
                    active_position = None

            if index + 1 < config.warmup_candles:
                continue

            window_start = max(0, index + 1 - config.analysis_lookback)
            visible_history = history[window_start:index + 1]
            pipeline_result = self.pipeline.run(
                symbol=symbol,
                timeframe=timeframe,
                candles=visible_history,
            )
            result.diagnostics.decisions_generated += 1

            direction = self._decision_direction(pipeline_result)
            if direction == "BUY":
                result.diagnostics.buy_signals += 1
            elif direction == "SELL":
                result.diagnostics.sell_signals += 1
            else:
                result.diagnostics.wait_results += 1
                continue

            if index == len(history) - 1:
                self._reject(result.diagnostics, "NO_NEXT_CANDLE")
                continue

            if active_trade is not None or pending is not None:
                self._reject(result.diagnostics, "POSITION_ALREADY_OPEN")
                continue

            pending = {
                "direction": direction,
                "signal_time": candle.time,
                "pipeline_result": pipeline_result,
                "context_snapshot": self.context_capture_engine.capture_decision(
                    pipeline_result=pipeline_result,
                    visible_candles=visible_history,
                    decision_time=candle.time,
                ),
            }

        if active_trade is not None:
            result.diagnostics.unresolved_trades = 1

        result.statistics = PerformanceAnalyzer().calculate(closed_positions)
        result.metrics = self._calculate_metrics(
            result.trades,
            config.starting_balance,
            result.statistics,
        )
        result.diagnostics.runtime_seconds = time.perf_counter() - started
        result.valid = True
        return result

    def _open_pending(
        self,
        pending,
        candle,
        balance,
        config,
        metadata,
        result,
    ):
        metadata_error = HistoricalValuation.metadata_error(metadata)
        if metadata_error:
            self._reject(
                result.diagnostics,
                f"VALUATION_METADATA_UNAVAILABLE:{metadata_error}",
            )
            return None

        pipeline_result = pending["pipeline_result"]
        direction = pending["direction"]
        spread_points = (
            config.spread_points
            if config.spread_points is not None
            else candle.spread or metadata.spread_points
        )
        spread = float(spread_points) * float(metadata.point)
        slippage = float(config.slippage_points) * float(metadata.point)
        entry = (
            float(candle.open) + spread + slippage
            if direction == "BUY"
            else float(candle.open) - spread - slippage
        )
        stop_loss = (
            pipeline_result.last_low
            if direction == "BUY"
            else pipeline_result.last_high
        )

        if stop_loss is None:
            self._reject(result.diagnostics, "MISSING_STOP_LEVEL")
            return None
        stop_loss = float(stop_loss)
        if direction == "BUY" and stop_loss >= entry:
            self._reject(result.diagnostics, "INVALID_BUY_STOP")
            return None
        if direction == "SELL" and stop_loss <= entry:
            self._reject(result.diagnostics, "INVALID_SELL_STOP")
            return None

        stop_distance = abs(entry - stop_loss)
        risk_profile = self.risk_engine.calculate(
            balance=balance,
            risk_percent=config.risk_percent,
            stop_distance=stop_distance,
        )
        if not risk_profile.valid:
            self._reject(result.diagnostics, "RISK_REJECTED")
            return None

        sizing = HistoricalValuation.size_for_risk(
            risk_profile.risk_amount, stop_distance, metadata,
        )
        if not sizing.valid:
            self._reject(result.diagnostics, sizing.reason)
            return None
        volume = sizing.rounded_volume
        risk_profile.lot_size = volume

        take_profit = float(
            entry + stop_distance * config.reward_risk_ratio
            if direction == "BUY"
            else entry - stop_distance * config.reward_risk_ratio
        )
        setup = TradeSetup(
            direction=direction,
            entry=entry,
            stop_loss=stop_loss,
            take_profit_1=take_profit,
            take_profit_2=take_profit,
            risk=stop_distance,
            reward=stop_distance * config.reward_risk_ratio,
            rr=config.reward_risk_ratio,
            valid=True,
            reason="Historical next-candle entry",
        )
        order = self.order_builder.build(result.symbol, setup, risk_profile)
        position = self.position_manager.open_position(
            result.diagnostics.opened_trades + 1,
            order,
        )
        position.open_time = candle.time

        entry_snapshot = self.context_capture_engine.capture_entry(
            pending["context_snapshot"],
            entry_candle=candle,
            entry_time=candle.time,
            risk_approved=risk_profile.valid,
            position_size=volume,
            sl_distance=stop_distance,
            tp_distance=stop_distance * config.reward_risk_ratio,
            rr=config.reward_risk_ratio,
        )
        shadow = self.shadow_score_engine.calculate(entry_snapshot.to_dict(), direction)
        trade = HistoricalTrade(
            trade_id=position.ticket,
            symbol=result.symbol,
            timeframe=result.timeframe,
            direction=direction,
            signal_time=pending["signal_time"],
            entry_time=candle.time,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            spread=spread,
            commission=config.commission_per_lot * volume,
            slippage=slippage,
            volume=volume,
            score=pipeline_result.score,
            confidence=pipeline_result.confidence,
            legacy_score=pipeline_result.score,
            legacy_confidence=pipeline_result.confidence,
            shadow_score=shadow.score,
            shadow_confidence=shadow.confidence,
            shadow_score_breakdown=shadow.components,
            shadow_score_result=shadow,
            detector_states=self._detector_states(pipeline_result),
            context_snapshot=entry_snapshot,
        )
        return trade, position

    @staticmethod
    def _detect_exit(trade, candle, config):
        if trade.direction == "BUY":
            stop_hit = candle.low <= trade.stop_loss
            target_hit = candle.high >= trade.take_profit
        else:
            stop_hit = candle.high >= trade.stop_loss
            target_hit = candle.low <= trade.take_profit

        if stop_hit and target_hit:
            reason = (
                "TAKE_PROFIT"
                if config.ambiguous_policy == "TAKE_PROFIT_FIRST"
                else "STOP_LOSS"
            )
        elif stop_hit:
            reason = "STOP_LOSS"
        elif target_hit:
            reason = "TAKE_PROFIT"
        else:
            return None

        level = trade.stop_loss if reason == "STOP_LOSS" else trade.take_profit
        if trade.direction == "BUY":
            exit_price = level - trade.slippage
        else:
            exit_price = level + trade.slippage
        return exit_price, reason

    def _close_trade(
        self,
        trade,
        position,
        candle,
        exit_price,
        exit_reason,
        balance,
        metadata,
        closed_positions,
    ):
        net_profit = HistoricalValuation.signed_pnl(
            trade.entry_price,
            exit_price,
            trade.direction,
            trade.volume,
            metadata,
            trade.commission,
        )
        risk_value = HistoricalValuation.monetary_value(
            abs(trade.entry_price - trade.stop_loss), trade.volume, metadata,
        )

        trade.exit_time = candle.time
        trade.exit_price = exit_price
        trade.exit_reason = exit_reason
        trade.profit = round(net_profit, 2)
        trade.r_multiple = round(net_profit / risk_value, 4) if risk_value else 0.0
        trade.status = "CLOSED"

        position = self.position_manager.close_position(
            position,
            close_price=exit_price,
            profit=trade.profit,
        )
        position.close_time = candle.time
        position.commission = trade.commission
        closed_positions.append(position)
        return balance + trade.profit

    @staticmethod
    def _decision_direction(pipeline_result):
        if not pipeline_result.valid or not pipeline_result.bos_detected:
            return "WAIT"
        if pipeline_result.bos_direction == "BULLISH":
            return "BUY"
        if pipeline_result.bos_direction == "BEARISH":
            return "SELL"
        return "WAIT"

    @staticmethod
    def _detector_states(pipeline_result):
        return {
            "structure": pipeline_result.structure_state,
            "bos": pipeline_result.bos_detected,
            "bos_direction": pipeline_result.bos_direction,
            "choch": pipeline_result.choch_detected,
            "liquidity": pipeline_result.liquidity_detected,
            "order_block": pipeline_result.order_block_detected,
            "fair_value_gap": pipeline_result.fair_value_gap_detected,
            "recommendation": pipeline_result.recommendation,
        }

    @staticmethod
    def _reject(diagnostics, reason):
        diagnostics.rejected_trades += 1
        diagnostics.rejection_reasons[reason] = (
            diagnostics.rejection_reasons.get(reason, 0) + 1
        )

    @staticmethod
    def _prepare_candles(candles, diagnostics):
        valid = []
        for candle in candles or []:
            if (
                candle.time is None
                or candle.high < max(candle.open, candle.close)
                or candle.low > min(candle.open, candle.close)
                or candle.low > candle.high
            ):
                diagnostics.skipped_invalid_candles += 1
                continue
            valid.append(candle)

        ordered = sorted(valid, key=lambda candle: candle.time)
        diagnostics.reordered_candles = sum(
            left is not right for left, right in zip(valid, ordered)
        )
        deduplicated = []
        for candle in ordered:
            if deduplicated and candle.time <= deduplicated[-1].time:
                diagnostics.skipped_invalid_candles += 1
                continue
            deduplicated.append(candle)
        return deduplicated

    @staticmethod
    def _calculate_metrics(trades, starting_balance, statistics):
        closed = [trade for trade in trades if trade.status == "CLOSED"]
        metrics = HistoricalMetrics(ending_balance=starting_balance)
        metrics.total_trades = len(closed)
        metrics.winning_trades = int(sum(trade.profit > 0 for trade in closed))
        metrics.losing_trades = int(sum(trade.profit < 0 for trade in closed))
        metrics.win_rate = (
            metrics.winning_trades / metrics.total_trades * 100.0
            if metrics.total_trades
            else 0.0
        )
        metrics.gross_profit = float(
            round(sum(max(0.0, t.profit) for t in closed), 2)
        )
        metrics.gross_loss = float(
            round(sum(abs(min(0.0, t.profit)) for t in closed), 2)
        )
        metrics.net_profit = float(round(sum(t.profit for t in closed), 2))
        metrics.profit_factor = (
            round(metrics.gross_profit / metrics.gross_loss, 4)
            if metrics.gross_loss
            else 0.0
        )
        metrics.expectancy = (
            round(metrics.net_profit / metrics.total_trades, 2)
            if metrics.total_trades
            else 0.0
        )
        metrics.average_r = (
            round(sum(t.r_multiple for t in closed) / metrics.total_trades, 4)
            if metrics.total_trades
            else 0.0
        )

        balance = starting_balance
        peak = starting_balance
        max_drawdown = 0.0
        max_drawdown_percent = 0.0
        metrics.equity_curve.append((0, balance))
        wins = losses = max_wins = max_losses = 0
        holding_minutes = []
        for index, trade in enumerate(closed, start=1):
            balance += trade.profit
            peak = max(peak, balance)
            drawdown = peak - balance
            drawdown_percent = drawdown / peak * 100.0 if peak else 0.0
            max_drawdown = max(max_drawdown, drawdown)
            max_drawdown_percent = max(max_drawdown_percent, drawdown_percent)
            metrics.equity_curve.append((index, round(balance, 2)))

            if trade.profit > 0:
                wins += 1
                losses = 0
            elif trade.profit < 0:
                losses += 1
                wins = 0
            else:
                wins = losses = 0
            max_wins = max(max_wins, wins)
            max_losses = max(max_losses, losses)

            if trade.entry_time is not None and trade.exit_time is not None:
                holding_minutes.append(
                    (trade.exit_time - trade.entry_time).total_seconds() / 60.0
                )

        metrics.maximum_drawdown = round(max_drawdown, 2)
        metrics.maximum_drawdown_percent = round(max_drawdown_percent, 4)
        metrics.maximum_consecutive_wins = max_wins
        metrics.maximum_consecutive_losses = max_losses
        metrics.average_holding_minutes = (
            round(sum(holding_minutes) / len(holding_minutes), 2)
            if holding_minutes
            else 0.0
        )
        metrics.ending_balance = round(balance, 2)
        metrics.return_percent = round(
            (balance - starting_balance) / starting_balance * 100.0,
            4,
        ) if starting_balance else 0.0
        return metrics
