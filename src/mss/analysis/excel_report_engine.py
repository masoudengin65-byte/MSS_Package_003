"""
MSS Excel Report Engine
Version : 1.0
Sprint : 36.0
Compatible : v0.31
"""

from pathlib import Path

from openpyxl import Workbook

from mss.domain.report import Report


class ExcelReportEngine:

    def build(
        self,
        report: Report,
        output_folder="reports",
    ) -> str:

        folder = Path(output_folder)

        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        filename = folder / "Backtest_Report.xlsx"

        workbook = Workbook()

        sheet = workbook.active

        sheet.title = "Summary"

        #
        # Summary
        #

        sheet["A1"] = report.title

        sheet["A3"] = "Processed Candles"
        sheet["B3"] = report.processed_candles

        sheet["A4"] = "Generated Signals"
        sheet["B4"] = report.generated_signals

        sheet["A5"] = "Executed Trades"
        sheet["B5"] = report.executed_trades

        sheet["A6"] = "Execution Time"
        sheet["B6"] = report.execution_time

        #
        # Performance
        #

        s = report.statistics

        row = 9

        values = [

            ("Total Trades", s.total_trades),

            ("Winning Trades", s.winning_trades),

            ("Losing Trades", s.losing_trades),

            ("Breakeven Trades", s.breakeven_trades),

            ("Gross Profit", s.gross_profit),

            ("Gross Loss", s.gross_loss),

            ("Net Profit", s.net_profit),

            ("Win Rate", s.win_rate),

            ("Profit Factor", s.profit_factor),

            ("Expectancy", s.expectancy),

            ("Max Drawdown", s.max_drawdown),

        ]

        for name, value in values:

            sheet.cell(row=row, column=1).value = name

            sheet.cell(row=row, column=2).value = value

            row += 1

        #
        # Equity Curve
        #

        row += 2

        sheet.cell(row=row, column=1).value = "Equity Curve"

        row += 1

        for value in s.equity_curve:

            sheet.cell(row=row, column=1).value = value

            row += 1

        workbook.save(filename)

        return str(filename)