#!/usr/bin/env python3
"""Versioned, non-parameterized valuation-archetype cards.

Cards specify reusable valuation implementation knowledge: required operating
capabilities, admissible calculation methods, evidence roles, overlap owners,
and incomplete-scope treatment.  They do not carry company facts, monetary
amounts, rates, multiples, or valuation-route instructions.
"""

from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


CARD_SCHEMA_VERSION = "valuation-archetype.v1"
VALIDATION_SCHEMA_VERSION = "valuation-archetype-validation.v1"
RESOLUTION_SCHEMA_VERSION = "valuation-archetype-resolution.v1"

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY_DIR = PROJECT_ROOT / "knowledge" / "valuation_archetypes"

CALCULATION_METHODS = {
    "DIRECT_RANGE",
    "SUM_OF_INPUT_RANGES",
    "PRODUCT_OF_INPUT_RANGES",
    "UNAVAILABLE",
}
EXCLUSION_DESTINATIONS = {
    "OTHER_REPLACEMENT_COMPONENT",
    "BALANCE_SHEET_WORKING_CAPITAL",
    "EPV_MAINTENANCE_NEED",
}
REQUIRED_PROHIBITED_CONTENT = {
    "CURRENCY_AMOUNT",
    "PERCENTAGE_OR_MULTIPLE",
    "COMPANY_FACT",
    "DEFAULT_HAIRCUT_OR_COMPLETION_RATE",
    "AUTOMATIC_MODEL_ROUTE",
}

TOP_LEVEL_FIELDS = {
    "schema_version",
    "card_id",
    "archetype_id",
    "version",
    "status",
    "valuation_family",
    "applicability",
    "components",
    "evidence_role_guidance",
    "completion_rule",
    "limits",
    "training_boundary",
}
APPLICABILITY_FIELDS = {
    "required_operating_characteristics",
    "required_company_conditions",
    "non_applicability_conditions",
}
COMPONENT_FIELDS = {
    "component_type",
    "presence_requirement",
    "requirement",
    "allowed_calculation_methods",
    "required_evidence_roles",
    "allowed_exclusion_destinations",
    "double_count_owner",
    "unknown_semantics",
    "recognition_semantics",
    "completion_semantics",
}
COMPLETION_RULE_FIELDS = {
    "company_level_range",
    "incomplete_scope",
    "epv_cross_check",
    "joint_protection",
}
LIMIT_FIELDS = {
    "company_fact_policy",
    "valuation_parameter_policy",
    "prohibited_content",
}
TRAINING_BOUNDARY_FIELDS = {"may_update", "may_not_supply"}
EVIDENCE_ROLE_GUIDANCE_FIELDS = {
    "role",
    "likely_official_sources",
    "likely_acquisition_modules",
    "query_hints",
    "bounded_stopping_rule",
}
FORBIDDEN_PARAMETER_FIELD_TOKENS = {
    "amount",
    "currency",
    "percentage",
    "percent",
    "multiple",
    "ratio",
    "haircut",
    "rate",
    "price",
    "value",
    "share",
    "company_id",
    "company_name",
}
PARAMETER_TEXT_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:%|x|倍))", re.IGNORECASE)
CURRENCY_AMOUNT_TEXT_RE = re.compile(
    r"(?:RMB|CNY|HKD|USD|人民币|港元|美元)\s*[\d,.]+"
    r"|\d+(?:\.\d+)?\s*(?:million|billion|mn|bn|百万元|千万元|万元|亿元)",
    re.IGNORECASE,
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _registry_path(path: str | Path | None = None) -> Path:
    return Path(path).expanduser().resolve() if path else DEFAULT_REGISTRY_DIR


def _reject_unknown_fields(
    value: dict[str, Any], allowed: set[str], prefix: str, findings: list[str]
) -> None:
    findings.extend(
        f"{prefix}:unknown_field:{field}" for field in sorted(set(value) - allowed)
    )


def _required_text(value: Any, *, prefix: str, findings: list[str]) -> None:
    if not _text(value):
        findings.append(prefix + ":missing_or_invalid_text")


def _text_list(value: Any, *, prefix: str, findings: list[str]) -> list[str]:
    items = _items(value)
    if not items or any(not _text(item) for item in items):
        findings.append(prefix + ":missing_or_invalid_list")
        return []
    normalized = [str(item).strip() for item in items]
    if len(normalized) != len(set(normalized)):
        findings.append(prefix + ":duplicate")
    return normalized


def _numeric_or_parameter_findings(value: Any, *, path: str = "$") -> list[str]:
    """Reject numeric content and encoded percentage or multiple values.

    A card's version is part of its identity and therefore remains a string;
    numbers are never permitted as JSON values.  This keeps cards from
    becoming a covert store for company-specific assumptions.
    """
    findings: list[str] = []
    if isinstance(value, bool):
        return [path + ":non_string_scalar_forbidden"]
    if isinstance(value, (int, float)):
        return [path + ":numeric_value_forbidden"]
    if isinstance(value, str):
        if PARAMETER_TEXT_RE.search(value):
            findings.append(path + ":percentage_or_multiple_text_forbidden")
        if CURRENCY_AMOUNT_TEXT_RE.search(value):
            findings.append(path + ":currency_amount_text_forbidden")
        return findings
    if isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_numeric_or_parameter_findings(item, path=f"{path}[{index}]"))
        return findings
    if isinstance(value, dict):
        for key, item in value.items():
            tokenized = {piece for piece in str(key).lower().split("_") if piece}
            if tokenized.intersection(FORBIDDEN_PARAMETER_FIELD_TOKENS):
                findings.append(path + f":forbidden_parameter_field:{key}")
            findings.extend(_numeric_or_parameter_findings(item, path=f"{path}.{key}"))
    return findings


def _validate_applicability(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    _reject_unknown_fields(item, APPLICABILITY_FIELDS, "applicability", findings)
    for field in sorted(APPLICABILITY_FIELDS):
        _text_list(item.get(field), prefix="applicability." + field, findings=findings)


def _validate_component(value: Any, *, index: int, seen: set[str], findings: list[str]) -> None:
    item = _mapping(value)
    prefix = f"components[{index}]"
    _reject_unknown_fields(item, COMPONENT_FIELDS, prefix, findings)
    component_type = str(item.get("component_type") or "")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", component_type):
        findings.append(prefix + ":component_type_invalid")
    elif component_type in seen:
        findings.append(prefix + ":component_type_duplicate")
    else:
        seen.add(component_type)
    _required_text(item.get("requirement"), prefix=prefix + ".requirement", findings=findings)
    if item.get("presence_requirement") not in {"REQUIRED", "OPTIONAL"}:
        findings.append(prefix + ":presence_requirement_invalid")
    methods = _text_list(
        item.get("allowed_calculation_methods"),
        prefix=prefix + ".allowed_calculation_methods",
        findings=findings,
    )
    if methods and not set(methods).issubset(CALCULATION_METHODS):
        findings.append(prefix + ":allowed_calculation_methods_invalid")
    if methods and "UNAVAILABLE" not in methods:
        findings.append(prefix + ":unavailable_method_required_for_unknown_boundary")
    _text_list(
        item.get("required_evidence_roles"),
        prefix=prefix + ".required_evidence_roles",
        findings=findings,
    )
    raw_allowed_exclusions = item.get("allowed_exclusion_destinations")
    allowed_exclusions = _items(raw_allowed_exclusions)
    if not isinstance(raw_allowed_exclusions, list):
        findings.append(prefix + ":allowed_exclusion_destinations_invalid")
    elif any(not _text(destination) for destination in allowed_exclusions):
        findings.append(prefix + ":allowed_exclusion_destinations_invalid")
    elif len(allowed_exclusions) != len(set(allowed_exclusions)):
        findings.append(prefix + ":allowed_exclusion_destinations_duplicate")
    elif not set(allowed_exclusions).issubset(EXCLUSION_DESTINATIONS):
        findings.append(prefix + ":allowed_exclusion_destinations_invalid")
    if not re.fullmatch(r"[A-Z][A-Z0-9_]*", str(item.get("double_count_owner") or "")):
        findings.append(prefix + ":double_count_owner_invalid")
    for field in ("unknown_semantics", "recognition_semantics", "completion_semantics"):
        _required_text(item.get(field), prefix=prefix + "." + field, findings=findings)


def _validate_completion_rule(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    _reject_unknown_fields(item, COMPLETION_RULE_FIELDS, "completion_rule", findings)
    for field in sorted(COMPLETION_RULE_FIELDS):
        _required_text(item.get(field), prefix="completion_rule." + field, findings=findings)


def _validate_evidence_role_guidance(
    value: Any, *, required_roles: set[str], findings: list[str]
) -> None:
    items = _items(value)
    if not items:
        findings.append("evidence_role_guidance:missing")
        return
    seen: set[str] = set()
    for index, raw_item in enumerate(items):
        item = _mapping(raw_item)
        prefix = f"evidence_role_guidance[{index}]"
        _reject_unknown_fields(item, EVIDENCE_ROLE_GUIDANCE_FIELDS, prefix, findings)
        role = str(item.get("role") or "")
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", role):
            findings.append(prefix + ":role_invalid")
        elif role in seen:
            findings.append(prefix + ":role_duplicate")
        else:
            seen.add(role)
        for field in (
            "likely_official_sources",
            "likely_acquisition_modules",
            "query_hints",
        ):
            _text_list(item.get(field), prefix=prefix + "." + field, findings=findings)
        _required_text(
            item.get("bounded_stopping_rule"),
            prefix=prefix + ".bounded_stopping_rule",
            findings=findings,
        )
    missing = sorted(required_roles - seen)
    extra = sorted(seen - required_roles)
    findings.extend("evidence_role_guidance:missing_role:" + role for role in missing)
    findings.extend("evidence_role_guidance:unknown_role:" + role for role in extra)


def _validate_limits(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    _reject_unknown_fields(item, LIMIT_FIELDS, "limits", findings)
    if item.get("company_fact_policy") != "NO_COMPANY_FACTS":
        findings.append("limits:company_fact_policy_invalid")
    if item.get("valuation_parameter_policy") != "NO_DEFAULT_NUMERIC_PARAMETERS":
        findings.append("limits:valuation_parameter_policy_invalid")
    prohibited = _text_list(
        item.get("prohibited_content"), prefix="limits.prohibited_content", findings=findings
    )
    if set(prohibited) != REQUIRED_PROHIBITED_CONTENT:
        findings.append("limits:prohibited_content_incomplete_or_invalid")


def _validate_training_boundary(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    _reject_unknown_fields(item, TRAINING_BOUNDARY_FIELDS, "training_boundary", findings)
    may_update = _text_list(item.get("may_update"), prefix="training_boundary.may_update", findings=findings)
    may_not_supply = _text_list(item.get("may_not_supply"), prefix="training_boundary.may_not_supply", findings=findings)
    if "VALUATION_PARAMETER" not in may_not_supply:
        findings.append("training_boundary:valuation_parameter_must_be_prohibited")
    if "COMPANY_FACT" not in may_not_supply:
        findings.append("training_boundary:company_fact_must_be_prohibited")
    if "AUTOMATIC_MODEL_ROUTE" not in may_not_supply:
        findings.append("training_boundary:automatic_model_route_must_be_prohibited")
    if not may_update:
        findings.append("training_boundary:may_update_missing")


def validate_valuation_archetype(payload: Any) -> dict[str, Any]:
    """Validate a valuation-archetype card without relying on its prose.

    The returned object is deliberately usable by both production loading and
    training admission.  It treats an invalid card as unavailable rather than
    supplying a partial template to a company valuation.
    """
    card = _mapping(payload)
    findings: list[str] = []
    if not card:
        findings.append("card:not_object")
    _reject_unknown_fields(card, TOP_LEVEL_FIELDS, "card", findings)
    if card.get("schema_version") != CARD_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    archetype_id = str(card.get("archetype_id") or "")
    version = str(card.get("version") or "")
    if not re.fullmatch(r"[a-z0-9_:-]+", archetype_id):
        findings.append("archetype_id_invalid")
    if not re.fullmatch(r"v[0-9]+", version):
        findings.append("version_invalid")
    if card.get("card_id") != f"VALUATION_ARCHETYPE:{archetype_id}:{version}":
        findings.append("card_id_identity_mismatch")
    if card.get("status") not in {"ACTIVE", "RETIRED"}:
        findings.append("status_invalid")
    if card.get("valuation_family") != "GOING_CONCERN_REPLACEMENT":
        findings.append("valuation_family_invalid")
    _validate_applicability(card.get("applicability"), findings)
    components = _items(card.get("components"))
    if not components:
        findings.append("components:missing")
    seen: set[str] = set()
    required_roles: set[str] = set()
    for index, component in enumerate(components):
        _validate_component(component, index=index, seen=seen, findings=findings)
        if isinstance(component, dict):
            required_roles.update(
                str(role) for role in component.get("required_evidence_roles") or []
                if _text(role)
            )
    if "evidence_role_guidance" in card:
        _validate_evidence_role_guidance(
            card.get("evidence_role_guidance"),
            required_roles=required_roles,
            findings=findings,
        )
    _validate_completion_rule(card.get("completion_rule"), findings)
    _validate_limits(card.get("limits"), findings)
    _validate_training_boundary(card.get("training_boundary"), findings)
    findings.extend(_numeric_or_parameter_findings(card))
    findings = list(dict.fromkeys(findings))
    state = "VALID" if not findings else "INVALID"
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": state,
        "status": "PASS" if state == "VALID" else "FAIL",
        "findings": findings,
    }


def _registry_cards(registry_dir: str | Path | None = None) -> list[tuple[Path, dict[str, Any]]]:
    root = _registry_path(registry_dir)
    if not root.is_dir():
        return []
    return [(path, _read_json(path)) for path in sorted(root.glob("*.json"))]


def validate_valuation_archetype_registry(
    registry_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate all cards and ensure each archetype/version identity is unique."""
    cards = _registry_cards(registry_dir)
    findings: list[str] = []
    summaries: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    if not cards:
        findings.append("registry:cards_missing")
    for path, card in cards:
        validation = validate_valuation_archetype(card)
        identity = (str(card.get("archetype_id") or ""), str(card.get("version") or ""))
        if identity in identities:
            findings.append("registry:duplicate_identity:" + ":".join(identity))
        identities.add(identity)
        if validation["state"] != "VALID":
            findings.extend(path.name + ":" + item for item in validation["findings"])
        summaries.append({
            "source": path.name,
            "card_id": card.get("card_id"),
            "archetype_id": card.get("archetype_id"),
            "version": card.get("version"),
            "status": card.get("status"),
            "validation_state": validation["state"],
        })
    findings = list(dict.fromkeys(findings))
    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "VALID" if not findings else "INVALID",
        "status": "PASS" if not findings else "FAIL",
        "findings": findings,
        "cards": summaries,
    }


def load_valuation_archetype(
    archetype_id: str,
    version: str | None = None,
    *,
    registry_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Load one exact valid card; implicit version selection is never a drift path."""
    target_id = str(archetype_id or "").strip()
    target_version = str(version or "").strip()
    matches: list[tuple[Path, dict[str, Any]]] = []
    for path, card in _registry_cards(registry_dir):
        if card.get("archetype_id") != target_id:
            continue
        if target_version and card.get("version") != target_version:
            continue
        matches.append((path, card))
    if not matches:
        suffix = ":" + target_version if target_version else ""
        raise ValueError("valuation_archetype_not_found:" + target_id + suffix)
    if not target_version and len(matches) != 1:
        raise ValueError("valuation_archetype_version_required:" + target_id)
    if len(matches) != 1:
        raise ValueError("valuation_archetype_duplicate_identity:" + target_id + ":" + target_version)
    path, card = matches[0]
    validation = validate_valuation_archetype(card)
    if validation["state"] != "VALID":
        raise ValueError(
            "valuation_archetype_invalid:" + path.name + ":" + ",".join(validation["findings"])
        )
    return deepcopy(card)


def list_valuation_archetypes(
    registry_dir: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List registry identities without exposing a company-specific projection."""
    result: list[dict[str, Any]] = []
    for path, card in _registry_cards(registry_dir):
        validation = validate_valuation_archetype(card)
        result.append({
            "source": path.name,
            "card_id": card.get("card_id"),
            "archetype_id": card.get("archetype_id"),
            "version": card.get("version"),
            "status": card.get("status"),
            "validation_state": validation["state"],
        })
    return result


def resolve_valuation_archetype(
    archetype_id: str,
    version: str | None = None,
    *,
    registry_dir: str | Path | None = None,
    allow_retired: bool = False,
) -> dict[str, Any]:
    """Resolve a reusable template, not a company valuation or route decision."""
    card = load_valuation_archetype(archetype_id, version, registry_dir=registry_dir)
    if card["status"] != "ACTIVE" and not allow_retired:
        raise ValueError("valuation_archetype_not_active:" + card["card_id"])
    return {
        "schema_version": RESOLUTION_SCHEMA_VERSION,
        "state": "RESOLVED",
        "card_id": card["card_id"],
        "archetype_id": card["archetype_id"],
        "version": card["version"],
        "status": card["status"],
        "valuation_family": card["valuation_family"],
        "required_component_specs": deepcopy(card["components"]),
        "evidence_role_guidance": deepcopy(card.get("evidence_role_guidance") or []),
        "applicability": deepcopy(card["applicability"]),
        "completion_rule": deepcopy(card["completion_rule"]),
        "limits": deepcopy(card["limits"]),
        "training_boundary": deepcopy(card["training_boundary"]),
    }


def _main() -> int:
    parser = argparse.ArgumentParser(description="Validate and resolve valuation-archetype cards.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--registry-dir")
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--registry-dir")
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("archetype_id")
    resolve_parser.add_argument("--version")
    resolve_parser.add_argument("--registry-dir")
    resolve_parser.add_argument("--allow-retired", action="store_true")
    args = parser.parse_args()
    if args.command == "validate":
        result: Any = validate_valuation_archetype_registry(args.registry_dir)
    elif args.command == "list":
        result = list_valuation_archetypes(args.registry_dir)
    else:
        result = resolve_valuation_archetype(
            args.archetype_id,
            args.version,
            registry_dir=args.registry_dir,
            allow_retired=args.allow_retired,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI path
    raise SystemExit(_main())
