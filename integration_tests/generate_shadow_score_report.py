"""Generate Sprint 82 report from the validated immutable Sprint 80 artifact."""

from mss.analysis.shadow_score_report_engine import ShadowScoreReportEngine


if __name__ == "__main__":
    output = ShadowScoreReportEngine().build_from_historical_workbook(
        "reports/MSS_Historical_Backtest_Context_v1.xlsx",
        "reports/MSS_Shadow_Score_Distribution.xlsx",
    )
    print("OUTPUT", output)
