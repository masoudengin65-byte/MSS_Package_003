"""
MSS MT5 Integration Test
Version : 1.0
Sprint : 45.1
"""

import MetaTrader5 as mt5


def main():

    print("=" * 60)
    print("MSS MT5 Integration Test")
    print("=" * 60)

    #
    # Connect
    #

    if not mt5.initialize():

        print("FAILED : MT5 initialize")

        print(mt5.last_error())

        return

    print("OK : Connected")

    #
    # Terminal
    #

    terminal = mt5.terminal_info()

    if terminal:

        print("\nTerminal")

        print("--------------------")

        print("Company :", terminal.company)

        print("Name    :", terminal.name)

        print("Path    :", terminal.path)

    #
    # Account
    #

    account = mt5.account_info()

    if account:

        print("\nAccount")

        print("--------------------")

        print("Login   :", account.login)

        print("Server  :", account.server)

        print("Balance :", account.balance)

        print("Equity  :", account.equity)

    #
    # Symbols
    #

    symbol = "EURUSD"

    info = mt5.symbol_info(symbol)

    if info is None:

        print("\nFAILED : Symbol not found")

        mt5.shutdown()

        return

    print("\nSymbol :", symbol)

    #
    # Tick
    #

    tick = mt5.symbol_info_tick(symbol)

    if tick:

        print("\nTick")

        print("--------------------")

        print("Bid :", tick.bid)

        print("Ask :", tick.ask)

    #
    # Done
    #

    mt5.shutdown()

    print("\nDisconnected")


if __name__ == "__main__":

    main()