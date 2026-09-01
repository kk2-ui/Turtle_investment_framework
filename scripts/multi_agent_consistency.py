#!/usr/bin/env python3
"""Consistency control plane for multi-agent enterprise judgment.

This module deliberately separates proposals from the canonical ledger.  Agents
submit narrow, source-bound proposals; one canonical owner accepts, rejects, or
localizes each proposal.  The functions here do not vote, infer economics, add
evidence, or generate an Episode.  They return a freeze record beside the
existing staged-ledger object, so the ledger schema remains the single source
of economic judgment and the deterministic staged compiler remains the only
downstream projection path.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable

from scripts.staged_judgment_ledger import (
    LEDGER_SCHEMA,
    validate_staged_judgment_ledger,
)

PROTOCOL_SCHEMA = "multi-agent-consistency-protocol.v1"
PROPOSAL_SCHEMA = "multi-agent-judgment-proposal.v1"
FREEZE_SCHEMA = "multi-agent-canonical-freeze.v1"
MANIFEST_SCHEMA = "multi-agent-consistency-manifest.v1"
THREE_LAYER_ACCEPTANCE_SCHEMA = "three-layer-method-acceptance.v1"

ROLES = {
    "evidence_owner",
    "industry_analyst",
    "company_economist",
    "challenger",
    "thesis_synthesizer",
    "canonical_owner",
}
MODES = {"PRODUCTION_SINGLE_OWNER", "FOUR_ARM_INDEPENDENT"}
SOURCE_TIME_ROLES = {"PRE_CUTOFF", "RESULT_KNOWN", "TRAINING_MEMORY"}
DISPOSITIONS = {"ACCEPT", "REJECT", "CONDITIONAL", "UNRESOLVED"}
_PROPOSAL_KEYS = {
    "schema_version", "proposal_id", "role", "target", "proposed_value",
    "evidence_ids", "reason",
}
_DECISION_KEYS = {
    "proposal_id", "disposition", "final_value", "rationale",
    "economic_impact", "prohibited_assumption", "remediation",
    "acceptance_criterion",
}
_FORBIDDEN_KEYS = {
    "price", "market_price", "share_price", "entry_price", "buyband",
    "buy_band", "expected_return", "realized_return", "outcome", "settlement",
    "investment_action", "portfolio_action", "action", "decision", "valuation_result", "return", "position",
}
_IMMUTABLE_COMPONENT_FIELDS = {"component_id", "economic_scope", "evidence_ids"}
_IMMUTABLE_TARGETS = {
    ("components", field) for field in _IMMUTABLE_COMPONENT_FIELDS
} | {
    ("claims", field) for field in {"claim_id", "surface", "evidence_ids"}
} | {
    ("evidence_refs", field) for field in {"evidence_id", "source_ref"}
}
_ECONOMIC_COMPONENT_FIELDS = {
    "treatment", "normal_earnings_use", "owner_cash_use", "financing_pressure_effect",
    "permanent_loss_use", "valuation_use", "valuation_route_bindings", "reason",
    "promotion_test", "invalidation_test",
}
_EVIDENCE_FIELDS = {"source_ref", "locator", "scope", "used_for"}
_CLAIM_FIELDS = {"statement", "direction", "mechanism", "treatment", "evidence_ids", "strongest_rival", "reversal_observations", "unknown"}


def _obj(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
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


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in _FORBIDDEN_KEYS:
                found.append(child_path)
            found.extend(_forbidden_paths(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden_paths(child, f"{path}[{index}]"))
    return found


def _target_parts(target: Any) -> list[str]:
    return [part for part in str(target or "").split(".") if part]


def _target_allowed_for_role(role: str, parts: list[str]) -> bool:
    if not parts:
        return False
    if role == "canonical_owner":
        return True
    root = parts[0]
    if role == "evidence_owner":
        return root == "evidence_refs" and len(parts) >= 3 and parts[2] in _EVIDENCE_FIELDS
    if role == "industry_analyst":
        return (root == "industry_future" and len(parts) >= 2) or (
            root == "claims" and len(parts) >= 3 and parts[1] == "INDUSTRY_FUTURE" and parts[2] in _CLAIM_FIELDS
        )
    if role == "company_economist":
        return (root == "components" and len(parts) >= 3 and parts[2] in _ECONOMIC_COMPONENT_FIELDS) or (
            root == "claims" and len(parts) >= 3 and parts[1] in {
                "SURVIVAL", "BUSINESS_POSITION", "ADAPTATION", "NORMALIZATION",
                "PERMANENT_LOSS", "VALUE_ROUTE",
            } and parts[2] in _CLAIM_FIELDS
        )
    if role == "challenger":
        return len(parts) >= 3 and root == "claims" and parts[2] in {
            "strongest_rival", "reversal_observations", "unknown",
        }
    if role == "thesis_synthesizer":
        return (root == "industry_future" and len(parts) >= 2) or (
            root == "claims" and len(parts) >= 3 and parts[1] in {
                "INDUSTRY_FUTURE", "INVESTMENT_TREATMENT",
            } and parts[2] in _CLAIM_FIELDS
        )
    return False


def _validate_target(target: Any) -> list[str]:
    parts = _target_parts(target)
    if not parts:
        return ["target_missing"]
    if any(part.lower() in _FORBIDDEN_KEYS for part in parts):
        return ["target_price_or_action_forbidden"]
    roots = {"evidence_refs", "components", "claims", "industry_future", "reversal_observations"}
    if parts[0] not in roots:
        return ["target_root_invalid"]
    if parts[0] in {"components", "claims"} and len(parts) < 3:
        return ["target_requires_identity_and_field"]
    if parts[0] == "evidence_refs" and len(parts) < 3:
        return ["target_requires_evidence_id_and_field"]
    if parts[0] == "industry_future" and len(parts) < 2:
        return ["target_requires_field"]
    return []


def validate_proposal(
    proposal: Any,
    *,
    contract: Any,
    source_index: Any,
    mode: str = "PRODUCTION_SINGLE_OWNER",
) -> dict[str, Any]:
    """Validate one narrow proposal without changing a ledger."""
    value = _obj(proposal)
    c = _obj(contract)
    index = source_index if isinstance(source_index, dict) else {}
    findings: list[str] = []
    if value.get("schema_version") != PROPOSAL_SCHEMA:
        findings.append("schema_version_invalid")
    if set(value) != _PROPOSAL_KEYS:
        findings.append("fields_invalid")
    role = str(value.get("role") or "")
    if role not in ROLES:
        findings.append("role_invalid")
    if mode not in MODES:
        findings.append("mode_invalid")
    target = value.get("target")
    findings.extend(_validate_target(target))
    if role in ROLES and not _target_allowed_for_role(role, _target_parts(target)):
        findings.append("role_target_not_permitted")
    for field in ("proposal_id", "reason"):
        if not _text(value.get(field)):
            findings.append(field + "_missing")
    if "proposed_value" not in value:
        findings.append("proposed_value_missing")
    if not isinstance(value.get("evidence_ids"), list) or not value.get("evidence_ids"):
        findings.append("evidence_ids_missing")
    evidence_ids = [str(item) for item in _list(value.get("evidence_ids"))]
    if len(evidence_ids) != len(set(evidence_ids)):
        findings.append("evidence_ids_duplicate")
    allowed_sources = {
        str(item.get("source_ref")): item
        for item in _list(c.get("allowed_sources"))
        if isinstance(item, dict)
    }
    cutoff = _instant(c.get("cutoff_at"))
    if cutoff is None:
        findings.append("contract_cutoff_invalid")
    for evidence_id in evidence_ids:
        entry = _obj(index.get(evidence_id))
        if not entry:
            findings.append("evidence_not_in_source_index:" + evidence_id)
            continue
        source_ref = str(entry.get("source_ref") or "")
        for field in ("source_ref", "available_at", "time_role"):
            if not _text(entry.get(field)):
                findings.append("evidence_index_incomplete:" + evidence_id + ":" + field)
        if entry.get("time_role") not in SOURCE_TIME_ROLES:
            findings.append("evidence_time_role_invalid:" + evidence_id)
        if source_ref not in allowed_sources:
            findings.append("evidence_source_not_allowed:" + evidence_id)
        if entry.get("time_role") == "TRAINING_MEMORY":
            findings.append("training_memory_cannot_support_proposal:" + evidence_id)
        available = _instant(entry.get("available_at"))
        if available is None:
            findings.append("evidence_index_time_invalid:" + evidence_id)
        if cutoff and available and available > cutoff:
            findings.append("evidence_after_cutoff:" + evidence_id)
    findings.extend("price_firewall:" + path for path in _forbidden_paths(value))
    return {
        "schema_version": "multi-agent-judgment-proposal-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def _resolve_target(container: dict[str, Any], target: str) -> tuple[Any, str] | None:
    """Resolve a dotted proposal target to a mutable parent and key."""
    parts = _target_parts(target)
    if len(parts) < 2:
        return None
    root = parts[0]
    if root == "industry_future":
        return container.setdefault("industry_future", {}), parts[1]
    if root == "reversal_observations":
        return container, root
    if root in {"components", "claims", "evidence_refs"} and len(parts) >= 3:
        identity, field = parts[1], ".".join(parts[2:])
        rows = container.get(root)
        if root == "evidence_refs":
            key = "evidence_id"
        else:
            key = "component_id" if root == "components" else "surface"
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict) and str(row.get(key)) == identity:
                    return row, field
        return None
    return None


def _set_target(container: dict[str, Any], target: str, value: Any) -> bool:
    resolved = _resolve_target(container, target)
    if resolved is None:
        return False
    parent, key = resolved
    if key == "reversal_observations":
        container[key] = deepcopy(value)
    elif isinstance(parent, dict):
        parts = key.split(".")
        cursor: Any = parent
        for part in parts[:-1]:
            if not isinstance(cursor, dict):
                return False
            cursor = cursor.setdefault(part, {})
        if not isinstance(cursor, dict):
            return False
        cursor[parts[-1]] = deepcopy(value)
    else:
        return False
    return True


def _decision_fields(decision: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    if set(decision) != _DECISION_KEYS:
        findings.append("decision_fields_invalid")
    if not _text(decision.get("proposal_id")):
        findings.append("decision_proposal_id_missing")
    if decision.get("disposition") not in DISPOSITIONS:
        findings.append("decision_disposition_invalid")
    for field in ("rationale", "economic_impact", "prohibited_assumption", "remediation", "acceptance_criterion"):
        if not _text(decision.get(field)):
            findings.append("decision_" + field + "_missing")
    if decision.get("disposition") in {"ACCEPT", "CONDITIONAL", "UNRESOLVED"} and "final_value" not in decision:
        findings.append("decision_final_value_missing")
    return findings


def freeze_canonical_ledger(
    ledger: Any,
    proposals: Iterable[Any],
    decisions: Iterable[Any],
    *,
    owner_id: str,
    contract: Any,
    source_index: Any,
    mode: str = "PRODUCTION_SINGLE_OWNER",
) -> dict[str, Any]:
    """Apply one owner's explicit decisions and validate the frozen ledger.

    Rejected proposals are retained only in the sidecar freeze record.  The
    canonical ledger contains accepted/conditional values and no collaboration
    metadata, preserving the existing ledger schema and one-way compiler.
    """
    value = deepcopy(_obj(ledger))
    proposal_list = [deepcopy(_obj(item)) for item in proposals]
    decision_list = [deepcopy(_obj(item)) for item in decisions]
    findings: list[str] = []
    if not _text(owner_id):
        findings.append("owner_id_missing")
    if mode not in MODES:
        findings.append("mode_invalid")
    if mode == "PRODUCTION_SINGLE_OWNER" and not _text(owner_id):
        findings.append("canonical_owner_required")
    proposal_by_id: dict[str, dict[str, Any]] = {}
    for proposal in proposal_list:
        validation = validate_proposal(proposal, contract=contract, source_index=source_index, mode=mode)
        findings.extend("proposal:" + item for item in validation["findings"])
        proposal_id = str(proposal.get("proposal_id") or "")
        if proposal_id in proposal_by_id:
            findings.append("proposal_id_duplicate:" + proposal_id)
        proposal_by_id[proposal_id] = proposal
    decided: set[str] = set()
    applied: list[str] = []
    rejected: list[str] = []
    for decision in decision_list:
        findings.extend(_decision_fields(decision))
        proposal_id = str(decision.get("proposal_id") or "")
        if proposal_id in decided:
            findings.append("decision_duplicate:" + proposal_id)
        decided.add(proposal_id)
        proposal = proposal_by_id.get(proposal_id)
        if proposal is None:
            findings.append("decision_proposal_unknown:" + proposal_id)
            continue
        disposition = decision.get("disposition")
        if disposition == "REJECT":
            rejected.append(proposal_id)
            continue
        target_parts = _target_parts(str(proposal.get("target")))
        if len(target_parts) >= 3 and (target_parts[0], target_parts[2]) in _IMMUTABLE_TARGETS:
            findings.append("immutable_target_forbidden:" + str(proposal.get("target")))
            continue
        if not _set_target(value, str(proposal.get("target")), decision.get("final_value")):
            findings.append("target_not_resolvable:" + str(proposal.get("target")))
            continue
        applied.append(proposal_id)
    missing = sorted(set(proposal_by_id) - decided)
    if missing:
        findings.extend("proposal_undecided:" + item for item in missing)
    value["status"] = "FROZEN"
    # The staged validator is the authority for ledger shape, local unknowns,
    # route/component permissions, and evidence bindings.
    ledger_validation = validate_staged_judgment_ledger(value, source_index, contract)
    if ledger_validation.get("state") != "VALID":
        findings.extend("ledger:" + str(item.get("code") or item) for item in ledger_validation.get("findings", []))
    freeze_record = {
        "schema_version": FREEZE_SCHEMA,
        "protocol_schema": PROTOCOL_SCHEMA,
        "owner_id": owner_id,
        "mode": mode,
        "ledger_id": value.get("ledger_id"),
        "company_id": value.get("company_id"),
        "cutoff_at": value.get("cutoff_at"),
        "proposal_ids": [str(item.get("proposal_id") or "") for item in proposal_list],
        "decisions": decision_list,
        "applied_proposal_ids": applied,
        "rejected_proposal_ids": rejected,
        "diagnostics": [],
        "state": "FROZEN" if not findings else "DIAGNOSTIC_ONLY",
    }
    freeze_record["diagnostics"] = [
        {"code": "CANONICAL_FREEZE_INVALID", "root_cause": "MODEL", "economic_impact": item,
         "missing_fact": item, "prohibited_assumption": "不得以投票或方便编译替代证据裁决",
         "remediation": "由 canonical owner 修正提案裁决或局部化 UNKNOWN",
         "acceptance_criterion": "所有提案有明确处置且 ledger validator 通过"}
        for item in list(dict.fromkeys(findings))
    ]
    return {
        "schema_version": FREEZE_SCHEMA,
        "state": freeze_record["state"],
        "ledger": value if freeze_record["state"] == "FROZEN" else None,
        "freeze_record": freeze_record,
        "findings": list(dict.fromkeys(findings)),
    }


def validate_consistency_manifest(manifest: Any) -> dict[str, Any]:
    """Validate shared identity/protocol fields for production or four-arm use."""
    value = _obj(manifest)
    findings: list[str] = []
    required = {"schema_version", "manifest_id", "mode", "company_id", "cutoff_at", "sample_identity", "common_source_refs", "component_vocabulary", "compiler", "budget", "outcome_access"}
    if value.get("schema_version") != MANIFEST_SCHEMA:
        findings.append("schema_version_invalid")
    if value.get("mode") not in MODES:
        findings.append("mode_invalid")
    if value.get("mode") == "FOUR_ARM_INDEPENDENT":
        required.add("arms")
        if "arms" not in value:
            findings.append("four_arm_registry_missing")
        else:
            arms = value.get("arms")
            if not isinstance(arms, list) or len(arms) != 4:
                findings.append("four_arm_registry_invalid")
            else:
                arm_ids = []
                for index, arm in enumerate(arms):
                    item = _obj(arm); arm_id = item.get("arm_id")
                    if set(item) != {"arm_id", "j0_task", "j1_task", "j2_task"}:
                        findings.append(f"four_arm[{index}]_fields_invalid")
                    if not _text(arm_id):
                        findings.append(f"four_arm[{index}]_id_missing")
                    arm_ids.append(str(arm_id))
                    for task in ("j0_task", "j1_task", "j2_task"):
                        if not _text(item.get(task)):
                            findings.append(f"four_arm[{index}]_{task}_missing")
                if len(arm_ids) != len(set(arm_ids)):
                    findings.append("four_arm_ids_duplicate")
    if set(value) != required:
        findings.append("fields_invalid")
    if not _text(value.get("manifest_id")) or not _text(value.get("company_id")):
        findings.append("identity_missing")
    if _instant(value.get("cutoff_at")) is None:
        findings.append("cutoff_at_invalid")
    refs = value.get("common_source_refs")
    if not isinstance(refs, list) or not refs:
        findings.append("common_sources_missing")
    elif any(not _text(item) for item in refs) or len(refs) != len(set(refs)):
        findings.append("common_sources_invalid")
    vocabulary = value.get("component_vocabulary")
    if not isinstance(vocabulary, list) or not vocabulary:
        findings.append("component_vocabulary_missing")
    elif any(not _text(item) for item in vocabulary) or len(vocabulary) != len(set(vocabulary)):
        findings.append("component_vocabulary_invalid")
    if not isinstance(value.get("compiler"), dict) or not _text(_obj(value.get("compiler")).get("name")):
        findings.append("compiler_missing")
    if not isinstance(value.get("budget"), dict) or not _text(_obj(value.get("budget")).get("policy")):
        findings.append("budget_missing")
    if value.get("outcome_access") != "SEALED":
        findings.append("outcome_must_remain_sealed")
    return {
        "schema_version": "multi-agent-consistency-manifest-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def validate_freeze_record(record: Any, *, ledger: Any, contract: Any | None = None,
                           source_index: Any | None = None) -> dict[str, Any]:
    value = _obj(record)
    findings: list[str] = []
    expected = {"schema_version", "protocol_schema", "owner_id", "mode", "ledger_id", "company_id", "cutoff_at", "proposal_ids", "decisions", "applied_proposal_ids", "rejected_proposal_ids", "diagnostics", "state"}
    if set(value) != expected:
        findings.append("freeze_record_fields_invalid")
    if value.get("schema_version") != FREEZE_SCHEMA:
        findings.append("schema_version_invalid")
    if value.get("protocol_schema") != PROTOCOL_SCHEMA:
        findings.append("protocol_schema_invalid")
    if value.get("state") != "FROZEN":
        findings.append("freeze_state_invalid")
    if not _text(value.get("owner_id")):
        findings.append("owner_id_missing")
    if value.get("ledger_id") != _obj(ledger).get("ledger_id"):
        findings.append("ledger_id_mismatch")
    if value.get("company_id") != _obj(ledger).get("company_id"):
        findings.append("company_id_mismatch")
    if not _text(_obj(ledger).get("company_name")):
        findings.append("ledger_company_name_missing")
    if _obj(ledger).get("status") != "FROZEN":
        findings.append("ledger_not_frozen")
    if value.get("cutoff_at") != _obj(ledger).get("cutoff_at") or _instant(value.get("cutoff_at")) is None:
        findings.append("cutoff_at_mismatch_or_invalid")
    if value.get("mode") not in MODES:
        findings.append("mode_invalid")
    if isinstance(contract, dict):
        for field in ("company_id", "cutoff_at"):
            if value.get(field) != contract.get(field):
                findings.append("contract_" + field + "_mismatch")
        if _obj(ledger).get("company_name") != contract.get("company_name"):
            findings.append("contract_company_name_mismatch")
    if not isinstance(value.get("proposal_ids"), list) or not value.get("proposal_ids"):
        findings.append("proposal_ids_missing")
    elif len(value["proposal_ids"]) != len(set(value["proposal_ids"])):
        findings.append("proposal_ids_duplicate")
    if not isinstance(value.get("decisions"), list) or not value.get("decisions"):
        findings.append("decisions_missing")
    else:
        decision_ids = []
        for decision in value["decisions"]:
            findings.extend("decision:" + item for item in _decision_fields(_obj(decision)))
            decision_ids.append(str(_obj(decision).get("proposal_id") or ""))
        if len(decision_ids) != len(set(decision_ids)):
            findings.append("decision_proposal_ids_duplicate")
        proposal_ids = [str(item) for item in _list(value.get("proposal_ids"))]
        if set(decision_ids) != set(proposal_ids):
            findings.append("decisions_do_not_cover_proposals")
        dispositions = {str(_obj(d).get("proposal_id")): _obj(d).get("disposition") for d in value["decisions"]}
        if set(str(x) for x in _list(value.get("rejected_proposal_ids"))) != {pid for pid, disp in dispositions.items() if disp == "REJECT"}:
            findings.append("rejected_partition_disposition_mismatch")
        if set(str(x) for x in _list(value.get("applied_proposal_ids"))) != {pid for pid, disp in dispositions.items() if disp != "REJECT"}:
            findings.append("applied_partition_disposition_mismatch")
    applied = value.get("applied_proposal_ids"); rejected = value.get("rejected_proposal_ids")
    if not isinstance(applied, list) or not isinstance(rejected, list):
        findings.append("freeze_partitions_missing")
    else:
        proposal_ids = {str(item) for item in _list(value.get("proposal_ids"))}
        if len(applied) != len(set(applied)) or len(rejected) != len(set(rejected)):
            findings.append("freeze_partition_duplicate")
        if set(applied) & set(rejected):
            findings.append("freeze_partition_overlap")
        if set(applied) | set(rejected) != proposal_ids:
            findings.append("freeze_partition_incomplete")
    if not isinstance(value.get("diagnostics"), list):
        findings.append("diagnostics_missing")
    ledger_validation = validate_staged_judgment_ledger(ledger, source_index, contract)
    if ledger_validation.get("state") != "VALID":
        findings.append("ledger_invalid")
    return {
        "schema_version": "multi-agent-canonical-freeze-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


def validate_three_layer_acceptance(acceptance: Any) -> dict[str, Any]:
    """Gate method release on independent judgment, review, outcome and holdout.

    Layer 1 proves a legal/reproducible ledger, layer 2 an anonymous review,
    and layer 3 a settled outcome.  A second unseen company or time holdout is
    required before ``LIMITED_METHOD_RELEASE``; compilation and sealed outcome
    access are deliberately insufficient.
    """
    value = _obj(acceptance)
    required = {"schema_version", "layer1", "layer2", "layer3", "holdout", "outcome_settled", "release_state"}
    findings: list[str] = []
    if set(value) != required:
        findings.append("acceptance_fields_invalid")
    if value.get("schema_version") != THREE_LAYER_ACCEPTANCE_SCHEMA:
        findings.append("acceptance_schema_invalid")

    def status(name: str) -> str:
        item = value.get(name)
        if isinstance(item, str):
            return item.upper()
        if isinstance(item, dict):
            return str(item.get("state") or item.get("status") or "").upper()
        return ""

    pass_states = {"PASS", "PASSED", "REVIEWABLE", "COMPLETED"}
    allowed_states = pass_states | {"PENDING", "SEALED", "NOT_STARTED", "FAIL", "FAILED"}

    for layer in ("layer1", "layer2", "layer3", "holdout"):
        if status(layer) not in allowed_states:
            findings.append(layer + "_state_invalid")
    if not isinstance(value.get("outcome_settled"), bool):
        findings.append("outcome_settled_invalid")
    elif not value["outcome_settled"] and value.get("release_state") == "LIMITED_METHOD_RELEASE":
        findings.append("outcome_not_settled")
    release = value.get("release_state")
    if release not in {"NO_RELEASE", "LIMITED_METHOD_RELEASE"}:
        findings.append("release_state_invalid")
    elif release == "LIMITED_METHOD_RELEASE" and not (
        all(status(layer) in pass_states for layer in ("layer1", "layer2", "layer3", "holdout"))
        and value.get("outcome_settled") is True
    ):
        findings.append("limited_release_gate_not_met")
    return {
        "schema_version": "three-layer-method-acceptance-validation.v1",
        "state": "REVIEWABLE" if not findings else "INVALID",
        "findings": list(dict.fromkeys(findings)),
    }


__all__ = [
    "PROTOCOL_SCHEMA", "PROPOSAL_SCHEMA", "FREEZE_SCHEMA", "MANIFEST_SCHEMA",
    "validate_proposal", "freeze_canonical_ledger", "validate_consistency_manifest",
    "validate_freeze_record", "validate_three_layer_acceptance", "THREE_LAYER_ACCEPTANCE_SCHEMA",
]


def _load_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    proposal = sub.add_parser("validate-proposal")
    proposal.add_argument("proposal"); proposal.add_argument("contract"); proposal.add_argument("source_index")
    proposal.add_argument("--mode", choices=sorted(MODES), default="PRODUCTION_SINGLE_OWNER")
    manifest = sub.add_parser("validate-manifest"); manifest.add_argument("manifest")
    acceptance = sub.add_parser("validate-acceptance"); acceptance.add_argument("acceptance")
    freeze = sub.add_parser("freeze")
    freeze.add_argument("ledger"); freeze.add_argument("proposals"); freeze.add_argument("decisions")
    freeze.add_argument("contract"); freeze.add_argument("source_index"); freeze.add_argument("--owner-id", required=True)
    freeze.add_argument("--mode", choices=sorted(MODES), default="PRODUCTION_SINGLE_OWNER")
    freeze.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "validate-proposal":
        result = validate_proposal(_load_json(args.proposal), contract=_load_json(args.contract), source_index=_load_json(args.source_index), mode=args.mode)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["state"] == "REVIEWABLE" else 1
    if args.command == "validate-manifest":
        result = validate_consistency_manifest(_load_json(args.manifest))
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["state"] == "REVIEWABLE" else 1
    if args.command == "validate-acceptance":
        result = validate_three_layer_acceptance(_load_json(args.acceptance))
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["state"] == "REVIEWABLE" else 1
    result = freeze_canonical_ledger(
        _load_json(args.ledger), _load_json(args.proposals), _load_json(args.decisions),
        owner_id=args.owner_id, contract=_load_json(args.contract), source_index=_load_json(args.source_index), mode=args.mode,
    )
    output = Path(args.output_dir)
    _dump_json(output / "canonical_freeze_result.json", result)
    if result.get("ledger") is not None:
        _dump_json(output / "canonical_ledger.json", result["ledger"])
    print(json.dumps({"state": result["state"], "output_dir": str(output.resolve())}, ensure_ascii=False))
    return 0 if result["state"] == "FROZEN" else 1


if __name__ == "__main__":
    raise SystemExit(main())
