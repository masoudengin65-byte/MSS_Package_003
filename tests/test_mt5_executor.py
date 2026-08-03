from unittest.mock import MagicMock
from unittest.mock import patch

from mss.execution.mt5_executor import MT5Executor


@patch("mss.execution.mt5_executor.mt5")
def test_initialize(mock_mt5):

    mock_mt5.initialize.return_value = True

    executor = MT5Executor()

    assert executor.initialize() is True


@patch("mss.execution.mt5_executor.mt5")
def test_shutdown(mock_mt5):

    executor = MT5Executor()

    executor.shutdown()

    mock_mt5.shutdown.assert_called_once()


@patch("mss.execution.mt5_executor.mt5")
def test_terminal_info(mock_mt5):

    terminal = MagicMock()

    mock_mt5.terminal_info.return_value = terminal

    executor = MT5Executor()

    assert executor.terminal_info() == terminal


@patch("mss.execution.mt5_executor.mt5")
def test_account_info(mock_mt5):

    account = MagicMock()

    mock_mt5.account_info.return_value = account

    executor = MT5Executor()

    assert executor.account_info() == account


@patch("mss.execution.mt5_executor.mt5")
def test_symbol_info(mock_mt5):

    symbol = MagicMock()

    mock_mt5.symbol_info.return_value = symbol

    executor = MT5Executor()

    assert executor.symbol_info("EURUSD") == symbol


@patch("mss.execution.mt5_executor.mt5")
def test_symbol_tick(mock_mt5):

    tick = MagicMock()

    mock_mt5.symbol_info_tick.return_value = tick

    executor = MT5Executor()

    assert executor.symbol_tick("EURUSD") == tick


@patch("mss.execution.mt5_executor.mt5")
def test_positions(mock_mt5):

    positions = [MagicMock()]

    mock_mt5.positions_get.return_value = positions

    executor = MT5Executor()

    assert executor.positions() == positions


@patch("mss.execution.mt5_executor.mt5")
def test_positions_symbol(mock_mt5):

    positions = [MagicMock()]

    mock_mt5.positions_get.return_value = positions

    executor = MT5Executor()

    assert executor.positions("EURUSD") == positions


@patch("mss.execution.mt5_executor.mt5")
def test_orders(mock_mt5):

    orders = [MagicMock()]

    mock_mt5.orders_get.return_value = orders

    executor = MT5Executor()

    assert executor.orders() == orders


@patch("mss.execution.mt5_executor.mt5")
def test_orders_symbol(mock_mt5):

    orders = [MagicMock()]

    mock_mt5.orders_get.return_value = orders

    executor = MT5Executor()

    assert executor.orders("EURUSD") == orders