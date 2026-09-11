from mss.analysis.fibo_group_forward_shadow_preregistration import (
    FiboGroupForwardShadowPreregistration,
)


def test_fibo_forward_contract_is_independent_and_activation_blocked(tmp_path):
    result = FiboGroupForwardShadowPreregistration.build(tmp_path)
    assert result["experiment"]["canonical_to_broker_symbol"] == {
        "BTCUSD": "BTC",
        "ETHUSD": "ETH",
    }
    assert result["experiment"]["duration"] == "45_CALENDAR_DAYS"
    assert result["activation_contract"]["prior_alpari_manifest_reuse_allowed"] is False
    assert result["journal_contract"]["duplicate_boundary_rejected"] is True
    assert result["safety"]["order_send_called"] is False
    assert "BLOCKED" in result["protocol_state"]
