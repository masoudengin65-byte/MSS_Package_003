"""
MSS Live Smart Money Integration Test
Sprint 56.1
"""

from datetime import datetime

import MetaTrader5 as mt5

from mss.analysis.smart_money_pipeline import SmartMoneyPipeline


SYMBOL = "EURUSD"
TIMEFRAME = mt5.TIMEFRAME_M15
CANDLE_COUNT = 100


def build_candles(rates):

    candles = []

    for r in rates:

        candle = type(
            "ReplayCandle",
            (),
            {
                "time": datetime.fromtimestamp(r["time"]),
                "open": r["open"],
                "high": r["high"],
                "low": r["low"],
                "close": r["close"],
                "tick_volume": r["tick_volume"],
                "spread": r["spread"],
                "real_volume": r["real_volume"],
            },
        )()

        candles.append(candle)

    return candles


def print_report(result, terminal, account, candle_count):

    print()
    print("=" * 60)
    print("MSS LIVE ANALYSIS REPORT")
    print("=" * 60)

    print(f"Broker          : {terminal.company}")
    print(f"Server          : {account.server}")
    print(f"Login           : {account.login}")

    print("-" * 60)

    print(f"Symbol          : {result.symbol}")
    print(f"Timeframe       : {result.timeframe}")

    print("-" * 60)

    print(f"Candles         : {candle_count}")
    print(f"Swings          : {result.swing_count}")

    print("-" * 60)

    print(f"Structure       : {result.structure_state}")

    print()

    print("Structure Details")
    print("-" * 60)

    print(f"Swing Count     : {result.swing_count}")
    print(f"BOS             : {result.bos_detected}")
    print(f"BOS Direction   : {result.bos_direction or '-'}")
    print(f"CHOCH           : {result.choch_detected}")
    print(f"CHOCH Direction : {result.choch_direction or '-'}")

    if hasattr(result, "last_high"):
        print(f"Last High       : {result.last_high}")

    if hasattr(result, "last_low"):
        print(f"Last Low        : {result.last_low}")

    if hasattr(result, "previous_high"):
        print(f"Previous High   : {result.previous_high}")

    if hasattr(result, "previous_low"):
        print(f"Previous Low    : {result.previous_low}")

    print()

    print("BOS Details")
    print("-" * 60)

    print(f"Current Close   : {result.current_close}")
    print(f"Next BOS Level  : {result.next_bos_level}")
    if result.distance_to_bos is None:

        print("Distance        : -")
        print("Distance (Pip)  : -")
        print("Progress        : -")

    else:

        print(f"Distance        : {result.distance_to_bos}")
        print(f"Distance (Pip)  : {result.distance_to_bos_pips:.1f}")
        print(f"Progress        : {result.bos_progress:.1f}%")

    print(f"Status          : {result.bos_status}")
    print(f"BOS Ready       : {result.bos_ready}")
    print(f"BOS Detected    : {result.bos_detected}")
    print(f"BOS Direction   : {result.bos_direction or '-'}")

    print("-" * 60)

    #
    # Trade Readiness
    #

    print()
    print("Trade Readiness")
    print("-" * 60)

    if result.bos_detected:

        readiness = "READY"

    elif result.bos_status == "BREAKING":

        readiness = "BREAKOUT"

    elif result.bos_status == "NEAR BOS":

        readiness = "PREPARE"

    elif result.structure_state == "RANGE":

        readiness = "NO STRUCTURE"

    else:

        readiness = "WAIT"

    print(f"Readiness      : {readiness}")
    print(f"Recommendation : {result.recommendation}")

    print("-" * 60)

    print(f"Score           : {result.score}")
    print(f"Confidence      : {result.confidence:.2f}")
    print(f"Recommendation  : {result.recommendation}")

    print("-" * 60)
        #
    # Pipeline Log
    #

    print("Pipeline Log")
    print("-" * 60)

    if result.distance_to_bos is None:

        print("Distance (Pip) : -")
        print("Progress       : -")

    else:

        print(f"Distance (Pip) : {result.distance_to_bos_pips:.1f}")
        print(f"Progress       : {result.bos_progress:.1f}%")

    print(f"Status         : {result.bos_status}")

    for log in result.logs:

        print(log)

    print("=" * 60)


def main():

    print("=" * 60)
    print("Connecting to MT5...")
    print("=" * 60)

    if not mt5.initialize():

        print("MT5 initialize failed")
        print(mt5.last_error())
        return

    terminal = mt5.terminal_info()
    account = mt5.account_info()

    rates = mt5.copy_rates_from_pos(

        SYMBOL,
        TIMEFRAME,
        0,
        CANDLE_COUNT,

    )

    if rates is None:

        print("No market data.")

        mt5.shutdown()

        return

    candles = build_candles(rates)

    pipeline = SmartMoneyPipeline()
        result = pipeline.run(

        symbol=SYMBOL,

        timeframe="M15",

        candles=candles,

    )

    print_report(

        result,

        terminal,

        account,

        len(candles),

    )

    mt5.shutdown()


if __name__ == "__main__":

    main()