from pathlib import Path

from mss.analysis.excel_report_engine import ExcelReportEngine
from mss.domain.report import Report
from mss.domain.trade_statistics import TradeStatistics


def build_report():

    stats = TradeStatistics()

    stats.total_trades = 10
    stats.winning_trades = 7
    stats.losing_trades = 3
    stats.breakeven_trades = 0

    stats.gross_profit = 850
    stats.gross_loss = 250
    stats.net_profit = 600

    stats.win_rate = 70.0
    stats.profit_factor = 3.40
    stats.expectancy = 60.0
    stats.max_drawdown = 120.0

    stats.equity_curve = [

        0,
        100,
        180,
        250,
        220,
        350,
        470,
        600,

    ]

    report = Report()

    report.processed_candles = 500

    report.generated_signals = 18

    report.executed_trades = 10

    report.execution_time = 0.42

    report.statistics = stats

    return report


def test_excel_report_created(tmp_path):

    report = build_report()

    filename = ExcelReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert Path(filename).exists()


def test_excel_report_extension(tmp_path):

    report = build_report()

    filename = ExcelReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert filename.endswith(".xlsx")


def test_excel_report_not_empty(tmp_path):

    report = build_report()

    filename = ExcelReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert Path(filename).stat().st_size > 0