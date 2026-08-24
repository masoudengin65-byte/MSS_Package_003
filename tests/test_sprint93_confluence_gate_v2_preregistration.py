import hashlib,json,subprocess,sys
from pathlib import Path
import pytest
from mss.analysis.sprint93_confluence_gate_v2_preregistration import Sprint93ConfluenceGateV2Preregistration as C

ROOT=Path(__file__).resolve().parents[1]; RUNNER=ROOT/"integration_tests/run_sprint93_2a_confluence_gate_v2_preregistration.py"; REPORT=ROOT/"reports/MSS_Sprint93_2A_Confluence_Gate_V2_Preregistration.json"
def blob(path): return subprocess.run(["git","cat-file","blob",f"{C.BASELINE_COMMIT}:{path}"],cwd=ROOT,check=True,stdout=subprocess.PIPE).stdout
def inputs(): return [json.loads(blob(p)) for p in ("reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json","reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json","reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json")]
def hashes(): return {p:hashlib.sha256(blob(p)).hexdigest() for p in C.REQUIRED_STRATEGY_COMPONENT_FILES}
def build(): return C().build(*inputs(),hashes())

def test_v1_is_superseded_and_inert():
    r=build(); assert r["schema_version"].endswith("_V2"); assert r["execution_id"].endswith("_V2"); assert r["v1_supersession"]["v1_authorizes_eligible_forward_data"] is False; assert r["v1_supersession"]["candles_at_or_before_invalid_v1_boundary_eligible"] is False
def test_activation_is_blocked_and_null():
    r=build(); a=r["activation"]; assert r["protocol_state"]=="BLOCKED_PENDING_PAIRED_EXECUTION_FREEZE"; assert a["forward_data_eligible"] is False; assert a["first_eligible_candle_open_utc"] is None; assert a["exclusive_experiment_end_utc"] is None; assert a["activation_manifest"] is None; assert r["v1_supersession"]["candles_collected_before_activation_manifest_eligible"] is False
def test_activation_boundary_exact():
    assert C.activation_window("2026-08-25T10:00:00Z")==('2026-08-26T10:00:00Z','2026-10-10T10:00:00Z'); assert C.activation_window("2026-08-25T10:00:01Z")==('2026-08-26T10:15:00Z','2026-10-10T10:15:00Z')
def test_activation_requires_public_merge_and_all_freezes():
    a=build()["activation"]; assert a["public_merge_metadata_required"] is True; assert a["unverifiable_merge_metadata_result"]==C.PROTOCOL_STATE; assert a["freeze_required_before_activation"]==["paired executor","journal schema","valuation logic","risk logic","evaluation implementation"]
def test_complete_transitive_universe_and_omissions_fixed():
    required=set(C.REQUIRED_STRATEGY_COMPONENT_FILES); assert len(required)==40
    for path in ("src/mss/analysis/real_swing_engine.py","src/mss/analysis/setup_scoring_engine.py","src/mss/analysis/structure_engine.py","src/mss/domain/trade_signal.py","src/mss/analysis/shadow_risk_calculator.py","src/mss/analysis/shadow_trade_journal.py","src/mss/analysis/shadow_trade_valuation.py","src/mss/domain/risk_profile.py"): assert path in required
def test_exact_baseline_blob_hash_constants(): assert hashes()==C.EXPECTED_STRATEGY_COMPONENT_SHA256
@pytest.mark.parametrize("mutation",["missing","extra","nonhex","substituted","fabricated"])
def test_bad_identity_rejected(mutation):
    h=hashes()
    if mutation=="missing": h.pop(next(iter(h)))
    elif mutation=="extra": h["src/mss/domain/fake.py"]="0"*64
    elif mutation=="nonhex": h[next(iter(h))]="Z"*64
    elif mutation=="substituted":
        items=list(h.items()); h=dict(items[1:2]+items[0:1]+items[2:])
    else: h[next(iter(h))]="0"*64
    with pytest.raises(RuntimeError): C().build(*inputs(),h)
def test_crlf_checkout_irrelevant_to_blob_hashing(tmp_path):
    path=C.REQUIRED_STRATEGY_COMPONENT_FILES[0]; checkout=blob(path).replace(b"\n",b"\r\n"); assert hashlib.sha256(checkout).hexdigest()!=hashes()[path]; assert hashlib.sha256(blob(path)).hexdigest()==C.EXPECTED_STRATEGY_COMPONENT_SHA256[path]
def test_pairing_and_no_trade_semantics_frozen():
    g=build()["research_evaluation_gate"]; assert g["pair_key"]==["canonical_symbol","decision_candle_open_utc"]; assert g["pair_population"].startswith("UNION"); assert g["no_position_branch_net_r"]==0.0; assert len(g["retained_pair_labels"])==3; assert g["pair_settlement_utc"].startswith("LATER_EXIT")
def test_timebox_marking_and_metrics_frozen():
    r=build(); g=r["research_evaluation_gate"]; assert r["paired_forward_shadow_contract"]["no_new_entries_at_or_after_exclusive_end"] is True; assert "FINAL_ELIGIBLE_M15_CLOSE" in g["open_at_exclusive_end"]; assert "ACTUAL_CANDIDATE_POSITIONS_ONLY" in g["candidate_trade_metrics_population"]; assert "ZERO_R_IS_NON_WIN" in g["win_rate"]; assert g["profit_factor_zero_loss_behavior"]=={"positive_gains":"POSITIVE_INFINITY","no_positive_gains":0.0}
def test_drawdown_and_bootstraps_frozen():
    g=build()["research_evaluation_gate"]; assert g["drawdown_order"]==["pair_settlement_utc","canonical_symbol","decision_candle_open_utc"]; assert g["candidate_maximum_drawdown_must_be_lte_baseline"] is True
    for key in ("ordinary_bootstrap","moving_block_bootstrap"): assert g[key]["seed"]==9320260825 and g[key]["resamples"]==10000
    assert g["moving_block_bootstrap"]["circular_blocks"] is True; assert g["moving_block_bootstrap"]["block_length_pair_rows"]==8; assert g["bootstrap_pass_probability"]==.80; assert g["unavailable_integrity_result"]=="INCONCLUSIVE"
def test_committed_json_equals_complete_rebuild():
    r=build(); r["audit"]["deterministic_rebuild"]=True; r["source_git_blob_sha256"]={k:hashlib.sha256(blob(p)).hexdigest() for k,p in {"g5":"reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json","h6":"reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json","c2":"reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json"}.items()}; assert REPORT.read_bytes()==(json.dumps(r,indent=2,sort_keys=True,allow_nan=False)+"\n").encode()
def test_runner_verify_is_read_only_and_passes():
    before=REPORT.read_bytes(); result=subprocess.run([sys.executable,str(RUNNER),"--verify"],cwd=ROOT,text=True,stdout=subprocess.PIPE,check=True); assert "PREREGISTRATION_VERIFY_PASS" in result.stdout; assert REPORT.read_bytes()==before
def test_prohibited_access_and_behavior_disabled():
    r=build(); assert all(r["audit"][k] is False for k in ("mt5_accessed","strategy_replay_run","outcomes_analyzed","development_accessed","validation_accessed","quarantine_accessed","true_oos_accessed","production_behavior_changed","order_check_called","order_send_called")); assert r["paired_forward_shadow_contract"]["order_check_allowed"] is False; assert r["paired_forward_shadow_contract"]["order_send_allowed"] is False
