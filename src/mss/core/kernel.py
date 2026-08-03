import MetaTrader5 as mt5

from mss.core.logger import Logger
from mss.core.event_bus import EventBus

from mss.adapters.mt5.adapter import MT5Adapter
from mss.adapters.mt5.history import HistoryService

from mss.analysis.structure_state import StructureState
from mss.analysis.structure_engine import StructureEngine


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

        candles = HistoryService().last(

            "XAUUSD",

            mt5.TIMEFRAME_M1,

            100,

        )

        engine = StructureEngine()

        analysis = engine.analyze(

            "XAUUSD",

            mt5.TIMEFRAME_M1,

            candles,

        )

        log.info("=======================================")
        log.info("MARKET ANALYSIS")
        log.info("=======================================")

        log.info("Symbol    : XAUUSD")

        log.info("Timeframe : M1")

        structure = analysis.structure

        if structure.state == StructureState.UPTREND:

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

        log.info("Liquidity  : NONE")

        log.info("OrderBlock : NONE")

        log.info("FVG        : NONE")

        log.info("---------------------------------------")

        log.info("Signal     : WAIT")

        log.info("=======================================")