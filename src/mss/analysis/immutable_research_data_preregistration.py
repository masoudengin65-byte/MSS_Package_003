"""Preregister repository-native immutable Development candle storage."""
import hashlib,json


class ImmutableResearchDataPreregistration:
    VERSION="MSS_SPRINT92H1_IMMUTABLE_RESEARCH_DATA_PREREGISTRATION_V1"
    @staticmethod
    def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
    def build(self,manifest,drift,closure):
        drift_rows={x['canonical_symbol']:x for x in drift['symbols']}; symbols=[]
        for row in manifest['symbols']:
            dev=next(x for x in row['slices'] if x['slice']=='DEVELOPMENT')
            symbols.append({'canonical_symbol':row['canonical_symbol'],'broker_symbol':row['broker_symbol'],'asset_class':row['asset_class'],
                'candle_count':dev['candle_count'],'first_open_timestamp':dev['first_candle_open_timestamp'],'last_open_timestamp':dev['last_candle_open_timestamp'],
                'expected_ohlcv_sha256':dev['ohlcv_sha256'],'g4_live_development_slice_reproduced':drift_rows[row['canonical_symbol']]['development_slice_reproduced'],
                'target_path':f"research_data/sprint92h/development/{row['canonical_symbol']}_M15_30000.jsonl"})
        return {'schema_version':self.VERSION,'mode':'STORAGE_PREREGISTRATION_ONLY_NO_CANDLE_EXPORT','baseline_commit':'a5e7787',
            'purpose':'REMOVE_FUTURE_RESEARCH_DEPENDENCE_ON_MUTABLE_BROKER_HISTORY',
            'dataset_scope':{'segment':'SPRINT_92C2_DEVELOPMENT_ONLY','symbol_count':8,'candles_per_symbol':30000,'total_candles':240000,
                'validation_export_prohibited':True,'external_history_export_prohibited':True,'true_future_oos_export_prohibited':True,'symbols':symbols},
            'canonical_format':{'container':'ONE_UNCOMPRESSED_UTF8_JSONL_FILE_PER_SYMBOL','newline':'LF','row_order':'STRICTLY_ASCENDING_EPOCH_SECONDS',
                'json_serialization':'SORT_KEYS_TRUE_COMPACT_SEPARATORS_NO_NAN','fields_in_semantic_schema':['time_epoch_seconds','open','high','low','close','tick_volume','spread','real_volume'],
                'numeric_policy':'PRESERVE_MT5_FLOAT_AND_INTEGER_VALUES_WITH_PYTHON_JSON_ROUNDTRIP','header_row':False,'bom':False},
            'integrity_contract':{'verify_expected_development_ohlcv_sha256_before_write':True,'compute_sha256_for_each_jsonl_file':True,
                'write_once_no_overwrite':True,'atomic_temporary_write_then_rename':True,'reopen_and_rehash_after_write':True,
                'manifest_must_record_file_size_row_count_boundaries_content_hash_and_file_hash':True,'all_eight_or_fail_without_partial_promotion':True},
            'future_reader_contract':{'must_verify_file_sha256_before_parse':True,'must_verify_row_count_boundaries_and_ohlcv_sha256_after_parse':True,
                'must_not_fallback_to_mt5_on_verification_failure':True,'strategy_replay_requires_explicit_separate_protocol':True},
            'execution_policy':{'authoritative_exports':1,'raw_price_preview_before_export':False,'outcome_analysis':False,'strategy_replay':False,
                'failed_export_artifacts_must_be_quarantined_not_promoted':True},
            'source_hashes':{'c2_manifest_payload_sha256':self.digest(manifest),'g4_drift_payload_sha256':self.digest(drift),'g5_closure_payload_sha256':self.digest(closure)},
            'audit':{'mt5_accessed':False,'candles_exported':False,'strategy_replay_run':False,'outcomes_analyzed':False,'validation_accessed':False,'true_future_oos_used':False},
            'acceptance':{'all_eight_development_slices_currently_reproduce':all(x['g4_live_development_slice_reproduced'] for x in symbols),'scope_is_development_only':True,'immutable_storage_not_yet_created':True}}
