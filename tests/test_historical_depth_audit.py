import copy

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


def rate(timestamp, **updates):
    row = {"time": timestamp, "open": 10.0, "high": 12.0, "low": 9.0, "close": 11.0,
           "tick_volume": 100, "spread": 2, "real_volume": 50}
    row.update(updates)
    return row


def rates(count, newest=2_000_000, step=900):
    return [rate(newest - step * (count - 1 - index)) for index in range(count)]


def test_progressive_depth_discovery_stops_on_short_return(monkeypatch):
    monkeypatch.setattr(HistoricalDepthAudit, "REQUEST_SIZES", (10, 20, 50))
    requests = []
    def fetch(symbol, timeframe, count):
        requests.append((symbol, timeframe, count))
        returned = min(count, 17)
        return rates(returned), {"code": 1, "message": "Success"}
    result, maximum = HistoricalDepthAudit.progressive_discovery(
        fetch, "BTCUSD", "BITCOIN", "CRYPTO", "M15", 3_000_000,
    )
    assert [row[2] for row in requests] == [10, 20]
    assert len(maximum) == result["total_available_candles"] == 17
    assert result["stop_reason"] == "RETURNED_FEWER_THAN_REQUESTED"


def test_completed_candle_filter_excludes_open_candle():
    source = [rate(1_000), rate(1_900)]
    assert HistoricalDepthAudit.completed_candles(source, "M15", 2_799) == [source[0]]
    assert HistoricalDepthAudit.completed_candles(source, "M15", 2_800) == source


def test_duplicate_detection_and_gap_reporting_are_separate():
    source = [rate(1_000), rate(1_900), rate(1_900), rate(3_700)]
    result = HistoricalDepthAudit.integrity(source, "M15", 10_000)
    assert result["duplicate_timestamp_count"] == 1
    assert result["gap_event_count"] == 1
    assert result["implied_missing_interval_count"] == 1
    assert result["chronological_order"] is True
    assert result["strictly_increasing_timestamps"] is False


def test_candle_hash_is_deterministic_and_content_sensitive():
    source = rates(3)
    assert HistoricalDepthAudit.candle_hash(source) == HistoricalDepthAudit.candle_hash(copy.deepcopy(source))
    changed = copy.deepcopy(source)
    changed[1]["close"] += 0.01
    assert HistoricalDepthAudit.candle_hash(source) != HistoricalDepthAudit.candle_hash(changed)


def test_depth_classification_thresholds():
    audit = HistoricalDepthAudit()
    assert audit.depth_classification(9_999) == "LIMITED_HISTORY"
    assert audit.depth_classification(10_000) == "MODERATE_HISTORY"
    assert audit.depth_classification(29_999) == "MODERATE_HISTORY"
    assert audit.depth_classification(30_000) == "DEEP_HISTORY"


def test_max_depth_stops_when_oldest_timestamp_does_not_move(monkeypatch):
    monkeypatch.setattr(HistoricalDepthAudit, "REQUEST_SIZES", (10, 20, 50))
    def fetch(symbol, timeframe, count):
        return [rate(1_000 + index * 900) for index in range(count)], None
    result, _ = HistoricalDepthAudit.progressive_discovery(
        fetch, "EURUSD", "EURUSD", "FOREX", "M15", 3_000_000,
    )
    assert result["stop_reason"] == "OLDEST_TIMESTAMP_NOT_MOVING"
    assert result["broker_depth_limit_reached"] is True


def test_canonical_broker_and_asset_class_are_preserved(monkeypatch):
    monkeypatch.setattr(HistoricalDepthAudit, "REQUEST_SIZES", (10,))
    result, _ = HistoricalDepthAudit.progressive_discovery(
        lambda symbol, timeframe, count: (rates(5), None),
        "ETHUSD", "ETHEREUM", "CRYPTO", "M15", 3_000_000,
    )
    assert (result["canonical_symbol"], result["broker_symbol"], result["asset_class"]) == ("ETHUSD", "ETHEREUM", "CRYPTO")
