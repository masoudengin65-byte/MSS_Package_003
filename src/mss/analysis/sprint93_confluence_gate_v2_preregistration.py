"""Outcome-blind Sprint 93.2A V2 preregistration contract."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import math
import re


class Sprint93ConfluenceGateV2Preregistration:
    VERSION = "MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V3"
    EXECUTION_ID = "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V3"
    BASELINE_COMMIT = "fcad91029799a4cd5fdee1fe130f58334cf63452"
    PROTOCOL_STATE = "BLOCKED_PENDING_PAIRED_EXECUTION_FREEZE"
    INVALID_V1_BOUNDARY = "2026-08-23T20:15:00Z"
    BOOTSTRAP_SEED = 9320260825
    BOOTSTRAP_RESAMPLES = 10_000
    MOVING_BLOCK_LENGTH = 8

    STRATEGY_COMPONENT_ROOTS = tuple(
        sorted(
            (
                "src/mss/analysis/smart_money_pipeline.py",
                "src/mss/analysis/confluence_engine.py",
                "src/mss/analysis/confluence_gated_smart_money_pipeline.py",
                "src/mss/domain/pipeline_result.py",
                "src/mss/analysis/frozen_shadow_strategy_adapter.py",
                "src/mss/analysis/shadow_trade_engine.py",
                "src/mss/analysis/virtual_position_engine.py",
                "src/mss/analysis/risk_engine.py",
                "src/mss/analysis/shadow_risk_calculator.py",
                "src/mss/analysis/shadow_trade_journal.py",
                "src/mss/analysis/shadow_trade_valuation.py",
                "src/mss/domain/trade_signal.py",
                "src/mss/domain/risk_profile.py",
            )
        )
    )
    TRANSITIVE_STRATEGY_COMPONENT_FILES = (
        "src/mss/analysis/bos_detector.py",
        "src/mss/analysis/choch_detector.py",
        "src/mss/analysis/confluence_engine.py",
        "src/mss/analysis/confluence_gated_smart_money_pipeline.py",
        "src/mss/analysis/displacement_detector.py",
        "src/mss/analysis/frozen_shadow_strategy_adapter.py",
        "src/mss/analysis/fvg_detector.py",
        "src/mss/analysis/fvg_validator.py",
        "src/mss/analysis/liquidity_detector.py",
        "src/mss/analysis/order_block_detector.py",
        "src/mss/analysis/premium_discount_engine.py",
        "src/mss/analysis/real_swing_engine.py",
        "src/mss/analysis/risk_engine.py",
        "src/mss/analysis/setup_scoring_engine.py",
        "src/mss/analysis/shadow_risk_calculator.py",
        "src/mss/analysis/shadow_trade_engine.py",
        "src/mss/analysis/shadow_trade_journal.py",
        "src/mss/analysis/shadow_trade_valuation.py",
        "src/mss/analysis/smart_money_pipeline.py",
        "src/mss/analysis/structure_engine.py",
        "src/mss/analysis/structure_state.py",
        "src/mss/analysis/swing_detector.py",
        "src/mss/analysis/swing_filter.py",
        "src/mss/analysis/swing_validator.py",
        "src/mss/analysis/virtual_position_engine.py",
        "src/mss/config/settings.py",
        "src/mss/domain/analysis_result.py",
        "src/mss/domain/candle.py",
        "src/mss/domain/displacement.py",
        "src/mss/domain/fair_value_gap.py",
        "src/mss/domain/liquidity.py",
        "src/mss/domain/market_context.py",
        "src/mss/domain/order_block.py",
        "src/mss/domain/pipeline_result.py",
        "src/mss/domain/premium_discount.py",
        "src/mss/domain/risk_profile.py",
        "src/mss/domain/setup_score.py",
        "src/mss/domain/swing_point.py",
        "src/mss/domain/trade_setup.py",
        "src/mss/domain/trade_signal.py",
    )
    PACKAGE_INITIALIZER_FILES = (
        "src/mss/__init__.py",
        "src/mss/analysis/__init__.py",
    )
    REQUIRED_STRATEGY_COMPONENT_FILES = tuple(
        sorted(TRANSITIVE_STRATEGY_COMPONENT_FILES + PACKAGE_INITIALIZER_FILES)
    )
    EXPECTED_STRATEGY_COMPONENT_IDENTITY = (
        ("src/mss/__init__.py", "b3a65c460b1862136f011b1f5d8299b915af4c0bca3149cb3a8252f0b34d53bd"),
        ("src/mss/analysis/__init__.py", "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
        ("src/mss/analysis/bos_detector.py", "72f01833b1f5bff21984c9d4bba10cbcd94db395681db3fe43cb8a3617162676"),
        ("src/mss/analysis/choch_detector.py", "02a71e36ba507e9b70971022e80cb037ce5a3ff9fec4c569ddb93eb2a6e76eb9"),
        ("src/mss/analysis/confluence_engine.py", "ca075db045bd991073532ee1868b2cadbec4fde086d4674423ae5456d03b9609"),
        ("src/mss/analysis/confluence_gated_smart_money_pipeline.py", "f984643cfb63b2859c58b38aaf7a4a0fbdfffa80612cf393a14a3553504ef4df"),
        ("src/mss/analysis/displacement_detector.py", "c0384c5a548f4716e3314a16c0876ae5e2bba48af79225a89d6bfca5f98e0a71"),
        ("src/mss/analysis/frozen_shadow_strategy_adapter.py", "0cc57ad0e1b81eec6c58108ce4a97395b7885226159f4354a9359943f6ae319f"),
        ("src/mss/analysis/fvg_detector.py", "d75608efdaa82c75a6b6b9b0f517818e2358fc00524a099da9b84a8b880a2b38"),
        ("src/mss/analysis/fvg_validator.py", "ac039778cd297dd7385717ec809c12017e259b67b458cf16b1dbb13666c08c1d"),
        ("src/mss/analysis/liquidity_detector.py", "541825930858d532fb5f0b515b7f2d69067ef9373d4ad5d5a1399d7275629e9b"),
        ("src/mss/analysis/order_block_detector.py", "2c690199cffdc8e55c97ebf825b903d569d6283c2f3115ee33d99e6148f39c82"),
        ("src/mss/analysis/premium_discount_engine.py", "e39c8eab4c58b41bead0ad462ce5ff610710af2c5c84365862848a638d65cd23"),
        ("src/mss/analysis/real_swing_engine.py", "4439a6b264196cb790f26767ab7af934a5a96008d700f74662a8eb2b2ea5b8c6"),
        ("src/mss/analysis/risk_engine.py", "270557b72b004441f439dde4b009cb303a15f9f8491b6d9b5f5588c9fedf87d4"),
        ("src/mss/analysis/setup_scoring_engine.py", "0fcbc17e68f0c4d1ea4c72ae494a0b3ab6553f45f62ad72a1457fe8066a3f69a"),
        ("src/mss/analysis/shadow_risk_calculator.py", "7b684367217f3cab31c138287b6c79a1727d7e5dfe10f56b6b644137fe025b79"),
        ("src/mss/analysis/shadow_trade_engine.py", "b96a9bb797d1d4ab9ce9ae5cd68e81a1eca510c342cf290bb6060785f0b98a3c"),
        ("src/mss/analysis/shadow_trade_journal.py", "0d62760918b75c1f11391fc4cf28c64f08e1ea14c810f8759105c952503b8171"),
        ("src/mss/analysis/shadow_trade_valuation.py", "a8d3359e051c32a5eb515fa75468c823237813349935eebfe410fbf214f100d3"),
        ("src/mss/analysis/smart_money_pipeline.py", "704ecd5bd41073821e4697142af649a21016a7e9dfdfd0072c18d80173bab4c0"),
        ("src/mss/analysis/structure_engine.py", "ba854bc379dd63060aee7fb7f8a67e7034f57b7413074a9233527ba5a5ccc272"),
        ("src/mss/analysis/structure_state.py", "166424b9f013678bbf8f4bd8a162b508de543e07b9a17afd19b3862e1610557d"),
        ("src/mss/analysis/swing_detector.py", "6a68f9c89b8a5dbf6102c71538cc8d30757b59034762c94b03f3f4e0ce0d1d9f"),
        ("src/mss/analysis/swing_filter.py", "c06d828d9ddbb6b8f5efb717408876eaca1f394477ef5223624f5ddd4c265e41"),
        ("src/mss/analysis/swing_validator.py", "03b365e86b5c7062933178cb31b1db102f093ad1fed1dab02a6fc7bf8ce57133"),
        ("src/mss/analysis/virtual_position_engine.py", "445681972752a57d92a3c3d1670e5b7ca53f708444b839f8beeb77b03ba0e26b"),
        ("src/mss/config/settings.py", "e3e81da35a97d94c8174bc4c0922d0ccc46edfb334faecf409994d9d930f26b1"),
        ("src/mss/domain/analysis_result.py", "d07028f6fdea9d05aa89f18ec1df72edab277549bb0f1ab5954ee2d902c619c2"),
        ("src/mss/domain/candle.py", "3d20c425c5638a54e680a69dd9504e736c675ce9e4cd54b2656e239481893f12"),
        ("src/mss/domain/displacement.py", "8c2c0ef84b79e66d643deda8848f495049d3764f3d6c5893a2897c4ef06e8ba3"),
        ("src/mss/domain/fair_value_gap.py", "c4eef0bcdf0f961bd677a17abf6cecee9769d404d9b4eaa73643a54154b234b5"),
        ("src/mss/domain/liquidity.py", "0f36e936b435cd5af3c352efd50e8e760d63561f095f2a83fec0037a3b3822c4"),
        ("src/mss/domain/market_context.py", "1235c434e7fe3fc29b0c4d084a201c0052182f09a5d681477be0c0e4191bbe34"),
        ("src/mss/domain/order_block.py", "be0c4ba835d544a0e76345d0e0a2f31d3743dcb507e55f8406c22aca4ea889e5"),
        ("src/mss/domain/pipeline_result.py", "e1b3c4d324dec5887d984d9d25ef13d51eeb7cf2e49734aa5e8ba897e74fcb23"),
        ("src/mss/domain/premium_discount.py", "43d6e7daa8e6a377a061c37c1c8c69b797904d9ce6b556f02c9e1a6bdb71348e"),
        ("src/mss/domain/risk_profile.py", "89b97dec6cec6dbf78b94720723acc08edcf6daf6c03877ba26153a56bee8bb9"),
        ("src/mss/domain/setup_score.py", "5d9587e45aad7ce4a80f27e0f9c99ad76961b3c3848020ae55c980e703038104"),
        ("src/mss/domain/swing_point.py", "fa28955a2c1d06fef5e4f842f625ecaee62ff2c825f20a406bf17ede6aca2f96"),
        ("src/mss/domain/trade_setup.py", "06f345c7a15b8b44b2cd6b8b93538b061c0004c2b0d7dfe8e23ed70746c2bd84"),
        ("src/mss/domain/trade_signal.py", "faf2901f4a738e053fd58a56ba9ae8419af48b7fb154372ced5e16dba985782f"),
    )
    PROTECTED_SOURCE_ARTIFACTS = (
        (
            "reports/MSS_Sprint92G5_Confluence_Gate_Research_Closure.json",
            "MSS_SPRINT92G5_CONFLUENCE_GATE_RESEARCH_CLOSURE_V1",
            "988c3b6b27959eab8556b90dbb3a6caf28d1ca446649af38c554dd70c493e96b",
        ),
        (
            "reports/MSS_Sprint92H6_Immutable_Development_Research_Closure.json",
            "MSS_SPRINT92H6_IMMUTABLE_DEVELOPMENT_RESEARCH_CLOSURE_V1",
            "ce67778431af1cb33dd7e1d882a82a3e75d0c1f3e41c173b3e7550187d14a3c6",
        ),
        (
            "reports/MSS_Sprint92C2_Extended_Dataset_Manifest.json",
            "MSS_SPRINT92C2_EXTENDED_DATASET_MANIFEST_V1",
            "803678dfb2959616c03c5d2688ab16627ab9f3cb5adbb4edbd2a943063159d35",
        ),
    )
    SYMBOLS = (("BTCUSD", "BITCOIN"), ("ETHUSD", "ETHEREUM"))
    PAIR_RECORD_TYPES = (
        "BASELINE_ACTUAL_TRADE",
        "CANDIDATE_ACTUAL_TRADE",
        "BASELINE_NO_TRADE",
        "CANDIDATE_NO_TRADE",
        "TIMEBOX_MTM_CLOSE",
    )
    ACTUAL_TRADE_DENOMINATORS = (
        "actual_trade_count",
        "actual_trade_mean_r",
        "expectancy",
        "profit_factor",
        "win_rate",
        "maximum_drawdown",
        "minimum_sample_gates",
    )
    INTEGRITY_FAILURE_CATEGORIES = (
        "lookahead",
        "valuation",
        "risk",
        "journal",
        "pairing",
        "integrity",
    )
    ACTIVATION_MANIFEST_REQUIRED_FIELDS = (
        "activation_pr_url",
        "activation_pr_number",
        "activation_pr_public_merged_at_utc",
        "activation_merge_commit_sha",
        "manifest_created_at_utc",
        "python_version",
        "numpy_version",
        "paired_executor_identity",
        "baseline_strategy_identity",
        "candidate_strategy_identity",
        "journal_implementation_identity",
        "journal_schema_identity",
        "risk_implementation_identity",
        "valuation_implementation_identity",
        "evaluation_implementation_identity",
        "complete_transitive_execution_file_identity",
        "transitive_execution_file_universe_complete",
        "computed_first_eligible_m15_open_utc",
        "computed_exclusive_45_day_end_utc",
        "no_forward_outcome_access_before_activation",
        "all_data_before_computed_start_permanently_ineligible",
        "write_once",
    )

    @staticmethod
    def _parse_utc_z(value: object, label: str) -> datetime:
        if not isinstance(value, str) or not value.endswith("Z"):
            raise ValueError(f"{label} must be a UTC Z timestamp")
        try:
            parsed = datetime.fromisoformat(value[:-1] + "+00:00")
        except ValueError as exc:
            raise ValueError(f"{label} must be a UTC Z timestamp") from exc
        if parsed.tzinfo != timezone.utc:
            raise ValueError(f"{label} must be UTC")
        return parsed

    @classmethod
    def activation_window(cls, merged_at_utc: str) -> tuple[str, str]:
        merged = cls._parse_utc_z(merged_at_utc, "mergedAt")
        start = merged + timedelta(hours=24)
        needs_round = bool(start.second or start.microsecond or start.minute % 15)
        start = start.replace(second=0, microsecond=0)
        if needs_round:
            start += timedelta(minutes=15 - start.minute % 15)
        render = lambda value: value.strftime("%Y-%m-%dT%H:%M:%SZ")
        return render(start), render(start + timedelta(days=45))

    @staticmethod
    def _require_sha256(value: object, label: str) -> None:
        if not isinstance(value, str) or len(value) != 64 or re.fullmatch(r"[0-9a-f]{64}", value) is None:
            raise RuntimeError(f"{label} must be exactly 64 lowercase hexadecimal characters")

    @staticmethod
    def _require_full_git_sha(value: object, label: str) -> None:
        if not isinstance(value, str) or len(value) != 40 or re.fullmatch(r"[0-9a-f]{40}", value) is None:
            raise RuntimeError(f"{label} must be an exact full 40-character commit SHA")

    @classmethod
    def _validate_component_identity(
        cls,
        baseline_commit: object,
        component_identity: object,
    ) -> None:
        cls._require_full_git_sha(baseline_commit, "baseline_commit")
        if baseline_commit != cls.BASELINE_COMMIT:
            raise RuntimeError("component identity is not bound to the frozen baseline commit")
        if not isinstance(component_identity, tuple) or not all(
            isinstance(item, tuple) and len(item) == 2 for item in component_identity
        ):
            raise RuntimeError("component identity must be an immutable tuple of immutable pairs")
        paths = tuple(item[0] for item in component_identity)
        if paths != cls.REQUIRED_STRATEGY_COMPONENT_FILES:
            raise RuntimeError("strategy-component identity path universe/order mismatch")
        for path, digest in component_identity:
            if not isinstance(path, str):
                raise RuntimeError("strategy-component identity path must be text")
            cls._require_sha256(digest, f"strategy-component SHA256 for {path}")
        if component_identity != cls.EXPECTED_STRATEGY_COMPONENT_IDENTITY:
            raise RuntimeError("strategy-component identity hash mismatch")

    @classmethod
    def validate_pair_record(cls, record: object) -> dict[str, object]:
        """Validate a fabricated pair record without executing or inspecting outcomes."""
        if not isinstance(record, Mapping) or set(record) != {
            "pair_key",
            "baseline_member",
            "candidate_member",
        }:
            raise RuntimeError("invalid pair record shape")
        pair_key = record["pair_key"]
        if not isinstance(pair_key, tuple) or len(pair_key) != 2 or not all(
            isinstance(value, str) and value for value in pair_key
        ):
            raise RuntimeError("pair key must be exactly (canonical_symbol, decision_candle_open_utc)")

        projected: dict[str, object] = {"pair_key": pair_key}
        actual_members = 0
        for branch in ("baseline", "candidate"):
            member = record[f"{branch}_member"]
            if not isinstance(member, Mapping) or set(member) != {
                "record_type",
                "actual_trade_net_r",
                "terminal_settlement_utc",
            }:
                raise RuntimeError(f"invalid {branch} member shape")
            record_type = member["record_type"]
            permitted = {
                f"{branch.upper()}_ACTUAL_TRADE",
                f"{branch.upper()}_NO_TRADE",
                "TIMEBOX_MTM_CLOSE",
            }
            if record_type not in permitted:
                raise RuntimeError(f"invalid {branch} record type")
            is_no_trade = record_type == f"{branch.upper()}_NO_TRADE"
            net_r = member["actual_trade_net_r"]
            settlement = member["terminal_settlement_utc"]
            if is_no_trade:
                if net_r is not None or settlement is not None:
                    raise RuntimeError("no-trade member cannot masquerade as an actual trade")
                projected[f"{branch}_paired_r"] = 0.0
                projected[f"{branch}_is_actual_trade"] = False
            else:
                if isinstance(net_r, bool) or not isinstance(net_r, (int, float)) or not math.isfinite(net_r):
                    raise RuntimeError("actual trade requires finite net R, including an allowed exact 0.0 R")
                if not isinstance(settlement, str) or not settlement:
                    raise RuntimeError("actual trade requires terminal settlement")
                actual_members += 1
                projected[f"{branch}_paired_r"] = float(net_r)
                projected[f"{branch}_is_actual_trade"] = True
                projected[f"{branch}_is_timebox_mtm"] = record_type == "TIMEBOX_MTM_CLOSE"
        if actual_members == 0:
            raise RuntimeError("pair population requires an actual virtual position in at least one branch")
        projected["candidate_minus_baseline_r"] = (
            projected["candidate_paired_r"] - projected["baseline_paired_r"]
        )
        return projected

    @classmethod
    def _path_hash_records(cls, records: object, label: str) -> tuple[tuple[str, str], ...]:
        if not isinstance(records, list) or not records:
            raise RuntimeError(f"{label} must be a non-empty ordered list")
        identity = []
        for record in records:
            if not isinstance(record, Mapping) or set(record) != {"path", "git_blob_sha256"}:
                raise RuntimeError(f"invalid {label} record")
            path = record["path"]
            if not isinstance(path, str) or not path:
                raise RuntimeError(f"invalid {label} path")
            cls._require_sha256(record["git_blob_sha256"], f"{label} SHA256 for {path}")
            identity.append((path, record["git_blob_sha256"]))
        result = tuple(identity)
        paths = tuple(path for path, _ in result)
        if paths != tuple(sorted(paths)) or len(paths) != len(set(paths)):
            raise RuntimeError(f"{label} paths must be unique and ordered")
        return result

    @classmethod
    def validate_activation_manifest(
        cls,
        manifest: object,
        *,
        public_pr_metadata: Mapping[str, object],
        publication_metadata: Mapping[str, object],
        runtime_versions: Mapping[str, object],
        observed_execution_identity: tuple[tuple[str, str], ...],
        no_forward_outcome_access_verified: bool,
        existing_manifest: object = None,
    ) -> bool:
        """Validate a future activation manifest while leaving this protocol blocked."""
        if existing_manifest is not None:
            raise RuntimeError("activation manifest is write-once and cannot be replaced")
        if not isinstance(manifest, Mapping):
            raise RuntimeError("activation manifest must be a mapping")
        missing = [field for field in cls.ACTIVATION_MANIFEST_REQUIRED_FIELDS if field not in manifest]
        if missing:
            raise RuntimeError(f"activation manifest missing required fields: {missing}")
        if manifest["write_once"] is not True:
            raise RuntimeError("activation manifest must be write-once")
        if manifest["transitive_execution_file_universe_complete"] is not True:
            raise RuntimeError("activation execution-file universe must be declared complete")
        if manifest["all_data_before_computed_start_permanently_ineligible"] is not True:
            raise RuntimeError("all data before the computed start must remain permanently ineligible")
        if manifest["no_forward_outcome_access_before_activation"] is not True or no_forward_outcome_access_verified is not True:
            raise RuntimeError("pre-activation no-forward-outcome-access proof is required")

        required_public_metadata = {"url", "number", "state", "mergedAt", "merge_commit_sha"}
        if not isinstance(public_pr_metadata, Mapping) or not required_public_metadata.issubset(public_pr_metadata):
            raise RuntimeError("complete public activation PR metadata is required")
        if public_pr_metadata["state"] != "MERGED":
            raise RuntimeError("activation PR must already be merged")
        if isinstance(manifest["activation_pr_number"], bool) or not isinstance(manifest["activation_pr_number"], int) or manifest["activation_pr_number"] <= 0:
            raise RuntimeError("activation PR number must be a positive integer")
        if not isinstance(manifest["activation_pr_url"], str) or not manifest["activation_pr_url"].startswith("https://"):
            raise RuntimeError("activation PR URL must be public HTTPS metadata")
        public_bindings = (
            (manifest["activation_pr_url"], public_pr_metadata["url"]),
            (manifest["activation_pr_number"], public_pr_metadata["number"]),
            (manifest["activation_pr_public_merged_at_utc"], public_pr_metadata["mergedAt"]),
            (manifest["activation_merge_commit_sha"], public_pr_metadata["merge_commit_sha"]),
        )
        if any(manifest_value != public_value for manifest_value, public_value in public_bindings):
            raise RuntimeError("activation manifest does not match public merged PR metadata")
        cls._require_full_git_sha(manifest["activation_merge_commit_sha"], "activation merge commit")

        if manifest["python_version"] != runtime_versions.get("python_version") or manifest["numpy_version"] != runtime_versions.get("numpy_version"):
            raise RuntimeError("activation runtime versions do not match the frozen environment")
        if not all(isinstance(manifest[field], str) and manifest[field] for field in ("python_version", "numpy_version")):
            raise RuntimeError("Python and NumPy versions must be frozen")

        merged_at = cls._parse_utc_z(manifest["activation_pr_public_merged_at_utc"], "activation mergedAt")
        created_at = cls._parse_utc_z(manifest["manifest_created_at_utc"], "manifest creation")
        committed_at = cls._parse_utc_z(publication_metadata.get("manifest_committed_at_utc"), "manifest commit")
        pushed_at = cls._parse_utc_z(publication_metadata.get("manifest_publicly_pushed_at_utc"), "manifest public push")
        computed_start, computed_end = cls.activation_window(manifest["activation_pr_public_merged_at_utc"])
        if manifest["computed_first_eligible_m15_open_utc"] != computed_start or manifest["computed_exclusive_45_day_end_utc"] != computed_end:
            raise RuntimeError("activation window does not match public mergedAt")
        start_at = cls._parse_utc_z(computed_start, "computed activation start")
        if not (merged_at < created_at <= committed_at <= pushed_at < start_at):
            raise RuntimeError("manifest must be created after merge and committed/publicly pushed before start; a new activation PR is required")

        universe = cls._path_hash_records(
            manifest["complete_transitive_execution_file_identity"],
            "complete execution-file identity",
        )
        if not isinstance(observed_execution_identity, tuple) or not all(
            isinstance(item, tuple) and len(item) == 2 for item in observed_execution_identity
        ):
            raise RuntimeError("observed execution identity must be an immutable ordered tuple")
        for path, digest in observed_execution_identity:
            if not isinstance(path, str):
                raise RuntimeError("observed execution identity path must be text")
            cls._require_sha256(digest, f"observed Git blob SHA256 for {path}")
        if observed_execution_identity != universe:
            raise RuntimeError("activation execution-file hash mismatch")
        universe_map = dict(universe)

        implementation_fields = (
            "paired_executor_identity",
            "journal_implementation_identity",
            "risk_implementation_identity",
            "valuation_implementation_identity",
            "evaluation_implementation_identity",
        )
        for field in implementation_fields:
            record = manifest[field]
            if not isinstance(record, Mapping) or set(record) != {"path", "git_blob_sha256"}:
                raise RuntimeError(f"invalid {field}")
            cls._require_sha256(record["git_blob_sha256"], f"{field} SHA256")
            if universe_map.get(record["path"]) != record["git_blob_sha256"]:
                raise RuntimeError(f"{field} does not match the execution-file universe")

        journal_schema = manifest["journal_schema_identity"]
        if not isinstance(journal_schema, Mapping) or set(journal_schema) != {
            "schema_identifier",
            "implementation_path",
            "git_blob_sha256",
        }:
            raise RuntimeError("invalid journal schema identity")
        if not isinstance(journal_schema["schema_identifier"], str) or not journal_schema["schema_identifier"]:
            raise RuntimeError("journal schema identifier must be frozen")
        cls._require_sha256(journal_schema["git_blob_sha256"], "journal schema implementation SHA256")
        if universe_map.get(journal_schema["implementation_path"]) != journal_schema["git_blob_sha256"]:
            raise RuntimeError("journal schema identity does not match the execution-file universe")

        for field in ("baseline_strategy_identity", "candidate_strategy_identity"):
            identity = manifest[field]
            if not isinstance(identity, Mapping) or set(identity) != {"strategy_identifier", "path_git_blob_sha256"}:
                raise RuntimeError(f"invalid {field}")
            if not isinstance(identity["strategy_identifier"], str) or not identity["strategy_identifier"]:
                raise RuntimeError(f"{field} identifier must be frozen")
            for path, digest in cls._path_hash_records(identity["path_git_blob_sha256"], field):
                if universe_map.get(path) != digest:
                    raise RuntimeError(f"{field} does not match the execution-file universe")
        return True

    def build(
        self,
        *,
        baseline_commit: str,
        component_identity: tuple[tuple[str, str], ...],
    ) -> dict[str, object]:
        self._validate_component_identity(baseline_commit, component_identity)
        return {
            "schema_version": self.VERSION,
            "execution_id": self.EXECUTION_ID,
            "baseline_commit": self.BASELINE_COMMIT,
            "protocol_state": self.PROTOCOL_STATE,
            "mode": "PREREGISTRATION_ONLY_NO_MT5_NO_MARKET_DATA_NO_REPLAY_NO_OUTCOME_INSPECTION_NO_PRODUCTION_CHANGE",
            "v1_supersession": {
                "superseded_schema_version": "MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V1",
                "superseded_execution_id": "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V1",
                "invalid_v1_boundary_utc": self.INVALID_V1_BOUNDARY,
                "v1_authorizes_eligible_forward_data": False,
                "candles_at_or_before_invalid_v1_boundary_eligible": False,
                "candles_collected_before_activation_manifest_eligible": False,
            },
            "v2_supersession": {
                "superseded_schema_version": "MSS_SPRINT93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_PREREGISTRATION_V2",
                "superseded_execution_id": "MSS_93_2A_CONFLUENCE_GATE_V2_FORWARD_SHADOW_V2",
                "supersession_reason": "OUTCOME_BLIND_SHARED_JOURNAL_SAFETY_HARDENING_BEFORE_ACTIVATION",
                "v2_authorizes_eligible_forward_data": False,
                "forward_outcomes_observed_before_v3_freeze": False,
                "candles_collected_before_v3_activation_manifest_eligible": False,
            },
            "activation": {
                "forward_data_eligible": False,
                "first_eligible_candle_open_utc": None,
                "exclusive_experiment_end_utc": None,
                "activation_manifest": None,
                "required_precondition": "SEPARATE_PAIRED_EXECUTION_FREEZE_PR_ALREADY_MERGED",
                "public_merge_metadata_required": True,
                "unverifiable_or_invalid_manifest_result": self.PROTOCOL_STATE,
                "boundary_rule": "CEIL_TO_M15(ACTIVATION_PR_PUBLIC_MERGED_AT_UTC_PLUS_EXACTLY_24_HOURS)",
                "end_rule": "COMPUTED_FIRST_ELIGIBLE_M15_OPEN_PLUS_EXACTLY_45_TIMES_24_HOURS_EXCLUSIVE",
                "write_once_manifest_required_fields": list(self.ACTIVATION_MANIFEST_REQUIRED_FIELDS),
                "manifest_validation_context_required": [
                    "public merged activation PR metadata",
                    "public manifest commit and push timestamps",
                    "observed Git-blob SHA256 identity at full merge commit",
                    "exact Python and NumPy versions",
                    "external proof of no pre-activation forward-outcome access",
                    "absence of any existing activation manifest",
                ],
                "activation_rules": {
                    "activation_pr_must_be_merged_before_manifest_creation": True,
                    "manifest_commit_and_public_push_must_be_strictly_before_start": True,
                    "commit_or_push_at_or_after_start_requires_new_activation_pr_and_boundary": True,
                    "retroactive_activation_allowed": False,
                    "hash_mismatch_keeps_activation_blocked": True,
                    "all_pre_start_data_permanently_ineligible": True,
                    "manifest_write_once": True,
                },
            },
            "candidate_contract": {
                "baseline": "UNCHANGED_SMART_MONEY_PIPELINE",
                "candidate": "CONFLUENCE_GATED_SMART_MONEY_PIPELINE",
                "single_change": "ENTRY_ELIGIBLE_ONLY_WHEN_EXISTING_CONFLUENCE_ENGINE_RETURNS_VALID_DIRECTION_MATCHING_BOS",
                "numeric_strategy_thresholds_unchanged": True,
                "production_pipeline_replacement": False,
            },
            "paired_forward_shadow_contract": {
                "symbols": [
                    {"canonical_symbol": canonical, "broker_symbol": broker, "timeframe": "M15"}
                    for canonical, broker in self.SYMBOLS
                ],
                "timebox_calendar_days": 45,
                "extension_after_timebox": False,
                "no_new_entries_at_or_after_exclusive_end": True,
                "final_eligible_completed_candle_timeframe": "M15",
                "order_check_allowed": False,
                "order_send_allowed": False,
                "real_order_allowed": False,
            },
            "research_evaluation_gate": {
                "pair_key": ["canonical_symbol", "decision_candle_open_utc"],
                "pair_population": "UNION_OF_DECISION_TIMESTAMPS_WHERE_EITHER_BRANCH_OPENS_AN_ACTUAL_VIRTUAL_POSITION",
                "pair_record_schema": {
                    "record_types": list(self.PAIR_RECORD_TYPES),
                    "baseline_member_types": [
                        "BASELINE_ACTUAL_TRADE",
                        "BASELINE_NO_TRADE",
                        "TIMEBOX_MTM_CLOSE",
                    ],
                    "candidate_member_types": [
                        "CANDIDATE_ACTUAL_TRADE",
                        "CANDIDATE_NO_TRADE",
                        "TIMEBOX_MTM_CLOSE",
                    ],
                    "timebox_mtm_branch_is_given_by_member_slot": True,
                    "no_trade_actual_trade_net_r": None,
                    "no_trade_paired_difference_projection_r": 0.0,
                    "actual_zero_r_remains_actual_trade": True,
                    "actual_zero_r_is_non_win": True,
                    "actual_zero_r_included_in": list(self.ACTUAL_TRADE_DENOMINATORS),
                    "actual_zero_r_profit_factor_contribution": {
                        "positive_sum_r": 0.0,
                        "negative_sum_r": 0.0,
                    },
                    "pair_requires_at_least_one_actual_trade_member": True,
                },
                "pair_settlement_utc": "LATEST_TERMINAL_SETTLEMENT_UTC_OF_ACTUAL_TRADE_MEMBERS_INCLUDING_ZERO_R",
                "no_trade_semantics": {
                    "contributes_zero_only_to_paired_difference": True,
                    "excluded_from": list(self.ACTUAL_TRADE_DENOMINATORS),
                },
                "timebox_mtm_close": {
                    "record_type": "TIMEBOX_MTM_CLOSE",
                    "valuation_candle": "FINAL_ELIGIBLE_COMPLETED_M15_CANDLE_BEFORE_EXCLUSIVE_END",
                    "uses_frozen_cost_and_valuation_model": True,
                    "applies_to_every_position_still_open_at_exclusive_end": True,
                    "deterministic": True,
                    "is_terminal_settled_actual_trade": True,
                    "included_in": list(self.ACTUAL_TRADE_DENOMINATORS),
                },
                "metric_definitions": {
                    "actual_trade_mean_r": "SUM(ACTUAL_TRADE_NET_R) / ACTUAL_TERMINAL_SETTLED_TRADE_COUNT",
                    "expectancy": "WIN_RATE * MEAN_POSITIVE_R - NON_WIN_RATE * MEAN_ABSOLUTE_NON_POSITIVE_R",
                    "mean_positive_r": "SUM(POSITIVE_ACTUAL_TRADE_NET_R) / COUNT(ACTUAL_TRADE_NET_R > 0)",
                    "mean_absolute_non_positive_r": "SUM(ABS(NON_POSITIVE_ACTUAL_TRADE_NET_R)) / COUNT(ACTUAL_TRADE_NET_R <= 0)",
                    "expectancy_zero_r_rule": "ZERO_R_ACTUAL_TRADES_ARE_INCLUDED_AMONG_NON_WINS",
                    "profit_factor": "SUM(POSITIVE_ACTUAL_TRADE_NET_R) / ABS(SUM(NEGATIVE_ACTUAL_TRADE_NET_R))",
                    "profit_factor_zero_loss_behavior": {
                        "positive_sum_greater_than_zero": "POSITIVE_INFINITY",
                        "positive_infinity_passes_threshold": True,
                        "positive_and_negative_sums_both_zero": 0.0,
                    },
                    "win_rate": "COUNT(ACTUAL_TRADE_NET_R > 0) / ACTUAL_TERMINAL_SETTLED_TRADE_COUNT",
                    "maximum_drawdown": "MAXIMUM_PEAK_TO_TROUGH_DECLINE_OF_CUMULATIVE_TERMINAL_SETTLED_NET_R_BEGINNING_AT_0.0_R",
                    "pooled_order": [
                        "pair_settlement_utc",
                        "canonical_symbol",
                        "decision_candle_open_utc",
                    ],
                },
                "gates": [
                    {"name": "paired_pooled_candidate_minus_baseline_mean_r", "operator": ">", "threshold": 0.0},
                    {"name": "candidate_actual_trade_pooled_mean_r", "operator": ">", "threshold": 0.0},
                    {"name": "candidate_actual_trade_pooled_expectancy", "operator": ">", "threshold": 0.0},
                    {"name": "candidate_pooled_profit_factor", "operator": ">=", "threshold": 1.10},
                    {"name": "candidate_pooled_win_rate", "operator": ">=", "threshold": 0.36},
                    {"name": "candidate_maximum_drawdown_r", "operator": "<=", "threshold": "BASELINE_MAXIMUM_DRAWDOWN_R"},
                    {"name": "candidate_terminal_settled_actual_trades_pooled", "operator": ">=", "threshold": 50},
                    {"name": "candidate_terminal_settled_actual_trades_per_symbol", "operator": ">=", "threshold": 15},
                    {"name": "ordinary_bootstrap_probability_paired_mean_difference_gt_zero", "operator": ">=", "threshold": 0.80},
                    {"name": "moving_block_bootstrap_probability_paired_mean_difference_gt_zero", "operator": ">=", "threshold": 0.80},
                    {"name": "failure_counts", "operator": "==", "threshold": 0, "categories": list(self.INTEGRITY_FAILURE_CATEGORIES)},
                ],
                "bootstrap": {
                    "input": "PAIRED_CANDIDATE_R_MINUS_BASELINE_R",
                    "symbol_strata_preserved": True,
                    "within_symbol_order": ["decision_candle_open_utc", "pair_key"],
                    "resamples": self.BOOTSTRAP_RESAMPLES,
                    "rng": {
                        "api": "numpy.random.Generator",
                        "bit_generator": "numpy.random.PCG64",
                        "construction": "numpy.random.Generator(numpy.random.PCG64(seed))",
                        "seed": self.BOOTSTRAP_SEED,
                    },
                    "runtime_versions_must_be_frozen_in_activation_manifest": ["python_version", "numpy_version"],
                    "ordinary": {
                        "symbols_sampled_independently": True,
                        "sampling": "WITH_REPLACEMENT",
                        "per_symbol_sample_count": "ORIGINAL_SYMBOL_PAIR_COUNT",
                        "pool_completed_symbol_samples": True,
                    },
                    "moving_block": {
                        "circular_wrapping": True,
                        "block_length_pair_rows": self.MOVING_BLOCK_LENGTH,
                        "block_start_indices": "UNIFORM_WITH_REPLACEMENT",
                        "blocks_per_symbol": "CEIL(SYMBOL_PAIR_COUNT / 8)",
                        "concatenate_blocks": True,
                        "truncate_to_original_symbol_pair_count": True,
                        "pool_completed_symbol_samples": True,
                    },
                    "probability": "EXACT_FRACTION_OF_10000_RESAMPLED_POOLED_MEANS_STRICTLY_GREATER_THAN_ZERO",
                    "empty_incomplete_or_structurally_invalid_population_result": "INCONCLUSIVE",
                    "inconclusive_can_pass": False,
                },
            },
            "strategy_component_identity": {
                "identity_type": "FROZEN_ORDERED_BASELINE_GIT_BLOB_SHA256_IDENTITY",
                "baseline_commit": self.BASELINE_COMMIT,
                "roots": list(self.STRATEGY_COMPONENT_ROOTS),
                "transitive_closure_file_count": len(self.TRANSITIVE_STRATEGY_COMPONENT_FILES),
                "package_initializer_file_count": len(self.PACKAGE_INITIALIZER_FILES),
                "ordered_path_sha256": [
                    {"path": path, "sha256": digest} for path, digest in component_identity
                ],
                "must_be_extended_by_write_once_activation_manifest": True,
                "paired_executor_present": False,
            },
            "protected_source_artifacts": [
                {
                    "path": path,
                    "schema_identifier": schema_identifier,
                    "expected_sha256": expected_sha256,
                }
                for path, schema_identifier, expected_sha256 in self.PROTECTED_SOURCE_ARTIFACTS
            ],
            "source_governance": {
                "historical_backfill": False,
                "development_reuse": False,
                "validation_reuse": False,
                "research_quarantine_reuse": False,
                "pre_protocol_true_oos_prefix_reuse": False,
            },
            "audit": {
                "deterministic_rebuild": False,
                "mt5_accessed": False,
                "market_data_accessed": False,
                "replay_data_accessed": False,
                "strategy_replay_run": False,
                "outcomes_analyzed": False,
                "development_accessed": False,
                "validation_accessed": False,
                "quarantine_accessed": False,
                "true_oos_accessed": False,
                "production_behavior_changed": False,
                "order_check_called": False,
                "order_send_called": False,
                "real_order_called": False,
            },
        }
