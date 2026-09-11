from types import SimpleNamespace

from mss.analysis.fibo_group_cost_scenario_protocol import (
    EXPECTED_SERVER,
    build_protocol,
    collect_snapshot,
)


class FakeMt5:
    def account_info(self):
        return SimpleNamespace(server=EXPECTED_SERVER)

    def symbol_info(self, name):
        return SimpleNamespace(
            point=0.01,
            digits=2,
            spread=10,
            swap_long=-1.0,
            swap_short=1.0,
            swap_mode=1,
            swap_rollover3days=3,
            trade_contract_size=1.0,
            trade_tick_size=0.01,
            trade_tick_value=0.01,
            volume_min=0.01,
            volume_step=0.01,
            trade_mode=4,
            currency_profit="USD",
            currency_margin="USD",
        )


def test_protocol_is_current_reference_only_and_keeps_replay_closed():
    snapshot = collect_snapshot(FakeMt5(), "2026-09-11T00:00:00+00:00")
    result = build_protocol(snapshot)
    assert [item["name"] for item in result["scenarios"]] == [
        "BASELINE_CURRENT_REFERENCE",
        "CONSERVATIVE",
        "STRESSED",
    ]
    assert result["scenarios"][2]["inputs"][0]["spread_points"] == 20.0
    assert result["scenarios"][0]["inputs"][0]["commission_per_lot"] is None
    assert result["research_boundary"]["historical_net_profit_replay_eligible"] is False
    assert result["safety"]["order_send_called"] is False
