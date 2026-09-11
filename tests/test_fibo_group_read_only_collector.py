from pathlib import Path
from types import SimpleNamespace

import pytest

from mss.analysis.fibo_group_read_only_collector import collect


def test_collector_requires_fibo_server_and_uses_only_read_only_calls(monkeypatch, tmp_path):
    root = Path(__file__).resolve().parents[1]
    terminal = tmp_path / "terminal64.exe"
    terminal.touch()
    calls = []
    rows = [
        {"time": 1_632_083_400, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5},
        {"time": 1_632_084_300, "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0},
    ]
    fake = SimpleNamespace(
        TIMEFRAME_M15=15,
        initialize=lambda **_: calls.append("initialize") or True,
        shutdown=lambda: calls.append("shutdown"),
        account_info=lambda: calls.append("account_info") or SimpleNamespace(server="FIBOGroup-MT5 Server"),
        symbol_select=lambda symbol, _: calls.append(("symbol_select", symbol)) or True,
        copy_rates_range=lambda symbol, *_: calls.append(("copy_rates_range", symbol)) or rows,
        last_error=lambda: "test",
        order_check=lambda *_: pytest.fail("order_check called"),
        order_send=lambda *_: pytest.fail("order_send called"),
    )
    result = collect(root, terminal, fake, output_root=tmp_path / "evidence")
    assert result["order_check_called"] is False
    assert result["order_send_called"] is False
    assert {item[1] for item in calls if isinstance(item, tuple)} == {"EURUSD", "XAUUSD", "BTC", "ETH"}


def test_collector_fails_before_symbol_access_for_wrong_server(tmp_path):
    root = Path(__file__).resolve().parents[1]
    terminal = tmp_path / "terminal64.exe"
    terminal.touch()
    fake = SimpleNamespace(
        initialize=lambda **_: True, shutdown=lambda: None,
        account_info=lambda: SimpleNamespace(server="Alpari-MT5"),
        symbol_select=lambda *_: pytest.fail("symbol access occurred"),
        order_check=lambda *_: None, order_send=lambda *_: None,
    )
    with pytest.raises(RuntimeError, match="not the preregistered FIBO"):
        collect(root, terminal, fake)
