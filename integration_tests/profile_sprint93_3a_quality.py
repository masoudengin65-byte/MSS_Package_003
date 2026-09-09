"""Bounded SQLite report projection over the deterministic audit."""
import json
import sqlite3
from pathlib import Path
from mss.analysis.historical_dataset_quality import audit_dataset

SQL = "SELECT json_extract(value, '$.symbol') AS symbol, json_extract(value, '$.performance_rows') AS rows, COALESCE(json_extract(value, '$.zero_counts_performance_only.spread'), 0) AS zeroSpreadRows, 1.0 * COALESCE(json_extract(value, '$.zero_counts_performance_only.spread'), 0) / json_extract(value, '$.performance_rows') AS zeroSpreadRate, json_extract(value, '$.internal_gap_count') AS gaps, json_extract(value, '$.internal_missing_slots') AS missingSlots, json_extract(value, '$.internal_weekend_slots') AS weekendSlots FROM json_each(:audit, '$.symbols') ORDER BY zeroSpreadRate DESC"

def profile():
    audit = audit_dataset(Path(__file__).resolve().parents[1])
    with sqlite3.connect(':memory:') as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(SQL, {'audit': json.dumps(audit)})]

if __name__ == '__main__':
    print(json.dumps(profile()))
