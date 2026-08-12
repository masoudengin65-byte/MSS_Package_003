import json
from pathlib import Path
from mss.analysis.external_historical_validation_closure import ExternalHistoricalValidationClosure


def test_closure_preserves_negative_results_and_sealed_oos():
    data=json.loads((Path(__file__).resolve().parents[1]/'reports/MSS_Sprint92E8_External_Historical_Validation_Closure.json').read_text(encoding='utf-8'))
    assert data['schema_version']==ExternalHistoricalValidationClosure.VERSION
    assert data['final_conclusions']['confirmed_robust_positive_symbols']==[]
    assert data['acceptance']['e4_usdjpy_not_confirmed'] is True
    assert data['acceptance']['e7_has_no_confirmed_symbol'] is True
    assert data['data_exposure_ledger']['true_future_oos_remains_sealed'] is True
    assert data['audit']['strategy_replay_run'] is False
    assert data['final_conclusions']['production_decision']=='NO_STRATEGY_OR_SYMBOL_FILTER_CHANGE'
