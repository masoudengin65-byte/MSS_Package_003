from pathlib import Path

from mss.analysis.pdf_report_engine import PDFReportEngine
from mss.domain.backtest_result import BacktestResult
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

    stats.win_rate = 70

    stats.profit_factor = 3.4

    stats.expectancy = 60

    stats.max_drawdown = 120

    stats.equity_curve = [

        0,

        100,

        160,

        220,

        180,

        310,

        420,

        600,

    ]

    report = Report()

    report.processed_candles = 500

    report.generated_signals = 18

    report.executed_trades = 10

    report.execution_time = 0.42

    report.statistics = stats

    return report


def test_pdf_report_created(tmp_path):

    report = build_report()

    filename = PDFReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert Path(

        filename,

    ).exists()


def test_pdf_report_valid(tmp_path):

    report = build_report()

    PDFReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert report.valid


def test_pdf_report_file_name(tmp_path):

    report = build_report()

    filename = PDFReportEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert filename.endswith(

        ".pdf"

    )