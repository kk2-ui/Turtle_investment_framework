#!/usr/bin/env python3
"""Generic cross-industry Enterprise Judgment training orchestration.

The module owns industry-block sampling and identity binding only. Judgment
claims remain in ``EnterpriseJudgmentEpisode``; source validation, outcome
acquisition, settlement and decision-utility review remain in their existing
canonical modules.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timezone
from typing import Any

try:
    from scripts import enterprise_judgment_episode as episode_module
    from scripts import enterprise_judgment_real_mechanism_training as mechanism_training
    from scripts import enterprise_judgment_source_packet as source_packet
    from scripts import judgment_decision_utility as decision_utility
    from scripts import judgment_training_decision_contract as decision_contract
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import enterprise_judgment_episode as episode_module
    import enterprise_judgment_real_mechanism_training as mechanism_training
    import enterprise_judgment_source_packet as source_packet
    import judgment_decision_utility as decision_utility
    import judgment_training_decision_contract as decision_contract


BLOCK_SCHEMA_VERSION = "industry-learning-block.v2"
SELECTION_SCHEMA_VERSION = "enterprise-judgment-industry-selection.v1"
PREOUTCOME_SCHEMA_VERSION = "enterprise-judgment-multidimensional-preoutcome.v1"
SELECTION_POLICY = "LOWEST_COMPANY_ID_WITH_COMPLETE_PRE_CUTOFF_STATIC_PDF_PACKET"
ELIGIBLE_PACKET_STATE = "COMPLETE_PRE_CUTOFF_STATIC_PDF"
BLOCK_OUTPUTS = ["INDUSTRY_CONTEXT", "EPISODE_SAMPLING", "RESEARCH_AGENDA"]
SELECTION_OUTPUTS = ["PRE_OUTCOME_EPISODE_SELECTION", "RESEARCH_AGENDA"]
PREOUTCOME_OUTPUTS = [
    "MULTIDIMENSIONAL_PAIRED_PREOUTCOME_RESEARCH",
    "OUTCOME_CUSTODY_REQUEST",
    "RESEARCH_AGENDA",
]
PREOUTCOME_RIGHTS = {
    "directional_learning": "NOT_AUTHORIZED",
    "enterprise_learning": "NOT_AUTHORIZED",
    "comparative": "NOT_AUTHORIZED",
    "method_transfer": "NOT_AUTHORIZED",
    "cjo": "NOT_AUTHORIZED",
    "valuation": "NOT_AUTHORIZED",
    "report": "NOT_AUTHORIZED",
    "investment": "NOT_AUTHORIZED",
}

_BLOCK_KEYS = {
    "schema_version",
    "block_id",
    "industry_id",
    "cutoff_at",
    "observation_window",
    "industry_epoch",
    "mechanism_arenas",
    "members",
    "selection_policy",
    "strongest_common_rivals",
    "unresolved_questions",
    "outcome_access_status",
    "roles",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_WINDOW_KEYS = {
    "event_start",
    "event_end",
    "accounting_period",
    "settlement_source_type",
    "boundary_note",
}
_EPOCH_KEYS = {
    "epoch_id",
    "condition",
    "observed_industry_volume",
    "observed_industry_revenue",
    "observed_concentration",
    "evidence_refs",
    "causal_credit",
}
_ARENA_KEYS = {"arena_id", "mechanism", "economic_scope", "value_driver", "failure_mode"}
_MEMBER_KEYS = {
    "rank",
    "company_id",
    "issuer_id",
    "company_name",
    "source_packet_ref",
    "packet_state",
    "archetype",
    "responsibility_boundary",
    "arena_ids",
    "cutoff_state",
    "decision_heterogeneity",
    "evidence_refs",
}
_SOURCE_REF_KEYS = {"receipt_id", "receipt_version"}
_SELECTION_POLICY_KEYS = {
    "policy_id",
    "rule",
    "eligible_packet_state",
    "tie_breaker",
    "prohibited_inputs",
}
_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}
_SELECTION_KEYS = {
    "schema_version",
    "selection_id",
    "block_id",
    "policy_id",
    "eligible_company_ids",
    "selected_rank",
    "company_id",
    "issuer_id",
    "cutoff_at",
    "source_packet_ref",
    "selection_used_outcome",
    "selection_used_source_convenience",
    "outcome_access_status",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_PREOUTCOME_KEYS = {
    "schema_version",
    "package_id",
    "industry_block_ref",
    "selection_ref",
    "source_packet_ref",
    "decision_contract",
    "baseline_episode",
    "enhanced_episode",
    "decision_utility_pairing",
    "outcome_measurement_contract",
    "contamination_boundary",
    "freeze_state",
    "frozen_at",
    "roles",
    "rights",
    "object_class",
    "claim_class",
    "allowed_outputs",
}
_BLOCK_REF_KEYS = {"block_id", "schema_version"}
_SELECTION_REF_KEYS = {"selection_id", "schema_version"}
_MEASUREMENT_REF_KEYS = {"contract_set_id", "contract_version"}
_CONTAMINATION_KEYS = {
    "historical_replay_status",
    "model_memory_mitigation",
    "score_authority",
    "allowed_use",
}
_FORBIDDEN_KEYS = {
    "price",
    "market_price",
    "share_price",
    "stock_price",
    "return",
    "valuation",
    "buyband",
    "buy_band",
    "portfolio_action",
    "investment_action",
    "outcome_value",
    "settlement_value",
}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(value: Any, keys: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        _add(findings, path + "_must_be_object")
        return item
    for key in sorted(set(item).difference(keys)):
        _add(findings, f"{path}_contains_unapproved_field:{key}")
    for key in sorted(keys.difference(item)):
        _add(findings, f"{path}_missing_required_field:{key}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        _add(findings, f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _instant(value: Any, path: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _add(findings, path + "_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _day(value: Any, path: str, findings: list[str]) -> date | None:
    if not _text(value):
        _add(findings, path + "_must_be_iso_date")
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        _add(findings, path + "_must_be_iso_date")
        return None


def _unique_texts(value: Any, path: str, findings: list[str], *, required: bool = True) -> list[str]:
    values = _items(value)
    if required and not values:
        _add(findings, path + "_required")
    if any(not _text(entry) for entry in values):
        _add(findings, path + "_must_contain_nonempty_strings")
    cleaned = [str(entry).strip() for entry in values if _text(entry)]
    if len(cleaned) != len(set(cleaned)):
        _add(findings, path + "_must_be_unique")
    return cleaned


def _forbidden_paths(value: Any, path: str = "industry_block") -> list[str]:
    paths: list[str] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            child = f"{path}.{key}"
            lowered = str(key).lower()
            if lowered == "rights":
                continue
            if lowered in _FORBIDDEN_KEYS or lowered.endswith("_price") or lowered.endswith("_return"):
                paths.append(child)
            else:
                paths.extend(_forbidden_paths(nested, child))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            paths.extend(_forbidden_paths(nested, f"{path}[{index}]"))
    return paths


def _source_packet_by_receipt(receipts: list[Any], findings: list[str]) -> dict[tuple[str, int], dict[str, Any]]:
    by_ref: dict[tuple[str, int], dict[str, Any]] = {}
    for index, raw in enumerate(receipts):
        validation = source_packet.validate_source_packet_receipt(raw)
        for finding in validation["findings"]:
            _add(findings, f"source_packets[{index}]:{finding}")
        receipt = _mapping(raw)
        key = (str(receipt.get("packet_id") or ""), receipt.get("packet_version"))
        if key in by_ref:
            _add(findings, f"source_packets[{index}].receipt_identity_duplicate")
        if validation["valid"]:
            by_ref[key] = receipt
    return by_ref


def _locator_ids(receipt: dict[str, Any]) -> set[str]:
    return {
        str(locator.get("locator_id"))
        for source in map(_mapping, _items(receipt.get("sources")))
        for locator in map(_mapping, _items(source.get("locators")))
        if _text(locator.get("locator_id"))
    }


def validate_industry_learning_block(block: Any, *, source_packets: list[Any]) -> dict[str, Any]:
    """Validate a cross-sectional industry block before any outcome access."""
    findings: list[str] = []
    item = _closed(block, _BLOCK_KEYS, "industry_block", findings)
    if item.get("schema_version") != BLOCK_SCHEMA_VERSION:
        _add(findings, "industry_block.schema_version_invalid")
    for field in ("block_id", "industry_id"):
        _require_text(item, field, "industry_block", findings)
    cutoff = _instant(item.get("cutoff_at"), "industry_block.cutoff_at", findings)
    if item.get("outcome_access_status") != "SEALED":
        _add(findings, "industry_block.outcome_access_must_remain_sealed")
    if item.get("object_class") != "INDUSTRY_LEARNING_BLOCK":
        _add(findings, "industry_block.object_class_invalid")
    if item.get("claim_class") != "CONDITIONAL_INDUSTRY_CONTEXT_AND_SAMPLING":
        _add(findings, "industry_block.claim_class_invalid")
    if item.get("allowed_outputs") != BLOCK_OUTPUTS:
        _add(findings, "industry_block.allowed_outputs_invalid")

    window = _closed(item.get("observation_window"), _WINDOW_KEYS, "industry_block.observation_window", findings)
    for field in ("accounting_period", "settlement_source_type", "boundary_note"):
        _require_text(window, field, "industry_block.observation_window", findings)
    start = _day(window.get("event_start"), "industry_block.observation_window.event_start", findings)
    end = _day(window.get("event_end"), "industry_block.observation_window.event_end", findings)
    if start and end and end < start:
        _add(findings, "industry_block.observation_window_dates_invalid")
    if cutoff and start and start < cutoff.date():
        _add(findings, "industry_block.event_window_must_not_start_before_cutoff")
    if window.get("settlement_source_type") != "OFFICIAL_ANNUAL_REPORT_STATIC_PDF":
        _add(findings, "industry_block.settlement_source_type_invalid")

    epoch = _closed(item.get("industry_epoch"), _EPOCH_KEYS, "industry_block.industry_epoch", findings)
    for field in _EPOCH_KEYS - {"evidence_refs"}:
        _require_text(epoch, field, "industry_block.industry_epoch", findings)
    epoch_refs = _unique_texts(epoch.get("evidence_refs"), "industry_block.industry_epoch.evidence_refs", findings)
    if epoch.get("causal_credit") != "NONE":
        _add(findings, "industry_block.industry_epoch_cannot_receive_company_causal_credit")

    arenas = [
        _closed(raw, _ARENA_KEYS, f"industry_block.mechanism_arenas[{index}]", findings)
        for index, raw in enumerate(_items(item.get("mechanism_arenas")))
    ]
    if not arenas:
        _add(findings, "industry_block.mechanism_arenas_required")
    arena_ids: set[str] = set()
    for index, arena in enumerate(arenas):
        for field in _ARENA_KEYS:
            _require_text(arena, field, f"industry_block.mechanism_arenas[{index}]", findings)
        arena_id = str(arena.get("arena_id") or "")
        if arena_id in arena_ids:
            _add(findings, f"industry_block.mechanism_arenas[{index}].arena_id_duplicate")
        arena_ids.add(arena_id)

    packets = _source_packet_by_receipt(source_packets, findings)
    members = [
        _closed(raw, _MEMBER_KEYS, f"industry_block.members[{index}]", findings)
        for index, raw in enumerate(_items(item.get("members")))
    ]
    if not members:
        _add(findings, "industry_block.requires_at_least_one_company")
    if [member.get("rank") for member in members] != list(range(1, len(members) + 1)):
        _add(findings, "industry_block.member_ranks_must_be_contiguous")
    company_ids: set[str] = set()
    issuer_ids: set[str] = set()
    all_locator_ids: set[str] = set()
    for index, member in enumerate(members):
        path = f"industry_block.members[{index}]"
        for field in (
            "company_id",
            "issuer_id",
            "company_name",
            "packet_state",
            "archetype",
            "responsibility_boundary",
            "cutoff_state",
            "decision_heterogeneity",
        ):
            _require_text(member, field, path, findings)
        company_id = str(member.get("company_id") or "")
        issuer_id = str(member.get("issuer_id") or "")
        if company_id in company_ids or issuer_id in issuer_ids:
            _add(findings, path + ".company_or_issuer_duplicate")
        company_ids.add(company_id)
        issuer_ids.add(issuer_id)
        if member.get("packet_state") != ELIGIBLE_PACKET_STATE:
            _add(findings, path + ".packet_state_invalid")
        member_arenas = _unique_texts(member.get("arena_ids"), path + ".arena_ids", findings)
        if any(arena_id not in arena_ids for arena_id in member_arenas):
            _add(findings, path + ".arena_id_unknown")
        source_ref = _closed(member.get("source_packet_ref"), _SOURCE_REF_KEYS, path + ".source_packet_ref", findings)
        packet = packets.get((str(source_ref.get("receipt_id") or ""), source_ref.get("receipt_version")))
        if not packet:
            _add(findings, path + ".source_packet_ref_unknown")
            continue
        if packet.get("company_id") != company_id or packet.get("issuer_id") != issuer_id:
            _add(findings, path + ".source_packet_identity_mismatch")
        if packet.get("cutoff_at") != item.get("cutoff_at"):
            _add(findings, path + ".source_packet_cutoff_mismatch")
        locators = _locator_ids(packet)
        all_locator_ids.update(locators)
        if any(ref not in locators for ref in _unique_texts(member.get("evidence_refs"), path + ".evidence_refs", findings)):
            _add(findings, path + ".evidence_ref_outside_source_packet")

    if any(ref not in all_locator_ids for ref in epoch_refs):
        _add(findings, "industry_block.industry_epoch.evidence_ref_outside_source_packets")

    policy = _closed(item.get("selection_policy"), _SELECTION_POLICY_KEYS, "industry_block.selection_policy", findings)
    for field in ("policy_id", "rule", "eligible_packet_state", "tie_breaker"):
        _require_text(policy, field, "industry_block.selection_policy", findings)
    if policy.get("rule") != SELECTION_POLICY:
        _add(findings, "industry_block.selection_policy.rule_invalid")
    if policy.get("eligible_packet_state") != ELIGIBLE_PACKET_STATE:
        _add(findings, "industry_block.selection_policy.packet_state_invalid")
    if policy.get("tie_breaker") != "LOWEST_ISSUER_ID":
        _add(findings, "industry_block.selection_policy.tie_breaker_invalid")
    prohibited = _unique_texts(policy.get("prohibited_inputs"), "industry_block.selection_policy.prohibited_inputs", findings)
    required_prohibited = {
        "POST_CUTOFF_OUTCOME",
        "OUTCOME_SOURCE_CONVENIENCE",
        "PRICE_OR_RETURN",
        "EXPECTED_METHOD_WINNER",
    }
    if set(prohibited) != required_prohibited:
        _add(findings, "industry_block.selection_policy.prohibited_inputs_invalid")

    _unique_texts(item.get("strongest_common_rivals"), "industry_block.strongest_common_rivals", findings)
    _unique_texts(item.get("unresolved_questions"), "industry_block.unresolved_questions", findings)
    roles = _closed(item.get("roles"), _ROLE_KEYS, "industry_block.roles", findings)
    role_values = [_require_text(roles, field, "industry_block.roles", findings) for field in sorted(_ROLE_KEYS)]
    if len(set(value for value in role_values if value)) != len(_ROLE_KEYS):
        _add(findings, "industry_block.roles_must_be_independent")
    for path in _forbidden_paths(item):
        _add(findings, "industry_block.forbidden_field:" + path)
    return {
        "valid": not findings,
        "findings": findings,
        "industry_learning_block": deepcopy(item) if not findings else None,
    }


def derive_selection(block: Any, *, source_packets: list[Any]) -> dict[str, Any]:
    """Select one company without using outcomes or source convenience."""
    validation = validate_industry_learning_block(block, source_packets=source_packets)
    if not validation["valid"]:
        return {"valid": False, "findings": validation["findings"], "selection": None}
    item = _mapping(block)
    members = sorted(
        (
            member for member in map(_mapping, _items(item.get("members")))
            if member.get("packet_state") == ELIGIBLE_PACKET_STATE
        ),
        key=lambda member: (str(member.get("company_id")), str(member.get("issuer_id"))),
    )
    selected = members[0]
    selection = {
        "schema_version": SELECTION_SCHEMA_VERSION,
        "selection_id": f"EJSEL:{item['block_id']}",
        "block_id": item["block_id"],
        "policy_id": _mapping(item["selection_policy"])["policy_id"],
        "eligible_company_ids": [member["company_id"] for member in members],
        "selected_rank": selected["rank"],
        "company_id": selected["company_id"],
        "issuer_id": selected["issuer_id"],
        "cutoff_at": item["cutoff_at"],
        "source_packet_ref": deepcopy(selected["source_packet_ref"]),
        "selection_used_outcome": False,
        "selection_used_source_convenience": False,
        "outcome_access_status": "SEALED",
        "object_class": "ENTERPRISE_JUDGMENT_INDUSTRY_SELECTION",
        "claim_class": "MECHANICAL_PRE_OUTCOME_SELECTION",
        "allowed_outputs": list(SELECTION_OUTPUTS),
    }
    return {"valid": True, "findings": [], "selection": selection}


def validate_selection_receipt(selection: Any, *, block: Any, source_packets: list[Any]) -> dict[str, Any]:
    findings: list[str] = []
    item = _closed(selection, _SELECTION_KEYS, "industry_selection", findings)
    if item.get("schema_version") != SELECTION_SCHEMA_VERSION:
        _add(findings, "industry_selection.schema_version_invalid")
    derived = derive_selection(block, source_packets=source_packets)
    for finding in derived["findings"]:
        _add(findings, "industry_selection.block:" + finding)
    if derived["selection"] is not None and item != derived["selection"]:
        _add(findings, "industry_selection.must_equal_mechanical_derivation")
    return {
        "valid": not findings,
        "findings": findings,
        "selection": deepcopy(item) if not findings else None,
    }


def _selected_packet(
    selection: dict[str, Any], source_packets: list[Any], findings: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    packet_ref = _mapping(selection.get("source_packet_ref"))
    matching = [
        _mapping(raw)
        for raw in source_packets
        if _mapping(raw).get("packet_id") == packet_ref.get("receipt_id")
        and _mapping(raw).get("packet_version") == packet_ref.get("receipt_version")
    ]
    if len(matching) != 1:
        _add(findings, "multidimensional_preoutcome.selected_source_packet_must_be_unique")
        return {}, {}
    packet = matching[0]
    validation = source_packet.validate_source_packet_receipt(packet)
    for finding in validation["findings"]:
        _add(findings, "multidimensional_preoutcome.selected_source_packet:" + finding)
    return packet, validation


def _validate_episode_source_binding(
    episode: dict[str, Any], *, packet: dict[str, Any], packet_validation: dict[str, Any],
    path: str, findings: list[str],
) -> None:
    packet_id = str(packet.get("packet_id") or "")
    locator_map = _mapping(packet_validation.get("locator_map"))
    field_map = _mapping(packet_validation.get("field_map"))
    for index, claim in enumerate(map(_mapping, _items(episode.get("claims")))):
        claim_path = f"{path}.claims[{index}]"
        if any(ref != packet_id for ref in _items(claim.get("evidence_refs"))):
            _add(findings, claim_path + ".evidence_refs_must_name_selected_packet")
        claim_id = str(claim.get("claim_id") or "")
        for locator_id in _items(claim.get("evidence_locator_refs")):
            locator = _mapping(locator_map.get(str(locator_id)))
            field = _mapping(field_map.get(str(locator.get("field_id") or "")))
            if not locator:
                _add(findings, claim_path + f".evidence_locator_not_in_selected_packet:{locator_id}")
            elif claim_id not in _items(field.get("material_claim_ids")):
                _add(findings, claim_path + f".locator_not_materially_bound_to_claim:{locator_id}")


def validate_preoutcome_package(
    package: Any, *, block: Any, source_packets: list[Any], selection: Any,
) -> dict[str, Any]:
    """Validate the complete Round 8 freeze before outcome content is opened."""
    findings: list[str] = []
    item = _closed(package, _PREOUTCOME_KEYS, "multidimensional_preoutcome", findings)
    if item.get("schema_version") != PREOUTCOME_SCHEMA_VERSION:
        _add(findings, "multidimensional_preoutcome.schema_version_invalid")
    _require_text(item, "package_id", "multidimensional_preoutcome", findings)
    frozen_at = _instant(item.get("frozen_at"), "multidimensional_preoutcome.frozen_at", findings)
    if item.get("freeze_state") != "PRE_OUTCOME_FROZEN":
        _add(findings, "multidimensional_preoutcome.freeze_state_invalid")
    if item.get("object_class") != "MULTIDIMENSIONAL_PREOUTCOME_PACKAGE":
        _add(findings, "multidimensional_preoutcome.object_class_invalid")
    if item.get("claim_class") != "SAME_EVIDENCE_BASELINE_ENHANCED_RESEARCH":
        _add(findings, "multidimensional_preoutcome.claim_class_invalid")
    if item.get("allowed_outputs") != PREOUTCOME_OUTPUTS:
        _add(findings, "multidimensional_preoutcome.allowed_outputs_invalid")
    if item.get("rights") != PREOUTCOME_RIGHTS:
        _add(findings, "multidimensional_preoutcome.rights_invalid")

    block_result = validate_industry_learning_block(block, source_packets=source_packets)
    for finding in block_result["findings"]:
        _add(findings, "multidimensional_preoutcome.industry_block:" + finding)
    selection_result = validate_selection_receipt(selection, block=block, source_packets=source_packets)
    for finding in selection_result["findings"]:
        _add(findings, "multidimensional_preoutcome.selection:" + finding)
    block_item = _mapping(block)
    selection_item = _mapping(selection)

    block_ref = _closed(
        item.get("industry_block_ref"), _BLOCK_REF_KEYS,
        "multidimensional_preoutcome.industry_block_ref", findings,
    )
    if block_ref != {
        "block_id": block_item.get("block_id"),
        "schema_version": block_item.get("schema_version"),
    }:
        _add(findings, "multidimensional_preoutcome.industry_block_ref_must_match")
    selection_ref = _closed(
        item.get("selection_ref"), _SELECTION_REF_KEYS,
        "multidimensional_preoutcome.selection_ref", findings,
    )
    if selection_ref != {
        "selection_id": selection_item.get("selection_id"),
        "schema_version": selection_item.get("schema_version"),
    }:
        _add(findings, "multidimensional_preoutcome.selection_ref_must_match")
    source_ref = _closed(
        item.get("source_packet_ref"), _SOURCE_REF_KEYS,
        "multidimensional_preoutcome.source_packet_ref", findings,
    )
    if source_ref != _mapping(selection_item.get("source_packet_ref")):
        _add(findings, "multidimensional_preoutcome.source_packet_ref_must_match_selection")

    packet, packet_validation = _selected_packet(selection_item, source_packets, findings)
    locator_ids = list(_mapping(packet_validation.get("locator_map")))
    contract = _mapping(item.get("decision_contract"))
    contract_result = decision_contract.validate_training_decision_contract(contract)
    for finding in contract_result["findings"]:
        _add(findings, "multidimensional_preoutcome.decision_contract:" + finding)
    expected_packet_refs = [{
        "receipt_id": packet.get("packet_id"),
        "receipt_version": packet.get("packet_version"),
    }]
    if _mapping(contract.get("evidence_budget")).get("source_packet_refs") != expected_packet_refs:
        _add(findings, "multidimensional_preoutcome.decision_contract_must_use_selected_packet")

    baseline = _mapping(item.get("baseline_episode"))
    enhanced = _mapping(item.get("enhanced_episode"))
    for role, episode in (("baseline", baseline), ("enhanced", enhanced)):
        episode_result = episode_module.validate_episode_manifest(
            episode, decision_contract=contract, evidence_locator_ids=locator_ids,
        )
        for finding in episode_result["findings"]:
            _add(findings, f"multidimensional_preoutcome.{role}_episode:" + finding)
        _validate_episode_source_binding(
            episode, packet=packet, packet_validation=packet_validation,
            path=f"multidimensional_preoutcome.{role}_episode", findings=findings,
        )

    pairing = _mapping(item.get("decision_utility_pairing"))
    pairing_result = decision_utility.validate_decision_utility_pairing(
        pairing,
        contract=contract,
        baseline_episode=baseline,
        enhanced_episode=enhanced,
    )
    for finding in pairing_result["findings"]:
        _add(findings, "multidimensional_preoutcome.decision_utility_pairing:" + finding)
    pairing_frozen_at = _instant(
        pairing.get("frozen_at"),
        "multidimensional_preoutcome.decision_utility_pairing.frozen_at",
        findings,
    )
    if frozen_at is not None and pairing_frozen_at != frozen_at:
        _add(findings, "multidimensional_preoutcome.pairing_freeze_must_match_package")

    measurement = _mapping(item.get("outcome_measurement_contract"))
    measurement_result = mechanism_training.validate_outcome_measurement_contract(measurement)
    for finding in measurement_result["findings"]:
        _add(findings, "multidimensional_preoutcome.measurement_contract:" + finding)
    if measurement.get("package_ref") != item.get("package_id"):
        _add(findings, "multidimensional_preoutcome.measurement_contract_package_ref_must_match")
    measurement_frozen_at = _instant(
        measurement.get("contract_frozen_at"),
        "multidimensional_preoutcome.measurement_contract.contract_frozen_at",
        findings,
    )
    if frozen_at is not None and measurement_frozen_at != frozen_at:
        _add(findings, "multidimensional_preoutcome.measurement_freeze_must_match_package")
    cell_ids = {
        str(_mapping(cell).get("cell_id"))
        for cell in _items(measurement.get("atomic_cells"))
        if _text(_mapping(cell).get("cell_id"))
    }
    for role, episode in (("baseline", baseline), ("enhanced", enhanced)):
        episode_cells = {
            str(_mapping(cell).get("outcome_cell_id"))
            for cell in _items(episode.get("outcome_cells"))
            if _text(_mapping(cell).get("outcome_cell_id"))
        }
        if episode_cells != cell_ids:
            _add(findings, f"multidimensional_preoutcome.{role}_episode_must_cover_measurement_cells")
        for component in map(_mapping, _items(episode.get("component_refs"))):
            if component.get("component_type") == "OUTCOME_MEASUREMENT_CONTRACT" and component.get("component_id") != measurement.get("contract_set_id"):
                _add(findings, f"multidimensional_preoutcome.{role}_measurement_component_must_match")

    selected_identity = {
        "company_id": selection_item.get("company_id"),
        "issuer_id": selection_item.get("issuer_id"),
        "cutoff_at": selection_item.get("cutoff_at"),
    }
    for path, component in (
        ("decision_contract", contract),
        ("baseline_episode", baseline),
        ("enhanced_episode", enhanced),
    ):
        if any(component.get(key) != value for key, value in selected_identity.items()):
            _add(findings, f"multidimensional_preoutcome.{path}_identity_must_match_selection")
    if measurement.get("company_id") != selected_identity["company_id"] or measurement.get("cutoff_at") != selected_identity["cutoff_at"]:
        _add(findings, "multidimensional_preoutcome.measurement_identity_must_match_selection")

    roles = _closed(item.get("roles"), _ROLE_KEYS, "multidimensional_preoutcome.roles", findings)
    if roles != _mapping(block_item.get("roles")) or roles != _mapping(contract.get("roles")):
        _add(findings, "multidimensional_preoutcome.roles_must_match_block_and_contract")
    contamination = _closed(
        item.get("contamination_boundary"), _CONTAMINATION_KEYS,
        "multidimensional_preoutcome.contamination_boundary", findings,
    )
    if contamination != {
        "historical_replay_status": "MODEL_MEMORY_MITIGATED",
        "model_memory_mitigation": "PROCEDURAL_OUTCOME_SEPARATION_ONLY",
        "score_authority": "NONE",
        "allowed_use": "DEVELOPMENT_MULTIDIMENSIONAL_UTILITY_ONLY",
    }:
        _add(findings, "multidimensional_preoutcome.contamination_boundary_invalid")
    for path in _forbidden_paths(item, path="multidimensional_preoutcome"):
        _add(findings, "multidimensional_preoutcome.forbidden_field:" + path)
    return {
        "valid": not findings,
        "findings": findings,
        "package": deepcopy(item) if not findings else None,
    }
