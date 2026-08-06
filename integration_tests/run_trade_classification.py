"""Generate the Sprint 78 diagnostic workbook from the validated baseline."""

from mss.analysis.trade_classification_engine import TradeClassificationEngine


if __name__ == "__main__":
    rows, output = TradeClassificationEngine().classify_workbook(
        "reports/MSS_Historical_Backtest.xlsx",
        "reports/MSS_Trade_Classification.xlsx",
    )
    print("SOURCE_ROWS", len(rows))
    print("CLOSED_TRADES", sum(row["Status"] == "CLOSED" for row in rows))
    print("OUTPUT", output)

