"""Classify reproducibility drift in frozen MT5 source windows."""


class FrozenSourceDriftAudit:
    VERSION="MSS_SPRINT92G4_FROZEN_SOURCE_DRIFT_AUDIT_V1"
    @staticmethod
    def classify(expected_count,actual_count,expected_first,actual_first,expected_last,actual_last,expected_hash,actual_hash):
        if actual_count!=expected_count: return 'COUNT_DRIFT'
        if actual_first!=expected_first or actual_last!=expected_last: return 'BOUNDARY_DRIFT'
        if actual_hash!=expected_hash: return 'CONTENT_REVISION_WITH_STABLE_BOUNDARIES'
        return 'EXACT_REPRODUCTION'
