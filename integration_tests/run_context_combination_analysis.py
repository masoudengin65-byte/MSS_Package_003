"""Generate deterministic Sprint 88 context-combination artifacts."""

from mss.analysis.context_combination_analysis import ContextCombinationAnalysis


def main():
    result = ContextCombinationAnalysis().run(
        {
            "historical": "reports/MSS_Historical_Backtest_Context_v1.xlsx",
            "expanded": "reports/MSS_Context_Expansion_v1.xlsx",
            "mtf": "reports/MSS_MTF_Context_v1.xlsx",
            "smart_money": "reports/MSS_SmartMoney_Evidence_v1.xlsx",
            "feature_discovery": "reports/MSS_Feature_Discovery.json",
            "shadow_validation": "reports/MSS_Shadow_Score_Validation.json",
        },
        "reports/MSS_Context_Combination_Analysis.xlsx",
        "reports/MSS_Context_Combination_Analysis.json",
    )
    summary = result["summary"]
    print("TOTAL_TRADES", summary["trade_count"])
    print("CLOSED_TRADES", summary["closed_trade_count"])
    print("UNRESOLVED_TRADES", summary["unresolved_trade_count"])
    print("COMBINATION_DEFINITIONS", summary["combination_definition_count"])
    print("OBSERVED_PATTERNS", summary["observed_pattern_count"])
    print("ADEQUATE_SAMPLES", summary["adequate_sample_pattern_count"])
    print("PROMISING_PATTERNS", summary["promising_pattern_count"])
    print("FUTURE_INVESTIGATION", summary["future_investigation_justified"])
    print("PRODUCTION_CHANGE_JUSTIFIED", summary["production_change_justified"])
    return result


if __name__ == "__main__":
    main()
