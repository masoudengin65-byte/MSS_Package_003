from pathlib import Path

from mss.analysis.equity_chart_engine import EquityChartEngine
from mss.domain.report import Report
from mss.domain.trade_statistics import TradeStatistics


def build_report():

    stats = TradeStatistics()

    stats.equity_curve = [

        0,
        120,
        180,
        260,
        220,
        350,
        420,
        510,
        620,

    ]

    report = Report()

    report.statistics = stats

    return report


def test_equity_chart_created(tmp_path):

    report = build_report()

    filename = EquityChartEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert Path(filename).exists()


def test_equity_chart_png(tmp_path):

    report = build_report()

    filename = EquityChartEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert filename.endswith(".png")


def test_equity_chart_not_empty(tmp_path):

    report = build_report()

    filename = EquityChartEngine().build(

        report,

        output_folder=tmp_path,

    )

    assert Path(filename).stat().st_size > 0