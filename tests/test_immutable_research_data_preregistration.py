import json
from pathlib import Path
from mss.analysis.immutable_research_data_preregistration import ImmutableResearchDataPreregistration


def test_h1_locks_development_only_write_once_storage():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92H1_Immutable_Research_Data_Preregistration.json').read_text(encoding='utf-8'))
    assert data['schema_version']==ImmutableResearchDataPreregistration.VERSION
    assert data['dataset_scope']['total_candles']==240000
    assert data['integrity_contract']['write_once_no_overwrite'] is True
    assert data['future_reader_contract']['must_not_fallback_to_mt5_on_verification_failure'] is True
    assert data['dataset_scope']['validation_export_prohibited'] is True
    assert data['audit']['candles_exported'] is False
    assert data['acceptance']['all_eight_development_slices_currently_reproduce'] is True
