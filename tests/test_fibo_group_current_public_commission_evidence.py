from pathlib import Path

from mss.analysis.fibo_group_current_public_commission_evidence import build_evidence


def test_current_public_commission_evidence_is_not_historical_profit_evidence():
    result = build_evidence(Path(__file__).resolve().parents[1])
    references = {
        item["symbol"]: item for item in result["current_public_commission_reference"]
    }
    assert references["EURUSD"]["amount"] == 3.0
    assert references["BTC"]["rate_percent"] == 0.15
    assert (
        result["interpretation_boundary"]["current_public_terms_are_historical_terms"]
        is False
    )
    assert result["safety"]["order_send_called"] is False
