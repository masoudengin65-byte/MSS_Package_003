"""Helpers for freezing older and exploratory M15 historical windows."""

from mss.analysis.historical_depth_audit import HistoricalDepthAudit


class ExtendedHistoricalUniverseFreeze:
    COUNT = 50_000
    EXPLORATORY = (
        ("EURGBP", "EURGBP", "FOREX"), ("EURJPY", "EURJPY", "FOREX"),
        ("GBPJPY", "GBPJPY", "FOREX"), ("NZDUSD", "NZDUSD", "FOREX"),
        ("AUDJPY", "AUDJPY", "FOREX"), ("CADJPY", "CADJPY", "FOREX"),
        ("CHFJPY", "CHFJPY", "FOREX"), ("EURCHF", "EURCHF", "FOREX"),
        ("GBPCHF", "GBPCHF", "FOREX"), ("AUDCAD", "AUDCAD", "FOREX"),
        ("NZDJPY", "NZDJPY", "FOREX"), ("US30", "US30", "INDEX"),
        ("NAS100", "NAS100", "INDEX"), ("WTI", "WTI", "ENERGY"),
    )

    @classmethod
    def manifest_row(cls, canonical, broker, asset_class, rates, boundary_epoch, role, anchor):
        integrity = HistoricalDepthAudit.integrity(rates, "M15", boundary_epoch)
        times = [int(HistoricalDepthAudit._value(row, "time")) for row in rates]
        return {
            "canonical_symbol": canonical, "broker_symbol": broker, "asset_class": asset_class,
            "research_role": role, "timeframe": "M15", "requested_count": cls.COUNT,
            "returned_count": len(rates), "anchor_timestamp": anchor,
            "first_open_timestamp": HistoricalDepthAudit._iso(times[0]) if times else None,
            "last_open_timestamp": HistoricalDepthAudit._iso(times[-1]) if times else None,
            "ohlcv_sha256": HistoricalDepthAudit.candle_hash(rates) if times else None,
            "integrity": integrity,
            "eligible_for_future_replay": len(rates) >= 10_000 and integrity["strictly_increasing_timestamps"]
                and integrity["duplicate_timestamp_count"] == 0 and integrity["future_candle_count"] == 0,
        }

    @staticmethod
    def no_overlap(older, consumed_first_epoch):
        return not older or int(HistoricalDepthAudit._value(older[-1], "time")) <= consumed_first_epoch
