"""
MT5 Session Manager
MSS Trading Assistant
"""

from dataclasses import dataclass

try:
    import MetaTrader5 as mt5
except ImportError:
    mt5 = None


@dataclass
class AccountInfo:
    login: int
    server: str
    balance: float
    equity: float
    leverage: int
    company: str
    currency: str


class MT5Session:
    """
    Manages MetaTrader5 connection.
    """

    def __init__(self):
        self._connected = False

    @property
    def connected(self):
        return self._connected

    def connect(self):

        if mt5 is None:
            return False, "MetaTrader5 package not installed"

        if self._connected:
            return True, "Already connected"

        if mt5.initialize():
            self._connected = True
            return True, "Connected"

        return False, str(mt5.last_error())

    def disconnect(self):

        if mt5 and self._connected:
            mt5.shutdown()
            self._connected = False

    def version(self):

        if not self._connected:
            return None

        return mt5.version()

    def terminal(self):

        if not self._connected:
            return None

        return mt5.terminal_info()

    def account(self):

        if not self._connected:
            return None

        info = mt5.account_info()

        if info is None:
            return None

        return AccountInfo(
            login=info.login,
            server=info.server,
            balance=info.balance,
            equity=info.equity,
            leverage=info.leverage,
            company=info.company,
            currency=info.currency,
        )