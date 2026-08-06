"""Generate Sprint 81 diagnostic edge-discovery artifacts."""

from mss.analysis.statistical_edge_discovery import StatisticalEdgeDiscovery


if __name__ == "__main__":
    result = StatisticalEdgeDiscovery().run(
        "reports/MSS_Historical_Backtest_Context_v1.xlsx",
        "reports/MSS_Historical_Backtest_Context_v1_audit.json",
        "reports/MSS_Statistical_Edge_Discovery.xlsx",
        "reports/MSS_Statistical_Edge_Discovery.json",
    )
    print("ANALYZED_CLOSED_TRADES", result["data_quality"]["closed_trades"])
    print("EXCLUDED_UNRESOLVED", result["data_quality"]["excluded_unresolved"])
    for label in ("RELIABLE_EDGE", "NEGATIVE_EDGE", "PROMISING_BUT_LIMITED"):
        print(label, sum(x["edge_label"] == label for x in result["edge_ranking"]))

