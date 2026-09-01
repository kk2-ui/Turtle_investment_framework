#!/usr/bin/env python3
"""Ex-ante Decision Contract for PIT company-state training.

The contract is deliberately smaller than a CJO.  It records the decision task
and its admissible evidence before a forecast is frozen, so historical replay
cannot quietly become a detached scoring exercise.  It contains no outcome,
price, valuation, or investment output.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "turtle-training-decision-contract.v1"
HISTORICAL_ALLOWED_OUTPUTS = ["CJO_TRAINING_MIRROR", "RESEARCH_AGENDA"]

_ROOT_KEYS = {
    "schema_version", "contract_id", "contract_version", "company_id", "issuer_id", "cutoff_at",
    "decision_purpose", "holding_horizon", "permanent_loss_constraints", "decision_flip_questions",
    "evidence_budget", "price_and_opportunity_cost_policy", "outcome_access", "roles", "object_class",
    "claim_class", "allowed_outputs",
}
_HORIZON_KEYS = {"minimum_years", "maximum_years"}
_CONSTRAINT_KEYS = {"constraint_id", "condition", "required_treatment"}
_QUESTION_KEYS = {"question_id", "statement", "decision_effect"}
_EVIDENCE_BUDGET_KEYS = {"evidence_budget_id", "source_packet_refs"}
_REFERENCE_KEYS = {"receipt_id", "receipt_version"}
_ROLE_KEYS = {"judgment_owner_id", "independent_challenger_id", "outcome_custodian_id"}


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _instant(value: Any, *, field: str, findings: list[str]) -> datetime | None:
    if not _text(value):
        findings.append(f"{field}_must_be_timezone_aware_iso8601")
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        findings.append(f"{field}_must_be_timezone_aware_iso8601")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        findings.append(f"{field}_must_be_timezone_aware_iso8601")
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str], *, required: set[str] | None = None) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, dict):
        findings.append(f"{path}_must_be_object")
        return item
    for field in sorted(set(item).difference(allowed)):
        findings.append(f"{path}_contains_unapproved_field:{field}")
    for field in sorted((allowed if required is None else required).difference(item)):
        findings.append(f"{path}_missing_required_field:{field}")
    return item


def _require_text(item: dict[str, Any], field: str, path: str, findings: list[str]) -> str:
    value = item.get(field)
    if not _text(value):
        findings.append(f"{path}.{field}_required")
        return ""
    return str(value).strip()


def _reference(value: Any, *, path: str, findings: list[str]) -> dict[str, Any] | None:
    item = _closed(value, _REFERENCE_KEYS, path, findings)
    receipt_id = _require_text(item, "receipt_id", path, findings)
    version = item.get("receipt_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append(f"{path}.receipt_version_must_be_positive_integer")
        return None
    return {"receipt_id": receipt_id, "receipt_version": version} if receipt_id else None


def validate_training_decision_contract(contract: Any) -> dict[str, Any]:
    """Validate a closed, outcome-free historical training decision task."""
    findings: list[str] = []
    item = _closed(contract, _ROOT_KEYS, "decision_contract", findings)
    if item.get("schema_version") != SCHEMA_VERSION:
        findings.append("decision_contract.schema_version_invalid")
    _require_text(item, "contract_id", "decision_contract", findings)
    version = item.get("contract_version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        findings.append("decision_contract.contract_version_must_be_positive_integer")
    _require_text(item, "company_id", "decision_contract", findings)
    _require_text(item, "issuer_id", "decision_contract", findings)
    _instant(item.get("cutoff_at"), field="decision_contract.cutoff_at", findings=findings)
    if item.get("decision_purpose") != "HISTORICAL_TRAINING":
        findings.append("decision_contract.only_historical_training_is_implemented")
    if item.get("price_and_opportunity_cost_policy") != "PROHIBITED_FOR_HISTORICAL_TRAINING":
        findings.append("decision_contract.price_and_opportunity_cost_must_remain_prohibited")
    if item.get("outcome_access") != "NONE":
        findings.append("decision_contract.outcome_access_must_be_none")
    if item.get("object_class") != "DECISION_CONTRACT" or item.get("claim_class") != "EX_ANTE_DECISION_SCOPE":
        findings.append("decision_contract.object_or_claim_class_invalid")
    if item.get("allowed_outputs") != HISTORICAL_ALLOWED_OUTPUTS:
        findings.append("decision_contract.allowed_outputs_must_exclude_investment_and_report")

    horizon = _closed(item.get("holding_horizon"), _HORIZON_KEYS, "decision_contract.holding_horizon", findings)
    minimum, maximum = horizon.get("minimum_years"), horizon.get("maximum_years")
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum < 1:
        findings.append("decision_contract.holding_horizon.minimum_years_invalid")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 1:
        findings.append("decision_contract.holding_horizon.maximum_years_invalid")
    elif isinstance(minimum, int) and not isinstance(minimum, bool) and minimum > maximum:
        findings.append("decision_contract.holding_horizon_order_invalid")

    constraints = _items(item.get("permanent_loss_constraints"))
    if not constraints:
        findings.append("decision_contract.permanent_loss_constraints_required")
    for index, raw in enumerate(constraints):
        entry = _closed(raw, _CONSTRAINT_KEYS, f"decision_contract.permanent_loss_constraints[{index}]", findings)
        for field in _CONSTRAINT_KEYS:
            _require_text(entry, field, f"decision_contract.permanent_loss_constraints[{index}]", findings)
    questions = _items(item.get("decision_flip_questions"))
    if not questions:
        findings.append("decision_contract.decision_flip_questions_required")
    for index, raw in enumerate(questions):
        entry = _closed(raw, _QUESTION_KEYS, f"decision_contract.decision_flip_questions[{index}]", findings)
        for field in _QUESTION_KEYS:
            _require_text(entry, field, f"decision_contract.decision_flip_questions[{index}]", findings)
    budget = _closed(item.get("evidence_budget"), _EVIDENCE_BUDGET_KEYS, "decision_contract.evidence_budget", findings)
    _require_text(budget, "evidence_budget_id", "decision_contract.evidence_budget", findings)
    refs = _items(budget.get("source_packet_refs"))
    if len(refs) != 1:
        findings.append("decision_contract.evidence_budget_requires_exactly_one_frozen_source_packet")
    for index, raw in enumerate(refs):
        _reference(raw, path=f"decision_contract.evidence_budget.source_packet_refs[{index}]", findings=findings)
    roles = _closed(item.get("roles"), _ROLE_KEYS, "decision_contract.roles", findings)
    role_values = [_require_text(roles, field, "decision_contract.roles", findings) for field in _ROLE_KEYS]
    if len(set(value for value in role_values if value)) != len(_ROLE_KEYS):
        findings.append("decision_contract.roles_must_be_independent")
    return {"valid": not findings, "findings": findings, "decision_contract": deepcopy(item) if not findings else None}


def validate_contract_for_forecast(contract: Any, forecast: Any) -> dict[str, Any]:
    """Bind a frozen training task to one company/cutoff/H1 source packet."""
    result = validate_training_decision_contract(contract)
    findings = list(result["findings"])
    value = _mapping(contract)
    item = _mapping(forecast)
    for field in ("company_id", "issuer_id", "cutoff_at"):
        if value.get(field) != item.get(field):
            findings.append(f"decision_contract.{field}_must_match_forecast")
    budget = _mapping(value.get("evidence_budget"))
    if _items(budget.get("source_packet_refs")) != _items(item.get("source_packet_refs")):
        findings.append("decision_contract.source_packet_must_match_forecast")
    return {"valid": not findings, "findings": findings, "decision_contract": deepcopy(value) if not findings else None}
