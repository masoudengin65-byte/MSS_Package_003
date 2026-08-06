"""Generate deterministic Sprint 83 shadow-score validation artifacts."""

from mss.analysis.shadow_score_validation import ShadowScoreValidation


def main():
    result = ShadowScoreValidation().run(
        "reports/MSS_Historical_Backtest_Context_v1.xlsx",
        "reports/MSS_Shadow_Score_Distribution.xlsx",
        "reports/MSS_Shadow_Score_Validation.xlsx",
        "reports/MSS_Shadow_Score_Validation.json",
    )
    integrity = result["data_integrity"]
    print("TOTAL_TRADES", integrity["total_historical_trades"])
    print("CLOSED_TRADES", integrity["closed_trades"])
    print("UNRESOLVED_TRADES", integrity["unresolved_trades"])
    print("MATCHED_TRADES", integrity["matched_trades"])
    print("SHADOW_SCORE_VERDICT", result["verdicts"]["shadow_score"])
    print("SHADOW_CONFIDENCE_VERDICT", result["verdicts"]["shadow_confidence"])
    return result


if __name__ == "__main__":
    main()
