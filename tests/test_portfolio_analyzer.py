from mss.analysis.portfolio_analyzer import PortfolioAnalyzer
from mss.domain.trade_statistics import TradeStatistics


def build_statistics():

    eurusd = TradeStatistics()

    eurusd.total_trades = 20
    eurusd.gross_profit = 1200
    eurusd.gross_loss = 400
    eurusd.net_profit = 800
    eurusd.win_rate = 70.0
    eurusd.profit_factor = 3.0

    gbpusd = TradeStatistics()

    gbpusd.total_trades = 10
    gbpusd.gross_profit = 600
    gbpusd.gross_loss = 200
    gbpusd.net_profit = 400
    gbpusd.win_rate = 60.0
    gbpusd.profit_factor = 2.5

    return {

        "EURUSD": eurusd,

        "GBPUSD": gbpusd,

    }


def test_portfolio_statistics():

    portfolio = PortfolioAnalyzer().calculate(

        build_statistics(),

    )

    assert portfolio.valid

    assert portfolio.total_symbols == 2

    assert portfolio.total_trades == 30

    assert portfolio.net_profit == 1200


def test_empty_portfolio():

    portfolio = PortfolioAnalyzer().calculate(

        {},

    )

    assert not portfolio.valid

    assert portfolio.total_symbols == 0


def test_none_portfolio():

    portfolio = PortfolioAnalyzer().calculate(

        None,

    )

    assert not portfolio.valid

    assert portfolio.total_symbols == 0