"""Audit local frozen files and emit a separate, repeatable report."""
import json
from pathlib import Path
from mss.analysis.historical_dataset_quality import audit_dataset

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'reports/MSS_Sprint93_3A_Data_Quality_V1.json'

if __name__ == '__main__':
    report = audit_dataset(ROOT)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)+'\n', encoding='utf-8', newline='\n')
    print('QUALITY_REPORT', OUTPUT)
    print('INTEGRITY_PASS', report['all_integrity_checks_pass'])
    for s in report['symbols']:
        print(s['symbol'], 'rows', s['performance_rows'], 'gaps',s['internal_gap_count'],
              'missing',s['internal_missing_slots'], 'weekend',s['internal_weekend_slots'],
              'zero_spreads',s['zero_counts_performance_only'].get('spread',0),
              'largest',s['largest_gaps'][:1])
