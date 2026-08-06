"""Generate deterministic Sprint 85 context-expansion artifacts."""

from mss.analysis.context_expansion_engine import ContextExpansionEngine


def main():
    result = ContextExpansionEngine().run(
        "reports/MSS_Historical_Backtest_Context_v1.xlsx",
        "reports/MSS_Context_Expansion_v1.xlsx",
        "reports/MSS_Context_Expansion_v1.json",
    )
    validation = result["data_validation"]
    print("TOTAL_TRADES", validation["trade_count"])
    print("CLOSED_TRADES", validation["closed_trade_count"])
    print("UNRESOLVED_TRADES", validation["unresolved_trade_count"])
    print("EXPANDED_FIELDS", validation["expanded_context_field_count"])
    print("PRODUCTION_CHANGE_JUSTIFIED", False)
    return result


if __name__ == "__main__":
    main()
