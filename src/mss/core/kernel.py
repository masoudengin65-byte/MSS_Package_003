import MetaTrader5 as mt5

from mss.core.logger import Logger
from mss.core.event_bus import EventBus

from mss.adapters.mt5.adapter import MT5Adapter
from mss.adapters.mt5.history import HistoryService
from mss.adapters.mt5.broker_clock import BrokerClock

from mss.analysis.structure_state import StructureState
from mss.analysis.market_analyzer import MarketAnalyzer
from mss.analysis.kill_zone_monitor import KillZoneMonitor
from mss.analysis.session_bias_engine import SessionBiasEngine
from mss.analysis.news_risk_filter import NewsRiskFilter
from mss.analysis.portfolio_exposure_engine import PortfolioExposureEngine
from mss.analysis.risk_engine import RiskEngine
from mss.analysis.execution_pipeline import ExecutionPipeline
from mss.analysis.performance_analyzer import PerformanceAnalyzer
from mss.analysis.strategy_optimizer import StrategyOptimizer
from mss.analysis.excel_report_engine import ExcelReportEngine
from mss.engine.signal_engine import SignalEngine
from mss.domain.pipeline_result import PipelineResult
from mss.domain.position import Position
from mss.domain.market_context import MarketContext
from mss.domain.trade_context import TradeContext
from mss.domain.optimization_result import OptimizationCase
from mss.domain.report import Report


class Kernel:

    def boot(self):

        log = Logger()

        bus = EventBus()

        bus.subscribe(
            "startup",
            lambda _: log.info("Startup event"),
        )

        bus.publish("startup")

        adapter = MT5Adapter()

        ok, msg = adapter.connect()

        if not ok:

            log.info(msg)

            return

        log.info("MT5 Connected")

        broker_time = BrokerClock().now("XAUUSD")

        kill_zone_status = KillZoneMonitor.from_config().evaluate(broker_time)

        news_filter, calendar_events = NewsRiskFilter.from_config()

        news_risk = news_filter.evaluate(broker_time, calendar_events)

        open_positions = self._open_positions(mt5.positions_get() or [])

        portfolio_exposure = PortfolioExposureEngine().calculate(
            open_positions
        )

        candles = HistoryService().last(

            "XAUUSD",

            mt5.TIMEFRAME_M1,

            100,

        )

        engine = MarketAnalyzer()

        analysis = engine.analyze(

            self._market_context("XAUUSD", mt5.TIMEFRAME_M1, candles),

        )

        pipeline_results = [
            self._to_pipeline_result(
                "XAUUSD", "M1", candles, analysis
            )
        ]

        for timeframe_name, timeframe in (
            ("M15", mt5.TIMEFRAME_M15),
            ("H1", mt5.TIMEFRAME_H1),
        ):
            timeframe_candles = HistoryService().last(
                "XAUUSD", timeframe, 100
            )
            timeframe_analysis = engine.analyze(
                self._market_context(
                    "XAUUSD",
                    timeframe,
                    timeframe_candles,
                )
            )
            pipeline_results.append(
                self._to_pipeline_result(
                    "XAUUSD",
                    timeframe_name,
                    timeframe_candles,
                    timeframe_analysis,
                )
            )

        session_bias = SessionBiasEngine().calculate(
            pipeline_results,
            analysis.premium_discount,
            kill_zone_status,
        )

        decision_context = TradeContext(
            symbol="XAUUSD",
            timeframe=mt5.TIMEFRAME_M1,
            analysis=analysis,
        )
        decision_context.kill_zone_status = kill_zone_status
        decision_context.session_bias = session_bias
        decision = SignalEngine().generate(decision_context)

        account = adapter.account()
        account_balance = account.balance if account is not None else 0.0
        trade_setup = analysis.trade_setup
        stop_distance = (
            abs(trade_setup.entry - trade_setup.stop_loss)
            if trade_setup.valid
            else 0.0
        )
        risk_profile = RiskEngine().calculate(
            balance=account_balance,
            risk_percent=1.0,
            stop_distance=stop_distance,
            news_risk_status=news_risk,
            portfolio_exposure=portfolio_exposure,
        )

        order, paper_position = ExecutionPipeline().execute(
            symbol="XAUUSD",
            trade_setup=trade_setup,
            account_balance=account_balance,
            risk_percent=1.0,
            ticket=int(broker_time.timestamp()) if broker_time else 1,
            news_risk_status=news_risk,
            portfolio_exposure=portfolio_exposure,
        )
        paper_positions = list(open_positions)
        if paper_position.valid:
            paper_positions.append(paper_position)

        statistics = PerformanceAnalyzer().calculate(paper_positions)
        optimization_cases = []
        if statistics.valid:
            optimization_cases.append(
                OptimizationCase(
                    parameters={"risk_percent": 1.0, "rr": trade_setup.rr},
                    profit=statistics.net_profit,
                    drawdown=statistics.max_drawdown,
                    win_rate=statistics.win_rate,
                    profit_factor=statistics.profit_factor,
                )
            )
        optimization = StrategyOptimizer().optimize(optimization_cases)

        final_decision = (
            paper_position.direction
            if paper_position.valid
            else "WAIT"
        )
        decision_reason = (
            "PAPER_TRADE_OPENED"
            if paper_position.valid
            else risk_profile.reason or decision.reason
        )

        report = Report(
            processed_candles=len(candles),
            generated_signals=0 if decision.signal == "WAIT" else 1,
            executed_trades=1 if paper_position.valid else 0,
            premium_discount=analysis.premium_discount,
            kill_zone_status=kill_zone_status,
            session_bias=session_bias,
            news_risk_status=news_risk,
            portfolio_exposure=portfolio_exposure,
            risk_profile=risk_profile,
            optimization_result=optimization,
            paper_positions=paper_positions,
            final_decision=final_decision,
            decision_reason=decision_reason,
            statistics=statistics,
            title="MSS PERSONAL EDITION v1.0",
            valid=True,
        )
        excel_file = ExcelReportEngine().build(report)

        log.info("=======================================")
        log.info("MARKET ANALYSIS")
        log.info("=======================================")

        log.info("Symbol    : XAUUSD")

        log.info("Timeframe : M1")

        log.info(f"Broker Time: {kill_zone_status.broker_time}")

        log.info(f"Session    : {kill_zone_status.current_session}")

        log.info(f"Kill Zone  : {kill_zone_status.active_kill_zone}")

        log.info(f"Remaining  : {kill_zone_status.remaining_time}")

        log.info(f"KZ Active  : {kill_zone_status.active}")

        log.info(f"Session Bias: {session_bias.bias}")

        log.info(f"Bias Strength: {session_bias.strength}")

        log.info(f"Bias Confidence: {session_bias.confidence}")

        log.info(f"Next Event : {news_risk.next_event}")

        log.info(f"Event Impact: {news_risk.event_impact}")

        log.info(f"Event Minutes: {news_risk.minutes_remaining}")

        log.info(f"Trading Status: {news_risk.trading_status}")

        log.info(f"Portfolio Exposure: {portfolio_exposure.portfolio_exposure}")

        log.info(f"Currency Exposure: {portfolio_exposure.currency_exposure}")

        log.info(f"Asset Exposure: {portfolio_exposure.asset_exposure}")

        log.info(f"Correlation Level: {portfolio_exposure.correlation_level}")

        log.info(f"Portfolio Risk Score: {portfolio_exposure.portfolio_risk_score}")

        log.info(f"Portfolio Risk Level: {portfolio_exposure.risk_level}")

        log.info(f"Decision Signal: {decision.signal}")

        log.info(f"Risk Approved: {risk_profile.valid}")

        log.info(f"Risk Reason: {risk_profile.reason or '-'}")

        log.info(f"Paper Order: {order.valid}")

        log.info(f"Paper Position: {paper_position.valid}")

        log.info(f"Performance Valid: {statistics.valid}")

        log.info(f"Net Profit: {statistics.net_profit}")

        log.info(f"Adaptive Optimizer: {optimization.valid}")

        log.info(f"Final Decision: {final_decision}")

        log.info(f"Decision Reason: {decision_reason}")

        log.info(f"Excel Journal: {excel_file}")

        structure = analysis.structure

        if structure is None:

            log.info("Trend     : UNKNOWN")

        elif structure.state == StructureState.UPTREND:

            log.info("Trend     : UPTREND")

        elif structure.state == StructureState.DOWNTREND:

            log.info("Trend     : DOWNTREND")

        elif structure.state == StructureState.RANGE:

            log.info("Trend     : RANGE")

        else:

            log.info("Trend     : UNKNOWN")

        if analysis.bos:

            log.info("---------------------------------------")

            log.info(f"BOS        : {analysis.bos.direction}")

            log.info(f"Level      : {analysis.bos.broken_level}")

            log.info(f"Close      : {analysis.bos.break_price}")

        else:

            log.info("---------------------------------------")

            log.info("BOS        : NONE")

        if analysis.choch:

            log.info("---------------------------------------")

            log.info(f"CHoCH      : {analysis.choch.direction}")

            log.info(f"Level      : {analysis.choch.level}")

        else:

            log.info("---------------------------------------")

            log.info("CHoCH      : NONE")

        log.info("---------------------------------------")

        premium_discount = analysis.premium_discount

        log.info(f"Premium Zone : {premium_discount.premium_zone}")

        log.info(f"Discount Zone: {premium_discount.discount_zone}")

        log.info(f"Equilibrium  : {premium_discount.equilibrium}")

        log.info(f"Current Zone : {premium_discount.current_zone}")

        log.info(
            "EQ Distance  : "
            f"{premium_discount.distance_to_equilibrium}"
        )

        log.info("---------------------------------------")

        liquidity = analysis.liquidity

        liquidity_detected = (
            liquidity.buy_side_liquidity
            or liquidity.sell_side_liquidity
            or liquidity.sweep_high
            or liquidity.sweep_low
        )

        log.info(f"Liquidity  : {liquidity_detected}")

        log.info(f"OrderBlock : {analysis.order_block.valid}")

        log.info(f"FVG        : {analysis.fair_value_gap.valid}")

        log.info("---------------------------------------")

        log.info("Signal     : WAIT")

        log.info("=======================================")

        adapter.shutdown()

        return {
            "analysis": analysis,
            "decision": decision,
            "risk_profile": risk_profile,
            "order": order,
            "paper_position": paper_position,
            "performance": statistics,
            "optimization": optimization,
            "report": report,
            "excel_file": excel_file,
        }

    @staticmethod
    def _to_pipeline_result(symbol, timeframe, candles, analysis):
        structure_state = (
            analysis.structure.state.value
            if analysis.structure is not None
            else "UNKNOWN"
        )
        bos = analysis.bos

        return PipelineResult(
            symbol=symbol,
            timeframe=timeframe,
            valid=bool(candles),
            structure_state=structure_state,
            bos_detected=bos is not None,
            bos_direction=getattr(bos, "direction", ""),
        )

    @staticmethod
    def _market_context(symbol, timeframe, candles):
        return MarketContext(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            swings=[],
            last_closed_candle=candles[-1] if candles else None,
        )

    @staticmethod
    def _open_positions(mt5_positions):
        return [
            Position(
                ticket=position.ticket,
                symbol=position.symbol,
                direction="BUY" if position.type == mt5.POSITION_TYPE_BUY else "SELL",
                volume=position.volume,
                entry_price=position.price_open,
                stop_loss=position.sl,
                take_profit=position.tp,
                status="OPEN",
                valid=True,
            )
            for position in mt5_positions
        ]
