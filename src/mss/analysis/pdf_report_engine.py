"""
MSS PDF Report Engine
Version : 1.0
Sprint : 35.0
Compatible : v0.31
"""

from pathlib import Path

from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Paragraph
from reportlab.platypus import Spacer
from reportlab.lib.styles import getSampleStyleSheet

from mss.domain.report import Report


class PDFReportEngine:

    def __init__(self):

        self.styles = getSampleStyleSheet()

        try:

            pdfmetrics.registerFont(

                TTFont(

                    "DejaVu",

                    "DejaVuSans.ttf",

                )

            )

            self.styles["Normal"].fontName = "DejaVu"

            self.styles["Heading1"].fontName = "DejaVu"

            self.styles["Heading2"].fontName = "DejaVu"

        except Exception:

            pass

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

        filename = folder / "Backtest_Report.pdf"

        doc = SimpleDocTemplate(

            str(filename),

            rightMargin=1 * cm,

            leftMargin=1 * cm,

            topMargin=1 * cm,

            bottomMargin=1 * cm,

        )

        story = []

        #
        # Title
        #

        story.append(

            Paragraph(

                report.title,

                self.styles["Heading1"],

            )

        )

        story.append(

            Paragraph(

                report.subtitle,

                self.styles["Normal"],

            )

        )

        story.append(

            Spacer(

                1,

                0.5 * cm,

            )

        )

        #
        # Summary
        #

        story.append(

            Paragraph(

                "SUMMARY",

                self.styles["Heading2"],

            )

        )

        summary = [

            f"Processed Candles : {report.processed_candles}",

            f"Generated Signals : {report.generated_signals}",

            f"Executed Trades : {report.executed_trades}",

            f"Execution Time : {report.execution_time:.4f} sec",

        ]

        for line in summary:

            story.append(

                Paragraph(

                    line,

                    self.styles["Normal"],

                )

            )

        story.append(

            Spacer(

                1,

                0.4 * cm,

            )

        )

        #
        # Performance
        #

        s = report.statistics

        story.append(

            Paragraph(

                "PERFORMANCE",

                self.styles["Heading2"],

            )

        )

        performance = [

            f"Total Trades : {s.total_trades}",

            f"Winning Trades : {s.winning_trades}",

            f"Losing Trades : {s.losing_trades}",

            f"Breakeven Trades : {s.breakeven_trades}",

            f"Gross Profit : {s.gross_profit:.2f}",

            f"Gross Loss : {s.gross_loss:.2f}",

            f"Net Profit : {s.net_profit:.2f}",

            f"Win Rate : {s.win_rate:.2f} %",

            f"Profit Factor : {s.profit_factor:.2f}",

            f"Expectancy : {s.expectancy:.2f}",

        ]

        for line in performance:

            story.append(

                Paragraph(

                    line,

                    self.styles["Normal"],

                )

            )

        story.append(

            Spacer(

                1,

                0.4 * cm,

            )

        )

        #
        # Risk
        #

        story.append(

            Paragraph(

                "RISK",

                self.styles["Heading2"],

            )

        )

        story.append(

            Paragraph(

                f"Maximum Drawdown : {s.max_drawdown:.2f}",

                self.styles["Normal"],

            )

        )

        story.append(

            Spacer(

                1,

                0.4 * cm,

            )

        )

        #
        # Equity
        #

        story.append(

            Paragraph(

                "EQUITY CURVE",

                self.styles["Heading2"],

            )

        )

        story.append(

            Paragraph(

                str(

                    s.equity_curve

                ),

                self.styles["Normal"],

            )

        )

        doc.build(

            story

        )

        report.pdf_file = str(filename)

        report.valid = True

        return str(filename)