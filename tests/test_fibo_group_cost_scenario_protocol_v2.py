from pathlib import Path

from mss.analysis.fibo_group_cost_scenario_protocol_v2 import build_protocol


def test_v2_labels_current_commissions_without_clearing_historical_replay():
    result = build_protocol(Path(__file__).resolve().parents[1])
    baseline = {item["symbol"]: item for item in result["scenarios"][0]["inputs"]}
    stressed = {item["symbol"]: item for item in result["scenarios"][2]["inputs"]}
    assert baseline["EURUSD"]["commission_amount_per_lot"] == 3.0
    assert stressed["BTC"]["commission_rate_percent_notional"] == 0.3
    assert (
        result["research_boundary"]["unit_conversion_or_aggregation_performed"] is False
    )
    assert result["research_boundary"]["historical_net_profit_replay_eligible"] is False
    assert result["safety"]["order_send_called"] is False
