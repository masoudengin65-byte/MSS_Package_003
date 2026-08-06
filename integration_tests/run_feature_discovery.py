"""Generate deterministic Sprint 84 feature-discovery artifacts."""

from mss.analysis.feature_discovery import FeatureDiscovery


def main():
    result = FeatureDiscovery().run(
        "reports/MSS_Historical_Backtest_Context_v1.xlsx",
        "reports/MSS_Feature_Discovery.xlsx",
        "reports/MSS_Feature_Discovery.json",
    )
    validation = result["data_validation"]
    print("TOTAL_TRADES", validation["trade_rows"])
    print("CLOSED_TRADES", validation["closed_trades"])
    print("UNRESOLVED_TRADES", validation["unresolved_trades"])
    print("RELIABLE_FEATURES", result["recommendations"]["measurable_features"])
    print("PRODUCTION_CONSIDERATION", result["recommendations"]["production_consideration_justified"])
    return result


if __name__ == "__main__":
    main()
