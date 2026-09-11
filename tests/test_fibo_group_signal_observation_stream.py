from datetime import UTC, datetime, timedelta

from mss.analysis.fibo_group_signal_observation_stream import observe_histories
from mss.domain.candle import Candle


def _candle(index: int) -> Candle:
    return Candle(
        time=datetime(2024, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index),
        open=1.0,
        high=1.1,
        low=0.9,
        close=1.0,
        tick_volume=1,
        spread=2,
        real_volume=0,
    )


def test_observation_stream_has_no_trade_or_outcome_fields(monkeypatch):
    class _Result:
        valid = True
        bos_detected = True
        bos_direction = "BULLISH"

    monkeypatch.setattr(
        "mss.analysis.fibo_group_signal_observation_stream.SmartMoneyPipeline.run",
        lambda *_args, **_kwargs: _Result(),
    )
    histories = {
        symbol: [_candle(index) for index in range(202)]
        for symbol in ("EURUSD", "XAUUSD", "BTCUSD", "ETHUSD")
    }
    result = observe_histories(histories, {symbol: "hash" for symbol in histories})
    assert result["summary"]["observation_count"] == 8
    assert all("entry_price" not in row for row in result["observations"])
    assert all(
        row["position_carries_across_unadjudicated_gap"] is False
        for row in result["observations"]
    )
    assert result["outcome_boundary"]["net_profit_metric_emitted"] is False
    assert result["safety"]["order_send_called"] is False
