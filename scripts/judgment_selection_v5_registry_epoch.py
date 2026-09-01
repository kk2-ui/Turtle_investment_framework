#!/usr/bin/env python3
"""Pure checks for a registry-aware V5 comparative-admission binding.

The binding is deliberately not another selection bundle.  It carries only
the pre-outcome carrier-panel provenance that legacy V5 cannot represent;
the paired ``judgment-selection-admission-v5.v1`` bundle remains the one
economic contract that is reviewed, sealed and later resolved.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from scripts import judgment_selection_v5 as v5
except ModuleNotFoundError:  # pragma: no cover - direct script import
    import judgment_selection_v5 as v5


SCHEMA_VERSION = "judgment-selection-v5-registry-binding.v1"
ADMISSION_EPOCH_ID = "JUDGMENT_SELECTION_ADMISSION_V5_REGISTRY_V1"
NOT_ADMITTED = v5.NOT_ADMITTED
SELECTION_ADMITTED = v5.SELECTION_ADMITTED

_BINDING_KEYS = {
    "schema_version", "admission_epoch_id", "binding_id", "selection_freeze_id",
    "registry_id", "preseal_registry_event_sequence", "target_carrier_id",
    "ordered_panel_carrier_ids", "registry_selection_arena_bridge", "registry_panel_disposition_ledger",
    "registry_preoutcome_review",
}
_DISPOSITION_KEYS = {"carrier_id", "panel_disposition", "reason_code", "source_ids"}
_ARENA_BRIDGE_KEYS = {
    "registry_competitive_arena_id", "selection_competitive_arena_id", "relation", "source_ids",
}
_REVIEW_KEYS = {
    "review_id", "pre_outcome_designer_id", "reviewer_id", "reviewed_at", "verdict",
    "reviewer_outcome_body_access", "reviewer_outcome_metadata_access", "reviewed_binding",
}
_REVIEWED_BINDING_KEYS = _BINDING_KEYS - {"registry_preoutcome_review"}


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _expected_reviewed_binding(binding: dict[str, Any]) -> dict[str, Any]:
    return {field: binding.get(field) for field in sorted(_REVIEWED_BINDING_KEYS)}


def validate_registry_aware_v5_binding(bundle: Any, binding: Any) -> dict[str, Any]:
    """Validate an offline, outcome-free registry binding plus its V5 root.

    Durable receipt/source/roster resolution is intentionally deferred to the
    registry control plane.  This function has no database dependency and
    therefore cannot grant a seal by itself.
    """
    base = v5.validate_v5_candidate(bundle)
    findings = [f"v5:{item}" for item in base.get("findings", [])]
    candidate = _obj(bundle)
    value = _obj(binding)
    if not value:
        findings.append("binding_not_object")
        return {"valid": False, "admission_status": NOT_ADMITTED, "findings": findings}
    unexpected = sorted(set(value).difference(_BINDING_KEYS))
    if unexpected:
        findings.extend(f"binding_contains_unapproved_field:{field}" for field in unexpected)
    if value.get("schema_version") != SCHEMA_VERSION:
        findings.append("binding_schema_version_invalid")
    if value.get("admission_epoch_id") != ADMISSION_EPOCH_ID:
        findings.append("binding_admission_epoch_invalid")
    for field in ("binding_id", "selection_freeze_id", "registry_id", "target_carrier_id"):
        if not _text(value.get(field)):
            findings.append(f"binding_{field}_required")
    sequence = value.get("preseal_registry_event_sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        findings.append("binding_preseal_registry_event_sequence_invalid")
    if value.get("selection_freeze_id") != candidate.get("selection_freeze_id"):
        findings.append("binding_selection_freeze_id_mismatch")

    panel = _items(value.get("ordered_panel_carrier_ids"))
    if not 2 <= len(panel) <= 7 or any(not _text(item) for item in panel) or len(set(panel)) != len(panel):
        findings.append("binding_external_comparator_capacity_or_identity_invalid")
    if value.get("target_carrier_id") in panel:
        findings.append("binding_target_cannot_be_panel_carrier")

    arena_bridge = _obj(value.get("registry_selection_arena_bridge"))
    unexpected_bridge = sorted(set(arena_bridge).difference(_ARENA_BRIDGE_KEYS))
    if unexpected_bridge:
        findings.extend(f"binding_arena_bridge_contains_unapproved_field:{field}" for field in unexpected_bridge)
    for field in ("registry_competitive_arena_id", "selection_competitive_arena_id"):
        if not _text(arena_bridge.get(field)):
            findings.append(f"binding_arena_bridge_{field}_required")
    if arena_bridge.get("relation") != "MECHANISM_COMPATIBLE":
        findings.append("binding_arena_bridge_relation_invalid")
    bridge_sources = _items(arena_bridge.get("source_ids"))
    if not bridge_sources or any(not _text(item) for item in bridge_sources) or len(set(bridge_sources)) != len(bridge_sources):
        findings.append("binding_arena_bridge_source_ids_required")

    ledger = _items(value.get("registry_panel_disposition_ledger"))
    by_carrier: dict[str, dict[str, Any]] = {}
    for index, raw in enumerate(ledger):
        item = _obj(raw)
        unexpected_item = sorted(set(item).difference(_DISPOSITION_KEYS))
        if unexpected_item:
            findings.extend(f"binding_ledger[{index}]_contains_unapproved_field:{field}" for field in unexpected_item)
        carrier_id = item.get("carrier_id")
        if not _text(carrier_id) or carrier_id in by_carrier:
            findings.append("binding_ledger_carrier_identity_missing_or_duplicate")
            continue
        by_carrier[carrier_id] = item
        if item.get("panel_disposition") not in {
            "TARGET", "EXTERNAL_SHOCK_COMPARATOR", "EXCLUDED_PREOUTCOME",
        }:
            findings.append("binding_ledger_disposition_invalid")
        if not _text(item.get("reason_code")):
            findings.append("binding_ledger_reason_code_required")
        source_ids = _items(item.get("source_ids"))
        if not source_ids or any(not _text(source_id) for source_id in source_ids) or len(set(source_ids)) != len(source_ids):
            findings.append("binding_ledger_source_ids_required")
    target = value.get("target_carrier_id")
    if _text(target) and by_carrier.get(target, {}).get("panel_disposition") != "TARGET":
        findings.append("binding_target_not_ledger_target")
    for carrier_id in panel:
        if by_carrier.get(carrier_id, {}).get("panel_disposition") != "EXTERNAL_SHOCK_COMPARATOR":
            findings.append("binding_panel_not_ledger_external_comparator")
    if len(ledger) < len(panel) + 1:
        findings.append("binding_ledger_must_include_target_and_panel")

    review = _obj(value.get("registry_preoutcome_review"))
    unexpected_review = sorted(set(review).difference(_REVIEW_KEYS))
    if unexpected_review:
        findings.extend(f"binding_review_contains_unapproved_field:{field}" for field in unexpected_review)
    for field in ("review_id", "pre_outcome_designer_id", "reviewer_id"):
        if not _text(review.get(field)):
            findings.append(f"binding_review_{field}_required")
    if review.get("verdict") != "ACCEPTED":
        findings.append("binding_review_not_accepted")
    if review.get("reviewer_outcome_body_access") != "NONE" or review.get("reviewer_outcome_metadata_access") != "NONE":
        findings.append("binding_reviewer_preoutcome_outcome_access_not_sealed")
    reviewed_at = _instant(review.get("reviewed_at"))
    sealed_at = _instant(candidate.get("sealed_at"))
    if reviewed_at is None:
        findings.append("binding_reviewed_at_invalid")
    elif sealed_at is not None and reviewed_at > sealed_at:
        findings.append("binding_review_after_selection_freeze")
    root_review = _obj(candidate.get("independent_pre_outcome_review"))
    if review.get("pre_outcome_designer_id") != root_review.get("pre_outcome_designer_id"):
        findings.append("binding_review_designer_mismatch")
    if review.get("reviewer_id") == review.get("pre_outcome_designer_id"):
        findings.append("binding_reviewer_not_independent")
    if review.get("reviewed_binding") != _expected_reviewed_binding(value):
        findings.append("binding_review_binding_does_not_match")

    if not base.get("valid") or base.get("admission_status") != SELECTION_ADMITTED:
        findings.append("binding_requires_selection_admitted_v5_root")
    return {
        "valid": not findings,
        "admission_status": SELECTION_ADMITTED if not findings else NOT_ADMITTED,
        "findings": findings,
    }
