#!/usr/bin/env python3
"""Bind every training run to one complete EnterpriseUnderwritingEpisode.

This is a thin execution contract over the existing underwriting read model.
It does not store facts, settle outcomes, score fields, freeze methods, or
create investment authority.  Teaching, blind replay, and prospective work
only determine source visibility and the Episode sample identity; the sole
primary training product is the complete Episode itself.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable

try:
    from scripts.enterprise_underwriting_episode import (
        EPISODE_SCHEMA,
        compile_golden_report_reader_brief,
        compile_underwriting_projections,
        derive_component_decision_summary,
        derive_economic_derivation_summary,
        validate_enterprise_underwriting_episode,
        validate_underwriting_projection_bundle,
    )
except ModuleNotFoundError:  # Direct ``python scripts/...`` execution.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.enterprise_underwriting_episode import (
        EPISODE_SCHEMA,
        compile_golden_report_reader_brief,
        compile_underwriting_projections,
        derive_component_decision_summary,
        derive_economic_derivation_summary,
        validate_enterprise_underwriting_episode,
        validate_underwriting_projection_bundle,
    )


CONTRACT_SCHEMA = "enterprise-underwriting-training-contract.v2"
LEGACY_CONTRACT_SCHEMA = "enterprise-underwriting-training-contract.v1"
CONTRACT_VALIDATION_SCHEMA = "enterprise-underwriting-training-contract-validation.v1"
EPISODE_VALIDATION_SCHEMA = "enterprise-underwriting-training-episode-validation.v1"
DOWNSTREAM_BUNDLE_SCHEMA = "enterprise-underwriting-training-downstream-bundle.v1"
RUN_RECEIPT_SCHEMA = "enterprise-underwriting-training-run-receipt.v1"
SUBAGENT_TASK_SCHEMA = "enterprise-underwriting-fresh-subagent-task.v1"

TRACK_BINDINGS = {
    "WORKED_CASE": {
        "sample_identity": "WORKED_CASE",
        "outcome_access": "RESULT_KNOWN",
    },
    "BLIND_REPLAY": {
        "sample_identity": "BLIND_REPLAY",
        "outcome_access": "SEALED",
    },
    "PROSPECTIVE": {
        "sample_identity": "PROSPECTIVE_EPISODE",
        "outcome_access": "NOT_YET_RELEASED",
    },
}

# ``TRAINING_MEMORY`` is deliberately distinct from issuer evidence.  A Blind
# Replay may use a lesson learned from an earlier, separately settled case to
# change its questions or evidence order, even though the lesson was written
# after the target's historical cutoff.  It can never support a target-company
# fact, so the Episode binding below keeps it out of evidence_trace and
# existing_object_refs.
SOURCE_TIME_ROLES = {"PRE_CUTOFF", "RESULT_KNOWN", "TRAINING_MEMORY"}
FEEDBACK_HORIZONS = {
    "EARLY_SIGNAL",
    "OPERATING_ADAPTATION",
    "NORMALIZATION_AND_CASH",
    "LONG_TERM_PERMANENT_LOSS",
}
EPISODE_CLAIMS = {
    "INDUSTRY_AND_SITUATION",
    "BUSINESS_POSITION_AND_ADAPTATION",
    "SURVIVAL_AND_FINANCING",
    "NORMAL_EARNINGS",
    "OWNER_CASH",
    "PERMANENT_LOSS",
    "VALUE_ROUTE",
}

ROOT_FIELDS = {
    "schema_version",
    "contract_id",
    "training_track",
    "company_id",
    "company_name",
    "cutoff_at",
    "sample_identity",
    "outcome_access",
    "allowed_sources",
    "feedback_clocks",
    "primary_training_product",
    "component_decision_interface",
    "economic_derivation_interface",
    "authority",
}
SOURCE_FIELDS = {"source_id", "source_ref", "available_at", "time_role"}
CLOCK_FIELDS = {
    "clock_id",
    "horizon",
    "opens_at",
    "episode_claims",
    "discriminating_observation",
}
PRODUCT_FIELDS = {"object_type", "schema_version", "completion_basis"}
PRIMARY_PRODUCT = {
    "object_type": "EnterpriseUnderwritingEpisode",
    "schema_version": EPISODE_SCHEMA,
    "completion_basis": "COMPLETE_EPISODE_VALIDATION_ONLY",
}
COMPONENT_DECISION_INTERFACE = {
    "schema_version": "enterprise-underwriting-component-decision-interface.v1",
    "completion_basis": "EXPLICIT_EFFECT_FOR_EACH_COMPONENT",
}
ECONOMIC_DERIVATION_INTERFACE_V1 = {
    "schema_version": "enterprise-underwriting-economic-derivation-interface.v1",
    "completion_basis": "PRICE_FREE_COMPONENT_BRIDGE_AND_DRIVER_SENSITIVITY",
}
ECONOMIC_DERIVATION_INTERFACE_V2 = {
    "schema_version": "enterprise-underwriting-economic-derivation-interface.v2",
    "completion_basis": (
        "PRICE_FREE_COMPONENT_BRIDGE_AND_EVIDENCED_DRIVER_SENSITIVITY"
    ),
}
# New contracts must opt into v2.  Keep this public alias for current callers.
ECONOMIC_DERIVATION_INTERFACE = ECONOMIC_DERIVATION_INTERFACE_V2
_ECONOMIC_DERIVATION_INTERFACES = {
    interface["schema_version"]: interface
    for interface in (
        ECONOMIC_DERIVATION_INTERFACE_V1,
        ECONOMIC_DERIVATION_INTERFACE_V2,
    )
}
TRAINING_AUTHORITY = "RESEARCH_TRAINING_ONLY_NO_PRICE_VALUATION_OR_INVESTMENT_AUTHORITY"
_AUTO_EXCLUDED_ROUTE_BINDING_USES = {
    "EXCLUDED",
    "UNRESOLVED",
    "SCENARIO_ONLY",
    "NOT_APPLICABLE",
}

_ROOT = Path(__file__).resolve().parents[1]
_EPISODE_JSON_SCHEMA_PATH = (
    _ROOT / "schemas/enterprise_underwriting_episode_v1.schema.json"
)
LEGACY_FROZEN_CONTRACT_REFS = {
    "UWTRAIN:CN600585:20240501:WORKED:V1": "docs/development/research/enterprise_underwriting_episodes/CN600585_20240501_TRAINING_CONTRACT_V1.json",
    "UWTRAIN:CN000100TTE:20040827:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN000100_TTE_WORKED_CONTRACT.json",
    "UWTRAIN:CN000651:20200501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN000651_WORKED_CONTRACT.json",
    "UWTRAIN:CN000877:20200501:BLIND:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN000877_BLIND_CONTRACT.json",
    "UWTRAIN:CN001914:20210501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN001914_WORKED_CONTRACT.json",
    "UWTRAIN:CN002120:20190501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN002120_WORKED_CONTRACT.json",
    "UWTRAIN:CN002242:20190501:BLIND:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN002242_BLIND_CONTRACT.json",
    "UWTRAIN:CN002352:20190501:BLIND:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN002352_BLIND_CONTRACT.json",
    "UWTRAIN:CN002468:20190501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN002468_WORKED_CONTRACT.json",
    "UWTRAIN:CN600233:20190501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN600233_WORKED_CONTRACT.json",
    "UWTRAIN:CN600315:20190501:CURRENT_AGENT_SELF_REPLAY:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN600315_CURRENT_AGENT_SELF_REPLAY_CONTRACT.json",
    "UWTRAIN:CN600690:20230501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN600690_WORKED_CONTRACT.json",
    "UWTRAIN:CN600801:20170412:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN600801_WORKED_CONTRACT.json",
    "UWTRAIN:CN600802:20150415:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN600802_WORKED_CONTRACT.json",
    "UWTRAIN:CN601966:20190501:CURRENT_AGENT_SELF_REPLAY:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN601966_CURRENT_AGENT_SELF_REPLAY_CONTRACT.json",
    "UWTRAIN:CN603043:20190501:SECOND_AB:BASELINE:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603043_SECOND_A_B_BASELINE_CONTRACT.json",
    "UWTRAIN:CN603043:20190501:SECOND_AB:ENHANCED:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603043_SECOND_A_B_ENHANCED_CONTRACT.json",
    "UWTRAIN:CN603555:20190501:CURRENT_AGENT_SELF_REPLAY:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603555_CURRENT_AGENT_SELF_REPLAY_CONTRACT.json",
    "UWTRAIN:CN603866:20190501:BLIND:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603866_BLIND_CONTRACT.json",
    "UWTRAIN:CN603885:20190501:CURRENT_AGENT_SELF_REPLAY:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603885_CURRENT_AGENT_SELF_REPLAY_CONTRACT.json",
    "UWTRAIN:CN603899:20190501:CURRENT_AGENT_SELF_REPLAY:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/CN603899_CURRENT_AGENT_SELF_REPLAY_CONTRACT.json",
    "UWTRAIN:HK01502:20230501:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/HK01502_WORKED_CONTRACT.json",
    "UWTRAIN:HK02669:20221231:WORKED:C1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/HK02669_WORKED_CONTRACT.json",
    "UWTRAIN:MAGNA:200903:WORKED:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/contracts/MAGNA_200903_WORKED_CONTRACT.json",
    "UWTRAIN:CN000672:20180430:COURSE2B:BASELINE:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/contracts/CN000672_COURSE2B_BASELINE_CONTRACT.json",
    "UWTRAIN:CN000672:20180430:COURSE2B:ENHANCED:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_2B_CN000672_20180430/contracts/CN000672_COURSE2B_ENHANCED_CONTRACT.json",
    "UWTRAIN:CN601888:20190501:INDEPENDENT_AB_3:BASELINE:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_INDEPENDENT_AB_3_20260830/contracts/CN601888_INDEPENDENT_AB_3_BASELINE_CONTRACT.json",
    "UWTRAIN:CN601888:20190501:INDEPENDENT_AB_3:ENHANCED:V1": "docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_INDEPENDENT_AB_3_20260830/contracts/CN601888_INDEPENDENT_AB_3_ENHANCED_CONTRACT.json",
}
_REPORT_AUTONOMY_2X2_ROOT = (
    "docs/development/research/training_campaigns/"
    "ENTERPRISE_UNDERWRITING_REPORT_AUTONOMY_2X2_CN000935_20180430"
)
FROZEN_DERIVATION_V1_CONTRACT_REFS = {
    f"UWTRAIN:CN000935:20180430:REPORT_AUTONOMY_2X2:{arm}:V{version}": (
        f"{_REPORT_AUTONOMY_2X2_ROOT}/"
        f"{'contracts' if version == 1 else f'contracts_v{version}'}/"
        f"CN000935_{label}_CONTRACT.json"
    )
    for version in (1, 2, 3, 4)
    for arm, label in (
        ("A00", "A00_BASELINE"),
        ("A01", "A01_INDUSTRY_ONLY"),
        ("A10", "A10_EXPERT_ONLY"),
        ("A11", "A11_COMBINED"),
    )
}
_PRICE_RESULT_KEYS = {
    "price",
    "market_price",
    "share_price",
    "entry_price",
    "buyband",
    "buy_band",
    "expected_return",
    "realized_return",
    "valuation_result",
}
_BLIND_RESULT_KEYS = {
    "outcome_result",
    "outcome_results",
    "observed_result",
    "result_value",
    "settlement",
    "settled_value",
    "post_outcome_review",
}
_LEGACY_COMPLETION_KEYS = {
    "axes",
    "outcome_cells",
    "material_treatment_snapshot",
    "field_completion",
    "gate_states",
    "receipt_completion",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _canonical_ref(value: Any) -> str:
    return str(value or "").split("#", 1)[0].strip()


def _source_ref_resolvable(value: Any) -> bool:
    reference = _canonical_ref(value)
    if not reference or "://" in reference:
        return False
    return (_ROOT / reference).is_file() or reference.startswith(
        ("SRC:", "OBS:", "DOC:", "CALC:", "canonical:")
    )


def _legacy_frozen_contract_findings(value: dict[str, Any]) -> list[str]:
    """Allow v1 only as exact replay of an explicitly named frozen contract."""

    contract_id = value.get("contract_id")
    reference = LEGACY_FROZEN_CONTRACT_REFS.get(str(contract_id or ""))
    if reference is None:
        return ["contract.legacy_v1_not_registered_for_frozen_replay"]
    path = _ROOT / reference
    try:
        canonical = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["contract.legacy_v1_frozen_reference_unavailable"]
    if value != canonical:
        return ["contract.legacy_v1_payload_differs_from_frozen_contract"]
    return []


def _frozen_derivation_v1_contract_findings(value: dict[str, Any]) -> list[str]:
    """Admit the old derivation policy only as an exact frozen replay."""

    contract_id = value.get("contract_id")
    reference = FROZEN_DERIVATION_V1_CONTRACT_REFS.get(
        str(contract_id or "")
    )
    if reference is None:
        return ["contract.derivation_interface_v1_not_registered_for_frozen_replay"]
    path = _ROOT / reference
    try:
        canonical = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return ["contract.derivation_interface_v1_frozen_reference_unavailable"]
    if value != canonical:
        return ["contract.derivation_interface_v1_payload_differs_from_frozen_contract"]
    return []


def _require_current_contract_for_new_execution(
    value: dict[str, Any], operation: str,
) -> None:
    if value.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError(
            f"legacy_v1_replay_only:{operation}; use validate-episode or "
            "compile-bundle with the exact frozen contract"
        )
    if value.get("economic_derivation_interface") == ECONOMIC_DERIVATION_INTERFACE_V1:
        raise ValueError(
            f"derivation_interface_v1_replay_only:{operation}; use "
            "validate-episode, validate-fresh-response, or compile-bundle with "
            "the exact frozen contract"
        )


def _result(schema_version: str, findings: list[str]) -> dict[str, Any]:
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": schema_version,
        "state": "REVIEWABLE" if not unique else "INVALID",
        "findings": unique,
    }


def _forbidden_paths(value: Any, forbidden: set[str], path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f"{path}.{key}"
            if str(key).lower() in forbidden:
                findings.append(child)
            else:
                findings.extend(_forbidden_paths(item, forbidden, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_forbidden_paths(item, forbidden, f"{path}[{index}]"))
    return findings


def build_training_contract(
    *,
    contract_id: str,
    training_track: str,
    company_id: str,
    company_name: str,
    cutoff_at: str,
    allowed_sources: list[dict[str, Any]],
    feedback_clocks: list[dict[str, Any]],
    economic_derivation_interface: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the minimal task envelope without adding another training object."""

    track = str(training_track or "").upper()
    binding = TRACK_BINDINGS.get(track, {})
    contract = {
        "schema_version": CONTRACT_SCHEMA,
        "contract_id": contract_id,
        "training_track": track,
        "company_id": company_id,
        "company_name": company_name,
        "cutoff_at": cutoff_at,
        "sample_identity": binding.get("sample_identity"),
        "outcome_access": binding.get("outcome_access"),
        "allowed_sources": deepcopy(allowed_sources),
        "feedback_clocks": deepcopy(feedback_clocks),
        "primary_training_product": deepcopy(PRIMARY_PRODUCT),
        "component_decision_interface": deepcopy(COMPONENT_DECISION_INTERFACE),
        "authority": TRAINING_AUTHORITY,
    }
    if economic_derivation_interface is not None:
        contract["economic_derivation_interface"] = deepcopy(
            economic_derivation_interface
        )
    return contract


def validate_training_contract(contract: Any) -> dict[str, Any]:
    """Validate identity, source visibility, and multi-clock feedback binding."""

    findings: list[str] = []
    value = _mapping(contract)
    if not value:
        return _result(CONTRACT_VALIDATION_SCHEMA, ["contract.must_be_object"])
    contract_schema = value.get("schema_version")
    allowed_fields = (
        ROOT_FIELDS - {
            "component_decision_interface",
            "economic_derivation_interface",
        }
        if contract_schema == LEGACY_CONTRACT_SCHEMA
        else ROOT_FIELDS
    )
    unexpected = sorted(set(value) - allowed_fields)
    if unexpected:
        findings.append("contract.unexpected_fields:" + ",".join(unexpected))
    if contract_schema not in {CONTRACT_SCHEMA, LEGACY_CONTRACT_SCHEMA}:
        findings.append("contract.schema_version_invalid")
    elif contract_schema == LEGACY_CONTRACT_SCHEMA:
        findings.extend(_legacy_frozen_contract_findings(value))
    for field in ("contract_id", "company_id", "company_name"):
        if not _text(value.get(field)):
            findings.append(f"contract.{field}_missing")

    cutoff = _instant(value.get("cutoff_at"))
    if cutoff is None:
        findings.append("contract.cutoff_at_invalid")

    track = str(value.get("training_track") or "").upper()
    binding = TRACK_BINDINGS.get(track)
    if binding is None:
        findings.append("contract.training_track_invalid")
    else:
        if value.get("sample_identity") != binding["sample_identity"]:
            findings.append("contract.sample_identity_not_bound_to_track")
        if value.get("outcome_access") != binding["outcome_access"]:
            findings.append("contract.outcome_access_not_bound_to_track")
    if track == "BLIND_REPLAY" and value.get("outcome_access") != "SEALED":
        findings.append("contract.blind_replay_requires_sealed_outcome")

    sources = value.get("allowed_sources")
    if not isinstance(sources, list) or not sources:
        findings.append("contract.allowed_sources_missing")
        sources = []
    source_ids: set[str] = set()
    source_refs: set[str] = set()
    for index, raw in enumerate(sources):
        path = f"contract.allowed_sources[{index}]"
        source = _mapping(raw)
        if not source:
            findings.append(path + ".must_be_object")
            continue
        extra = sorted(set(source) - SOURCE_FIELDS)
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        source_id = source.get("source_id")
        source_ref = _canonical_ref(source.get("source_ref"))
        if not _text(source_id) or source_id in source_ids:
            findings.append(path + ".source_id_missing_or_duplicate")
        else:
            source_ids.add(str(source_id))
        if not source_ref or source_ref in source_refs:
            findings.append(path + ".source_ref_missing_or_duplicate")
        else:
            source_refs.add(source_ref)
            if not _source_ref_resolvable(source_ref):
                findings.append(path + ".source_ref_not_resolvable")
        available = _instant(source.get("available_at"))
        if available is None:
            findings.append(path + ".available_at_invalid")
        time_role = source.get("time_role")
        if time_role not in SOURCE_TIME_ROLES:
            findings.append(path + ".time_role_invalid")
        if track in {"BLIND_REPLAY", "PROSPECTIVE"} and time_role == "RESULT_KNOWN":
            findings.append(path + ".result_known_source_forbidden")
        if (
            time_role == "PRE_CUTOFF"
            and cutoff is not None
            and available is not None
            and available > cutoff
        ):
            findings.append(path + ".available_after_cutoff")

    clocks = value.get("feedback_clocks")
    if not isinstance(clocks, list) or len(clocks) < 2:
        findings.append("contract.feedback_clocks_requires_multiple_items")
        clocks = []
    clock_ids: set[str] = set()
    horizons: set[str] = set()
    for index, raw in enumerate(clocks):
        path = f"contract.feedback_clocks[{index}]"
        clock = _mapping(raw)
        if not clock:
            findings.append(path + ".must_be_object")
            continue
        extra = sorted(set(clock) - CLOCK_FIELDS)
        if extra:
            findings.append(path + ".unexpected_fields:" + ",".join(extra))
        clock_id = clock.get("clock_id")
        if not _text(clock_id) or clock_id in clock_ids:
            findings.append(path + ".clock_id_missing_or_duplicate")
        else:
            clock_ids.add(str(clock_id))
        horizon = clock.get("horizon")
        if horizon not in FEEDBACK_HORIZONS:
            findings.append(path + ".horizon_invalid")
        else:
            horizons.add(str(horizon))
        opens = _instant(clock.get("opens_at"))
        if opens is None:
            findings.append(path + ".opens_at_invalid")
        elif cutoff is not None and opens <= cutoff:
            findings.append(path + ".opens_at_must_follow_cutoff")
        claims = clock.get("episode_claims")
        if not isinstance(claims, list) or not claims:
            findings.append(path + ".episode_claims_missing")
        elif len(claims) != len(set(claims)) or not set(claims) <= EPISODE_CLAIMS:
            findings.append(path + ".episode_claims_invalid")
        if not _text(clock.get("discriminating_observation")):
            findings.append(path + ".discriminating_observation_missing")
    if len(clocks) >= 2 and len(horizons) < 2:
        findings.append("contract.feedback_clocks_must_use_distinct_horizons")

    product = _mapping(value.get("primary_training_product"))
    if set(product) != PRODUCT_FIELDS or product != PRIMARY_PRODUCT:
        findings.append("contract.primary_training_product_must_be_complete_episode_only")
    if (
        contract_schema == CONTRACT_SCHEMA
        and _mapping(value.get("component_decision_interface"))
        != COMPONENT_DECISION_INTERFACE
    ):
        findings.append("contract.component_decision_interface_invalid")
    derivation_interface = _mapping(value.get("economic_derivation_interface"))
    if "economic_derivation_interface" in value:
        expected_interface = _ECONOMIC_DERIVATION_INTERFACES.get(
            derivation_interface.get("schema_version")
        )
        if derivation_interface != expected_interface:
            findings.append("contract.economic_derivation_interface_invalid")
        elif derivation_interface == ECONOMIC_DERIVATION_INTERFACE_V1:
            findings.extend(_frozen_derivation_v1_contract_findings(value))
    if value.get("authority") != TRAINING_AUTHORITY:
        findings.append("contract.authority_invalid")
    return _result(CONTRACT_VALIDATION_SCHEMA, findings)


def validate_training_episode(contract: Any, episode: Any) -> dict[str, Any]:
    """Validate one Episode against the task without rewarding local artifacts."""

    findings: list[str] = []
    contract_result = validate_training_contract(contract)
    findings.extend("contract:" + item for item in contract_result["findings"])
    contract_value = _mapping(contract)
    episode_value = _mapping(episode)

    requires_v2_magnitude_evidence = (
        contract_value.get("economic_derivation_interface")
        == ECONOMIC_DERIVATION_INTERFACE_V2
    )
    episode_result = validate_enterprise_underwriting_episode(
        episode_value,
        require_bounded_sensitivity_magnitude_evidence=(
            requires_v2_magnitude_evidence
        ),
    )
    findings.extend("episode:" + item for item in episode_result["findings"])
    if episode_value:
        for field in ("company_id", "company_name", "cutoff_at", "sample_identity"):
            if episode_value.get(field) != contract_value.get(field):
                findings.append("binding." + field + "_mismatch")

        allowed_sources = [
            _mapping(item)
            for item in _items(contract_value.get("allowed_sources"))
            if isinstance(item, dict)
        ]
        allowed = {_canonical_ref(item.get("source_ref")) for item in allowed_sources}
        training_memory = {
            _canonical_ref(item.get("source_ref"))
            for item in allowed_sources
            if item.get("time_role") == "TRAINING_MEMORY"
        }
        for index, item in enumerate(_items(episode_value.get("evidence_trace"))):
            reference = _canonical_ref(_mapping(item).get("source_ref"))
            if reference not in allowed:
                findings.append(f"binding.evidence_trace[{index}].source_not_allowed")
            elif reference in training_memory:
                findings.append(f"binding.evidence_trace[{index}].training_memory_not_company_evidence")
        for index, item in enumerate(_items(episode_value.get("existing_object_refs"))):
            reference = _canonical_ref(_mapping(item).get("ref"))
            if reference not in allowed:
                findings.append(f"binding.existing_object_refs[{index}].source_not_allowed")
            elif reference in training_memory:
                findings.append(f"binding.existing_object_refs[{index}].training_memory_not_company_evidence")

        findings.extend(
            "episode.price_or_return_forbidden:" + path
            for path in _forbidden_paths(episode_value, _PRICE_RESULT_KEYS)
        )
        findings.extend(
            "episode.legacy_completion_forbidden:" + path
            for path in _forbidden_paths(episode_value, _LEGACY_COMPLETION_KEYS)
        )
        if contract_value.get("training_track") in {"BLIND_REPLAY", "PROSPECTIVE"}:
            findings.extend(
                "episode.preoutcome_result_forbidden:" + path
                for path in _forbidden_paths(episode_value, _BLIND_RESULT_KEYS)
            )
        if (
            contract_value.get("schema_version") == CONTRACT_SCHEMA
            and not _items(episode_value.get("component_decisions"))
        ):
            findings.append("binding.component_decisions_required_by_contract")
        if (
            contract_value.get("economic_derivation_interface")
            in (
                ECONOMIC_DERIVATION_INTERFACE_V1,
                ECONOMIC_DERIVATION_INTERFACE_V2,
            )
            and not _mapping(episode_value.get("economic_derivation"))
        ):
            findings.append("binding.economic_derivation_required_by_contract")
    return _result(EPISODE_VALIDATION_SCHEMA, findings)


def compile_price_free_downstream_bundle(contract: Any, episode: Any) -> dict[str, Any]:
    """Compile existing price-free projections after the sole product validates."""

    validation = validate_training_episode(contract, episode)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("training_episode_invalid:" + ",".join(validation["findings"]))
    projections = compile_underwriting_projections(episode)
    projection_validation = validate_underwriting_projection_bundle(episode, projections)
    if projection_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "underwriting_projection_invalid:" + ",".join(projection_validation["findings"])
        )
    value = _mapping(episode)
    thesis = _mapping(value.get("underwriting_thesis"))
    return {
        "schema_version": DOWNSTREAM_BUNDLE_SCHEMA,
        "contract_id": _mapping(contract).get("contract_id"),
        "company_id": value.get("company_id"),
        "cutoff_at": value.get("cutoff_at"),
        "sample_identity": value.get("sample_identity"),
        "primary_training_product": {
            "object_type": "EnterpriseUnderwritingEpisode",
            "episode_id": value.get("episode_id"),
            "underwriting_thesis_id": thesis.get("thesis_id"),
        },
        "authority": "PRICE_FREE_RESEARCH_CANDIDATES_ONLY",
        "projections": projections,
        "boundary": {
            "contains_outcome_results": False,
            "contains_price_or_valuation_results": False,
            "grants_investment_authority": False,
        },
    }


def _source_materials(contract: dict[str, Any]) -> list[dict[str, str]]:
    """Read only the source files named by the already validated contract."""
    materials: list[dict[str, str]] = []
    for item in _items(contract.get("allowed_sources")):
        source = _mapping(item)
        reference = _canonical_ref(source.get("source_ref"))
        path = Path(reference).expanduser()
        if not path.is_absolute():
            path = _ROOT / path
        if not path.is_file():
            raise ValueError(
                "training source is not a readable local artifact; prepare a source-package "
                "text artifact before running the Agent: " + reference
            )
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                "training source must be a UTF-8 research artifact: " + reference
            ) from exc
        materials.append({
            "source_id": str(source.get("source_id") or ""),
            "source_ref": reference,
            "content": content,
        })
    return materials


def build_training_agent_messages(
    contract: Any,
    *,
    source_materials: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Build the one complete-Episode task consumed by the training Agent."""
    validation = validate_training_contract(contract)
    if validation["state"] != "REVIEWABLE":
        raise ValueError("training_contract_invalid:" + ",".join(validation["findings"]))
    value = _mapping(contract)
    _require_current_contract_for_new_execution(value, "build-agent-messages")
    source_blocks = []
    source_roles = {
        _canonical_ref(item.get("source_ref")): str(item.get("time_role") or "")
        for item in _items(value.get("allowed_sources"))
        if isinstance(item, dict)
    }
    for item in source_materials:
        source_ref = str(item.get("source_ref") or "")
        source_blocks.append(
            "\n".join([
                "<source>",
                "source_id=" + str(item.get("source_id") or ""),
                "source_ref=" + source_ref,
                "time_role=" + source_roles.get(_canonical_ref(source_ref), ""),
                str(item.get("content") or ""),
                "</source>",
            ])
        )
    component_decision_requirement = ""
    if value.get("schema_version") == CONTRACT_SCHEMA:
        component_decision_requirement = """
The Episode must also contain component_decisions with exactly one entry for every
component_treatments component_id. For each component, state its comparable economic_scope,
whether it enters base or conditional normal earnings, whether it forms an owner-cash
range, how it changes financing pressure, how it enters permanent-loss analysis and the
value route, plus separate promotion and invalidation tests. valuation_route_bindings
must name every exact primary, corroborative, stress, excluded, scenario, or unresolved
route_id that the component can feed, with that route-specific use; one unrelated primary
component cannot authorize another component's EPV, owner-cash, or capital-return route.
value_route.route_component_requirements must name the required and optional component_ids
for every route. Every required component must retain a role-compatible route binding;
an optional component may remain excluded without invalidating the route.
These downstream uses are
the decision; the UNDERWRITE/CONDITIONALLY_UNDERWRITE/SCENARIO_ONLY/EXCLUDE_FROM_BASE/
CANNOT_BOUND label cannot substitute for them. A component excluded, scenario-only, or
unbounded at the component level cannot silently become a base-range or primary value
input."""
    economic_derivation_requirement = ""
    if value.get("economic_derivation_interface") == ECONOMIC_DERIVATION_INTERFACE:
        economic_derivation_requirement = """
The Episode must also contain economic_derivation. Its normal_earnings_bridge rows
identify component_id, sign, evidence, economic reason, and either a bounded range or
an explicit UNKNOWN with reason and conservative treatment. The bridge must contain
exactly one REFERENCE_EARNINGS baseline and at most one row for each component_id and
row_role pair; changing row_id never makes a duplicated contribution distinct. If any
BASE_RANGE row exists, the reference baseline itself must have BASE_RANGE authority;
otherwise, if a CONDITIONAL_RANGE row exists, the reference must have CONDITIONAL_RANGE
authority. Adjustments cannot create an authorized earnings range without that baseline.
Do not author a row-level
normal_earnings_use: the compiler derives BASE_RANGE, CONDITIONAL_RANGE, SCENARIO_ONLY,
or EXCLUDED solely from component_decisions. UNKNOWN is not zero and must not be turned
into a point estimate. driver_sensitivity_specs must give each key operating driver a
LOW_BASE_HIGH set or BOUNDED_RANGE, trace its transmission to normal earnings and owner
cash with either a signed BOUNDED delta range that includes zero or an explicit UNKNOWN,
name only routes whose exact component binding use matches the route role, and cite valid
reversal observations. EXCLUDED, SCENARIO_ONLY, or UNRESOLVED component authority cannot
be upgraded to DIRECT normal-earnings or owner-cash transmission. Every non-PRESERVED
BOUNDED normal-earnings or owner-cash delta needs its own structured magnitude_evidence:
one or more evidence ids not reused from the driver input cases, the exact sensitivity
component_ids and responsibility_boundary, matching driver metric/unit/horizon, matching
affected axis and delta unit, and a non-empty calculation_binding whose input evidence
ids are the same magnitude evidence ids. Each cited evidence_trace item must itself
carry a sensitivity_magnitude_observation with those exact component, responsibility,
driver metric/unit, horizon, affected-axis, delta-unit, and calculation-input fields;
those canonical trace fields, not repeated labels inside magnitude_evidence, authorize
the magnitude. Do not use the transmission basis text or a component's existing
authority as a magnitude substitute. PRESERVED [0,0] may remain without magnitude
evidence. UNKNOWN deltas have no numeric attribution. Keep
this interface price-free: do not provide value, return, or action results."""
    system = """You are Turtle's enterprise-underwriting training synthesizer.
Your only product is one complete EnterpriseUnderwritingEpisode JSON object.
Connect industry future and profit-pool transmission, company position and adaptation,
survival and financing, normalized economics, owner cash, permanent-loss paths, value
route, strongest rival, and reversal observations into one best-current judgment.
Evidence discipline is a constraint, not the product: localize an unknown and continue
the rest of the company. Do not emit axes, outcome cells, receipts, gates, scores,
market price, valuation results, expected return, BuyBand, or investment action.
When capital spending matters, keep three distinct economic questions: operating cash
less economic maintenance capital (normal owner cash), operating cash less all
long-lived-asset spending (current capital-allocation and financing pressure), and the
subsequent return on growth capital. Missing growth-return evidence or total spending
must never be renamed as maintenance capital or used to invent a negative owner-cash
point estimate; give a conditional treatment and continue the company judgment.
Capital intensity is economic, not a fixed-asset label: for a channel, service, retail,
or acquisition-led company, identify material working-capital, lease, logistics, people,
integration, or customer-acquisition commitments alongside long-lived assets. Do not call
a company cash-light merely because capex is low, and do not force a capital-spending
problem where those commitments are immaterial.
Use only the supplied sources. Every evidence_trace.source_ref and existing_object_ref.ref
must exactly match a supplied source_ref. Return JSON only, with schema_version
enterprise-underwriting-episode.v2. The underwriting_thesis must include
economic_directions.normal_earnings, owner_cash, and permanent_loss, each chosen from
IMPROVES, DETERIORATES, MIXED, UNKNOWN, or NONE. Only primary valuation model roles are
mandatory; corroborative and stress roles may be empty or omitted when economically
inapplicable. A source labelled TRAINING_MEMORY is prior curriculum guidance only: use it
to change questions, evidence order, rival checks, or conditional treatment, but never
as a target-company fact and never cite it in evidence_trace or existing_object_refs.""" + component_decision_requirement + economic_derivation_requirement
    user = "\n".join([
        "Create the complete pre-outcome Episode for this frozen training contract:",
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True),
        "\nAllowed source material:",
        "\n\n".join(source_blocks),
        "\nReturn the JSON object now.",
    ])
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_agent_episode(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return deepcopy(raw)
    text = str(raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("training Agent did not return an Episode JSON object")
    payload = json.loads(text[start:end + 1])
    if not isinstance(payload, dict):
        raise ValueError("training Agent Episode must be a JSON object")
    return payload


def _materialize_unknown_sensitivity_transmissions(episode: dict[str, Any]) -> None:
    """Canonicalize the one self-contradictory sensitivity representation.

    A response which explicitly says a delta is ``UNKNOWN`` cannot at the same
    time claim a DIRECT or PRESERVED transmission.  The delta is the more
    specific economic assertion, so the runner carries that uncertainty to the
    matching transmission status.  It never changes any other delta or fills a
    missing sensitivity case, basis, component, route, or evidence reference.
    """

    derivation = _mapping(episode.get("economic_derivation"))
    for raw_spec in _items(derivation.get("driver_sensitivity_specs")):
        transmission = _mapping(_mapping(raw_spec).get("transmission"))
        for axis in ("normal_earnings", "owner_cash"):
            treatment = _mapping(transmission.get(axis))
            if _mapping(treatment.get("delta")).get("status") == "UNKNOWN":
                treatment["status"] = "UNKNOWN"


def _materialize_excluded_value_routes(episode: dict[str, Any]) -> None:
    """Register passive component-bound routes without resolving role conflicts.

    Component ledgers can name a route solely to say that it is excluded,
    unresolved, scenario-only, or not applicable.  Those passive routes belong
    in ``value_route.excluded_routes`` unless the Agent already registered the
    same route as an active model role.  The runner only appends missing route
    ids; it never removes an active/excluded conflict or manufactures a route
    requirement, component binding, or economic treatment.
    """

    value_route = _mapping(episode.get("value_route"))
    if not value_route:
        return
    existing_excluded = value_route.get("excluded_routes")
    if existing_excluded is not None and not isinstance(existing_excluded, list):
        return

    active_route_ids = {
        str(route_id)
        for route_id in _items(value_route.get("primary_routes"))
        if _text(route_id)
    }
    model_roles = _mapping(value_route.get("valuation_model_roles"))
    for role in ("primary", "corroborative", "stress"):
        active_route_ids.update(
            str(route_id)
            for route_id in _items(model_roles.get(role))
            if _text(route_id)
        )

    excluded_routes = list(existing_excluded or [])
    registered_excluded = {
        str(route_id) for route_id in excluded_routes if _text(route_id)
    }
    for raw_decision in _items(episode.get("component_decisions")):
        for raw_binding in _items(
            _mapping(raw_decision).get("valuation_route_bindings")
        ):
            binding = _mapping(raw_binding)
            route_id = binding.get("route_id")
            if (
                not _text(route_id)
                or binding.get("use") not in _AUTO_EXCLUDED_ROUTE_BINDING_USES
            ):
                continue
            route_id = str(route_id)
            if route_id in active_route_ids or route_id in registered_excluded:
                continue
            excluded_routes.append(route_id)
            registered_excluded.add(route_id)
    value_route["excluded_routes"] = excluded_routes


def materialize_fresh_subagent_episode(agent_response: Any) -> dict[str, Any]:
    """Return the sole canonical Episode representation of a fresh response.

    The fresh Agent remains responsible for every economic claim and every
    validator-facing ledger.  This narrow compiler step only derives two
    summaries, propagates an already-declared UNKNOWN sensitivity delta, and
    registers otherwise passive component-bound routes as excluded.  It is
    intentionally applied before every fresh-response validation and run, so
    an omitted compiler-owned field cannot produce different verdicts by path.
    """

    episode = _parse_agent_episode(agent_response)
    _materialize_unknown_sensitivity_transmissions(episode)
    _materialize_excluded_value_routes(episode)

    if isinstance(episode.get("component_decisions"), list):
        episode["component_decision_summary"] = derive_component_decision_summary(
            episode["component_decisions"]
        )
    else:
        episode.pop("component_decision_summary", None)
    if isinstance(episode.get("economic_derivation"), dict):
        episode["economic_derivation_summary"] = derive_economic_derivation_summary(
            episode
        )
    else:
        episode.pop("economic_derivation_summary", None)
    return episode


def validate_fresh_subagent_response(contract: Any, agent_response: Any) -> dict[str, Any]:
    """Validate a fresh response through the same canonicalization as ``run``."""

    return validate_training_episode(
        contract, materialize_fresh_subagent_episode(agent_response)
    )


def _atomic_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def run_training_agent(
    contract: Any,
    *,
    output_dir: str | Path,
    episode_generator: Callable[[list[dict[str, str]]], Any],
    source_materials: list[dict[str, str]] | None = None,
    execution_mode: str = "IN_PROCESS_AGENT_CALLBACK",
) -> dict[str, Any]:
    """Generate, validate, and persist the sole training product.

    ``episode_generator`` may be an in-process model callback or the response
    returned by a coordinator-spawned fresh Codex sub-agent.  It is invoked only
    after the source contract has validated.  Local artifacts are written only
    after the returned complete Episode passes the same binding validator used
    by replay.  Merely running ``validate-episode`` never completes training.
    """
    contract_value = _mapping(contract)
    contract_validation = validate_training_contract(contract_value)
    if contract_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "training_contract_invalid:" + ",".join(contract_validation["findings"])
        )
    _require_current_contract_for_new_execution(contract_value, "run")
    materials = source_materials if source_materials is not None else _source_materials(contract_value)
    allowed_refs = {
        _canonical_ref(item.get("source_ref"))
        for item in _items(contract_value.get("allowed_sources"))
        if isinstance(item, dict)
    }
    observed_refs = {
        _canonical_ref(item.get("source_ref"))
        for item in materials if isinstance(item, dict)
    }
    if observed_refs != allowed_refs:
        raise ValueError("training Agent source materials must exactly match the contract allowlist")
    messages = build_training_agent_messages(
        contract_value,
        source_materials=materials,
    )
    episode = materialize_fresh_subagent_episode(episode_generator(messages))
    episode_validation = validate_training_episode(contract_value, episode)
    if episode_validation["state"] != "REVIEWABLE":
        raise ValueError(
            "training_agent_episode_invalid:" + ",".join(episode_validation["findings"])
        )
    bundle = compile_price_free_downstream_bundle(contract_value, episode)
    output = Path(output_dir).expanduser().resolve()
    episode_path = output / "enterprise_underwriting_episode.json"
    bundle_path = output / "enterprise_underwriting_downstream_bundle.json"
    _atomic_json(episode_path, episode)
    _atomic_json(bundle_path, bundle)
    return {
        "schema_version": RUN_RECEIPT_SCHEMA,
        "state": "TRAINING_EPISODE_COMPLETED",
        "contract_id": contract_value.get("contract_id"),
        "episode_id": episode.get("episode_id"),
        "underwriting_thesis_id": _mapping(episode.get("underwriting_thesis")).get("thesis_id"),
        "episode_path": str(episode_path),
        "downstream_bundle_path": str(bundle_path),
        "execution_mode": execution_mode,
        "completion_basis": (
            "FRESH_CODEX_SUBAGENT_GENERATED_COMPLETE_EPISODE_VALIDATED"
            if execution_mode == "CODEX_FRESH_SUBAGENT"
            else "AGENT_GENERATED_COMPLETE_EPISODE_VALIDATED"
        ),
        "authority": TRAINING_AUTHORITY,
    }


def build_fresh_subagent_task(contract: Any) -> dict[str, Any]:
    """Render the exact task for a ``fork_turns=none`` Codex sub-agent.

    This is an ephemeral orchestration packet, not a training product or a
    second evidence store.  The coordinator should place it outside the repo,
    give only this packet to one fresh sub-agent, then pass that Agent's JSON
    response to ``run --agent-response``.
    """

    contract_value = _mapping(contract)
    validation = validate_training_contract(contract_value)
    if validation["state"] != "REVIEWABLE":
        raise ValueError(
            "training_contract_invalid:" + ",".join(validation["findings"])
        )
    _require_current_contract_for_new_execution(
        contract_value, "render-subagent-task"
    )
    messages = build_training_agent_messages(
        contract_value,
        source_materials=_source_materials(contract_value),
    )
    execution_schema = json.loads(
        _EPISODE_JSON_SCHEMA_PATH.read_text(encoding="utf-8")
    )
    if (
        contract_value.get("economic_derivation_interface")
        == ECONOMIC_DERIVATION_INTERFACE_V2
    ):
        sensitivity_required = execution_schema["$defs"][
            "driver_sensitivity_spec"
        ]["required"]
        if "responsibility_boundary" not in sensitivity_required:
            sensitivity_required.append("responsibility_boundary")
    messages[0]["content"] += """
The enclosing fresh-task packet includes the complete frozen Episode JSON Schema at
response_contract.episode_json_schema. Treat that schema as the authoritative response
shape: include every field required at the applicable schema location; use only values
allowed by enum or const; and wherever additionalProperties is false, do not add or
rename fields. Do not invent a parallel structure when the schema already defines one.

The following cross-field rules are also part of the response contract because JSON
Schema alone cannot express them:
- Copy company_id, company_name, cutoff_at, and sample_identity verbatim from the
  frozen contract.
- Copy situation_model.industry_future_thesis.strongest_rival verbatim into both the
  top-level strongest_rival and underwriting_thesis.strongest_rival. Copy its entire
  reversal_observations array verbatim into the top-level reversal_observations.
- Every evidence_trace item must have evidence_id, source_ref, locator, scope, and
  used_for. Evidence ids must be unique. Every cited source_ref/ref must exactly equal
  an allowed non-TRAINING_MEMORY source_ref. Every existing_object_refs item must have
  kind, ref, and role.
- component_decisions must cover every component_treatments component_id exactly once.
  valuation_use is the highest-authority use in that component's route bindings, in
  this order: PRIMARY_INPUT, CONDITIONAL_PRIMARY_INPUT, CORROBORATIVE_INPUT,
  SCENARIO_ONLY, STRESS_ONLY, UNRESOLVED, EXCLUDED, NOT_APPLICABLE. Every
  non-NOT_APPLICABLE valuation use needs a binding. Excluded/scenario/unbounded
  treatments cannot become base or primary inputs; CANNOT_BOUND retains an UNRESOLVED
  downstream use and CONDITIONALLY_UNDERWRITE retains a conditional downstream use.
- Give every bound or named primary, corroborative, stress, or excluded value route one
  route_component_requirements entry. Required and optional component ids must be known,
  unique and disjoint. Each route must have a role-compatible bound component; every
  required component must itself have a role-compatible binding. One route cannot be
  both active and excluded.
- normal_earnings_bridge must contain exactly one REFERENCE_EARNINGS row, no duplicate
  component_id/row_role pair, and at least one row for every component whose
  normal_earnings_use is not NOT_APPLICABLE. A BASE_RANGE or CONDITIONAL_RANGE row needs
  a reference row with the same authority. Every row and sensitivity evidence_id must
  exist in evidence_trace, as must every component_treatments evidence_id.
- In each driver sensitivity, named components and valuation routes must exist. Each
  route must be bound to every named component and the binding use must be compatible
  with the route's primary/corroborative/stress role. DIRECT transmission requires base
  or conditional component authority. UNKNOWN transmission requires an UNKNOWN delta;
  a BOUNDED delta is signed and includes zero; PRESERVED requires a zero delta. Every
  non-PRESERVED BOUNDED delta needs separate structured magnitude evidence with matching
  component ids, responsibility boundary, driver metric/unit/horizon, affected axis and
  delta unit, plus a calculation binding. Those evidence ids must not be driver-case
  evidence; each must resolve to an evidence_trace sensitivity_magnitude_observation
  whose canonical component, responsibility, driver metric/unit, horizon, affected
  axis, delta unit, and calculation inputs match the delta. Repeated labels in the delta
  do not substitute. Neither prose basis nor existing component authority substitutes.
  Every reversal_observation_ref must resolve to the top-level copied array.
  Every driver sensitivity itself must include a non-empty responsibility_boundary,
  including a sensitivity whose transmission is UNKNOWN or PRESERVED.
- The runner makes only three narrow deterministic materializations before validation:
  it derives component_decision_summary and economic_derivation_summary; when a
  sensitivity delta.status is UNKNOWN it changes that matching transmission status to
  UNKNOWN; and it registers an otherwise unregistered EXCLUDED, UNRESOLVED,
  SCENARIO_ONLY, or NOT_APPLICABLE component-bound route in excluded_routes. These
  are not substitutes for your economics. You must still supply every material
  component, route requirement, evidence reference, economic reason, sensitivity
  case, treatment, boundary, and reversal condition yourself. Do not rely on the
  runner to repair an invalid or conflicting judgment.
Keep the whole Episode price-, return-, outcome-, and action-free."""
    return {
        "schema_version": SUBAGENT_TASK_SCHEMA,
        "state": "FRESH_SUBAGENT_TASK_READY",
        "contract_id": contract_value.get("contract_id"),
        "execution_mode": "CODEX_FRESH_SUBAGENT",
        "required_context": "fork_turns=none",
        "messages": messages,
        "response_contract": {
            "format": "ONE_ENTERPRISE_UNDERWRITING_EPISODE_JSON_OBJECT",
            "schema_authority": (
                "CONTRACT_BOUND_EXECUTION_EPISODE_JSON_SCHEMA"
                if contract_value.get("economic_derivation_interface")
                == ECONOMIC_DERIVATION_INTERFACE_V2
                else "FROZEN_COMPLETE_EPISODE_JSON_SCHEMA"
            ),
            "schema_requirements": [
                "Honor every applicable required field in episode_json_schema.",
                "Honor every enum and const value in episode_json_schema.",
                "Where additionalProperties is false, emit no undeclared fields.",
                "Use the schema's field names and nesting; do not invent a substitute structure.",
            ],
            "semantic_requirements": [
                (
                    "Copy company_id, company_name, cutoff_at, and sample_identity "
                    "verbatim from the frozen contract."
                ),
                (
                    "Copy industry_future_thesis.strongest_rival verbatim to both "
                    "top-level strongest_rival and underwriting_thesis.strongest_rival, "
                    "and copy its reversal_observations array verbatim to the top level."
                ),
                (
                    "Evidence ids are unique; every evidence item has source_ref, locator, "
                    "scope, and used_for; every existing-object reference has kind, ref, "
                    "and role; citations exactly match an allowed non-TRAINING_MEMORY source."
                ),
                (
                    "component_decisions cover component_treatments exactly once; valuation_use "
                    "is derived from route bindings in the specified authority order; base, "
                    "conditional, excluded, scenario, and unresolved uses remain compatible "
                    "with the component treatment; all treatment evidence ids resolve."
                ),
                (
                    "Every bound or named primary, corroborative, stress, or excluded route has "
                    "one component requirement and at least one role-compatible binding; required "
                    "and optional component ids are known, unique, disjoint, and role-compatible."
                ),
                (
                    "The normal-earnings bridge has exactly one authority-compatible reference "
                    "row and covers every component whose normal_earnings_use is not NOT_APPLICABLE."
                ),
                (
                    "Sensitivity components, evidence, reversal refs, and routes resolve; route "
                    "binding uses match route roles; DIRECT has range authority, UNKNOWN uses an "
                    "UNKNOWN delta, bounded deltas include zero, and PRESERVED has zero delta. "
                    "Every non-PRESERVED bounded delta has separate calculation-bound magnitude "
                    "evidence with matching component, responsibility boundary, driver metric/unit/"
                    "horizon, affected axis, and delta unit. Each evidence id resolves to canonical "
                    "evidence_trace sensitivity_magnitude_observation metadata with matching "
                    "calculation inputs; repeated delta labels, driver-case evidence, basis prose, and "
                    "component authority cannot substitute."
                ),
                (
                    "The runner only derives component_decision_summary and "
                    "economic_derivation_summary, propagates an explicitly UNKNOWN delta "
                    "to its matching transmission, and registers otherwise passive excluded "
                    "component-bound routes. It does not supply economics, evidence, route "
                    "requirements, or resolve conflicts."
                ),
                "Keep the Episode price-, return-, outcome-, and action-free.",
            ],
            "episode_json_schema": execution_schema,
            "must_not_read": [
                "parent_conversation",
                "sibling_arm",
                "sources_outside_task_packet",
                "sealed_outcome",
                "price_or_return",
            ],
        },
    }


def run_fresh_subagent_response(
    contract: Any,
    *,
    agent_response: Any,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Finalize one response produced by the active Codex fresh sub-agent.

    Freshness and sibling isolation are orchestration responsibilities of the
    coordinator that owns ``spawn_agent``.  This function deliberately avoids
    signatures, hashes, or provider credentials; it binds the returned Episode
    to the contract, validates it, and persists the same canonical products as
    the in-process callback path.
    """

    return run_training_agent(
        contract,
        output_dir=output_dir,
        episode_generator=lambda _messages: agent_response,
        execution_mode="CODEX_FRESH_SUBAGENT",
    )


def _runtime_episode_generator(
    *, provider: str, model: str,
) -> Callable[[list[dict[str, str]]], str]:
    try:
        from scripts.turtle_agent.llm_client import LlmClient
    except ModuleNotFoundError:  # pragma: no cover - direct script fallback
        from turtle_agent.llm_client import LlmClient
    client = LlmClient(provider=provider, model=model or None)

    def generate(messages: list[dict[str, str]]) -> str:
        response = client.chat_with_retry(
            messages,
            temperature=0.2,
            max_tokens=16384,
            max_retries=1,
        )
        return response.content

    return generate


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required: {path}")
    return payload


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate_contract = sub.add_parser("validate-contract")
    validate_contract.add_argument("contract", type=Path)
    for name in ("validate-episode", "compile-bundle"):
        command = sub.add_parser(name)
        command.add_argument("contract", type=Path)
        command.add_argument("episode", type=Path)
    validate_fresh = sub.add_parser("validate-fresh-response")
    validate_fresh.add_argument("contract", type=Path)
    validate_fresh.add_argument("agent_response", type=Path)
    reader_brief = sub.add_parser("compile-reader-brief")
    reader_brief.add_argument("episode", type=Path)
    reader_brief.add_argument("--output", type=Path, required=True)
    render = sub.add_parser("render-subagent-task")
    render.add_argument("contract", type=Path)
    render.add_argument("--output", type=Path, required=True)
    run = sub.add_parser("run")
    run.add_argument("contract", type=Path)
    run.add_argument("--output-dir", type=Path, required=True)
    mode = run.add_mutually_exclusive_group(required=True)
    mode.add_argument("--agent-response", type=Path)
    mode.add_argument(
        "--provider", choices=["anthropic", "openai", "deepseek", "deepseek_oa"],
        help="Explicit opt-in to an external API provider; never the default.",
    )
    run.add_argument("--model", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        contract = _read_json(args.contract) if hasattr(args, "contract") else None
        if args.command == "compile-reader-brief":
            episode = _read_json(args.episode)
            brief = compile_golden_report_reader_brief(episode)
            _atomic_json(args.output.expanduser().resolve(), brief)
            result = {
                "schema_version": "enterprise-underwriting-reader-brief-receipt.v1",
                "state": "READER_BRIEF_COMPILED",
                "episode_id": episode.get("episode_id"),
                "brief_path": str(args.output.expanduser().resolve()),
            }
        elif args.command == "validate-contract":
            result = validate_training_contract(contract)
        elif args.command == "validate-fresh-response":
            result = validate_fresh_subagent_response(
                contract, _read_json(args.agent_response)
            )
        elif args.command == "render-subagent-task":
            task = build_fresh_subagent_task(contract)
            _atomic_json(args.output.expanduser().resolve(), task)
            result = {
                "schema_version": SUBAGENT_TASK_SCHEMA,
                "state": "FRESH_SUBAGENT_TASK_READY",
                "contract_id": contract.get("contract_id"),
                "task_path": str(args.output.expanduser().resolve()),
                "execution_mode": "CODEX_FRESH_SUBAGENT",
            }
        elif args.command == "run":
            if args.agent_response is not None:
                if args.model:
                    raise ValueError("--model requires explicit --provider")
                result = run_fresh_subagent_response(
                    contract,
                    agent_response=_read_json(args.agent_response),
                    output_dir=args.output_dir,
                )
            else:
                result = run_training_agent(
                    contract,
                    output_dir=args.output_dir,
                    episode_generator=_runtime_episode_generator(
                        provider=args.provider,
                        model=args.model,
                    ),
                    execution_mode="EXPLICIT_EXTERNAL_API",
                )
        else:
            episode = _read_json(args.episode)
            result = (
                validate_training_episode(contract, episode)
                if args.command == "validate-episode"
                else compile_price_free_downstream_bundle(contract, episode)
            )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError, RuntimeError) as exc:
        result = {
            "schema_version": "enterprise-underwriting-training-cli-error.v1",
            "state": "INVALID",
            "findings": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("state", "REVIEWABLE") != "INVALID" else 1


if __name__ == "__main__":
    raise SystemExit(main())
