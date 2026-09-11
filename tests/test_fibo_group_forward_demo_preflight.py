from pathlib import Path
from types import SimpleNamespace

from mss.analysis.fibo_group_forward_demo_preflight import run_preflight


class _Mt5:
    ACCOUNT_TRADE_MODE_DEMO = 0
    TIMEFRAME_M15 = 15

    def __init__(self):
        self.order_check = object()
        self.order_send = object()
        self.shutdown_count = 0

    def shutdown(self):
        self.shutdown_count += 1

    def initialize(self, **_kwargs):
        return True

    def last_error(self):
        return "none"

    def account_info(self):
        return SimpleNamespace(server="FIBOGroup-MT5 Server", trade_mode=0)

    def terminal_info(self):
        return SimpleNamespace(connected=True)

    def symbol_select(self, *_args):
        return True

    def symbol_info(self, _symbol):
        return SimpleNamespace(point=0.01, volume_min=0.01, volume_step=0.01)

    def copy_rates_from_pos(self, *_args):
        return [object(), object()]


def test_fibo_demo_preflight_is_read_only_and_keeps_activation_blocked(tmp_path):
    terminal = tmp_path / "terminal64.exe"
    terminal.write_bytes(b"terminal")
    mt5 = _Mt5()
    original_check, original_send = mt5.order_check, mt5.order_send
    result = run_preflight(terminal, mt5)
    assert result["account_is_demo"] is True
    assert len(result["symbols"]) == 4
    assert result["forward_shadow_activation_eligible"] is False
    assert result["safety"]["order_send_called"] is False
    assert mt5.order_check is original_check
    assert mt5.order_send is original_send
