#!/usr/bin/env python3
"""V3 Phase E gate for competitive explanations, thresholds and probabilities."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_citation import EvidenceRegistry
    from scripts.base_rate_case_library import validate_verified_episode_reference
    from scripts.metric_reconstruction_contract import contract_findings
    from scripts.phase10_acquisition import (
        licensed_industry_series_contract_findings,
        validate_source_role_provenance,
    )
except ModuleNotFoundError:
    from evidence_citation import EvidenceRegistry
    from base_rate_case_library import validate_verified_episode_reference
    from metric_reconstruction_contract import contract_findings
    from phase10_acquisition import (
        licensed_industry_series_contract_findings,
        validate_source_role_provenance,
    )


SCHEMA_VERSION = "thesis-test-ledger.v1"
POLICY_VERSION = "thesis-test-policy.v3"
FORWARD_JUDGMENT_CONTRACT_VERSION = "p27-licensed-industry-series.v1"
# P29 makes the optional industry-architecture experiment evidence-bound for
# newly frozen CJO cards.  Older snapshots remain readable: this version is
# only added by the CJO authoring/promotion path when a card actually contains
# an industry-architecture object.
INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION = "p29-industry-architecture-provenance.v1"
PIT_SOURCE_PROVENANCE_PROJECTION_SCHEMA_VERSION = "phase10-pit-source-provenance-projection.v1"
PROBABILITY_KINDS = {"frequency", "base_rate", "analyst_subjective", "scenario_weight"}
CJO_PROBABILITY_MODES = {"NO_PROBABILITY", "QUALIFIED_PROBABILITY"}
CJO_EMPIRICAL_PROBABILITY_KINDS = {"frequency", "base_rate"}
THRESHOLD_BASES = {"historical_volatility", "peer_benchmark", "model_sensitivity", "contractual", "accounting_regulatory", "base_rate", "expert_judgment"}
ACTIONS = {"buy", "hold", "increase", "reduce", "avoid", "exit", "reassess"}
OPERATORS = {">", ">=", "<", "<=", "==", "changes_to"}
PREDICTION_OPERATORS = {"AT_LEAST", "AT_MOST", "EQUALS", "RANGE"}
BASELINE_METHODS = {"CARRY_FORWARD", "INDUSTRY_ADJUSTED_CARRY_FORWARD", "EQUAL_WEIGHT_DRIVER_RULE"}
BASELINE_FORMULAS = {
    "CARRY_FORWARD": "LAST_OBSERVED_VALUE",
    "INDUSTRY_ADJUSTED_CARRY_FORWARD": "COMPANY_LEVEL_PLUS_INDUSTRY_DELTA",
    "EQUAL_WEIGHT_DRIVER_RULE": "EQUAL_WEIGHT_NUMERIC_DRIVERS",
}
FORWARD_MATERIALITIES = {
    "CENTRAL_THESIS", "INDUSTRY_STRUCTURE", "NORMALIZED_EARNINGS",
    "OWNER_CASH", "VALUATION", "RETURN", "PERMANENT_LOSS",
}
SETTLEMENT_MATERIALITIES = {"CENTRAL_THESIS", "VALUATION", "RETURN", "PERMANENT_LOSS"}
TRANSMISSION_CHANNELS = ("normalized_earnings", "owner_cash", "valuation", "expected_return")
TRANSMISSION_DIRECTIONS = {"increase", "decrease", "stable", "range", "not_material", "unknown"}
MATERIAL_TRANSMISSION_DIRECTIONS = {"increase", "decrease", "stable", "range"}
TERMINAL_OUTCOME_SCOPE = "TERMINAL_OPERATING_OUTCOME"
SCENARIO_ROLES = {"TERMINAL_OUTCOME", "MECHANISM"}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}
CJO_TRANSMISSION_CHANNELS = ("normalized_earnings", "owner_cash")
DIAGNOSTIC_LIKELIHOODS = {"LOW", "MEDIUM", "HIGH"}
RIVAL_SIGNAL_STAGES = {"EARLY_MECHANISM", "TERMINAL_OPERATING"}
ANALOGY_SETTLEMENT_RULE = "DERIVE_FROM_PAIR_SIGNALS_ONLY"
ANALOGY_FORBIDDEN_FIELD_TOKENS = {"price", "valuation", "probability", "return"}
ANALOGY_SUPPORT_ROLES = {"PRIMARY_SUPPORT", "QUESTION_ONLY"}
NEAR_MISS_STATUSES = {"VERIFIED_EPISODE", "UNKNOWN_NO_QUALIFIED_EPISODE"}
FORWARD_OUTCOME_SOURCE_TYPES = {
    "ANNUAL_REPORT", "INTERIM_REPORT", "EXCHANGE_ANNOUNCEMENT",
    "LICENSED_INDUSTRY_DATA", "OTHER_OFFICIAL",
}
QUANTITATIVE_INDUSTRY_INFERENCE_MODES = {
    "WITHIN_PROVIDER_RELATIVE_CHANGE", "LEVEL_WITH_STATED_LIMITS",
}
INDUSTRY_ARCHITECTURE_ELEMENTS = (
    "division_of_labour", "interface_control", "co_specialized_assets",
    "factor_mobility", "appropriation_node",
)
INDUSTRY_ARCHITECTURE_STATUSES = {"VERIFIED", "UNKNOWN"}
INDUSTRY_ARCHITECTURE_SOURCE_CLASSES = {
    "OFFICIAL_STATISTICS", "LICENSED_INDUSTRY_DATA", "COMPETITOR_DISCLOSURE",
    "SUPPLIER_OR_CUSTOMER_DISCLOSURE", "REGULATORY_DISCLOSURE",
}
CRITICAL_ASSUMPTION_SIDES = {"PRIMARY", "RIVAL"}
CRITICAL_ASSUMPTION_STATUSES = {"VERIFIED", "TESTABLE", "UNKNOWN"}
CAUSAL_TRACE_EDGE_STATUSES = {"VERIFIED", "TESTABLE", "UNKNOWN"}
SELECTION_ADMISSION_STATUSES = {
    "NOT_SELECTION_ELIGIBLE", "NO_PRIMARY", "SELECTION_ADMITTED",
}
REQUIRED_TRIGGER_METRICS = {"trigger.buy", "trigger.reduce", "trigger.exit"}
INTERNAL_EVIDENCE = {"report_internal", "report_derivation", "framework_method", "claim_evidence.json", "decision_ledger.json", "valuation_model.json", "thesis_test.json"}
_ANCHOR_PATTERNS = {
    "central": re.compile(r"\[central-path:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
    "test": re.compile(r"\[thesis-test:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
    "threshold": re.compile(r"\[threshold:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
    "probability": re.compile(r"\[probability:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I),
}
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.M)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}
    return value if isinstance(value, dict) else {}


def _has_industry_architecture_card(cards: Any) -> bool:
    """Whether this CJO freeze carries the optional H7 architecture object."""
    return any(
        isinstance(card, dict) and isinstance(card.get("industry_architecture"), dict)
        for card in (cards or [])
    )


def _canonical_industry_architecture_source_class(
    document: dict[str, Any], *,
    pit_source_provenance_by_id: dict[str, dict[str, Any]] | None = None,
    projected_document_source_ids: set[str] | None = None,
) -> tuple[str | None, list[str], list[str]]:
    """Map only source classes the canonical document contract can prove.

    Company filings, a self-described vertical integration narrative, and a
    ranking table do not become an external class merely because a card calls
    them one.  Ordinary document metadata can establish official statistics
    and a PIT-projected, versioned licensed industry export.  The three
    external-publisher roles are available only through P33's source-package
    contract and its read-only PIT projection; URLs, titles, legal names and
    free-text relationship labels never classify a document.
    """
    doc_type = str(document.get("doc_type") or "")
    authority = str(document.get("authority") or "")
    if doc_type == "official_statistics" and authority == "official_statistics":
        return "OFFICIAL_STATISTICS", [], []
    if (
        doc_type == "licensed_industry_data"
        and authority == "industry_data"
        and all(str(document.get(key) or "").strip() for key in (
            "source_id", "source_version", "revision_policy",
        ))
    ):
        return "LICENSED_INDUSTRY_DATA", [], []

    role_contract = document.get("source_role_provenance")
    if not isinstance(role_contract, dict):
        return None, [], []
    invalid: list[str] = []
    incomplete: list[str] = []
    source_id = str(document.get("source_id") or "").strip()
    if not source_id:
        return None, ["source_role_provenance:document_source_id_missing"], []
    source_projection = (pit_source_provenance_by_id or {}).get(source_id)
    if source_projection is None:
        return None, [], ["source_role_provenance:pit_source_projection_missing"]
    for field in ("source_id", "source_version", "revision_policy"):
        if str(document.get(field) or "").strip() != str(source_projection.get(field) or "").strip():
            invalid.append("source_role_provenance:document_" + field + "_does_not_match_pit_source")
    projected_role_contract = source_projection.get("source_role_provenance")
    if not isinstance(projected_role_contract, dict):
        incomplete.append("source_role_provenance:pit_source_role_contract_missing")
    elif projected_role_contract != role_contract:
        invalid.append("source_role_provenance:document_role_contract_does_not_match_pit_source")

    source_index = {
        source_key: {**source, "admissible": source.get("admission_status") == "ADMITTED"}
        for source_key, source in (pit_source_provenance_by_id or {}).items()
        if isinstance(source, dict)
    }
    role_validation = validate_source_role_provenance(
        {"source_role_provenance": role_contract}, source_index=source_index,
    )
    invalid.extend(role_validation["invalid_findings"])
    incomplete.extend(role_validation["incomplete_findings"])
    basis = role_contract.get("role_basis") if isinstance(role_contract.get("role_basis"), dict) else {}
    basis_source_id = str(basis.get("source_id") or "").strip()
    if basis_source_id and projected_document_source_ids is not None and basis_source_id not in projected_document_source_ids:
        incomplete.append("source_role_provenance:role_basis_source_not_projected")
    role = str(role_contract.get("relative_role") or "").strip()
    if invalid or incomplete or role not in INDUSTRY_ARCHITECTURE_SOURCE_CLASSES:
        return None, list(dict.fromkeys(invalid)), list(dict.fromkeys(incomplete))
    return role, [], []


def _industry_architecture_provenance_findings(
    *,
    prefix: str,
    element: dict[str, Any],
    evidence: dict[str, dict[str, Any]],
    documents_by_id: dict[str, dict[str, Any]],
    observations_by_id: dict[str, dict[str, Any]],
    pit_source_provenance_by_id: dict[str, dict[str, Any]],
    projected_document_source_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Bind a new CJO VERIFIED architecture item to canonical source facts.

    This is intentionally a narrow cross-reference validator.  The evidence,
    document and observation ledgers retain responsibility for their own
    schemas and content validation; here we prevent a model from declaring an
    external source class which the canonical evidence identity cannot support.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    evidence_ids = element.get("evidence_ids")
    source_classes = element.get("source_classes")
    bindings = element.get("evidence_bindings")
    if not isinstance(bindings, list) or not bindings:
        return invalid, [prefix + ":verified_evidence_bindings_missing"]

    binding_evidence_ids: list[str] = []
    binding_source_classes: list[str] = []
    seen_evidence_ids: set[str] = set()
    for index, binding in enumerate(bindings):
        binding_prefix = f"{prefix}:evidence_bindings[{index}]"
        if not isinstance(binding, dict):
            invalid.append(binding_prefix + ":not_object")
            continue
        evidence_id = str(binding.get("evidence_id") or "").strip()
        source_id = str(binding.get("source_id") or "").strip()
        source_class = str(binding.get("source_class") or "").strip()
        if not evidence_id:
            incomplete.append(binding_prefix + ":evidence_id_missing")
            continue
        if evidence_id in seen_evidence_ids:
            invalid.append(binding_prefix + ":duplicate_evidence_id")
            continue
        seen_evidence_ids.add(evidence_id)
        binding_evidence_ids.append(evidence_id)
        if not source_id:
            incomplete.append(binding_prefix + ":source_id_missing")
            continue
        if source_class not in INDUSTRY_ARCHITECTURE_SOURCE_CLASSES:
            invalid.append(binding_prefix + ":source_class_invalid")
            continue
        binding_source_classes.append(source_class)

        raw_fact = evidence.get(evidence_id)
        if raw_fact is None:
            # The ordinary card validator emits the familiar unknown-evidence
            # finding.  Keep this helper focused on provenance rather than
            # duplicating that error under a second name.
            continue
        if str(raw_fact.get("source_id") or "").strip() != source_id:
            invalid.append(binding_prefix + ":source_id_does_not_match_evidence")
            continue
        if raw_fact.get("direct_support") is not True:
            invalid.append(binding_prefix + ":evidence_not_direct_support")
        if raw_fact.get("support_type") != "supports":
            invalid.append(binding_prefix + ":evidence_not_supporting")
        if raw_fact.get("basis_match") != "exact":
            invalid.append(binding_prefix + ":evidence_basis_not_exact")
        if raw_fact.get("claim_distance") not in {"raw_data", "direct_statement"}:
            invalid.append(binding_prefix + ":evidence_not_first_order")

        document = documents_by_id.get(source_id)
        if document is None:
            incomplete.append(binding_prefix + ":source_document_missing")
            continue
        if str(raw_fact.get("authority") or "").strip() != str(document.get("authority") or "").strip():
            invalid.append(binding_prefix + ":evidence_authority_does_not_match_document")
        canonical_class, canonical_invalid, canonical_incomplete = _canonical_industry_architecture_source_class(
            document,
            pit_source_provenance_by_id=pit_source_provenance_by_id,
            projected_document_source_ids=projected_document_source_ids,
        )
        invalid.extend(binding_prefix + ":" + item for item in canonical_invalid)
        incomplete.extend(binding_prefix + ":" + item for item in canonical_incomplete)
        if canonical_class is None:
            invalid.append(binding_prefix + ":source_class_not_canonical")
            continue
        if source_class != canonical_class:
            invalid.append(binding_prefix + ":source_class_does_not_match_document")
            continue

        if canonical_class == "LICENSED_INDUSTRY_DATA":
            canonical_source_id = str(binding.get("canonical_source_id") or "").strip()
            if not canonical_source_id:
                incomplete.append(binding_prefix + ":canonical_source_id_missing")
            elif canonical_source_id != str(document.get("source_id") or "").strip():
                invalid.append(binding_prefix + ":canonical_source_id_does_not_match_document")
        else:
            observation_id = str(raw_fact.get("observation_id") or "").strip()
            if not observation_id:
                incomplete.append(binding_prefix + ":observation_id_missing")
            else:
                observation = observations_by_id.get(observation_id)
                if observation is None:
                    invalid.append(binding_prefix + ":observation_unknown")
                elif observation.get("status") != "VERIFIED":
                    invalid.append(binding_prefix + ":observation_not_verified")
                elif str(observation.get("doc_id") or "").strip() != source_id:
                    invalid.append(binding_prefix + ":observation_document_mismatch")

    if isinstance(evidence_ids, list) and set(str(item) for item in evidence_ids) != set(binding_evidence_ids):
        invalid.append(prefix + ":evidence_bindings_do_not_match_evidence_ids")
    if isinstance(source_classes, list) and set(str(item) for item in source_classes) != set(binding_source_classes):
        invalid.append(prefix + ":evidence_bindings_do_not_match_source_classes")
    return invalid, incomplete


def _canonical(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at"): value.pop(key, None)
    return value


def _operating_judgment_projection(value: dict[str, Any]) -> dict[str, Any]:
    """The CJO part that an investment ledger may enrich but not rewrite."""
    transmission = value.get("transmission") if isinstance(value.get("transmission"), dict) else {}
    return {
        key: deepcopy(value.get(key))
        for key in (
            "judgment_id", "statement", "materiality", "claim_id", "competitive_test_id",
            "probability_set_id", "scenario_id", "mechanism_chain_ids", "evidence_ids",
            "leading_signal_threshold_ids", "falsifier", "prediction", "baseline",
            "settlement_contract", "observable_outcome", "financial_driver_ids",
            "rival_hypothesis_pair_id", "rival_signal_id",
        )
    } | {
        "transmission": {
            key: deepcopy(transmission.get(key))
            for key in CJO_TRANSMISSION_CHANNELS
        }
    }


def _operating_chain_projection(value: dict[str, Any]) -> dict[str, Any]:
    transmission = value.get("transmission") if isinstance(value.get("transmission"), dict) else {}
    return {
        key: deepcopy(value.get(key))
        for key in ("chain_id", "probability_set_id", "scenario_id", "mechanism", "leading_signal_threshold_ids")
    } | {
        "transmission": {
            key: deepcopy(transmission.get(key))
            for key in CJO_TRANSMISSION_CHANNELS
        }
    }


def _central_path_projection(value: dict[str, Any]) -> dict[str, Any]:
    """Compare the economic path, not chapter placement or editorial wording."""
    return {
        key: deepcopy(value.get(key))
        for key in (
            "path_id", "horizon_years", "probability_set_id", "selected_scenario_id",
            "competing_scenario_id", "competitive_test_ids", "mechanism_chain_ids",
            "forward_judgment_ids",
        )
    }


def _validate_company_judgment_lineage(
    payload: dict[str, Any], *, output: Path | None,
) -> tuple[list[str], list[str]]:
    """Require an investment ledger to preserve its frozen CJO operating path."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if output is None:
        return ["company_judgment_lineage_output_dir_required"], incomplete
    predecessor = _read_json(output / "company_judgment_predecessor.json")
    source = predecessor.get("source") if isinstance(predecessor.get("source"), dict) else {}
    lineage = payload.get("company_judgment_lineage")
    if not predecessor:
        return invalid, ["company_judgment_predecessor_missing"]
    if not isinstance(lineage, dict):
        return invalid, ["company_judgment_lineage_missing"]
    snapshot_fingerprint = str(source.get("snapshot_fingerprint") or "")
    thesis_sha256 = str(source.get("thesis_sha256") or "")
    if not snapshot_fingerprint or not thesis_sha256:
        invalid.append("company_judgment_predecessor_identity_invalid")
        return invalid, incomplete
    if lineage.get("predecessor_snapshot_fingerprint") != snapshot_fingerprint:
        invalid.append("company_judgment_lineage_snapshot_mismatch")
    if lineage.get("predecessor_thesis_sha256") != thesis_sha256:
        invalid.append("company_judgment_lineage_thesis_hash_mismatch")
    central = payload.get("central_path") if isinstance(payload.get("central_path"), dict) else {}
    inherited_central = predecessor.get("central_path") if isinstance(predecessor.get("central_path"), dict) else {}
    if not inherited_central:
        invalid.append("company_judgment_predecessor_central_path_invalid")
    elif _central_path_projection(central) != _central_path_projection(inherited_central):
        invalid.append("company_judgment_lineage_central_path_rewritten")
    inherited_judgments = {
        str(item.get("judgment_id")): item
        for item in predecessor.get("forward_judgments") or []
        if isinstance(item, dict) and item.get("judgment_id")
    }
    current_judgments = {
        str(item.get("judgment_id")): item
        for item in payload.get("forward_judgments") or []
        if isinstance(item, dict) and item.get("judgment_id")
    }
    if not inherited_judgments:
        invalid.append("company_judgment_predecessor_forward_judgments_invalid")
    for judgment_id, inherited in inherited_judgments.items():
        current = current_judgments.get(judgment_id)
        if current is None:
            invalid.append(f"company_judgment_lineage_forward_judgment_missing:{judgment_id}")
        elif _operating_judgment_projection(current) != _operating_judgment_projection(inherited):
            invalid.append(f"company_judgment_lineage_forward_judgment_rewritten:{judgment_id}")
    inherited_chains = {
        str(item.get("chain_id")): item
        for item in predecessor.get("mechanism_chains") or []
        if isinstance(item, dict) and item.get("chain_id")
    }
    current_chains = {
        str(item.get("chain_id")): item
        for item in payload.get("mechanism_chains") or []
        if isinstance(item, dict) and item.get("chain_id")
    }
    if not inherited_chains:
        invalid.append("company_judgment_predecessor_mechanism_chains_invalid")
    for chain_id, inherited in inherited_chains.items():
        current = current_chains.get(chain_id)
        if current is None:
            invalid.append(f"company_judgment_lineage_mechanism_chain_missing:{chain_id}")
        elif _operating_chain_projection(current) != _operating_chain_projection(inherited):
            invalid.append(f"company_judgment_lineage_mechanism_chain_rewritten:{chain_id}")
    return invalid, incomplete


def thesis_test_fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def bind_thesis_test_references(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir); chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    additions: dict[int, list[str]] = {}
    central = payload.get("central_path") if isinstance(payload.get("central_path"), dict) else {}
    path_id = str(central.get("path_id") or "").strip()
    if path_id:
        for chapter in central.get("chapters") or []:
            if not isinstance(chapter, int):
                continue
            path = chapter_dir / f"_ch{chapter:02d}.md"
            if not path.is_file():
                continue
            if path_id not in _ANCHOR_PATTERNS["central"].findall(path.read_text(encoding="utf-8")):
                additions.setdefault(chapter, []).append(f"- 中心路径引用：[central-path: {path_id}]")
    specs = (
        ("competitive_tests", "test_id", "thesis-test", "竞争解释测试"),
        ("thresholds", "threshold_id", "threshold", "监控阈值"),
        ("probability_sets", "set_id", "probability", "情景概率"),
    )
    for collection, id_key, anchor, label in specs:
        pattern = _ANCHOR_PATTERNS["test" if anchor == "thesis-test" else anchor]
        for item in payload.get(collection) or []:
            if not isinstance(item, dict): continue
            item_id = str(item.get(id_key) or "").strip()
            if not item_id: continue
            for chapter in item.get("chapters") or []:
                if not isinstance(chapter, int): continue
                path = chapter_dir / f"_ch{chapter:02d}.md"
                if not path.is_file(): continue
                text = path.read_text(encoding="utf-8")
                if item_id in pattern.findall(text): continue
                additions.setdefault(chapter, []).append(f"- {label}引用：[{anchor}: {item_id}]")
    changed: list[int] = []
    for chapter, rows in additions.items():
        path = chapter_dir / f"_ch{chapter:02d}.md"; text = path.read_text(encoding="utf-8")
        block = "\n\n### Canonical thesis bindings\n\n" + "\n".join(rows) + "\n"
        path.write_text(text.rstrip() + block, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": sorted(changed), "anchors_inserted": sum(map(len, additions.values()))}


def promote_reviewable_thesis_test(output_dir: str | Path, *, report_text: str) -> dict[str, Any]:
    output = Path(output_dir); payload = _read_json(output / "thesis_test.json")
    if not payload: return {"promoted": False, "error": "thesis_test_missing"}
    policy = _read_json(output / "thesis_test_policy.json")
    validation = validate_thesis_test_ledger(
        payload, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
        monitoring_required=bool(policy.get("monitoring_required")),
        forward_judgment_required=bool(policy.get("forward_judgment_required")),
        rival_hypothesis_pair_required=bool(policy.get("rival_hypothesis_pair_required")),
        company_judgment_lineage_required=bool(policy.get("company_judgment_lineage_required")),
        required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS),
    )
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "validation": validation}
    promoted = deepcopy(payload); promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {
        "frozen": True,
        "fingerprint": "",
        "frozen_at": _now(),
        "forward_judgment_contract_version": FORWARD_JUDGMENT_CONTRACT_VERSION,
    }
    if (
        promoted.get("analysis_purpose") == "COMPANY_JUDGMENT_ONLY"
        and _has_industry_architecture_card(promoted.get("analogy_transfer_cards"))
    ):
        promoted["freeze"]["industry_architecture_provenance_contract_version"] = (
            INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
        )
    promoted["freeze"]["fingerprint"] = thesis_test_fingerprint(promoted)
    result = persist_thesis_test_ledger(output, promoted, report_text=report_text, allow_frozen_update=True)
    result["promoted"] = bool(result.get("written")); return result


def initialize_thesis_test_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool, monitoring_required: bool = False,
    forward_judgment_required: bool = False, rival_hypothesis_pair_required: bool = False,
    company_judgment_lineage_required: bool = False,
) -> dict[str, Any]:
    payload = {"schema_version": POLICY_VERSION, "run_id": str(run_id), "enforced": bool(enforced),
               "required_trigger_metric_ids": sorted(REQUIRED_TRIGGER_METRICS),
               "monitoring_required": bool(monitoring_required),
               "forward_judgment_required": bool(forward_judgment_required),
               "rival_hypothesis_pair_required": bool(rival_hypothesis_pair_required),
               "company_judgment_lineage_required": bool(company_judgment_lineage_required),
               "created_at": _now()}
    path = Path(output_dir) / "thesis_test_policy.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"); return payload


def build_thesis_test_ledger(
    output_dir: str | Path,
    competitive_tests: list[dict[str, Any]],
    thresholds: list[dict[str, Any]],
    probability_sets: list[dict[str, Any]],
    *,
    central_path: dict[str, Any] | None = None,
    mechanism_chains: list[dict[str, Any]] | None = None,
    forward_judgments: list[dict[str, Any]] | None = None,
    rival_hypothesis_pairs: list[dict[str, Any]] | None = None,
    analogy_transfer_cards: list[dict[str, Any]] | None = None,
    selection_admission: dict[str, Any] | None = None,
    probability_mode: str = "",
    probability_qualification: dict[str, Any] | None = None,
    analysis_purpose: str = "INVESTMENT_DECISION",
    change_reason: str,
    freeze: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir); contract = _read_json(output / "analysis_contract.json")
    payload: dict[str, Any] = {"schema_version": SCHEMA_VERSION, "report_id": str(contract.get("ts_code") or contract.get("code") or output.name), "revision": 1, "lifecycle": "decision_ready" if freeze else "reviewable", "analysis_purpose": str(analysis_purpose), "change_reason": str(change_reason or "").strip(), "competitive_tests": deepcopy(competitive_tests), "thresholds": deepcopy(thresholds), "probability_sets": deepcopy(probability_sets), "generated_at": _now()}
    if central_path is not None:
        payload["central_path"] = deepcopy(central_path)
    if mechanism_chains is not None:
        payload["mechanism_chains"] = deepcopy(mechanism_chains)
    if forward_judgments is not None:
        payload["forward_judgments"] = deepcopy(forward_judgments)
    if rival_hypothesis_pairs is not None:
        payload["rival_hypothesis_pairs"] = deepcopy(rival_hypothesis_pairs)
    if analogy_transfer_cards is not None:
        payload["analogy_transfer_cards"] = deepcopy(analogy_transfer_cards)
    if selection_admission is not None:
        payload["selection_admission"] = deepcopy(selection_admission)
    elif analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        # Ordinary company work may freeze a central path for operational
        # research without claiming that it is an R-07 selection episode.
        payload["selection_admission"] = {"status": "NOT_SELECTION_ELIGIBLE"}
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and str(probability_mode or "").strip():
        payload["probability_mode"] = str(probability_mode).strip()
        if probability_qualification is not None:
            payload["probability_qualification"] = deepcopy(probability_qualification)
    if analysis_purpose == "INVESTMENT_DECISION":
        predecessor = _read_json(output / "company_judgment_predecessor.json")
        source = predecessor.get("source") if isinstance(predecessor.get("source"), dict) else {}
        if predecessor:
            payload["company_judgment_lineage"] = {
                "predecessor_snapshot_fingerprint": source.get("snapshot_fingerprint"),
                "predecessor_thesis_sha256": source.get("thesis_sha256"),
                "central_path_id": (predecessor.get("central_path") or {}).get("path_id"),
                "forward_judgment_ids": sorted(
                    str(item.get("judgment_id"))
                    for item in predecessor.get("forward_judgments") or []
                    if isinstance(item, dict) and item.get("judgment_id")
                ),
            }
    payload["freeze"] = {
        "frozen": bool(freeze),
        "fingerprint": thesis_test_fingerprint(payload) if freeze else "",
        "frozen_at": _now() if freeze else None,
        **({"forward_judgment_contract_version": FORWARD_JUDGMENT_CONTRACT_VERSION} if freeze else {}),
    }
    if (
        freeze
        and analysis_purpose == "COMPANY_JUDGMENT_ONLY"
        and _has_industry_architecture_card(analogy_transfer_cards)
    ):
        payload["freeze"]["industry_architecture_provenance_contract_version"] = (
            INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
        )
        payload["freeze"]["fingerprint"] = thesis_test_fingerprint(payload)
    return payload


def _chapters(report_text: str) -> dict[int, str]:
    matches = list(_CHAPTER_RE.finditer(report_text)); result: dict[int, str] = {}
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(report_text); result[int(match.group(1))] = report_text[match.start():end]
    return result


def _num(value: Any) -> float | None:
    try: result = float(value)
    except (TypeError, ValueError): return None
    return result if math.isfinite(result) else None


def _iso_date(value: Any):
    try:
        return datetime.fromisoformat(str(value or "")[:10]).date()
    except ValueError:
        return None


def _decimals(value: Any) -> int:
    text = str(value)
    return len(text.rstrip("0").split(".", 1)[1]) if "." in text else 0


def _ids(payload: dict[str, Any], key: str) -> set[str]:
    return {str(item.get(key)) for item in payload if isinstance(item, dict) and item.get(key)}


def _same_prediction(left: Any, right: Any) -> bool:
    """Compare frozen predicates without collapsing a range to a midpoint."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    fields = ("metric", "operator", "unit", "horizon", "resolution_due", "value", "range_low", "range_high")
    return all(left.get(field) == right.get(field) for field in fields)


def _prediction_is_met_at(prediction: dict[str, Any], value: float) -> bool:
    """Evaluate a valid frozen predicate at a finite candidate outcome."""
    operator = prediction.get("operator")
    if operator == "RANGE":
        low, high = _num(prediction.get("range_low")), _num(prediction.get("range_high"))
        return low is not None and high is not None and low <= value <= high
    target = _num(prediction.get("value"))
    if target is None:
        return False
    if operator == "AT_LEAST":
        return value >= target
    if operator == "AT_MOST":
        return value <= target
    return operator == "EQUALS" and value == target


def _pair_allows_each_side_to_win(primary: Any, rival: Any) -> bool:
    """Require a pair to contain an outcome uniquely compatible with each side.

    Different strings are not enough: ``AT_LEAST 90`` and ``AT_LEAST 95``
    leave the rival with no observation that can support it without also
    supporting the primary.  Endpoints and their immediate neighbours cover
    every truth-region of these one-dimensional predicates without inventing
    a midpoint or an arbitrary range-width limit.
    """
    if not isinstance(primary, dict) or not isinstance(rival, dict):
        return False

    def boundaries(prediction: dict[str, Any]) -> list[float]:
        if prediction.get("operator") == "RANGE":
            values = [_num(prediction.get("range_low")), _num(prediction.get("range_high"))]
        else:
            values = [_num(prediction.get("value"))]
        return [value for value in values if value is not None]

    candidates: set[float] = set()
    for boundary in [*boundaries(primary), *boundaries(rival)]:
        candidates.update({boundary, math.nextafter(boundary, -math.inf), math.nextafter(boundary, math.inf)})
    primary_only = any(
        _prediction_is_met_at(primary, value) and not _prediction_is_met_at(rival, value)
        for value in candidates
    )
    rival_only = any(
        _prediction_is_met_at(rival, value) and not _prediction_is_met_at(primary, value)
        for value in candidates
    )
    return primary_only and rival_only


def _prediction_findings(label: str, prediction: Any) -> tuple[list[str], list[str]]:
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(prediction, dict):
        return [label + ":prediction_invalid"], incomplete
    for key in ("metric", "unit", "horizon", "resolution_due"):
        if not str(prediction.get(key) or "").strip():
            incomplete.append(f"{label}:prediction_{key}_missing")
    operator = prediction.get("operator")
    if operator not in PREDICTION_OPERATORS:
        invalid.append(f"{label}:prediction_operator_invalid")
    elif operator == "RANGE":
        low, high = _num(prediction.get("range_low")), _num(prediction.get("range_high"))
        if low is None or high is None or low > high:
            invalid.append(f"{label}:prediction_range_invalid")
        if prediction.get("value") not in (None, ""):
            invalid.append(f"{label}:prediction_range_cannot_carry_point_value")
    elif _num(prediction.get("value")) is None:
        invalid.append(f"{label}:prediction_value_invalid")
    if _iso_date(prediction.get("resolution_due")) is None:
        invalid.append(f"{label}:prediction_resolution_due_invalid")
    return invalid, incomplete


def _analogy_has_forbidden_field(value: Any) -> bool:
    if isinstance(value, dict):
        return any(
            any(token in str(key).lower() for token in ANALOGY_FORBIDDEN_FIELD_TOKENS)
            or _analogy_has_forbidden_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_analogy_has_forbidden_field(item) for item in value)
    return False


def _case_archetype_ids() -> set[str]:
    """Resolve the existing book-method cards; no parallel case library exists."""
    path = Path(__file__).resolve().parents[1] / "config" / "insight_case_benchmark.json"
    payload = _read_json(path)
    archetypes = payload.get("archetypes") if isinstance(payload.get("archetypes"), dict) else {}
    return {str(key) for key in archetypes if str(key).strip()}


def _baseline_calculation_findings(
    judgment_id: str, baseline: dict[str, Any], prediction: dict[str, Any], evidence_ids: list[Any],
) -> tuple[list[str], list[str]]:
    """Check that a simple baseline is reproducible from frozen numeric inputs.

    This validates only the three explicitly supported simple rules.  It does
    not estimate a company forecast or infer a driver.  A free-text baseline
    would make the later "increment over baseline" claim untestable.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    calculation = baseline.get("calculation")
    if not isinstance(calculation, dict):
        return invalid, [f"{judgment_id}:baseline_calculation_missing"]
    method = baseline.get("method")
    expected_formula = BASELINE_FORMULAS.get(str(method))
    if calculation.get("formula_id") != expected_formula:
        invalid.append(f"{judgment_id}:baseline_formula_does_not_match_method")
    inputs = calculation.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        return invalid, [*incomplete, f"{judgment_id}:baseline_calculation_inputs_missing"]
    normalized: list[dict[str, Any]] = []
    known_evidence = {str(item) for item in evidence_ids}
    for index, raw in enumerate(inputs):
        prefix = f"{judgment_id}:baseline_calculation_inputs[{index}]"
        if not isinstance(raw, dict):
            invalid.append(prefix + ":not_object")
            continue
        evidence_id = str(raw.get("evidence_id") or "").strip()
        role = str(raw.get("role") or "").strip()
        value = _num(raw.get("value"))
        if not evidence_id:
            incomplete.append(prefix + ":evidence_id_missing")
        elif evidence_id not in known_evidence:
            invalid.append(prefix + ":evidence_not_declared_for_baseline")
        if not role:
            incomplete.append(prefix + ":role_missing")
        if value is None:
            invalid.append(prefix + ":value_invalid")
        if raw.get("unit") != prediction.get("unit"):
            invalid.append(prefix + ":unit_does_not_match_prediction")
        normalized.append({"evidence_id": evidence_id, "role": role, "value": value})
    if invalid or incomplete:
        return invalid, incomplete

    by_role: dict[str, list[float]] = {}
    for item in normalized:
        by_role.setdefault(str(item["role"]), []).append(float(item["value"]))
    baseline_prediction = baseline.get("prediction") if isinstance(baseline.get("prediction"), dict) else {}

    def matches(value: float) -> bool:
        if baseline_prediction.get("operator") == "RANGE":
            low, high = _num(baseline_prediction.get("range_low")), _num(baseline_prediction.get("range_high"))
            return low is not None and high is not None and math.isclose(low, value, abs_tol=1e-9) and math.isclose(high, value, abs_tol=1e-9)
        point = _num(baseline_prediction.get("value"))
        return point is not None and math.isclose(point, value, abs_tol=1e-9)

    if method == "CARRY_FORWARD":
        values = by_role.get("LAST_OBSERVED", [])
        if len(normalized) != 1 or len(values) != 1:
            invalid.append(f"{judgment_id}:baseline_carry_forward_requires_one_last_observed_input")
        elif not matches(values[0]):
            invalid.append(f"{judgment_id}:baseline_carry_forward_value_does_not_match_input")
    elif method == "INDUSTRY_ADJUSTED_CARRY_FORWARD":
        required = ("COMPANY_PRIOR", "INDUSTRY_PRIOR", "INDUSTRY_CURRENT")
        if any(len(by_role.get(role, [])) != 1 for role in required) or len(normalized) != 3:
            invalid.append(f"{judgment_id}:baseline_industry_adjusted_inputs_invalid")
        else:
            predicted = by_role["COMPANY_PRIOR"][0] + by_role["INDUSTRY_CURRENT"][0] - by_role["INDUSTRY_PRIOR"][0]
            if not matches(predicted):
                invalid.append(f"{judgment_id}:baseline_industry_adjusted_value_does_not_reconcile")
    elif method == "EQUAL_WEIGHT_DRIVER_RULE":
        values = by_role.get("DRIVER", [])
        if len(normalized) < 2 or len(values) != len(normalized):
            invalid.append(f"{judgment_id}:baseline_equal_weight_requires_two_or_more_driver_inputs")
        elif not matches(sum(values) / len(values)):
            invalid.append(f"{judgment_id}:baseline_equal_weight_value_does_not_reconcile")
    return invalid, incomplete


def _selection_admission_findings(
    payload: dict[str, Any], *, analysis_purpose: str,
    central: dict[str, Any] | None, probability_scenarios: dict[str, set[str]],
    probability_mode: str | None = None,
    declared_scenario_ids: set[str] | None = None,
    judgments: list[dict[str, Any]], evidence: dict[str, dict[str, Any]],
    pairs: dict[str, dict[str, Any]], mechanism_by_id: dict[str, dict[str, Any]],
    threshold_by_id: dict[str, dict[str, Any]],
) -> tuple[dict[str, Any], list[str], list[str]]:
    """Validate the optional R-07 selection-learning receipt for a CJO.

    A central path remains useful for ordinary company research.  This receipt
    is deliberately opt-in: only a CJO that asks to count a path choice as a
    selection-learning episode must prove that its pre-cutoff evidence was
    directional and that its simple challenger made a different prediction.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    raw = payload.get("selection_admission")
    default = {"status": "NOT_SELECTION_ELIGIBLE"}
    if raw is None:
        return default, invalid, incomplete
    if analysis_purpose != "COMPANY_JUDGMENT_ONLY":
        return default, ["selection_admission_only_supported_for_company_judgment"], incomplete
    if not isinstance(raw, dict):
        return default, ["selection_admission_not_object"], incomplete
    status = str(raw.get("status") or "").strip()
    if not status:
        return default, invalid, ["selection_admission:status_missing"]
    if status not in SELECTION_ADMISSION_STATUSES:
        return {"status": status}, ["selection_admission:status_invalid"], incomplete
    binding = raw.get("selection_register_binding")
    if binding is not None:
        if status not in {"SELECTION_ADMITTED", "NO_PRIMARY"}:
            invalid.append("selection_admission:selection_register_binding_only_supported_for_selection_admitted_or_no_primary")
        elif not isinstance(binding, dict):
            invalid.append("selection_admission:selection_register_binding_not_object")
        else:
            binding_fields = {
                "register_id", "register_fingerprint", "selection_entry_id", "company_id", "company_cluster_id",
            }
            invalid.extend(
                "selection_admission:selection_register_binding_unsupported_field:" + str(field)
                for field in binding if field not in binding_fields
            )
            for field in sorted(binding_fields):
                if not str(binding.get(field) or "").strip():
                    incomplete.append("selection_admission:selection_register_binding_" + field + "_missing")
            if str(binding.get("register_id") or "") and not str(binding.get("register_id")).startswith("CSR:"):
                invalid.append("selection_admission:selection_register_binding_register_id_invalid")
            if str(binding.get("selection_entry_id") or "") and not str(binding.get("selection_entry_id")).startswith("CSRSEL:"):
                invalid.append("selection_admission:selection_register_binding_selection_entry_id_invalid")
            fingerprint = str(binding.get("register_fingerprint") or "")
            if fingerprint and (len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint)):
                invalid.append("selection_admission:selection_register_binding_register_fingerprint_invalid")
    if status == "NOT_SELECTION_ELIGIBLE":
        return {"status": status}, invalid, incomplete

    no_probability = probability_mode == "NO_PROBABILITY"
    central = central if isinstance(central, dict) else {}
    selected_scenario_id = str(central.get("selected_scenario_id") or "")
    competing_scenario_id = str(central.get("competing_scenario_id") or "")
    probability_set_id = str(central.get("probability_set_id") or "")
    central_as_of = _iso_date(central.get("as_of"))
    if status != "NO_PRIMARY" and (
        not selected_scenario_id or not competing_scenario_id or (
            not no_probability and not probability_set_id
        )
    ):
        incomplete.append("selection_admission:central_path_identity_missing")

    candidate_ids = raw.get("candidate_scenario_ids")
    if not isinstance(candidate_ids, list) or len(candidate_ids) < 2:
        incomplete.append("selection_admission:candidate_scenario_ids_missing")
        candidate_ids = []
    else:
        candidate_ids = [str(item or "").strip() for item in candidate_ids]
        if any(not item for item in candidate_ids) or len(candidate_ids) != len(set(candidate_ids)):
            invalid.append("selection_admission:candidate_scenario_ids_invalid")
        known_scenarios = (
            set(declared_scenario_ids or set())
            if no_probability else probability_scenarios.get(probability_set_id, set())
        )
        unknown = sorted(set(candidate_ids) - known_scenarios)
        if unknown:
            invalid.append("selection_admission:candidate_scenario_unknown:" + ",".join(unknown))
        for scenario_id, label in (
            (selected_scenario_id, "selected"),
            (competing_scenario_id, "competing"),
        ):
            if scenario_id and scenario_id not in candidate_ids:
                invalid.append(f"selection_admission:{label}_scenario_not_in_candidates")

    strongest_rival_id = str(raw.get("strongest_rival_scenario_id") or "").strip()
    if not strongest_rival_id:
        incomplete.append("selection_admission:strongest_rival_scenario_id_missing")
    elif status != "NO_PRIMARY" and strongest_rival_id != competing_scenario_id:
        invalid.append("selection_admission:strongest_rival_must_match_central_competing_scenario")
    elif strongest_rival_id not in candidate_ids:
        invalid.append("selection_admission:strongest_rival_not_in_candidates")
    if not str(raw.get("strongest_rival_not_selected_reason") or "").strip():
        incomplete.append("selection_admission:strongest_rival_not_selected_reason_missing")

    pair_id = str(raw.get("rival_hypothesis_pair_id") or "").strip()
    pair = pairs.get(pair_id)
    if not pair_id:
        incomplete.append("selection_admission:rival_hypothesis_pair_id_missing")
    elif pair is None:
        invalid.append("selection_admission:rival_hypothesis_pair_unknown")

    if status == "NO_PRIMARY":
        if not str(raw.get("no_primary_reason") or "").strip():
            incomplete.append("selection_admission:no_primary_reason_missing")
        return {"status": status}, invalid, incomplete

    judgments_by_id = {
        str(item.get("judgment_id") or ""): item
        for item in judgments if isinstance(item, dict) and str(item.get("judgment_id") or "").strip()
    }
    selection_judgment_ids = raw.get("selection_forward_judgment_ids")
    if not isinstance(selection_judgment_ids, list) or not selection_judgment_ids:
        incomplete.append("selection_admission:selection_forward_judgment_ids_missing")
        selection_judgment_ids = []
    else:
        selection_judgment_ids = [str(item or "").strip() for item in selection_judgment_ids]
        if any(not item for item in selection_judgment_ids) or len(selection_judgment_ids) != len(set(selection_judgment_ids)):
            invalid.append("selection_admission:selection_forward_judgment_ids_invalid")

    selection_evidence = raw.get("selection_evidence")
    if selection_evidence is not None and not isinstance(selection_evidence, list):
        invalid.append("selection_admission:selection_evidence_not_array")
    if not isinstance(selection_evidence, list):
        selection_evidence = []
    selection_evidence_bundles = raw.get("selection_evidence_bundles")
    if selection_evidence_bundles is not None and not isinstance(selection_evidence_bundles, list):
        invalid.append("selection_admission:selection_evidence_bundles_not_array")
    if not isinstance(selection_evidence_bundles, list):
        selection_evidence_bundles = []
    if not selection_evidence and not selection_evidence_bundles:
        incomplete.append("selection_admission:selection_evidence_missing")
    common_fact_ids = {
        str(item) for item in (pair or {}).get("common_fact_evidence_ids") or []
        if str(item).strip()
    }
    discriminators_by_judgment = {
        str(item.get("forward_judgment_id") or ""): item
        for item in (pair or {}).get("discriminators") or []
        if isinstance(item, dict) and str(item.get("forward_judgment_id") or "").strip()
    }
    primary_chain = mechanism_by_id.get(str((pair or {}).get("primary_mechanism_chain_id") or ""))
    rival_chain = mechanism_by_id.get(str((pair or {}).get("rival_mechanism_chain_id") or ""))
    primary_trace_edges = {
        str(item.get("edge_id") or ""): item
        for item in (pair or {}).get("causal_trace") or []
        if isinstance(item, dict) and str(item.get("edge_id") or "").strip()
    }
    selected_sequence_judgments: set[str] = set()
    supports_selected = False
    seen_selection_evidence_ids: set[str] = set()
    seen_bundle_ids: set[str] = set()

    def validate_evidence_fact(item: dict[str, Any], prefix: str) -> tuple[str, str]:
        """Validate one frozen source fact without requiring it to decide alone."""
        nonlocal supports_selected
        evidence_id = str(item.get("evidence_id") or "").strip()
        source_id = str(item.get("source_id") or "").strip()
        source_group_id = str(item.get("source_group_id") or "").strip()
        evidence_row = evidence.get(evidence_id)
        if not evidence_id:
            incomplete.append(prefix + ":evidence_id_missing")
        elif evidence_id in seen_selection_evidence_ids:
            invalid.append(prefix + ":evidence_id_reused_across_selection_admission")
        else:
            seen_selection_evidence_ids.add(evidence_id)
        if evidence_id and evidence_row is None:
            invalid.append(prefix + ":evidence_unknown")
        elif evidence_id in common_fact_ids:
            invalid.append(prefix + ":common_fact_cannot_be_selection_evidence")
        if not source_id:
            incomplete.append(prefix + ":source_id_missing")
        elif evidence_row is not None and source_id != str(evidence_row.get("source_id") or ""):
            invalid.append(prefix + ":source_id_does_not_match_evidence")
        if not source_group_id:
            incomplete.append(prefix + ":source_group_id_missing")
        elif evidence_row is not None and source_group_id != str(evidence_row.get("source_group_id") or ""):
            invalid.append(prefix + ":source_group_id_does_not_match_evidence")
        if evidence_row is not None:
            published_at = _iso_date(evidence_row.get("published_at"))
            data_as_of = _iso_date(evidence_row.get("data_as_of"))
            if published_at is None or data_as_of is None:
                incomplete.append(prefix + ":evidence_pre_cutoff_dates_missing")
            elif central_as_of is not None and (published_at > central_as_of or data_as_of > central_as_of):
                invalid.append(prefix + ":evidence_not_pre_cutoff")
        return evidence_id, source_group_id

    def validate_selection_sequence(
        *, prefix: str, forward_judgment_id: str, leading_threshold_id: str,
        evidence_edges: list[tuple[str, str]],
    ) -> bool:
        """Bind a selection receipt to one early FJ and two-sided threshold."""
        sequence_valid = True
        if not forward_judgment_id:
            incomplete.append(prefix + ":forward_judgment_id_missing")
            sequence_valid = False
        elif forward_judgment_id not in selection_judgment_ids:
            invalid.append(prefix + ":forward_judgment_not_selected_for_admission")
            sequence_valid = False
        else:
            judgment = judgments_by_id.get(forward_judgment_id)
            discriminator = discriminators_by_judgment.get(forward_judgment_id)
            if judgment is None:
                invalid.append(prefix + ":forward_judgment_unknown")
                sequence_valid = False
            elif pair_id and str(judgment.get("rival_hypothesis_pair_id") or "") != pair_id:
                invalid.append(prefix + ":forward_judgment_rival_pair_invalid")
                sequence_valid = False
            if discriminator is None:
                invalid.append(prefix + ":forward_judgment_not_pair_discriminator")
                sequence_valid = False
            elif discriminator.get("stage") != "EARLY_MECHANISM":
                invalid.append(prefix + ":forward_judgment_not_early_mechanism")
                sequence_valid = False
            else:
                early_signal_id = str(discriminator.get("signal_id") or "")
                for side, chain, label in (
                    ("PRIMARY", primary_chain, "primary"),
                    ("RIVAL", rival_chain, "rival"),
                ):
                    if not any(
                        edge.get("mechanism_side") == side
                        and edge.get("mechanism_chain_id") == (chain or {}).get("chain_id")
                        and edge.get("status") == "TESTABLE"
                        and early_signal_id in {
                            str(value) for value in edge.get("linked_discriminator_ids") or []
                        }
                        for edge in primary_trace_edges.values()
                    ):
                        invalid.append(prefix + f":{label}_early_signal_not_testable")
                        sequence_valid = False
        for evidence_id, primary_causal_edge_id in evidence_edges:
            edge_prefix = prefix
            if len(evidence_edges) > 1:
                edge_prefix += ":component[" + evidence_id + "]"
            if not primary_causal_edge_id:
                incomplete.append(edge_prefix + ":primary_causal_edge_id_missing")
                sequence_valid = False
                continue
            primary_edge = primary_trace_edges.get(primary_causal_edge_id)
            if primary_edge is None:
                invalid.append(edge_prefix + ":primary_causal_edge_unknown")
                sequence_valid = False
                continue
            if primary_edge.get("mechanism_side") != "PRIMARY" or primary_edge.get("status") != "VERIFIED":
                invalid.append(edge_prefix + ":primary_causal_edge_not_primary_verified")
                sequence_valid = False
            if primary_chain is not None and primary_edge.get("mechanism_chain_id") != primary_chain.get("chain_id"):
                invalid.append(edge_prefix + ":primary_causal_edge_not_primary_mechanism")
                sequence_valid = False
            if evidence_id and evidence_id not in {
                str(value) for value in primary_edge.get("evidence_ids") or []
            }:
                invalid.append(edge_prefix + ":primary_causal_edge_does_not_contain_evidence")
                sequence_valid = False
        if not leading_threshold_id:
            incomplete.append(prefix + ":leading_threshold_id_missing")
            sequence_valid = False
        else:
            threshold = threshold_by_id.get(leading_threshold_id)
            if threshold is None:
                invalid.append(prefix + ":leading_threshold_unknown")
                sequence_valid = False
            if forward_judgment_id:
                judgment = judgments_by_id.get(forward_judgment_id)
                if judgment is not None and leading_threshold_id not in {
                    str(value) for value in judgment.get("leading_signal_threshold_ids") or []
                }:
                    invalid.append(prefix + ":leading_threshold_not_forward_judgment_signal")
                    sequence_valid = False
            if primary_chain is not None and leading_threshold_id not in {
                str(value) for value in primary_chain.get("leading_signal_threshold_ids") or []
            }:
                invalid.append(prefix + ":leading_threshold_not_primary_mechanism_signal")
                sequence_valid = False
            if rival_chain is not None and leading_threshold_id not in {
                str(value) for value in rival_chain.get("leading_signal_threshold_ids") or []
            }:
                invalid.append(prefix + ":leading_threshold_not_rival_mechanism_signal")
                sequence_valid = False
            if threshold is not None and threshold.get("discrimination_target") != (pair or {}).get("competitive_test_id"):
                invalid.append(prefix + ":leading_threshold_not_pair_competitive_test")
                sequence_valid = False
        return sequence_valid

    for index, item in enumerate(selection_evidence):
        prefix = f"selection_admission:selection_evidence[{index}]"
        if not isinstance(item, dict):
            invalid.append(prefix + ":not_object")
            continue
        evidence_id, _ = validate_evidence_fact(item, prefix)
        supports_scenario_id = str(item.get("supports_scenario_id") or "").strip()
        if supports_scenario_id not in candidate_ids:
            invalid.append(prefix + ":supports_scenario_not_candidate")
        elif supports_scenario_id == selected_scenario_id:
            supports_selected = True
        for key in (
            "directional_reason", "why_rival_cannot_equally_explain", "distortion_downgrade",
        ):
            if not str(item.get(key) or "").strip():
                incomplete.append(prefix + f":{key}_missing")

        forward_judgment_id = str(item.get("forward_judgment_id") or "").strip()
        primary_causal_edge_id = str(item.get("primary_causal_edge_id") or "").strip()
        leading_threshold_id = str(item.get("leading_threshold_id") or "").strip()
        sequence_valid = validate_selection_sequence(
            prefix=prefix,
            forward_judgment_id=forward_judgment_id,
            leading_threshold_id=leading_threshold_id,
            evidence_edges=[(evidence_id, primary_causal_edge_id)],
        )
        if sequence_valid:
            selected_sequence_judgments.add(forward_judgment_id)

    allowed_bundle_roles = {
        "DECISION_IMPLEMENTATION", "CUSTOMER_OR_COMPETITOR_RESPONSE", "UNIT_ECONOMICS",
        "WORKING_CAPITAL_OR_CASH", "CAPITAL_RETURN",
    }
    for index, bundle in enumerate(selection_evidence_bundles):
        prefix = f"selection_admission:selection_evidence_bundles[{index}]"
        if not isinstance(bundle, dict):
            invalid.append(prefix + ":not_object")
            continue
        bundle_id = str(bundle.get("bundle_id") or "").strip()
        if not bundle_id:
            incomplete.append(prefix + ":bundle_id_missing")
        elif bundle_id in seen_bundle_ids:
            invalid.append(prefix + ":bundle_id_reused")
        else:
            seen_bundle_ids.add(bundle_id)
        supports_scenario_id = str(bundle.get("supports_scenario_id") or "").strip()
        if supports_scenario_id not in candidate_ids:
            invalid.append(prefix + ":supports_scenario_not_candidate")
        elif supports_scenario_id == selected_scenario_id:
            supports_selected = True
        for key in (
            "joint_directional_reason", "joint_rival_exclusion_reason", "joint_distortion_downgrade",
        ):
            if not str(bundle.get(key) or "").strip():
                incomplete.append(prefix + f":{key}_missing")
        components = bundle.get("components")
        if not isinstance(components, list) or len(components) < 2:
            incomplete.append(prefix + ":components_require_two_or_more")
            components = []
        roles: set[str] = set()
        source_groups: set[str] = set()
        source_ids: set[str] = set()
        evidence_edges: list[tuple[str, str]] = []
        for component_index, component in enumerate(components):
            component_prefix = prefix + f":components[{component_index}]"
            if not isinstance(component, dict):
                invalid.append(component_prefix + ":not_object")
                continue
            evidence_id, source_group_id = validate_evidence_fact(component, component_prefix)
            if source_group_id:
                source_groups.add(source_group_id)
            source_id = str(component.get("source_id") or "").strip()
            if source_id:
                source_ids.add(source_id)
            role = str(component.get("component_role") or "").strip()
            if not role:
                incomplete.append(component_prefix + ":component_role_missing")
            elif role not in allowed_bundle_roles:
                invalid.append(component_prefix + ":component_role_invalid")
            else:
                roles.add(role)
            component_forward_judgment_id = str(component.get("forward_judgment_id") or "").strip()
            if not component_forward_judgment_id:
                incomplete.append(component_prefix + ":forward_judgment_id_missing")
            elif component_forward_judgment_id != str(bundle.get("forward_judgment_id") or "").strip():
                invalid.append(component_prefix + ":forward_judgment_id_does_not_match_bundle")
            evidence_edges.append((evidence_id, str(component.get("primary_causal_edge_id") or "").strip()))
        required_roles = {"DECISION_IMPLEMENTATION", "CUSTOMER_OR_COMPETITOR_RESPONSE"}
        if not required_roles.issubset(roles):
            incomplete.append(prefix + ":decision_and_customer_or_competitor_roles_required")
        if len(source_groups) < 2:
            incomplete.append(prefix + ":two_independent_source_groups_required")
        if len(source_ids) < 2:
            incomplete.append(prefix + ":two_distinct_source_ids_required")
        sequence_valid = validate_selection_sequence(
            prefix=prefix,
            forward_judgment_id=str(bundle.get("forward_judgment_id") or "").strip(),
            leading_threshold_id=str(bundle.get("leading_threshold_id") or "").strip(),
            evidence_edges=evidence_edges,
        )
        if sequence_valid:
            selected_sequence_judgments.add(str(bundle.get("forward_judgment_id") or "").strip())
    if not supports_selected:
        incomplete.append("selection_admission:selected_path_directional_evidence_missing")

    for judgment_id in selection_judgment_ids:
        judgment = judgments_by_id.get(judgment_id)
        prefix = "selection_admission:" + judgment_id
        if judgment is None:
            invalid.append(prefix + ":forward_judgment_unknown")
            continue
        if str(judgment.get("scenario_id") or "") != selected_scenario_id:
            invalid.append(prefix + ":not_selected_scenario_judgment")
        if pair_id and str(judgment.get("rival_hypothesis_pair_id") or "") != pair_id:
            invalid.append(prefix + ":rival_pair_link_invalid")
        prediction = judgment.get("prediction") if isinstance(judgment.get("prediction"), dict) else {}
        baseline = judgment.get("baseline") if isinstance(judgment.get("baseline"), dict) else {}
        baseline_prediction = baseline.get("prediction") if isinstance(baseline.get("prediction"), dict) else {}
        if not baseline_prediction:
            incomplete.append(prefix + ":baseline_prediction_missing")
        elif _same_prediction(prediction, baseline_prediction):
            invalid.append(prefix + ":baseline_prediction_not_distinct")
        outcome = judgment.get("observable_outcome") if isinstance(judgment.get("observable_outcome"), dict) else {}
        contract_outcome = dict(outcome)
        contract_outcome["unit"] = prediction.get("unit")
        contract_invalid, contract_incomplete = contract_findings(
            contract_outcome,
            prefix=prefix + ":observable_outcome",
            allowed_source_types={
                str(source_type).strip()
                for source_type in outcome.get("allowed_source_types") or []
                if str(source_type).strip()
            },
        )
        invalid.extend(contract_invalid)
        incomplete.extend(contract_incomplete)
        if judgment_id not in selected_sequence_judgments:
            incomplete.append(prefix + ":selection_evidence_sequence_missing")

    return {"status": status}, invalid, incomplete


def _cjo_probability_qualification_findings(
    payload: dict[str, Any], *, evidence: dict[str, dict[str, Any]],
    registry: EvidenceRegistry, output: Path | None, case_library_dir: str | Path | None,
) -> tuple[list[str], list[str]]:
    """Require an empirical basis before a new CJO claims calibrated odds.

    This is intentionally a narrow receipt, not a second case library.  A
    qualified CJO may rely on either multiple settled, independently recorded
    episodes or an externally observable frequency.  Analyst confidence and a
    named scenario are never substitutes for either route.
    """
    invalid: list[str] = []
    incomplete: list[str] = []
    raw = payload.get("probability_qualification")
    if not isinstance(raw, dict):
        return invalid, ["company_judgment_probability_qualification_missing"]
    for key in ("event_definition", "calibration_plan", "as_of"):
        if not str(raw.get(key) or "").strip():
            incomplete.append(f"company_judgment_probability_qualification:{key}_missing")
    if raw.get("as_of") not in (None, "") and _iso_date(raw.get("as_of")) is None:
        invalid.append("company_judgment_probability_qualification:as_of_invalid")

    episodes = raw.get("independent_episode_references")
    external_evidence_ids = raw.get("external_frequency_evidence_ids")
    has_episodes = isinstance(episodes, list) and bool(episodes)
    has_external_frequency = isinstance(external_evidence_ids, list) and bool(external_evidence_ids)
    if not has_episodes and not has_external_frequency:
        incomplete.append("company_judgment_probability_qualification:empirical_basis_missing")

    if episodes not in (None, [], "") and not isinstance(episodes, list):
        invalid.append("company_judgment_probability_qualification:independent_episode_references_not_array")
        episodes = []
    if isinstance(episodes, list) and episodes:
        if len(episodes) < 2:
            incomplete.append("company_judgment_probability_qualification:two_independent_episodes_required")
        seen_cases: set[str] = set()
        for index, reference in enumerate(episodes):
            prefix = f"company_judgment_probability_qualification:independent_episode_references[{index}]"
            if not isinstance(reference, dict):
                invalid.append(prefix + ":not_object")
                continue
            case_id = str(reference.get("case_id") or "").strip()
            episode_id = str(reference.get("episode_id") or "").strip()
            outcome_event_id = str(reference.get("outcome_event_id") or "").strip()
            if not case_id or not episode_id or not outcome_event_id:
                incomplete.append(prefix + ":identity_missing")
                continue
            if case_id in seen_cases:
                invalid.append(prefix + ":case_not_independent")
            seen_cases.add(case_id)
            verified = validate_verified_episode_reference(
                case_id=case_id,
                episode_id=episode_id,
                outcome_event_id=outcome_event_id,
                library_dir=case_library_dir,
            )
            invalid.extend(prefix + ":" + item for item in verified.get("invalid_findings") or [])
            incomplete.extend(prefix + ":" + item for item in verified.get("incomplete_findings") or [])

    if external_evidence_ids not in (None, [], "") and not isinstance(external_evidence_ids, list):
        invalid.append("company_judgment_probability_qualification:external_frequency_evidence_ids_not_array")
        external_evidence_ids = []
    if isinstance(external_evidence_ids, list) and external_evidence_ids:
        if not str(raw.get("external_frequency_definition") or "").strip():
            incomplete.append("company_judgment_probability_qualification:external_frequency_definition_missing")
        for index, evidence_id in enumerate(external_evidence_ids):
            prefix = f"company_judgment_probability_qualification:external_frequency_evidence_ids[{index}]"
            row = evidence.get(str(evidence_id))
            if row is None:
                invalid.append(prefix + ":evidence_unknown")
                continue
            authority = str(row.get("authority") or "").strip().lower()
            if authority in {"company_filing", "company_disclosure", "management"}:
                invalid.append(prefix + ":company_source_is_not_external_frequency")
            # The evidence identity is registered only when the claimed raw
            # fact exists in this CJO; a bare plausible source label must not
            # manufacture an external-frequency basis.
            canonical, unresolved = registry.canonicalize_anchor(str(evidence_id))
            if output is not None and (unresolved or not canonical):
                invalid.append(prefix + ":source_unresolved")
            elif canonical and set(canonical).issubset(INTERNAL_EVIDENCE):
                invalid.append(prefix + ":circular_internal_source")
    return list(dict.fromkeys(invalid)), list(dict.fromkeys(incomplete))


def validate_thesis_test_ledger(
    payload: dict[str, Any], *, output_dir: str | Path | None = None,
    report_text: str = "", enforced: bool = False, monitoring_required: bool = False,
    forward_judgment_required: bool = False, rival_hypothesis_pair_required: bool = False,
    company_judgment_lineage_required: bool = False,
    required_trigger_metric_ids: set[str] | frozenset[str] = REQUIRED_TRIGGER_METRICS,
    case_library_dir: str | Path | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []; incomplete: list[str] = []; warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION: invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or "").strip(): invalid.append("report_id_missing")
    if not str(payload.get("change_reason") or "").strip(): incomplete.append("change_reason_missing")
    freeze = payload.get("freeze") if isinstance(payload.get("freeze"), dict) else {}
    is_series_contract_freeze = (
        freeze.get("forward_judgment_contract_version") == FORWARD_JUDGMENT_CONTRACT_VERSION
    )
    analysis_purpose = str(payload.get("analysis_purpose") or "INVESTMENT_DECISION")
    if analysis_purpose not in ANALYSIS_PURPOSES:
        invalid.append("analysis_purpose_invalid")
    investment_purpose = analysis_purpose == "INVESTMENT_DECISION"
    industry_architecture_provenance_required = (
        analysis_purpose == "COMPANY_JUDGMENT_ONLY"
        and freeze.get("industry_architecture_provenance_contract_version")
        == INDUSTRY_ARCHITECTURE_PROVENANCE_CONTRACT_VERSION
    )
    transmission_channels = (
        TRANSMISSION_CHANNELS if investment_purpose else CJO_TRANSMISSION_CHANNELS
    )
    output = Path(output_dir) if output_dir is not None else None
    if output is not None:
        try:
            from scripts.case_selection_register import validate_output_case_selection
        except ModuleNotFoundError:
            from case_selection_register import validate_output_case_selection
        selection_admission = validate_output_case_selection(output)
        if selection_admission.get("state") in {"INVALID", "INCOMPLETE"}:
            invalid.extend(
                "case_selection:" + item
                for item in selection_admission.get("invalid_findings") or []
            )
            incomplete.extend(
                "case_selection:" + item
                for item in selection_admission.get("incomplete_findings") or []
            )
    registry = EvidenceRegistry()
    if output is not None and output.is_dir(): registry.register_from_output_dir(str(output))
    claim_ledger = _read_json(output / "claim_evidence.json") if output is not None else {}
    claim_ids = _ids(claim_ledger.get("claims") or [], "claim_id")
    evidence = {str(item.get("evidence_id")): item for claim in claim_ledger.get("claims") or [] if isinstance(claim, dict) for item in claim.get("raw_facts") or [] if isinstance(item, dict) and item.get("evidence_id")}
    document_manifest = _read_json(output / "document_manifest.json") if output is not None else {}
    documents_by_id = {
        str(item.get("doc_id")): item
        for item in document_manifest.get("documents") or []
        if isinstance(item, dict) and item.get("doc_id")
    }
    projected_document_source_ids = {
        str(item.get("source_id") or "").strip()
        for item in documents_by_id.values()
        if str(item.get("source_id") or "").strip()
    }
    pit_source_provenance = _read_json(output / "pit_source_provenance.json") if output is not None else {}
    pit_source_provenance_by_id = {
        str(item.get("source_id") or "").strip(): item
        for item in pit_source_provenance.get("sources") or []
        if isinstance(item, dict) and str(item.get("source_id") or "").strip()
    }
    fact_observations = _read_json(output / "fact_observations.json") if output is not None else {}
    observations_by_id = {
        str(item.get("observation_id")): item
        for item in fact_observations.get("observations") or []
        if isinstance(item, dict) and item.get("observation_id")
    }
    decisions = {str(item.get("entry_id")): item for item in (_read_json(output / "decision_ledger.json").get("entries") or []) if isinstance(item, dict) and item.get("entry_id") and item.get("status") == "active"} if output is not None else {}
    valuation_models = {
        str(item.get("model_id")): item
        for item in (_read_json(output / "valuation_model.json").get("models") or [])
        if isinstance(item, dict) and item.get("model_id") and item.get("status") == "active"
    } if output is not None else {}
    chapter_text = _chapters(report_text)

    tests = payload.get("competitive_tests"); thresholds = payload.get("thresholds"); probability_sets = payload.get("probability_sets")
    if not isinstance(tests, list): invalid.append("competitive_tests_not_array"); tests = []
    if not isinstance(thresholds, list): invalid.append("thresholds_not_array"); thresholds = []
    if not isinstance(probability_sets, list): invalid.append("probability_sets_not_array"); probability_sets = []
    probability_mode = str(payload.get("probability_mode") or "").strip()
    cjo_no_probability = False
    cjo_qualified_probability = False
    if not investment_purpose and probability_mode:
        if probability_mode not in CJO_PROBABILITY_MODES:
            invalid.append("company_judgment_probability_mode_invalid")
        elif probability_mode == "NO_PROBABILITY":
            cjo_no_probability = True
            if probability_sets:
                invalid.append("company_judgment_no_probability_probability_sets_forbidden")
            if payload.get("probability_qualification") not in (None, "", [], {}):
                invalid.append("company_judgment_no_probability_qualification_forbidden")
        else:
            cjo_qualified_probability = True
            qualification_invalid, qualification_incomplete = _cjo_probability_qualification_findings(
                payload, evidence=evidence, registry=registry, output=output,
                case_library_dir=case_library_dir,
            )
            invalid.extend(qualification_invalid)
            incomplete.extend(qualification_incomplete)
    selection_raw = payload.get("selection_admission")
    selection_status = str(selection_raw.get("status") or "NOT_SELECTION_ELIGIBLE") if isinstance(selection_raw, dict) else ""
    if cjo_no_probability:
        if selection_status not in {"NO_PRIMARY", "SELECTION_ADMITTED"}:
            incomplete.append("company_judgment_no_probability_selection_status_required")
        if selection_status == "NO_PRIMARY" and payload.get("central_path") is not None:
            invalid.append("company_judgment_no_probability_no_primary_cannot_carry_central_path")
        if selection_status == "SELECTION_ADMITTED" and payload.get("central_path") is None:
            incomplete.append("company_judgment_no_probability_selection_admitted_central_path_missing")
    if enforced and not tests: incomplete.append("competitive_test_missing")
    test_ids = _ids(tests, "test_id"); threshold_ids = _ids(thresholds, "threshold_id"); probability_ids = _ids(probability_sets, "set_id")
    threshold_by_id = {
        str(item.get("threshold_id") or ""): item
        for item in thresholds if isinstance(item, dict) and str(item.get("threshold_id") or "").strip()
    }
    probability_scenarios = {
        str(item.get("set_id")): _ids(item.get("estimates") or [], "scenario_id")
        for item in probability_sets if isinstance(item, dict) and item.get("set_id")
    }
    for items, key, label in ((tests, "test_id", "test"), (thresholds, "threshold_id", "threshold"), (probability_sets, "set_id", "probability_set")):
        values = [str(item.get(key)) for item in items if isinstance(item, dict) and item.get(key)]
        if len(values) != len(set(values)): invalid.append("duplicate_" + label + "_id")

    for idx, pset in enumerate(probability_sets):
        prefix = f"probability_sets[{idx}]"
        if not isinstance(pset, dict): invalid.append(prefix + ":not_object"); continue
        sid = str(pset.get("set_id") or prefix)
        if pset.get("mutually_exclusive") is not True: invalid.append(f"{sid}:not_mutually_exclusive")
        if pset.get("collectively_exhaustive") is not True: invalid.append(f"{sid}:not_collectively_exhaustive")
        estimates = pset.get("estimates")
        if not isinstance(estimates, list) or len(estimates) < 2: invalid.append(f"{sid}:estimates_invalid"); estimates = []
        scenario_ids = [str(item.get("scenario_id")) for item in estimates if isinstance(item, dict)]
        if len(scenario_ids) != len(set(scenario_ids)): invalid.append(f"{sid}:duplicate_scenario_id")
        total = 0.0
        for eidx, estimate in enumerate(estimates):
            ep = f"{sid}.estimates[{eidx}]"
            if not isinstance(estimate, dict): invalid.append(ep + ":not_object"); continue
            value = _num(estimate.get("value")); kind = estimate.get("kind")
            if not str(estimate.get("scenario_id") or "").strip(): invalid.append(ep + ":scenario_id_missing")
            if not str(estimate.get("label") or "").strip(): incomplete.append(ep + ":label_missing")
            if kind not in PROBABILITY_KINDS: invalid.append(ep + ":kind_invalid")
            elif cjo_qualified_probability and kind not in CJO_EMPIRICAL_PROBABILITY_KINDS:
                invalid.append(ep + ":company_judgment_qualified_probability_requires_empirical_kind")
            if value is None or not 0 <= value <= 1: invalid.append(ep + ":value_invalid")
            else: total += value
            if not str(estimate.get("basis") or "").strip(): incomplete.append(ep + ":basis_missing")
            interval = estimate.get("interval")
            if not isinstance(interval, list) or len(interval) != 2 or any(_num(v) is None for v in interval): invalid.append(ep + ":interval_invalid")
            else:
                lo, hi = float(interval[0]), float(interval[1])
                if not (0 <= lo <= hi <= 1) or (value is not None and not lo <= value <= hi): invalid.append(ep + ":interval_inconsistent")
                if kind == "analyst_subjective" and hi - lo < 0.10 and not str(estimate.get("calibration_history_id") or "").strip(): invalid.append(ep + ":subjective_false_precision")
            sources = estimate.get("source_ids") or []
            if kind in {"frequency", "base_rate"} and not sources: incomplete.append(ep + ":empirical_source_missing")
            for source in sources:
                canonical, unresolved = registry.canonicalize_anchor(str(source))
                if output is not None and (unresolved or not canonical): invalid.append(ep + f":source_unresolved:{source}")
                elif canonical and set(canonical).issubset(INTERNAL_EVIDENCE): invalid.append(ep + ":circular_internal_source")
            if kind == "analyst_subjective" and _decimals(estimate.get("value")) > 2 and not estimate.get("calibration_history_id"): invalid.append(ep + ":subjective_probability_overprecise")
            if not str(estimate.get("as_of") or "").strip(): incomplete.append(ep + ":as_of_missing")
        if estimates and not math.isclose(total, 1.0, abs_tol=0.01): invalid.append(f"{sid}:probabilities_not_sum_to_one:{total:.4f}")
        if monitoring_required:
            due = str(pset.get("resolution_due") or "").strip()
            try:
                due_date = datetime.fromisoformat(due[:10]).date()
                as_of_dates = [datetime.fromisoformat(str(item.get("as_of"))[:10]).date() for item in estimates if item.get("as_of")]
            except ValueError:
                invalid.append(f"{sid}:resolution_due_invalid")
            else:
                if not as_of_dates or due_date <= max(as_of_dates):
                    invalid.append(f"{sid}:resolution_due_not_after_prediction")
        chapters = pset.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{sid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if sid not in _ANCHOR_PATTERNS["probability"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"probability_reference_missing:Ch{chapter}:{sid}")

    covered_trigger_metrics: set[str] = set()
    for idx, threshold in enumerate(thresholds):
        prefix = f"thresholds[{idx}]"
        if not isinstance(threshold, dict): invalid.append(prefix + ":not_object"); continue
        tid = str(threshold.get("threshold_id") or prefix)
        for key in ("metric", "unit", "operator", "basis_description", "observation_frequency", "window", "aggregation", "accounting_definition", "discrimination_target"):
            if not str(threshold.get(key) or "").strip(): incomplete.append(f"{tid}:{key}_missing")
        current, value = _num(threshold.get("current_value")), _num(threshold.get("threshold_value"))
        if current is None or value is None: invalid.append(f"{tid}:numeric_value_invalid")
        if threshold.get("basis_type") not in THRESHOLD_BASES: invalid.append(f"{tid}:basis_type_invalid")
        if investment_purpose and threshold.get("action") not in ACTIONS: invalid.append(f"{tid}:action_invalid")
        if not investment_purpose and any(
            threshold.get(key) not in (None, "", [], {})
            for key in ("action", "decision_entry_ids")
        ):
            invalid.append(f"{tid}:company_judgment_cannot_carry_action_or_decision")
        if threshold.get("operator") not in OPERATORS: invalid.append(f"{tid}:operator_invalid")
        if threshold.get("aggregation") not in {"single_period", "rolling_average", "consecutive_periods", "cumulative"}: invalid.append(f"{tid}:aggregation_invalid")
        if threshold.get("seasonal_adjustment") not in {"adjusted", "not_needed", "unavailable"}: incomplete.append(f"{tid}:seasonal_adjustment_missing")
        precision = threshold.get("precision") or {}
        if not isinstance(precision, dict): invalid.append(f"{tid}:precision_invalid"); precision = {}
        justified = precision.get("justified_decimals")
        if not isinstance(justified, int) or justified < 0: invalid.append(f"{tid}:precision_invalid")
        elif value is not None and _decimals(threshold.get("threshold_value")) > justified: invalid.append(f"{tid}:pseudo_precision")
        if not str(precision.get("basis") or "").strip(): incomplete.append(f"{tid}:precision_basis_missing")
        if threshold.get("basis_type") == "expert_judgment":
            warnings.append(f"{tid}:expert_judgment_threshold")
            if threshold.get("decision_entry_ids") and not str(threshold.get("independent_validation") or "").strip(): incomplete.append(f"{tid}:expert_judgment_trigger_needs_validation")
        if threshold.get("discrimination_target") not in test_ids | {"decision_rule"}: invalid.append(f"{tid}:unknown_discrimination_target")
        if not investment_purpose and threshold.get("discrimination_target") == "decision_rule":
            invalid.append(f"{tid}:company_judgment_cannot_target_decision_rule")
        sources = threshold.get("source_ids") or []
        if not sources: incomplete.append(f"{tid}:source_ids_missing")
        for source in sources:
            canonical, unresolved = registry.canonicalize_anchor(str(source))
            if output is not None and (unresolved or not canonical): invalid.append(f"{tid}:source_unresolved:{source}")
            elif canonical and set(canonical).issubset(INTERNAL_EVIDENCE): invalid.append(f"{tid}:circular_internal_source")
        refs = threshold.get("decision_entry_ids") or []
        if investment_purpose:
            if not refs: incomplete.append(f"{tid}:decision_entry_ids_missing")
            for ref in refs:
                entry = decisions.get(str(ref))
                if output is not None and entry is None: invalid.append(f"{tid}:unknown_decision_entry:{ref}")
                elif entry and entry.get("metric_id") in REQUIRED_TRIGGER_METRICS:
                    metric_id = str(entry.get("metric_id")); covered_trigger_metrics.add(metric_id)
                    allowed_actions = {"trigger.buy": {"buy", "increase"}, "trigger.reduce": {"reduce", "reassess"}, "trigger.exit": {"exit", "avoid"}}
                    if threshold.get("action") not in allowed_actions[metric_id]: invalid.append(f"{tid}:action_decision_trigger_mismatch:{metric_id}")
        chapters = threshold.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{tid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if tid not in _ANCHOR_PATTERNS["threshold"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"threshold_reference_missing:Ch{chapter}:{tid}")
    if enforced and investment_purpose:
        for metric in sorted(set(required_trigger_metric_ids) - covered_trigger_metrics): incomplete.append("decision_trigger_threshold_missing:" + metric)

    for idx, test in enumerate(tests):
        prefix = f"competitive_tests[{idx}]"
        if not isinstance(test, dict): invalid.append(prefix + ":not_object"); continue
        tid = str(test.get("test_id") or prefix)
        claim_id = str(test.get("thesis_claim_id") or "")
        if output is not None and claim_id not in claim_ids: invalid.append(f"{tid}:unknown_thesis_claim:{claim_id}")
        for key in ("primary_explanation", "strongest_alternative"):
            if not str(test.get(key) or "").strip(): incomplete.append(f"{tid}:{key}_missing")
        if str(test.get("primary_explanation") or "").strip() == str(test.get("strongest_alternative") or "").strip(): invalid.append(f"{tid}:alternative_not_competitive")
        alt_evidence = test.get("alternative_evidence_ids") or []
        if not alt_evidence: incomplete.append(f"{tid}:alternative_evidence_missing")
        for eid in alt_evidence:
            if output is not None and str(eid) not in evidence: invalid.append(f"{tid}:unknown_alternative_evidence:{eid}")
            elif evidence.get(str(eid), {}).get("support_type") not in {"contradicts", "context"}: invalid.append(f"{tid}:alternative_evidence_does_not_support_alternative:{eid}")
        observations = test.get("discriminating_observations")
        if not isinstance(observations, list) or not observations: incomplete.append(f"{tid}:discriminating_observation_missing"); observations = []
        for oidx, obs in enumerate(observations):
            op = f"{tid}.observations[{oidx}]"
            if not isinstance(obs, dict): invalid.append(op + ":not_object"); continue
            for key in ("observation_id", "metric", "availability", "primary_prediction", "alternative_prediction", "update_rule"):
                if not str(obs.get(key) or "").strip(): incomplete.append(f"{op}:{key}_missing")
            if str(obs.get("primary_prediction") or "").strip() == str(obs.get("alternative_prediction") or "").strip(): invalid.append(f"{op}:predictions_not_discriminating")
            diagnosticity = obs.get("diagnosticity")
            if forward_judgment_required or diagnosticity is not None:
                if not isinstance(diagnosticity, dict):
                    incomplete.append(f"{op}:diagnosticity_missing")
                else:
                    primary_likelihood = str(diagnosticity.get("primary_likelihood") or "").strip()
                    alternative_likelihood = str(diagnosticity.get("alternative_likelihood") or "").strip()
                    for key, likelihood in (
                        ("primary_likelihood", primary_likelihood),
                        ("alternative_likelihood", alternative_likelihood),
                    ):
                        if not likelihood:
                            incomplete.append(f"{op}:diagnosticity_{key}_missing")
                        elif likelihood not in DIAGNOSTIC_LIKELIHOODS:
                            invalid.append(f"{op}:diagnosticity_{key}_invalid")
                    if primary_likelihood and alternative_likelihood and primary_likelihood == alternative_likelihood:
                        invalid.append(f"{op}:diagnosticity_not_asymmetric")
                    if not str(diagnosticity.get("rationale") or "").strip():
                        incomplete.append(f"{op}:diagnosticity_rationale_missing")
            if obs.get("threshold_id") not in threshold_ids: invalid.append(f"{op}:unknown_threshold")
        probability_set_id = test.get("probability_set_id")
        if cjo_no_probability:
            if "probability_set_id" in test:
                invalid.append(f"{tid}:company_judgment_no_probability_set_id_forbidden")
            for key in ("primary_scenario_id", "alternative_scenario_id"):
                if not str(test.get(key) or "").strip():
                    incomplete.append(f"{tid}:{key}_missing")
            if test.get("primary_scenario_id") == test.get("alternative_scenario_id"):
                invalid.append(f"{tid}:scenario_mapping_not_distinct")
        elif probability_set_id not in probability_ids: invalid.append(f"{tid}:unknown_probability_set")
        else:
            selected = next((
                item for item in probability_sets
                if isinstance(item, dict) and item.get("set_id") == probability_set_id
            ), {})
            scenarios = _ids(selected.get("estimates") or [], "scenario_id")
            if test.get("primary_scenario_id") not in scenarios: invalid.append(f"{tid}:primary_scenario_unknown")
            if test.get("alternative_scenario_id") not in scenarios: invalid.append(f"{tid}:alternative_scenario_unknown")
            if test.get("primary_scenario_id") == test.get("alternative_scenario_id"): invalid.append(f"{tid}:scenario_mapping_not_distinct")
        flip = test.get("flip_condition") or {}
        if not isinstance(flip, dict):
            invalid.append(f"{tid}:flip_condition_invalid")
            flip = {}
        if flip.get("threshold_id") not in threshold_ids: invalid.append(f"{tid}:flip_threshold_unknown")
        for key in ("basis", "window"):
            if not str(flip.get(key) or "").strip(): incomplete.append(f"{tid}:flip_{key}_missing")
        if investment_purpose:
            if _num(test.get("valuation_after_flip")) is None: invalid.append(f"{tid}:valuation_after_flip_invalid")
            if _num(test.get("position_after_flip")) is None: invalid.append(f"{tid}:position_after_flip_invalid")
            if test.get("action_after_flip") not in ACTIONS: invalid.append(f"{tid}:action_after_flip_invalid")
            refs = test.get("decision_entry_ids") or []
            if not refs: incomplete.append(f"{tid}:decision_entry_ids_missing")
            for ref in refs:
                if output is not None and str(ref) not in decisions: invalid.append(f"{tid}:unknown_decision_entry:{ref}")
        elif any(
            test.get(key) not in (None, "", [], {})
            for key in (
                "valuation_after_flip", "position_after_flip", "action_after_flip",
                "decision_entry_ids",
            )
        ):
            invalid.append(f"{tid}:company_judgment_cannot_carry_investment_flip")
        chapters = test.get("chapters") or []
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{tid}:chapters_invalid")
        elif enforced:
            for chapter in chapters:
                if tid not in _ANCHOR_PATTERNS["test"].findall(chapter_text.get(int(chapter), "")): incomplete.append(f"thesis_test_reference_missing:Ch{chapter}:{tid}")

    # G1-J extends the existing thesis ledger instead of creating a parallel
    # forecast system.  The policy flag keeps historical ledgers readable,
    # while all new unified runs must freeze one selected path and 3-5
    # decision-material, settleable forward judgments.
    forward_invalid: list[str] = []
    forward_incomplete: list[str] = []
    central = payload.get("central_path")
    judgments = payload.get("forward_judgments")
    forward_present = central is not None or judgments is not None
    central_id = ""
    central_selected_scenario_id = ""
    mechanism_chains = payload.get("mechanism_chains")
    mechanism_items: list[dict[str, Any]] = []
    mechanism_by_id: dict[str, dict[str, Any]] = {}

    if forward_judgment_required or forward_present:
        if mechanism_chains is None:
            forward_incomplete.append("mechanism_chains_missing")
        elif not isinstance(mechanism_chains, list):
            forward_invalid.append("mechanism_chains_not_array")
        else:
            mechanism_items = [item for item in mechanism_chains if isinstance(item, dict)]
            if len(mechanism_items) != len(mechanism_chains):
                forward_invalid.append("mechanism_chains_item_not_object")
            if not mechanism_items:
                forward_incomplete.append("mechanism_chains_empty")
    for idx, chain in enumerate(mechanism_items):
        cid = str(chain.get("chain_id") or f"mechanism_chains[{idx}]")
        required_chain_keys = (
            ("chain_id", "scenario_id", "mechanism") if cjo_no_probability
            else ("chain_id", "probability_set_id", "scenario_id", "mechanism")
        )
        for key in required_chain_keys:
            if not str(chain.get(key) or "").strip():
                forward_incomplete.append(f"{cid}:{key}_missing")
        if cid in mechanism_by_id:
            forward_invalid.append("duplicate_mechanism_chain_id")
        else:
            mechanism_by_id[cid] = chain
        probability_set_id = str(chain.get("probability_set_id") or "")
        scenario_id = str(chain.get("scenario_id") or "")
        if cjo_no_probability:
            if "probability_set_id" in chain:
                forward_invalid.append(f"{cid}:company_judgment_no_probability_set_id_forbidden")
        elif probability_set_id not in probability_ids:
            forward_invalid.append(f"{cid}:unknown_probability_set")
        elif scenario_id not in probability_scenarios.get(probability_set_id, set()):
            forward_invalid.append(f"{cid}:unknown_scenario")
        signal_ids = chain.get("leading_signal_threshold_ids")
        if not isinstance(signal_ids, list) or not signal_ids:
            forward_incomplete.append(f"{cid}:leading_signal_threshold_ids_missing")
            signal_ids = []
        for threshold_id in signal_ids:
            if str(threshold_id) not in threshold_ids:
                forward_invalid.append(f"{cid}:unknown_leading_signal:{threshold_id}")
        transmission = chain.get("transmission")
        if not isinstance(transmission, dict):
            forward_invalid.append(f"{cid}:transmission_invalid")
            transmission = {}
        for channel in transmission_channels:
            bridge = transmission.get(channel)
            if not isinstance(bridge, dict):
                forward_incomplete.append(f"{cid}:transmission_{channel}_missing")
                continue
            direction = bridge.get("direction")
            if direction not in TRANSMISSION_DIRECTIONS:
                forward_invalid.append(f"{cid}:transmission_{channel}_direction_invalid")
            if not str(bridge.get("basis") or "").strip():
                forward_incomplete.append(f"{cid}:transmission_{channel}_basis_missing")
            if direction in {"unknown", "not_material"} and not str(bridge.get("conservative_treatment") or "").strip():
                forward_incomplete.append(f"{cid}:transmission_{channel}_conservative_treatment_missing")
        if investment_purpose:
            decision_ids = chain.get("decision_entry_ids")
            if not isinstance(decision_ids, list) or not decision_ids:
                forward_incomplete.append(f"{cid}:decision_entry_ids_missing")
                decision_ids = []
            for decision_id in decision_ids:
                if output is not None and str(decision_id) not in decisions:
                    forward_invalid.append(f"{cid}:unknown_decision_entry:{decision_id}")
        elif chain.get("decision_entry_ids") not in (None, "", [], {}):
            forward_invalid.append(f"{cid}:company_judgment_cannot_carry_decision")
        if not investment_purpose and any(
            transmission.get(channel) not in (None, "", [], {})
            for channel in ("valuation", "expected_return")
        ):
            forward_invalid.append(f"{cid}:company_judgment_cannot_carry_investment_transmission")

    central_required = forward_judgment_required and not (
        cjo_no_probability and selection_status == "NO_PRIMARY"
    )
    if central_required and central is None:
        forward_incomplete.append("central_path_missing")
    if forward_judgment_required and judgments is None:
        forward_incomplete.append("forward_judgments_missing")

    if central is not None:
        if not isinstance(central, dict):
            forward_invalid.append("central_path_not_object")
            central = {}
        central_id = str(central.get("path_id") or "").strip()
        central_required_keys = (
            ("path_id", "statement", "as_of", "selection_basis") if cjo_no_probability
            else ("path_id", "statement", "as_of", "why_more_likely")
        )
        for key in central_required_keys:
            if not str(central.get(key) or "").strip():
                forward_incomplete.append(f"central_path:{key}_missing")
        horizon = _num(central.get("horizon_years"))
        if horizon not in {3.0, 5.0}:
            forward_invalid.append("central_path:horizon_years_must_be_3_or_5")
        probability_set_id = str(central.get("probability_set_id") or "")
        selected_scenario_id = str(central.get("selected_scenario_id") or "")
        central_selected_scenario_id = selected_scenario_id
        competing_scenario_id = str(central.get("competing_scenario_id") or "")
        if cjo_no_probability:
            if "probability_set_id" in central:
                forward_invalid.append("central_path:company_judgment_no_probability_set_id_forbidden")
            if "why_more_likely" in central:
                forward_invalid.append("central_path:company_judgment_no_probability_more_likely_forbidden")
            if not selected_scenario_id or not competing_scenario_id:
                forward_incomplete.append("central_path:scenario_identity_missing")
            elif selected_scenario_id == competing_scenario_id:
                forward_invalid.append("central_path:scenarios_not_distinct")
            if _iso_date(central.get("as_of")) is None:
                forward_invalid.append("central_path:as_of_invalid")
        elif probability_set_id not in probability_ids:
            forward_invalid.append("central_path:unknown_probability_set")
        else:
            scenarios = probability_scenarios.get(probability_set_id, set())
            if selected_scenario_id not in scenarios:
                forward_invalid.append("central_path:selected_scenario_unknown")
            if competing_scenario_id not in scenarios:
                forward_invalid.append("central_path:competing_scenario_unknown")
            if selected_scenario_id == competing_scenario_id:
                forward_invalid.append("central_path:scenarios_not_distinct")
            selected_set = next((
                item for item in probability_sets
                if isinstance(item, dict) and item.get("set_id") == probability_set_id
            ), {})
            estimates = selected_set.get("estimates") or []
            outcome_scope = str(selected_set.get("outcome_scope") or "")
            if not outcome_scope:
                forward_incomplete.append("central_path:probability_set_outcome_scope_missing")
            elif outcome_scope != TERMINAL_OUTCOME_SCOPE:
                forward_invalid.append("central_path:probability_set_not_terminal_operating_outcome")
            if not str(selected_set.get("outcome_space_definition") or "").strip():
                forward_incomplete.append("central_path:outcome_space_definition_missing")
            set_horizon = _num(selected_set.get("horizon_years"))
            if set_horizon is None:
                forward_incomplete.append("central_path:probability_set_horizon_years_missing")
            elif set_horizon not in {3.0, 5.0}:
                forward_invalid.append("central_path:probability_set_horizon_years_must_be_3_or_5")
            elif horizon in {3.0, 5.0} and set_horizon != horizon:
                forward_invalid.append("central_path:probability_set_horizon_mismatch")
            for eidx, estimate in enumerate(estimates):
                if not isinstance(estimate, dict):
                    continue
                ep = f"{probability_set_id}.estimates[{eidx}]"
                role = estimate.get("scenario_role")
                if role not in SCENARIO_ROLES:
                    forward_incomplete.append(f"{ep}:scenario_role_missing")
                elif role != "TERMINAL_OUTCOME":
                    forward_invalid.append(f"{ep}:scenario_role_not_terminal_outcome")
            selected_estimate = next((
                item for item in estimates
                if isinstance(item, dict) and item.get("scenario_id") == selected_scenario_id
            ), {})
            selected_value = _num(selected_estimate.get("value"))
            other_values = [
                _num(item.get("value")) for item in estimates
                if isinstance(item, dict) and item.get("scenario_id") != selected_scenario_id
            ]
            if selected_value is not None and any(
                value is not None and value > selected_value for value in other_values
            ):
                forward_invalid.append("central_path:selected_scenario_not_most_likely")
            central_as_of = _iso_date(central.get("as_of"))
            selected_as_of = _iso_date(selected_estimate.get("as_of"))
            if central_as_of is None:
                forward_invalid.append("central_path:as_of_invalid")
            elif selected_as_of is not None and central_as_of != selected_as_of:
                forward_invalid.append("central_path:as_of_probability_identity_mismatch")
        central_test_ids = central.get("competitive_test_ids")
        if not isinstance(central_test_ids, list) or not central_test_ids:
            forward_incomplete.append("central_path:competitive_test_ids_missing")
            central_test_ids = []
        for test_id in central_test_ids:
            if str(test_id) not in test_ids:
                forward_invalid.append(f"central_path:unknown_competitive_test:{test_id}")
        selected_tests = [
            item for item in tests
            if isinstance(item, dict) and str(item.get("test_id")) in {str(value) for value in central_test_ids}
        ]
        if (cjo_no_probability or probability_set_id in probability_ids) and selected_scenario_id:
            if not any(
                item.get("primary_scenario_id") == selected_scenario_id
                and (cjo_no_probability or item.get("probability_set_id") == probability_set_id)
                for item in selected_tests
            ):
                forward_invalid.append("central_path:selected_scenario_not_primary_explanation")
            if not any(
                chain.get("scenario_id") == selected_scenario_id
                and (cjo_no_probability or chain.get("probability_set_id") == probability_set_id)
                for chain in mechanism_items
            ):
                forward_incomplete.append("central_path:mechanism_chain_missing")
        chapters = central.get("chapters")
        if not isinstance(chapters, list) or not chapters or any(
            not isinstance(chapter, int) or chapter < 0 or chapter > 14 for chapter in chapters
        ):
            forward_invalid.append("central_path:chapters_invalid")
        elif enforced and central_id:
            for chapter in chapters:
                if central_id not in _ANCHOR_PATTERNS["central"].findall(chapter_text.get(chapter, "")):
                    forward_incomplete.append(f"central_path_reference_missing:Ch{chapter}:{central_id}")

    forward_items: list[dict[str, Any]] = []
    if judgments is not None:
        if not isinstance(judgments, list):
            forward_invalid.append("forward_judgments_not_array")
        else:
            forward_items = [item for item in judgments if isinstance(item, dict)]
            if len(forward_items) != len(judgments):
                forward_invalid.append("forward_judgments_item_not_object")
            if len(judgments) < 3:
                forward_incomplete.append("forward_judgments_fewer_than_3")
            if len(judgments) > 5:
                forward_invalid.append("forward_judgments_more_than_5")

    judgment_ids = [str(item.get("judgment_id") or "") for item in forward_items]
    if len([value for value in judgment_ids if value]) != len(set(value for value in judgment_ids if value)):
        forward_invalid.append("duplicate_forward_judgment_id")
    baseline_ids: set[str] = set()
    settlement_claim_ids: set[str] = set()
    transmission_coverage: set[str] = set()
    linked_decision_metrics: set[str] = set()
    for idx, judgment in enumerate(forward_items):
        jid = str(judgment.get("judgment_id") or f"forward_judgments[{idx}]")
        for key in ("judgment_id", "statement", "falsifier"):
            if not str(judgment.get(key) or "").strip():
                forward_incomplete.append(f"{jid}:{key}_missing")
        if judgment.get("materiality") not in FORWARD_MATERIALITIES:
            forward_invalid.append(f"{jid}:materiality_invalid")
        elif not investment_purpose and judgment.get("materiality") in {"VALUATION", "RETURN"}:
            forward_invalid.append(f"{jid}:company_judgment_materiality_invalid")
        claim_id = str(judgment.get("claim_id") or "")
        if not claim_id:
            forward_incomplete.append(f"{jid}:claim_id_missing")
        elif output is not None and claim_id not in claim_ids:
            forward_invalid.append(f"{jid}:unknown_claim:{claim_id}")
        test_id = str(judgment.get("competitive_test_id") or "")
        if test_id not in test_ids:
            forward_invalid.append(f"{jid}:unknown_competitive_test:{test_id}")
        probability_set_id = str(judgment.get("probability_set_id") or "")
        scenario_id = str(judgment.get("scenario_id") or "")
        if cjo_no_probability:
            if "probability_set_id" in judgment:
                forward_invalid.append(f"{jid}:company_judgment_no_probability_set_id_forbidden")
            if not scenario_id:
                forward_incomplete.append(f"{jid}:scenario_id_missing")
        elif probability_set_id not in probability_ids:
            forward_invalid.append(f"{jid}:unknown_probability_set")
        elif scenario_id not in probability_scenarios.get(probability_set_id, set()):
            forward_invalid.append(f"{jid}:unknown_scenario")
        mechanism_chain_ids = judgment.get("mechanism_chain_ids")
        if not isinstance(mechanism_chain_ids, list) or not mechanism_chain_ids:
            forward_incomplete.append(f"{jid}:mechanism_chain_ids_missing")
            mechanism_chain_ids = []
        for chain_id in mechanism_chain_ids:
            chain = mechanism_by_id.get(str(chain_id))
            if chain is None:
                forward_invalid.append(f"{jid}:unknown_mechanism_chain:{chain_id}")
            elif (
                chain.get("scenario_id") != scenario_id
                or (not cjo_no_probability and chain.get("probability_set_id") != probability_set_id)
            ):
                forward_invalid.append(f"{jid}:mechanism_chain_scenario_mismatch:{chain_id}")
        evidence_ids = judgment.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            forward_incomplete.append(f"{jid}:evidence_ids_missing")
            evidence_ids = []
        for evidence_id in evidence_ids:
            if output is not None and str(evidence_id) not in evidence:
                forward_invalid.append(f"{jid}:unknown_evidence:{evidence_id}")
        signal_ids = judgment.get("leading_signal_threshold_ids")
        if not isinstance(signal_ids, list) or not signal_ids:
            forward_incomplete.append(f"{jid}:leading_signal_threshold_ids_missing")
            signal_ids = []
        for threshold_id in signal_ids:
            if str(threshold_id) not in threshold_ids:
                forward_invalid.append(f"{jid}:unknown_leading_signal:{threshold_id}")

        prediction = judgment.get("prediction")
        if not isinstance(prediction, dict):
            forward_invalid.append(f"{jid}:prediction_invalid")
            prediction = {}
        for key in ("metric", "unit", "horizon", "resolution_due"):
            if not str(prediction.get(key) or "").strip():
                forward_incomplete.append(f"{jid}:prediction_{key}_missing")
        operator = prediction.get("operator")
        if operator not in PREDICTION_OPERATORS:
            forward_invalid.append(f"{jid}:prediction_operator_invalid")
        if operator == "RANGE":
            low, high = _num(prediction.get("range_low")), _num(prediction.get("range_high"))
            if low is None or high is None or low > high:
                forward_invalid.append(f"{jid}:prediction_range_invalid")
        elif operator in PREDICTION_OPERATORS and _num(prediction.get("value")) is None:
            forward_invalid.append(f"{jid}:prediction_value_invalid")
        due = _iso_date(prediction.get("resolution_due"))
        if due is None:
            forward_invalid.append(f"{jid}:resolution_due_invalid")
        elif cjo_no_probability:
            as_of = _iso_date(prediction.get("as_of"))
            if as_of is None:
                forward_incomplete.append(f"{jid}:prediction_as_of_missing")
            elif due <= as_of:
                forward_invalid.append(f"{jid}:resolution_due_not_after_prediction")
        else:
            estimates = next((
                item.get("estimates") or [] for item in probability_sets
                if isinstance(item, dict) and item.get("set_id") == probability_set_id
            ), [])
            as_of_dates = [_iso_date(item.get("as_of")) for item in estimates if isinstance(item, dict)]
            as_of_dates = [value for value in as_of_dates if value is not None]
            if not as_of_dates or due <= max(as_of_dates):
                forward_invalid.append(f"{jid}:resolution_due_not_after_prediction")

        # A frozen simple baseline is a challenger for the operating judgment,
        # never an automatic path selector.  It must be directly comparable,
        # otherwise later “outperformance” can be manufactured by changing the
        # target, horizon, or evidence boundary.
        baseline = judgment.get("baseline")
        if not isinstance(baseline, dict):
            forward_incomplete.append(f"{jid}:baseline_missing")
        else:
            baseline_id = str(baseline.get("baseline_id") or "").strip()
            if not baseline_id:
                forward_incomplete.append(f"{jid}:baseline_id_missing")
            elif baseline_id in baseline_ids:
                forward_invalid.append("duplicate_forward_judgment_baseline_id")
            else:
                baseline_ids.add(baseline_id)
            if baseline.get("method") not in BASELINE_METHODS:
                forward_invalid.append(f"{jid}:baseline_method_invalid")
            for key in ("statement", "scope_conditions"):
                if not str(baseline.get(key) or "").strip():
                    forward_incomplete.append(f"{jid}:baseline_{key}_missing")
            baseline_evidence_ids = baseline.get("input_evidence_ids")
            if not isinstance(baseline_evidence_ids, list) or not baseline_evidence_ids:
                forward_incomplete.append(f"{jid}:baseline_input_evidence_ids_missing")
                baseline_evidence_ids = []
            for evidence_id in baseline_evidence_ids:
                if output is not None and str(evidence_id) not in evidence:
                    forward_invalid.append(f"{jid}:baseline_unknown_evidence:{evidence_id}")
            baseline_prediction = baseline.get("prediction")
            if not isinstance(baseline_prediction, dict):
                forward_invalid.append(f"{jid}:baseline_prediction_invalid")
                baseline_prediction = {}
            for key in ("metric", "unit", "horizon", "resolution_due"):
                if baseline_prediction.get(key) != prediction.get(key):
                    forward_invalid.append(f"{jid}:baseline_prediction_{key}_does_not_match_judgment")
            baseline_operator = baseline_prediction.get("operator")
            if baseline_operator not in PREDICTION_OPERATORS:
                forward_invalid.append(f"{jid}:baseline_prediction_operator_invalid")
            if baseline_operator == "RANGE":
                low, high = _num(baseline_prediction.get("range_low")), _num(baseline_prediction.get("range_high"))
                if low is None or high is None or low > high:
                    forward_invalid.append(f"{jid}:baseline_prediction_range_invalid")
            elif baseline_operator in PREDICTION_OPERATORS and _num(baseline_prediction.get("value")) is None:
                forward_invalid.append(f"{jid}:baseline_prediction_value_invalid")
            calculation_invalid, calculation_incomplete = _baseline_calculation_findings(
                jid, baseline, prediction, baseline_evidence_ids,
            )
            forward_invalid.extend(calculation_invalid)
            forward_incomplete.extend(calculation_incomplete)

        # This contract carries the FJ into the historical settlement engine
        # without retyping it later.  The adapter may add no midpoint, source,
        # threshold, or observation window on the author's behalf.
        settlement = judgment.get("settlement_contract")
        if not isinstance(settlement, dict):
            forward_incomplete.append(f"{jid}:settlement_contract_missing")
        else:
            settlement_claim_id = str(settlement.get("calibration_claim_id") or "").strip()
            if not settlement_claim_id:
                forward_incomplete.append(f"{jid}:settlement_calibration_claim_id_missing")
            elif not settlement_claim_id.startswith("HBTCLM:"):
                forward_invalid.append(f"{jid}:settlement_calibration_claim_id_invalid")
            elif settlement_claim_id in settlement_claim_ids:
                forward_invalid.append("duplicate_forward_judgment_settlement_claim_id")
            else:
                settlement_claim_ids.add(settlement_claim_id)
            if settlement.get("materiality") not in SETTLEMENT_MATERIALITIES:
                forward_invalid.append(f"{jid}:settlement_materiality_invalid")
            elif not investment_purpose and settlement.get("materiality") not in {"CENTRAL_THESIS", "PERMANENT_LOSS"}:
                forward_invalid.append(f"{jid}:company_judgment_settlement_materiality_invalid")
            source_ids = settlement.get("source_ids")
            if not isinstance(source_ids, list) or not source_ids or any(not str(item or "").strip() for item in source_ids):
                forward_incomplete.append(f"{jid}:settlement_source_ids_missing")
            threshold = settlement.get("threshold")
            if not isinstance(threshold, dict):
                forward_incomplete.append(f"{jid}:settlement_threshold_missing")
                threshold = {}
            for key in ("metric", "operator", "value", "unit", "consequence"):
                if threshold.get(key) in (None, ""):
                    forward_incomplete.append(f"{jid}:settlement_threshold_{key}_missing")
            for key in ("metric", "unit"):
                if threshold.get(key) not in (None, "") and threshold.get(key) != prediction.get(key):
                    forward_invalid.append(f"{jid}:settlement_threshold_{key}_does_not_match_prediction")
            if threshold.get("value") not in (None, "") and _num(threshold.get("value")) is None:
                forward_invalid.append(f"{jid}:settlement_threshold_value_invalid")
            window = settlement.get("observation_window")
            if not isinstance(window, dict):
                forward_incomplete.append(f"{jid}:settlement_observation_window_missing")
                window = {}
            opens_after, closes_at = _iso_date(window.get("opens_after")), _iso_date(window.get("closes_at"))
            if opens_after is None or closes_at is None:
                forward_invalid.append(f"{jid}:settlement_observation_window_dates_invalid")
            elif opens_after >= closes_at:
                forward_invalid.append(f"{jid}:settlement_observation_window_invalid")

        outcome = judgment.get("observable_outcome")
        if not isinstance(outcome, dict):
            forward_invalid.append(f"{jid}:observable_outcome_invalid")
            outcome = {}
        for key in ("measurement_basis", "measurement_rule", "settlement_version_policy"):
            if not str(outcome.get(key) or "").strip():
                forward_incomplete.append(f"{jid}:observable_outcome_{key}_missing")
        if outcome.get("settlement_version_policy") not in {
            "INITIAL_DISCLOSURE", "LATEST_OFFICIAL_AS_OF_EVALUATION",
        }:
            forward_invalid.append(f"{jid}:settlement_version_policy_invalid")
        period = outcome.get("measurement_period")
        if not isinstance(period, dict):
            forward_invalid.append(f"{jid}:measurement_period_invalid")
            period = {}
        start, end = _iso_date(period.get("start")), _iso_date(period.get("end"))
        if period.get("kind") not in {"REPORTING_PERIOD", "EVENT_WINDOW"}:
            forward_invalid.append(f"{jid}:measurement_period_kind_invalid")
        if start is None or end is None or start > end:
            forward_invalid.append(f"{jid}:measurement_period_dates_invalid")
        elif due is not None and end > due:
            forward_invalid.append(f"{jid}:measurement_period_ends_after_resolution_due")
        source_types = outcome.get("allowed_source_types")
        if not isinstance(source_types, list) or not source_types:
            forward_incomplete.append(f"{jid}:allowed_source_types_missing")
        elif any(value not in FORWARD_OUTCOME_SOURCE_TYPES for value in source_types):
            forward_invalid.append(f"{jid}:allowed_source_type_invalid")
        elif "LICENSED_INDUSTRY_DATA" in source_types:
            inference = outcome.get("industry_measurement_inference")
            if inference in (None, ""):
                forward_incomplete.append(f"{jid}:industry_measurement_inference_missing")
            elif inference not in QUANTITATIVE_INDUSTRY_INFERENCE_MODES:
                forward_invalid.append(f"{jid}:industry_measurement_inference_not_quantitative")
            # New frozen vendor-based FJs must pin a stable panel identity.
            # The authoring gate has no admitted manifest to inspect; the
            # production adapter resolves the declared source id before it
            # projects the judgment into a historical case.
            if is_series_contract_freeze:
                series_invalid, series_incomplete = licensed_industry_series_contract_findings(
                    outcome.get("licensed_industry_series_contract"),
                    prefix=f"{jid}:observable_outcome",
                )
                forward_invalid.extend(series_invalid)
                forward_incomplete.extend(series_incomplete)
                series = outcome.get("licensed_industry_series_contract")
                if isinstance(series, dict):
                    if series.get("metric_id") not in (None, "") and series.get("metric_id") != prediction.get("metric"):
                        forward_invalid.append(f"{jid}:licensed_industry_series_metric_does_not_match_prediction")
                    settlement_source_ids = (
                        settlement.get("source_ids") if isinstance(settlement, dict) else None
                    )
                    if (
                        isinstance(settlement_source_ids, list)
                        and str(series.get("pre_cutoff_source_id") or "")
                        and str(series.get("pre_cutoff_source_id")) not in {str(item) for item in settlement_source_ids}
                    ):
                        forward_invalid.append(f"{jid}:licensed_industry_series_pre_cutoff_source_not_in_settlement_contract")
        elif outcome.get("industry_measurement_inference") not in (None, ""):
            forward_invalid.append(f"{jid}:industry_measurement_inference_without_industry_source")

        if investment_purpose:
            model_ids = judgment.get("valuation_model_ids")
            if not isinstance(model_ids, list) or not model_ids:
                forward_incomplete.append(f"{jid}:valuation_model_ids_missing")
                model_ids = []
            for model_id in model_ids:
                if output is not None and str(model_id) not in valuation_models:
                    forward_invalid.append(f"{jid}:unknown_valuation_model:{model_id}")
            decision_ids = judgment.get("decision_entry_ids")
            if not isinstance(decision_ids, list) or not decision_ids:
                forward_incomplete.append(f"{jid}:decision_entry_ids_missing")
                decision_ids = []
            for decision_id in decision_ids:
                if output is not None and str(decision_id) not in decisions:
                    forward_invalid.append(f"{jid}:unknown_decision_entry:{decision_id}")
                elif output is not None:
                    linked_decision_metrics.add(str(decisions[str(decision_id)].get("metric_id") or ""))
        elif any(
            judgment.get(key) not in (None, "", [], {})
            for key in ("valuation_model_ids", "decision_entry_ids")
        ):
            forward_invalid.append(f"{jid}:company_judgment_cannot_carry_investment_binding")

        transmission = judgment.get("transmission")
        if not isinstance(transmission, dict):
            forward_invalid.append(f"{jid}:transmission_invalid")
            transmission = {}
        for channel in transmission_channels:
            bridge = transmission.get(channel)
            if not isinstance(bridge, dict):
                forward_incomplete.append(f"{jid}:transmission_{channel}_missing")
                continue
            direction = bridge.get("direction")
            if direction not in TRANSMISSION_DIRECTIONS:
                forward_invalid.append(f"{jid}:transmission_{channel}_direction_invalid")
            if not str(bridge.get("basis") or "").strip():
                forward_incomplete.append(f"{jid}:transmission_{channel}_basis_missing")
            if direction in {"unknown", "not_material"} and not str(bridge.get("conservative_treatment") or "").strip():
                forward_incomplete.append(f"{jid}:transmission_{channel}_conservative_treatment_missing")
            if direction in MATERIAL_TRANSMISSION_DIRECTIONS:
                transmission_coverage.add(channel)
        if not investment_purpose and any(
            transmission.get(channel) not in (None, "", [], {})
            for channel in ("valuation", "expected_return")
        ):
            forward_invalid.append(f"{jid}:company_judgment_cannot_carry_investment_transmission")
    if forward_judgment_required or forward_present:
        for channel in transmission_channels:
            if channel not in transmission_coverage:
                forward_incomplete.append(f"forward_judgment_transmission_uncovered:{channel}")
        if investment_purpose and output is not None and "valuation.v_final" not in linked_decision_metrics:
            forward_incomplete.append("forward_judgment_decision_link_missing:valuation.v_final")
        if investment_purpose and output is not None and not any(
            metric.startswith("return.gg.") for metric in linked_decision_metrics
        ):
            forward_incomplete.append("forward_judgment_decision_link_missing:expected_return")
        forward_invalid.extend(item for item in invalid if ":diagnosticity" in item)
        forward_incomplete.extend(item for item in incomplete if ":diagnosticity" in item)

    # A competitive_test explains why an alternative deserves attention.  A
    # rival pair makes both causal paths and their future split observable.
    # Legacy frozen ledgers stay opt-in; policies created for a new G1-J freeze
    # require the pair and its transfer card before the ledger can freeze.
    pair_invalid: list[str] = []
    pair_incomplete: list[str] = []
    cards_invalid: list[str] = []
    cards_incomplete: list[str] = []
    pairs = payload.get("rival_hypothesis_pairs")
    cards = payload.get("analogy_transfer_cards")
    pair_present = pairs is not None or cards is not None
    pair_items: list[dict[str, Any]] = []
    pair_by_id: dict[str, dict[str, Any]] = {}
    signal_ids: set[str] = set()
    pair_signal_ids_by_pair: dict[str, set[str]] = {}
    signal_metadata_by_id: dict[str, dict[str, str]] = {}
    signal_by_judgment: dict[str, tuple[str, str]] = {}
    forward_judgment_by_id = {
        str(item.get("judgment_id") or ""): item
        for item in forward_items
        if str(item.get("judgment_id") or "").strip()
    }
    critical_assumption_ids: set[str] = set()
    if rival_hypothesis_pair_required and not pair_present:
        pair_incomplete.append("rival_hypothesis_pairs_required_for_forward_judgment")
        cards_incomplete.append("analogy_transfer_cards_required_for_forward_judgment")
    if pair_present:
        if not isinstance(pairs, list):
            pair_invalid.append("rival_hypothesis_pairs_not_array")
        elif not pairs:
            pair_incomplete.append("rival_hypothesis_pairs_missing")
        else:
            pair_items = [item for item in pairs if isinstance(item, dict)]
            if len(pair_items) != len(pairs):
                pair_invalid.append("rival_hypothesis_pairs_item_not_object")
        for idx, pair in enumerate(pair_items):
            pair_id = str(pair.get("pair_id") or f"rival_hypothesis_pairs[{idx}]")
            for key in (
                "pair_id", "competitive_test_id", "primary_mechanism_chain_id",
                "rival_mechanism_chain_id",
            ):
                if not str(pair.get(key) or "").strip():
                    pair_incomplete.append(f"{pair_id}:{key}_missing")
            if not pair_id.startswith("RHP:"):
                pair_invalid.append(f"{pair_id}:pair_id_invalid")
            if pair_id in pair_by_id:
                pair_invalid.append("duplicate_rival_hypothesis_pair_id")
            else:
                pair_by_id[pair_id] = pair
            test_id = str(pair.get("competitive_test_id") or "")
            if test_id not in test_ids:
                pair_invalid.append(f"{pair_id}:unknown_competitive_test")
            primary_chain_id = str(pair.get("primary_mechanism_chain_id") or "")
            rival_chain_id = str(pair.get("rival_mechanism_chain_id") or "")
            primary_chain = mechanism_by_id.get(primary_chain_id)
            rival_chain = mechanism_by_id.get(rival_chain_id)
            if primary_chain is None:
                pair_invalid.append(f"{pair_id}:unknown_primary_mechanism_chain")
            if rival_chain is None:
                pair_invalid.append(f"{pair_id}:unknown_rival_mechanism_chain")
            if primary_chain_id and primary_chain_id == rival_chain_id:
                pair_invalid.append(f"{pair_id}:mechanisms_not_competitive")
            if primary_chain and rival_chain and (
                primary_chain.get("probability_set_id") != rival_chain.get("probability_set_id")
                or primary_chain.get("scenario_id") == rival_chain.get("scenario_id")
            ):
                pair_invalid.append(f"{pair_id}:mechanism_scenarios_not_competitive")
            common_facts = pair.get("common_fact_evidence_ids")
            if not isinstance(common_facts, list) or not common_facts:
                pair_incomplete.append(f"{pair_id}:common_fact_evidence_ids_missing")
                common_facts = []
            for evidence_id in common_facts:
                if output is not None and str(evidence_id) not in evidence:
                    pair_invalid.append(f"{pair_id}:unknown_common_fact_evidence:{evidence_id}")
            discriminators = pair.get("discriminators")
            if not isinstance(discriminators, list) or len(discriminators) < 2:
                pair_incomplete.append(f"{pair_id}:two_or_more_discriminators_required")
                discriminators = []
            sequences: list[int] = []
            signal_schedule: list[tuple[int, datetime.date, str, str]] = []
            stages: set[str] = set()
            pair_signal_ids: set[str] = set()
            for didx, discriminator in enumerate(discriminators):
                prefix = f"{pair_id}.discriminators[{didx}]"
                if not isinstance(discriminator, dict):
                    pair_invalid.append(prefix + ":not_object")
                    continue
                signal_id = str(discriminator.get("signal_id") or "")
                for key in ("signal_id", "forward_judgment_id"):
                    if not str(discriminator.get(key) or "").strip():
                        pair_incomplete.append(f"{prefix}:{key}_missing")
                if not signal_id.startswith("RHPSIG:"):
                    pair_invalid.append(f"{prefix}:signal_id_invalid")
                elif signal_id in signal_ids:
                    pair_invalid.append("duplicate_rival_hypothesis_signal_id")
                else:
                    signal_ids.add(signal_id)
                    pair_signal_ids.add(signal_id)
                sequence = discriminator.get("sequence")
                if not isinstance(sequence, int) or sequence < 1:
                    pair_invalid.append(f"{prefix}:sequence_invalid")
                else:
                    sequences.append(sequence)
                stage = discriminator.get("stage")
                if stage not in RIVAL_SIGNAL_STAGES:
                    pair_invalid.append(f"{prefix}:stage_invalid")
                else:
                    stages.add(stage)
                judgment_id = str(discriminator.get("forward_judgment_id") or "")
                judgment = forward_judgment_by_id.get(judgment_id)
                if judgment is None:
                    pair_invalid.append(f"{prefix}:unknown_forward_judgment")
                    continue
                if judgment_id in signal_by_judgment:
                    pair_invalid.append(f"{prefix}:forward_judgment_reused")
                else:
                    signal_by_judgment[judgment_id] = (pair_id, signal_id)
                if signal_id in pair_signal_ids:
                    signal_metadata_by_id[signal_id] = {
                        "pair_id": pair_id,
                        "stage": str(stage or ""),
                        "forward_judgment_id": judgment_id,
                    }
                primary_prediction = discriminator.get("primary_prediction")
                rival_prediction = discriminator.get("rival_prediction")
                primary_invalid, primary_incomplete = _prediction_findings(prefix + ".primary", primary_prediction)
                rival_invalid, rival_incomplete = _prediction_findings(prefix + ".rival", rival_prediction)
                pair_invalid.extend(primary_invalid); pair_invalid.extend(rival_invalid)
                pair_incomplete.extend(primary_incomplete); pair_incomplete.extend(rival_incomplete)
                if _same_prediction(primary_prediction, rival_prediction):
                    pair_invalid.append(f"{prefix}:predictions_not_discriminating")
                elif not _pair_allows_each_side_to_win(primary_prediction, rival_prediction):
                    pair_invalid.append(f"{prefix}:predictions_do_not_allow_both_sides_to_win")
                for field in ("metric", "unit", "horizon", "resolution_due"):
                    if isinstance(primary_prediction, dict) and primary_prediction.get(field) != judgment.get("prediction", {}).get(field):
                        pair_invalid.append(f"{prefix}:primary_prediction_{field}_does_not_match_forward_judgment")
                    if isinstance(primary_prediction, dict) and isinstance(rival_prediction, dict) and primary_prediction.get(field) != rival_prediction.get(field):
                        pair_invalid.append(f"{prefix}:rival_prediction_{field}_does_not_match_primary")
                if isinstance(primary_prediction, dict) and not _same_prediction(primary_prediction, judgment.get("prediction")):
                    pair_invalid.append(f"{prefix}:primary_prediction_does_not_match_forward_judgment")
                due = _iso_date((primary_prediction or {}).get("resolution_due"))
                if isinstance(sequence, int) and sequence >= 1 and due is not None:
                    signal_schedule.append((sequence, due, str(stage or ""), prefix))
                if stage == "EARLY_MECHANISM":
                    as_of = _iso_date((central or {}).get("as_of"))
                    if as_of is not None and due is not None:
                        days = (due - as_of).days
                        if not 183 <= days <= 366:
                            pair_invalid.append(f"{prefix}:early_signal_not_within_six_to_twelve_months")
            if sequences and sorted(sequences) != list(range(1, len(discriminators) + 1)):
                pair_invalid.append(f"{pair_id}:discriminator_sequence_not_contiguous")
            ordered_schedule = sorted(signal_schedule)
            terminal_seen = False
            for _, _, stage, _ in ordered_schedule:
                if stage == "TERMINAL_OPERATING":
                    terminal_seen = True
                elif stage == "EARLY_MECHANISM" and terminal_seen:
                    pair_invalid.append(f"{pair_id}:early_signal_must_precede_terminal_signal")
                    break
            early_due = [due for _, due, stage, _ in ordered_schedule if stage == "EARLY_MECHANISM"]
            terminal_due = [due for _, due, stage, _ in ordered_schedule if stage == "TERMINAL_OPERATING"]
            if early_due and terminal_due and max(early_due) >= min(terminal_due):
                pair_invalid.append(f"{pair_id}:early_signal_resolution_due_not_before_terminal_signal")
            if "EARLY_MECHANISM" not in stages:
                pair_invalid.append(f"{pair_id}:early_mechanism_signal_missing")
            if "TERMINAL_OPERATING" not in stages:
                pair_invalid.append(f"{pair_id}:terminal_operating_signal_missing")

            # A mechanism chain cannot turn a convenient observation into a
            # conclusion by leaving its necessary premises implicit.  This
            # is not a probability layer: each material premise is either
            # already evidenced, tied to a frozen discriminator, or retained
            # as UNKNOWN with an explicit conservative treatment.
            assumptions = pair.get("critical_assumptions")
            if not isinstance(assumptions, list):
                if rival_hypothesis_pair_required:
                    pair_incomplete.append(f"{pair_id}:critical_assumptions_missing")
                assumptions = []
            elif not assumptions and rival_hypothesis_pair_required:
                pair_incomplete.append(f"{pair_id}:critical_assumptions_missing")
            seen_sides: set[str] = set()
            unknown_by_side: set[str] = set()
            for aidx, assumption in enumerate(assumptions):
                prefix = f"{pair_id}.critical_assumptions[{aidx}]"
                if not isinstance(assumption, dict):
                    pair_invalid.append(prefix + ":not_object")
                    continue
                assumption_id = str(assumption.get("assumption_id") or "")
                for key in ("assumption_id", "mechanism_side", "statement", "why_necessary", "status"):
                    if not str(assumption.get(key) or "").strip():
                        pair_incomplete.append(prefix + ":" + key + "_missing")
                if not assumption_id.startswith("RHPASM:"):
                    pair_invalid.append(prefix + ":assumption_id_invalid")
                elif assumption_id in critical_assumption_ids:
                    pair_invalid.append("duplicate_rival_hypothesis_critical_assumption_id")
                else:
                    critical_assumption_ids.add(assumption_id)
                side = str(assumption.get("mechanism_side") or "")
                if side not in CRITICAL_ASSUMPTION_SIDES:
                    pair_invalid.append(prefix + ":mechanism_side_invalid")
                else:
                    seen_sides.add(side)
                status = str(assumption.get("status") or "")
                if status not in CRITICAL_ASSUMPTION_STATUSES:
                    pair_invalid.append(prefix + ":status_invalid")
                    continue
                evidence_ids = assumption.get("evidence_ids")
                linked_signals = assumption.get("linked_discriminator_ids")
                if status == "VERIFIED":
                    if not isinstance(evidence_ids, list) or not evidence_ids:
                        pair_incomplete.append(prefix + ":verified_evidence_ids_missing")
                    else:
                        for evidence_id in evidence_ids:
                            if output is not None and str(evidence_id) not in evidence:
                                pair_invalid.append(prefix + ":unknown_verified_evidence:" + str(evidence_id))
                elif status == "TESTABLE":
                    if not isinstance(linked_signals, list) or not linked_signals:
                        pair_incomplete.append(prefix + ":testable_discriminator_ids_missing")
                    else:
                        for signal_id in linked_signals:
                            if str(signal_id) not in pair_signal_ids:
                                pair_invalid.append(prefix + ":unknown_or_cross_pair_discriminator:" + str(signal_id))
                else:
                    unknown_by_side.add(side)
                    if not str(assumption.get("conservative_treatment") or "").strip():
                        pair_incomplete.append(prefix + ":unknown_conservative_treatment_missing")
                    if evidence_ids not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":unknown_cannot_claim_verified_evidence")
                    if linked_signals not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":unknown_cannot_claim_testable_discriminator")
            if rival_hypothesis_pair_required:
                for side in CRITICAL_ASSUMPTION_SIDES - seen_sides:
                    pair_incomplete.append(f"{pair_id}:critical_assumption_{side.lower()}_side_missing")
            selected_side = (
                "PRIMARY" if primary_chain and primary_chain.get("scenario_id") == central_selected_scenario_id
                else "RIVAL" if rival_chain and rival_chain.get("scenario_id") == central_selected_scenario_id
                else ""
            )
            if selected_side and selected_side in unknown_by_side:
                pair_incomplete.append(
                    f"{pair_id}:selected_{selected_side.lower()}_critical_assumption_unknown"
                )

            # A pair is not a causal trace merely because it has a prose
            # mechanism and two terminal predictions.  Freeze the material
            # arrows, so a later observation can be attributed to the link it
            # actually tests rather than retroactively validating the story.
            trace = pair.get("causal_trace")
            if not isinstance(trace, list):
                if rival_hypothesis_pair_required:
                    pair_incomplete.append(f"{pair_id}:causal_trace_missing")
                trace = []
            elif not trace and rival_hypothesis_pair_required:
                pair_incomplete.append(f"{pair_id}:causal_trace_missing")
            trace_ids: set[str] = set()
            trace_count_by_side: dict[str, int] = {side: 0 for side in CRITICAL_ASSUMPTION_SIDES}
            trace_unknown_by_side: set[str] = set()
            trace_early_test_by_side: set[str] = set()
            trace_test_signals_by_side: dict[str, set[str]] = {
                side: set() for side in CRITICAL_ASSUMPTION_SIDES
            }
            expected_chain_by_side = {
                "PRIMARY": primary_chain_id,
                "RIVAL": rival_chain_id,
            }
            signal_stage_by_id = {
                str(item.get("signal_id") or ""): str(item.get("stage") or "")
                for item in discriminators if isinstance(item, dict)
            }
            for eidx, edge in enumerate(trace):
                prefix = f"{pair_id}.causal_trace[{eidx}]"
                if not isinstance(edge, dict):
                    pair_invalid.append(prefix + ":not_object")
                    continue
                edge_id = str(edge.get("edge_id") or "")
                for key in (
                    "edge_id", "mechanism_side", "mechanism_chain_id", "from_state",
                    "to_state", "why_diagnostic", "status",
                ):
                    if not str(edge.get(key) or "").strip():
                        pair_incomplete.append(prefix + ":" + key + "_missing")
                if not edge_id.startswith("RHPEDGE:"):
                    pair_invalid.append(prefix + ":edge_id_invalid")
                elif edge_id in trace_ids:
                    pair_invalid.append("duplicate_rival_hypothesis_causal_trace_edge_id")
                else:
                    trace_ids.add(edge_id)
                side = str(edge.get("mechanism_side") or "")
                if side not in CRITICAL_ASSUMPTION_SIDES:
                    pair_invalid.append(prefix + ":mechanism_side_invalid")
                else:
                    trace_count_by_side[side] += 1
                    if str(edge.get("mechanism_chain_id") or "") != expected_chain_by_side[side]:
                        pair_invalid.append(prefix + ":mechanism_chain_side_mismatch")
                if (
                    str(edge.get("from_state") or "").strip()
                    and str(edge.get("from_state") or "").strip()
                    == str(edge.get("to_state") or "").strip()
                ):
                    pair_invalid.append(prefix + ":from_and_to_state_not_distinct")
                status = str(edge.get("status") or "")
                if status not in CAUSAL_TRACE_EDGE_STATUSES:
                    pair_invalid.append(prefix + ":status_invalid")
                    continue
                evidence_ids = edge.get("evidence_ids")
                linked_signals = edge.get("linked_discriminator_ids")
                if status == "VERIFIED":
                    if not isinstance(evidence_ids, list) or not evidence_ids:
                        pair_incomplete.append(prefix + ":verified_evidence_ids_missing")
                    else:
                        for evidence_id in evidence_ids:
                            if output is not None and str(evidence_id) not in evidence:
                                pair_invalid.append(prefix + ":unknown_verified_evidence:" + str(evidence_id))
                    if linked_signals not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":verified_cannot_claim_testable_discriminator")
                elif status == "TESTABLE":
                    if not isinstance(linked_signals, list) or not linked_signals:
                        pair_incomplete.append(prefix + ":testable_discriminator_ids_missing")
                    else:
                        for signal_id in linked_signals:
                            signal_id = str(signal_id)
                            if signal_id not in pair_signal_ids:
                                pair_invalid.append(prefix + ":unknown_or_cross_pair_discriminator:" + signal_id)
                            elif side in CRITICAL_ASSUMPTION_SIDES:
                                trace_test_signals_by_side[side].add(signal_id)
                                if signal_stage_by_id.get(signal_id) == "EARLY_MECHANISM":
                                    trace_early_test_by_side.add(side)
                    if evidence_ids not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":testable_cannot_claim_verified_evidence")
                else:
                    if side in CRITICAL_ASSUMPTION_SIDES:
                        trace_unknown_by_side.add(side)
                    if not str(edge.get("conservative_treatment") or "").strip():
                        pair_incomplete.append(prefix + ":unknown_conservative_treatment_missing")
                    if evidence_ids not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":unknown_cannot_claim_verified_evidence")
                    if linked_signals not in (None, "", [], {}):
                        pair_invalid.append(prefix + ":unknown_cannot_claim_testable_discriminator")
            if rival_hypothesis_pair_required:
                for side, count in trace_count_by_side.items():
                    if count < 2:
                        pair_incomplete.append(f"{pair_id}:causal_trace_{side.lower()}_two_or_more_edges_required")
                    if side not in trace_early_test_by_side:
                        pair_incomplete.append(f"{pair_id}:causal_trace_{side.lower()}_early_discriminator_missing")
                    for signal_id in sorted(pair_signal_ids - trace_test_signals_by_side[side]):
                        pair_incomplete.append(
                            f"{pair_id}:causal_trace_{side.lower()}_signal_unlinked:{signal_id}"
                        )
            if selected_side and selected_side in trace_unknown_by_side:
                pair_incomplete.append(f"{pair_id}:selected_{selected_side.lower()}_causal_trace_unknown")
            pair_signal_ids_by_pair[pair_id] = pair_signal_ids

        if not isinstance(cards, list):
            cards_invalid.append("analogy_transfer_cards_not_array")
            card_items: list[dict[str, Any]] = []
        elif not cards:
            cards_incomplete.append("analogy_transfer_cards_missing")
            card_items = []
        else:
            card_items = [item for item in cards if isinstance(item, dict)]
            if len(card_items) != len(cards):
                cards_invalid.append("analogy_transfer_cards_item_not_object")
        seen_card_ids: set[str] = set()
        card_pair_ids: set[str] = set()
        archetype_ids = _case_archetype_ids()
        for idx, card in enumerate(card_items):
            card_id = str(card.get("card_id") or f"analogy_transfer_cards[{idx}]")
            for key in ("card_id", "target_pair_id", "source_case_id", "settlement_rule"):
                if not str(card.get(key) or "").strip():
                    cards_incomplete.append(f"{card_id}:{key}_missing")
            if not card_id.startswith("ATC:"):
                cards_invalid.append(f"{card_id}:card_id_invalid")
            if card_id in seen_card_ids:
                cards_invalid.append("duplicate_analogy_transfer_card_id")
            seen_card_ids.add(card_id)
            target_pair_id = str(card.get("target_pair_id") or "")
            if target_pair_id not in pair_by_id:
                cards_invalid.append(f"{card_id}:unknown_target_pair")
            else:
                card_pair_ids.add(target_pair_id)
            target_pair_signal_ids = pair_signal_ids_by_pair.get(target_pair_id, set())
            source_case_id = str(card.get("source_case_id") or "")
            if source_case_id not in archetype_ids:
                cards_invalid.append(f"{card_id}:unknown_source_case")
            state_vector = card.get("target_state_vector")
            if not isinstance(state_vector, list) or len(state_vector) < 3:
                cards_incomplete.append(f"{card_id}:three_or_more_state_dimensions_required")
            structural_mapping = card.get("structural_mapping")
            if not isinstance(structural_mapping, list) or not structural_mapping:
                cards_incomplete.append(f"{card_id}:structural_mapping_missing")
            else:
                for midx, mapping in enumerate(structural_mapping):
                    if not isinstance(mapping, dict):
                        cards_invalid.append(f"{card_id}.structural_mapping[{midx}]:not_object")
                        continue
                    for key in ("source_driver", "target_driver", "intermediate_variable", "operating_outcome"):
                        if not str(mapping.get(key) or "").strip():
                            cards_incomplete.append(f"{card_id}.structural_mapping[{midx}]:{key}_missing")
            mismatch = card.get("mismatch_dimensions")
            if not isinstance(mismatch, list) or not mismatch:
                cards_incomplete.append(f"{card_id}:mismatch_dimensions_missing")
            application_rule = card.get("application_rule")
            if not isinstance(application_rule, dict):
                cards_incomplete.append(f"{card_id}:application_rule_missing")
            else:
                for key in ("when_to_apply", "when_not_to_apply"):
                    if not str(application_rule.get(key) or "").strip():
                        cards_incomplete.append(f"{card_id}.application_rule:{key}_missing")
            invalidations = card.get("invalidation_conditions")
            if not isinstance(invalidations, list) or not invalidations:
                cards_incomplete.append(f"{card_id}:invalidation_conditions_missing")
            else:
                for iidx, condition in enumerate(invalidations):
                    if not isinstance(condition, dict):
                        cards_invalid.append(f"{card_id}.invalidation_conditions[{iidx}]:not_object")
                        continue
                    signal_id = str(condition.get("signal_id") or "")
                    if signal_id not in signal_ids:
                        cards_invalid.append(f"{card_id}.invalidation_conditions[{iidx}]:unknown_signal")
                    elif target_pair_id in pair_by_id and signal_id not in target_pair_signal_ids:
                        cards_invalid.append(f"{card_id}.invalidation_conditions[{iidx}]:signal_not_in_target_pair")
                    for key in ("condition", "effect"):
                        if not str(condition.get(key) or "").strip():
                            cards_incomplete.append(f"{card_id}.invalidation_conditions[{iidx}]:{key}_missing")
            near_miss = card.get("strongest_near_miss")
            if not isinstance(near_miss, dict):
                cards_incomplete.append(f"{card_id}:strongest_near_miss_missing")
            else:
                status = str(near_miss.get("status") or "")
                if status:
                    support_role = str(card.get("support_role") or "")
                    if support_role not in ANALOGY_SUPPORT_ROLES:
                        cards_invalid.append(f"{card_id}:support_role_invalid")
                    if status not in NEAR_MISS_STATUSES:
                        cards_invalid.append(f"{card_id}:strongest_near_miss_status_invalid")
                    elif status == "VERIFIED_EPISODE":
                        identities_valid = True
                        for key, prefix in (
                            ("case_id", "CASE:"),
                            ("episode_id", "MEP:"),
                            ("outcome_event_id", "CASEEV:"),
                        ):
                            value = str(near_miss.get(key) or "")
                            if not value:
                                cards_incomplete.append(f"{card_id}:strongest_near_miss_{key}_missing")
                                identities_valid = False
                            elif not value.startswith(prefix):
                                cards_invalid.append(f"{card_id}:strongest_near_miss_{key}_invalid")
                                identities_valid = False
                        for key in ("structural_break", "source_reference"):
                            if not str(near_miss.get(key) or "").strip():
                                cards_incomplete.append(f"{card_id}:strongest_near_miss_{key}_missing")
                        if identities_valid:
                            episode_reference = validate_verified_episode_reference(
                                case_id=str(near_miss.get("case_id") or ""),
                                episode_id=str(near_miss.get("episode_id") or ""),
                                outcome_event_id=str(near_miss.get("outcome_event_id") or ""),
                                library_dir=case_library_dir,
                            )
                            cards_invalid.extend(
                                f"{card_id}:strongest_near_miss_{finding}"
                                for finding in episode_reference.get("invalid_findings") or []
                            )
                    elif status == "UNKNOWN_NO_QUALIFIED_EPISODE":
                        if str(card.get("support_role") or "") != "QUESTION_ONLY":
                            cards_invalid.append(f"{card_id}:unknown_near_miss_cannot_be_primary_support")
                        for key in ("unknown_reason", "conservative_treatment"):
                            if not str(near_miss.get(key) or "").strip():
                                cards_incomplete.append(f"{card_id}:strongest_near_miss_{key}_missing")
                        if any(str(near_miss.get(key) or "").strip() for key in ("case_id", "episode_id", "outcome_event_id")):
                            cards_invalid.append(f"{card_id}:unknown_near_miss_cannot_claim_episode")
                elif rival_hypothesis_pair_required:
                    cards_invalid.append(f"{card_id}:strongest_near_miss_status_invalid")
                else:
                    for key in ("case_id", "structural_break", "source_reference"):
                        if not str(near_miss.get(key) or "").strip():
                            cards_incomplete.append(f"{card_id}:strongest_near_miss_{key}_missing")
            linked_signals = card.get("linked_discriminator_ids")
            if not isinstance(linked_signals, list) or not linked_signals:
                cards_incomplete.append(f"{card_id}:linked_discriminator_ids_missing")
                linked_signal_ids: set[str] = set()
            elif any(str(signal_id) not in signal_ids for signal_id in linked_signals):
                cards_invalid.append(f"{card_id}:unknown_linked_discriminator")
                linked_signal_ids = {str(signal_id) for signal_id in linked_signals}
            else:
                linked_signal_ids = {str(signal_id) for signal_id in linked_signals}
                if target_pair_id in pair_by_id and not linked_signal_ids.issubset(target_pair_signal_ids):
                    cards_invalid.append(f"{card_id}:linked_discriminator_not_in_target_pair")

            # H7 is optional.  When used, though, it has to freeze structural
            # claims and create a real pair discriminator—not decorate a
            # report with an untestable value-chain picture.
            architecture = card.get("industry_architecture")
            if architecture is not None:
                if not isinstance(architecture, dict):
                    cards_invalid.append(f"{card_id}:industry_architecture_not_object")
                else:
                    architecture_has_unknown = False
                    for element_name in INDUSTRY_ARCHITECTURE_ELEMENTS:
                        element = architecture.get(element_name)
                        prefix = f"{card_id}.industry_architecture.{element_name}"
                        if not isinstance(element, dict):
                            cards_incomplete.append(prefix + ":missing")
                            continue
                        if not str(element.get("statement") or "").strip():
                            cards_incomplete.append(prefix + ":statement_missing")
                        status = str(element.get("status") or "")
                        if status not in INDUSTRY_ARCHITECTURE_STATUSES:
                            cards_invalid.append(prefix + ":status_invalid")
                            continue
                        evidence_ids = element.get("evidence_ids")
                        source_classes = element.get("source_classes")
                        if status == "VERIFIED":
                            if not isinstance(evidence_ids, list) or not evidence_ids:
                                cards_incomplete.append(prefix + ":verified_evidence_ids_missing")
                            else:
                                for evidence_id in evidence_ids:
                                    if output is not None and str(evidence_id) not in evidence:
                                        cards_invalid.append(prefix + ":unknown_verified_evidence:" + str(evidence_id))
                            if not isinstance(source_classes, list) or not source_classes:
                                cards_incomplete.append(prefix + ":verified_source_classes_missing")
                            elif any(str(value) not in INDUSTRY_ARCHITECTURE_SOURCE_CLASSES for value in source_classes):
                                cards_invalid.append(prefix + ":verified_source_class_invalid")
                            if industry_architecture_provenance_required:
                                provenance_invalid, provenance_incomplete = (
                                    _industry_architecture_provenance_findings(
                                        prefix=prefix,
                                        element=element,
                                        evidence=evidence,
                                        documents_by_id=documents_by_id,
                                        observations_by_id=observations_by_id,
                                        pit_source_provenance_by_id=pit_source_provenance_by_id,
                                        projected_document_source_ids=projected_document_source_ids,
                                    )
                                )
                                cards_invalid.extend(provenance_invalid)
                                cards_incomplete.extend(provenance_incomplete)
                        else:
                            architecture_has_unknown = True
                            for key in ("unknown_reason", "conservative_treatment"):
                                if not str(element.get(key) or "").strip():
                                    cards_incomplete.append(prefix + ":unknown_" + key + "_missing")
                            if evidence_ids not in (None, "", [], {}):
                                cards_invalid.append(prefix + ":unknown_cannot_claim_verified_evidence")
                            if source_classes not in (None, "", [], {}):
                                cards_invalid.append(prefix + ":unknown_cannot_claim_source_class")

                    discriminator = architecture.get("interface_discriminator")
                    if not isinstance(discriminator, dict):
                        cards_incomplete.append(f"{card_id}:industry_architecture_interface_discriminator_missing")
                    else:
                        signal_id = str(discriminator.get("signal_id") or "")
                        causal_edge_id = str(discriminator.get("causal_edge_id") or "")
                        for key in ("signal_id", "causal_edge_id", "mechanism_edge", "why_discriminating"):
                            if not str(discriminator.get(key) or "").strip():
                                cards_incomplete.append(f"{card_id}.industry_architecture.interface_discriminator:{key}_missing")
                        if signal_id and signal_id not in linked_signal_ids:
                            cards_invalid.append(f"{card_id}:industry_architecture_discriminator_not_linked_to_card")
                        if signal_id and signal_id not in signal_ids:
                            cards_invalid.append(f"{card_id}:industry_architecture_discriminator_unknown")
                        metadata = signal_metadata_by_id.get(signal_id)
                        if metadata and target_pair_id in pair_by_id:
                            if metadata.get("pair_id") != target_pair_id:
                                cards_invalid.append(f"{card_id}:industry_architecture_discriminator_not_in_target_pair")
                            elif metadata.get("stage") != "EARLY_MECHANISM":
                                cards_invalid.append(f"{card_id}:industry_architecture_discriminator_not_early_mechanism")
                            else:
                                judgment = forward_judgment_by_id.get(
                                    str(metadata.get("forward_judgment_id") or "")
                                )
                                if judgment is not None and judgment.get("materiality") != "INDUSTRY_STRUCTURE":
                                    cards_invalid.append(
                                        f"{card_id}:industry_architecture_discriminator_not_industry_structure"
                                    )
                        target_pair = pair_by_id.get(target_pair_id)
                        target_trace = {
                            str(edge.get("edge_id") or ""): edge
                            for edge in (target_pair or {}).get("causal_trace") or []
                            if isinstance(edge, dict) and str(edge.get("edge_id") or "").strip()
                        }
                        if causal_edge_id and causal_edge_id not in target_trace:
                            cards_invalid.append(
                                f"{card_id}:industry_architecture_causal_edge_not_in_target_pair"
                            )
                        edge = target_trace.get(causal_edge_id)
                        if edge is not None:
                            if edge.get("status") != "TESTABLE":
                                cards_invalid.append(
                                    f"{card_id}:industry_architecture_causal_edge_not_testable"
                                )
                            elif signal_id not in {
                                str(value) for value in edge.get("linked_discriminator_ids") or []
                            }:
                                cards_invalid.append(
                                    f"{card_id}:industry_architecture_causal_edge_signal_unlinked"
                                )

                    query = architecture.get("minimal_external_query")
                    if not isinstance(query, dict):
                        cards_incomplete.append(f"{card_id}:industry_architecture_minimal_external_query_missing")
                    else:
                        for key in ("question", "metric", "why_required"):
                            if not str(query.get(key) or "").strip():
                                cards_incomplete.append(f"{card_id}.industry_architecture.minimal_external_query:{key}_missing")
                        source_classes = query.get("allowed_source_classes")
                        if not isinstance(source_classes, list) or not source_classes:
                            cards_incomplete.append(f"{card_id}.industry_architecture.minimal_external_query:allowed_source_classes_missing")
                        elif any(str(value) not in INDUSTRY_ARCHITECTURE_SOURCE_CLASSES for value in source_classes):
                            cards_invalid.append(f"{card_id}.industry_architecture.minimal_external_query:allowed_source_class_invalid")
                    if architecture_has_unknown and str(card.get("support_role") or "") != "QUESTION_ONLY":
                        cards_invalid.append(f"{card_id}:industry_architecture_unknown_cannot_be_primary_support")
            if card.get("settlement_rule") != ANALOGY_SETTLEMENT_RULE:
                cards_invalid.append(f"{card_id}:settlement_rule_invalid")
            if _analogy_has_forbidden_field(card):
                cards_invalid.append(f"{card_id}:forbidden_price_probability_or_valuation_field")
        for pair_id in pair_by_id:
            if pair_id not in card_pair_ids:
                cards_incomplete.append(f"{pair_id}:analogy_transfer_card_missing")
        for judgment in forward_items:
            judgment_id = str(judgment.get("judgment_id") or "")
            pair_id, signal_id = signal_by_judgment.get(judgment_id, ("", ""))
            if not pair_id:
                pair_incomplete.append(f"{judgment_id}:rival_hypothesis_signal_missing")
                continue
            if judgment.get("rival_hypothesis_pair_id") != pair_id:
                pair_invalid.append(f"{judgment_id}:rival_hypothesis_pair_link_invalid")
            if judgment.get("rival_signal_id") != signal_id:
                pair_invalid.append(f"{judgment_id}:rival_signal_link_invalid")

    declared_scenario_ids = {
        str(item.get(key) or "").strip()
        for collection, keys in (
            (tests, ("primary_scenario_id", "alternative_scenario_id")),
            (mechanism_items, ("scenario_id",)),
            (forward_items, ("scenario_id",)),
            ([central] if isinstance(central, dict) else [], ("selected_scenario_id", "competing_scenario_id")),
        )
        for item in collection if isinstance(item, dict)
        for key in keys
        if str(item.get(key) or "").strip()
    }
    selection_admission, selection_invalid, selection_incomplete = _selection_admission_findings(
        payload,
        analysis_purpose=analysis_purpose,
        central=central if isinstance(central, dict) else None,
        probability_scenarios=probability_scenarios,
        probability_mode=probability_mode or None,
        declared_scenario_ids=declared_scenario_ids,
        judgments=forward_items,
        evidence=evidence,
        pairs=pair_by_id,
        mechanism_by_id=mechanism_by_id,
        threshold_by_id=threshold_by_id,
    )

    invalid.extend(pair_invalid); incomplete.extend(pair_incomplete)
    invalid.extend(cards_invalid); incomplete.extend(cards_incomplete)
    invalid.extend(selection_invalid); incomplete.extend(selection_incomplete)

    if company_judgment_lineage_required:
        lineage_invalid, lineage_incomplete = _validate_company_judgment_lineage(
            payload, output=output,
        )
        invalid.extend(lineage_invalid)
        incomplete.extend(lineage_incomplete)

    invalid.extend(forward_invalid)
    incomplete.extend(forward_incomplete)
    forward_invalid = list(dict.fromkeys(forward_invalid))
    forward_incomplete = list(dict.fromkeys(forward_incomplete))
    forward_state = (
        "INVALID" if forward_invalid else "INCOMPLETE" if forward_incomplete
        else "DECISION_READY" if (forward_judgment_required or forward_present) else "SKIP"
    )
    pair_state = "INVALID" if pair_invalid else "INCOMPLETE" if pair_incomplete else "DECISION_READY" if pair_present else "SKIP"
    card_state = "INVALID" if cards_invalid else "INCOMPLETE" if cards_incomplete else "DECISION_READY" if pair_present else "SKIP"

    known = {"central": {central_id} if central_id else set(), "test": test_ids, "threshold": threshold_ids, "probability": probability_ids}
    for kind, pattern in _ANCHOR_PATTERNS.items():
        for ref in sorted(set(pattern.findall(report_text)) - known[kind]): invalid.append(f"unknown_{kind}_reference:{ref}")
    frozen = bool((payload.get("freeze") or {}).get("frozen"))
    if frozen and (payload.get("freeze") or {}).get("fingerprint") != thesis_test_fingerprint(payload): invalid.append("freeze_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING" if payload.get("lifecycle") == "monitoring" else "DECISION_READY" if frozen else "REVIEWABLE"
    return {"schema_version": "thesis-test-validation.v1", "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS", "analysis_purpose": analysis_purpose, "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings, "competitive_test_ids": sorted(test_ids), "threshold_ids": sorted(threshold_ids), "probability_set_ids": sorted(probability_ids), "covered_trigger_metric_ids": sorted(covered_trigger_metrics), "forward_judgment_required": bool(forward_judgment_required), "rival_hypothesis_pair_required": bool(rival_hypothesis_pair_required), "company_judgment_lineage_required": bool(company_judgment_lineage_required), "selection_admission": selection_admission, "selection_admission_invalid_findings": list(dict.fromkeys(selection_invalid)), "selection_admission_incomplete_findings": list(dict.fromkeys(selection_incomplete)), "forward_judgment_state": forward_state, "forward_judgment_count": len(forward_items), "forward_judgment_invalid_findings": forward_invalid, "forward_judgment_incomplete_findings": forward_incomplete, "rival_hypothesis_pair_state": pair_state, "rival_hypothesis_pair_count": len(pair_items), "rival_hypothesis_pair_invalid_findings": list(dict.fromkeys(pair_invalid)), "rival_hypothesis_pair_incomplete_findings": list(dict.fromkeys(pair_incomplete)), "analogy_transfer_card_state": card_state, "analogy_transfer_card_count": len(card_items) if pair_present else 0, "analogy_transfer_card_invalid_findings": list(dict.fromkeys(cards_invalid)), "analogy_transfer_card_incomplete_findings": list(dict.fromkeys(cards_incomplete)), "enforced": bool(enforced)}


def persist_thesis_test_ledger(output_dir: str | Path, payload: dict[str, Any], *, report_text: str = "", allow_frozen_update: bool = False) -> dict[str, Any]:
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True); path = output / "thesis_test.json"; diff_path = output / "thesis_test_diff.json"
    old = _read_json(path); policy = _read_json(output / "thesis_test_policy.json")
    validation = validate_thesis_test_ledger(payload, output_dir=output, report_text=report_text, enforced=bool(policy.get("enforced")), monitoring_required=bool(policy.get("monitoring_required")), forward_judgment_required=bool(policy.get("forward_judgment_required")), rival_hypothesis_pair_required=bool(policy.get("rival_hypothesis_pair_required")), company_judgment_lineage_required=bool(policy.get("company_judgment_lineage_required")), required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS))
    if validation["state"] == "INVALID" or (validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen"))):
        # Preserve the exact structured candidate.  A validation report alone
        # cannot be repaired deterministically because it contains field paths
        # but not the submitted values.  This also prevents a fresh-context
        # model from reconstructing a large ledger and repeating the same
        # schema mistakes at additional cost.
        (output / "thesis_test_last_rejected.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "thesis_test_last_rejected_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "validation": validation, "error": "invalid or incomplete thesis test cannot be frozen"}
    changed = bool(old) and thesis_test_fingerprint(old) != thesis_test_fingerprint(payload)
    diff = {"schema_version": "thesis-test-diff.v1", "generated_at": _now(), "old_fingerprint": thesis_test_fingerprint(old) if old else None, "new_fingerprint": thesis_test_fingerprint(payload), "change_reason": payload.get("change_reason")}
    if old and bool((old.get("freeze") or {}).get("frozen")) and changed and not allow_frozen_update:
        diff["status"] = "REJECTED_FROZEN"; diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "diff_path": str(diff_path), "thesis_test_frozen": True, "validation": validation, "error": "frozen thesis test rejected update"}
    if old and not changed:
        expected = thesis_test_fingerprint(old)
        old_fingerprint_valid = (
            (old.get("freeze") or {}).get("fingerprint") == expected
        )
        supplied_fingerprint_valid = (
            (payload.get("freeze") or {}).get("fingerprint")
            == thesis_test_fingerprint(payload)
        )
        if (
            allow_frozen_update
            and not old_fingerprint_valid
            and supplied_fingerprint_valid
        ):
            diff["status"] = "METADATA_REPAIRED"
            ledger = payload
        else:
            diff["status"] = "NO_CHANGE"
            ledger = old
    else:
        diff["status"] = "APPLIED" if old else "INITIALIZED"
        ledger = payload
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"); diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path), "diff_path": str(diff_path), "ledger": ledger, "validation": validation, "diff": diff}


def evaluate_output_thesis_test(output_dir: str | Path, *, report_text: str = "", persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir); policy = _read_json(output / "thesis_test_policy.json"); ledger = _read_json(output / "thesis_test.json"); enforced = bool(policy.get("enforced"))
    if not ledger:
        state = "INCOMPLETE" if enforced else "SKIP"; result = {"schema_version": "thesis-test-validation.v1", "state": state, "status": "FAIL" if enforced else "SKIP", "invalid_findings": [], "incomplete_findings": ["thesis_test_missing"] if enforced else [], "warnings": [], "forward_judgment_required": bool(policy.get("forward_judgment_required")), "forward_judgment_state": "INCOMPLETE" if policy.get("forward_judgment_required") else "SKIP", "forward_judgment_count": 0, "forward_judgment_invalid_findings": [], "forward_judgment_incomplete_findings": ["thesis_test_missing"] if policy.get("forward_judgment_required") else [], "enforced": enforced, "policy": policy}
    else:
        result = validate_thesis_test_ledger(ledger, output_dir=output, report_text=report_text, enforced=enforced, monitoring_required=bool(policy.get("monitoring_required")), forward_judgment_required=bool(policy.get("forward_judgment_required")), rival_hypothesis_pair_required=bool(policy.get("rival_hypothesis_pair_required")), company_judgment_lineage_required=bool(policy.get("company_judgment_lineage_required")), required_trigger_metric_ids=set(policy.get("required_trigger_metric_ids") or REQUIRED_TRIGGER_METRICS)); result["policy"] = policy
    if persist: (output / "thesis_test_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
