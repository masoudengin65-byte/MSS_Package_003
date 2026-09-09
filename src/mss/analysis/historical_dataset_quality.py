"""Reproducible integrity and readiness audit of frozen M15 files; no strategy."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace('+00:00', 'Z')


def audit_rows(rows, start, end, warmup=500):
    errors = Counter()
    months = Counter()
    gaps = []
    spreads = []
    previous = None
    seen = set()
    performance = []
    warmup_count = 0
    zeros = Counter()
    for row in rows:
        epoch = row.get('time')
        if type(epoch) is not int:
            errors['invalid_timestamp_type'] += 1
            continue
        if epoch in seen:
            errors['duplicate_timestamp'] += 1
        seen.add(epoch)
        if epoch % 900:
            errors['unaligned_timestamp'] += 1
        if previous is not None and epoch <= previous:
            errors['non_increasing_timestamp'] += 1
        if previous is not None and epoch > previous + 900:
            first, stop = max(previous + 900, start), min(epoch, end)
            if stop > first:
                gaps.append({'start_utc': iso(first), 'end_utc_exclusive': iso(stop),
                             'slots': (stop-first)//900,
                             'weekend_slots': sum(datetime.fromtimestamp(t, timezone.utc).weekday() >= 5 for t in range(first, stop, 900)),
                             'closure_status': 'UNVERIFIED'})
        previous = epoch
        eligible = row.get('performance_eligible')
        expected = start <= epoch < end
        if type(eligible) is not bool or eligible != expected:
            errors['eligibility_mismatch'] += 1
        if epoch >= end:
            errors['at_or_after_exclusive_end'] += 1
        if epoch < start:
            warmup_count += 1
        numeric = [row.get(k) for k in ('open', 'high', 'low', 'close')]
        valid_price = all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in numeric)
        if not valid_price:
            errors['invalid_price'] += 1
        else:
            o, h, l, c = numeric
            if not l <= min(o,c) <= max(o,c) <= h:
                errors['invalid_ohlc_relationship'] += 1
        for name in ('spread', 'tick_volume', 'real_volume'):
            value = row.get(name)
            if type(value) is not int or value < 0:
                errors['invalid_'+name] += 1
            elif expected and value == 0:
                zeros[name] += 1
        if expected:
            performance.append(epoch)
            months[iso(epoch)[:7]] += 1
            if type(row.get('spread')) is int and row['spread'] >= 0:
                spreads.append(row['spread'])
    if warmup_count != warmup:
        errors['warmup_count_mismatch'] += 1
    if not performance or performance[0] != start:
        errors['missing_start_boundary'] += 1
    # Include uncovered leading/trailing calendar slots, even when likely closed.
    leading = max(0, (performance[0]-start)//900) if performance else (end-start)//900
    trailing = max(0, (end-performance[-1]-900)//900) if performance else 0
    spreads.sort()
    return {
        'row_count': len(rows), 'performance_rows': len(performance), 'warmup_rows': warmup_count,
        'integrity_errors': dict(errors), 'integrity_pass': not errors,
        'first_performance_utc': iso(performance[0]) if performance else None,
        'last_performance_utc': iso(performance[-1]) if performance else None,
        'calendar_slots': (end-start)//900,
        'internal_gap_count': len(gaps), 'internal_missing_slots': sum(g['slots'] for g in gaps),
        'internal_weekend_slots': sum(g['weekend_slots'] for g in gaps),
        'leading_missing_slots': leading, 'trailing_missing_slots': trailing,
        'largest_gaps': sorted(gaps, key=lambda g: (-g['slots'],g['start_utc']))[:10],
        'monthly_performance_rows': dict(sorted(months.items())),
        'zero_counts_performance_only': dict(zeros),
        'spread_points_median': spreads[len(spreads)//2] if spreads else None,
        'spread_points_max': max(spreads) if spreads else None,
        'gap_calendar_classification': 'UTC_DAY_PATTERN_ONLY_NOT_BROKER_CLOSURE_PROOF',
    }


def audit_dataset(root: Path):
    manifest_path = root / 'reports/MSS_Sprint93_3A_Four_Year_MT5_Dataset_Freeze_V2.json'
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    start = int(datetime.fromisoformat(manifest['window']['start_utc_inclusive'].replace('Z','+00:00')).timestamp())
    end = int(datetime.fromisoformat(manifest['window']['end_utc_exclusive'].replace('Z','+00:00')).timestamp())
    outputs = []
    for symbol in manifest['symbols']:
        path = root / manifest['provenance']['dataset_directory'] / symbol['dataset']['path']
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != symbol['dataset']['sha256']:
            raise ValueError('Frozen file hash mismatch: '+symbol['canonical_symbol'])
        rows = [json.loads(line) for line in raw.splitlines()]
        result = audit_rows(rows, start, end, manifest['window']['warmup_candles'])
        if result['row_count'] != symbol['dataset']['row_count']:
            raise ValueError('Frozen row count mismatch')
        result.update(symbol=symbol['canonical_symbol'], broker_symbol=symbol['broker_symbol'],
                      hash_verified=True)
        metadata = symbol['contract_metadata']
        currency = metadata['currency_profit']
        result['valuation'] = {
            'profit_currency': currency, 'contract_size_snapshot': metadata['trade_contract_size'],
            'minimum_volume_snapshot': metadata['volume_min'], 'calc_mode': metadata['trade_calc_mode'],
            'usd_conversion_route': 'IDENTITY' if currency == 'USD' else {'JPY':'INVERSE_USDJPY','CAD':'INVERSE_USDCAD'}.get(currency,'UNSUPPORTED'),
            'historical_contract_schedule_present': False,
            'historical_commission_schedule_present': False,
            'historical_swap_schedule_present': False,
            'slippage_model_preregistered': False,
            'current_tick_value_used': False,
        }
        outputs.append(result)
    return {
        'schema_version': 'MSS_SPRINT93_3A_DATA_QUALITY_V1',
        'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
        'window': manifest['window'], 'symbols': outputs,
        'all_integrity_checks_pass': all(x['integrity_pass'] for x in outputs),
        'total_rows': sum(x['row_count'] for x in outputs),
        'total_performance_rows': sum(x['performance_rows'] for x in outputs),
        'replay_eligible': False,
        'blockers': ['No historical broker calendar supplied to adjudicate gaps',
                     'Contract snapshot does not establish historical contract terms',
                     'Commission, swap and slippage assumptions require documented authority before net-profit replay'],
        'sources': ['https://www.mql5.com/en/docs/python_metatrader5/mt5copyratesrange_py',
                    'https://www.mql5.com/en/book/automation/experts/experts_ordercalcprofit'],
        'audit': {'raw_data_modified':False,'strategy_run':False,'orders_sent':False},
    }
