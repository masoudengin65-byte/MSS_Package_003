from mss.adapters.mt5.session import MT5Session


class MT5Adapter:

    def __init__(self):
        self.session = MT5Session()

    def connect(self):
        return self.session.connect()

    def shutdown(self):
        self.session.disconnect()

    def account(self):
        return self.session.account()

    def version(self):
        return self.session.version()

    def terminal(self):
        return self.session.terminal()