#!/usr/bin/env python3
"""Validate a local, pre-selection issuer exposure ledger for a test cohort.

The ledger is deliberately smaller than a selection register.  It records
only issuer identity, prior training exposure, and the intended panel side so
that a prospective test issuer cannot accidentally be reused from a Pack,
teacher, holdout, target, or campaign.  It neither reads the referenced
artifacts nor selects a company, acquires a source, reads an outcome, or
scores an issuer.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import re
from typing import Any, Mapping


SCHEMA_VERSION = "report-autonomy-cohort-exposure-ledger.v1"
VALIDATION_SCHEMA_VERSION = "report-autonomy-cohort-exposure-ledger-validation.v1"

EXPOSURE_ROLES = {"PACK", "TEACHER", "HOLDOUT", "TARGET", "CAMPAIGN"}
INTENDED_SIDES = {"PACK_BUILDING", "TEST_ACQUISITION", "EXCLUDED", "UNASSIGNED"}

_ROOT_FIELDS = {
    "schema_version",
    "ledger_id",
    "state",
    "scope",
    "issuer_identities",
    "exposures",
}
_SCOPE_FIELDS = {"industry_scope", "cutoff_at", "data_policy"}
_IDENTITY_FIELDS = {
    "issuer_id",
    "legal_entity_id",
    "issuer_name",
    "security_identifiers",
    "aliases",
    "intended_side",
    "intended_side_reason",
}
_EXPOSURE_FIELDS = {"exposure_id", "issuer_id", "role", "reference"}
_LOCAL_ONLY_DATA_POLICY = "LOCAL_ONLY_NO_OUTCOME_OR_PRICE"
_PRE_SELECTION_STATE = "PRE_SELECTION"
_NAME_TOKEN = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff]+")
_SECURITY_IDENTIFIER = re.compile(r"^[A-Z][A-Z0-9_-]*:[A-Z0-9]+$")
_UNCONFIRMED_LEGAL_ENTITY_PREFIX = "LEGAL_ENTITY_UNCONFIRMED:"


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _items(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) and value.strip() else ""


def _add(findings: list[str], finding: str) -> None:
    if finding not in findings:
        findings.append(finding)


def _closed(value: Any, allowed: set[str], path: str, findings: list[str]) -> dict[str, Any]:
    item = _mapping(value)
    if not isinstance(value, Mapping):
        _add(findings, path + ".must_be_object")
        return item
    extra = sorted(set(item) - allowed)
    missing = sorted(allowed - set(item))
    if extra:
        _add(findings, path + ".unexpected_fields:" + ",".join(extra))
    if missing:
        _add(findings, path + ".missing_fields:" + ",".join(missing))
    return item


def _normal_name(value: str) -> str:
    return _NAME_TOKEN.sub("", value).lower()


def _canonical_security_identifier(value: str) -> str:
    """Return the one supported local security key, or reject the spelling.

    The pre-selection ledger intentionally accepts only ``MARKET:SECURITY``
    identities.  It case-normalizes and permits harmless whitespace around
    the separator, so ``cn : 002508`` and ``CN:002508`` cannot name separate
    issuers.  Other market-specific spellings must be curated before they can
    enter the ledger; guessing a cross-market conversion here would weaken the
    very collision gate this object supplies.
    """
    candidate = re.sub(r"\s*:\s*", ":", value.strip()).upper()
    return candidate if _SECURITY_IDENTIFIER.fullmatch(candidate) else ""


def _local_reference(value: Any) -> bool:
    """Accept opaque local references without opening them.

    A local file path or identifier is enough for an exposure assertion.  A
    URL would expand the ledger beyond its local-only feasibility role, so it
    is not admissible here.
    """

    reference = _text(value)
    return bool(reference) and "://" not in reference


def _iso_instant(value: Any) -> bool:
    text = _text(value)
    if not text:
        return False
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _validate_scope(raw: Any, findings: list[str]) -> dict[str, Any]:
    scope = _closed(raw, _SCOPE_FIELDS, "scope", findings)
    if not _text(scope.get("industry_scope")):
        _add(findings, "scope.industry_scope_required")
    if not _iso_instant(scope.get("cutoff_at")):
        _add(findings, "scope.cutoff_at_invalid")
    if scope.get("data_policy") != _LOCAL_ONLY_DATA_POLICY:
        _add(findings, "scope.data_policy_must_be_local_only_no_outcome_or_price")
    return scope


def _validate_identities(raw: Any, findings: list[str]) -> dict[str, dict[str, Any]]:
    identities = _items(raw)
    if not identities:
        _add(findings, "issuer_identities_missing")
        return {}

    by_issuer_id: dict[str, dict[str, Any]] = {}
    legal_entity_owners: dict[str, str] = {}
    security_owners: dict[str, str] = {}
    name_owners: dict[str, str] = {}
    for index, raw_identity in enumerate(identities):
        path = f"issuer_identities[{index}]"
        identity = _closed(raw_identity, _IDENTITY_FIELDS, path, findings)
        issuer_id = _text(identity.get("issuer_id"))
        legal_entity_id = _text(identity.get("legal_entity_id"))
        issuer_name = _text(identity.get("issuer_name"))
        intended_side = identity.get("intended_side")
        reason = _text(identity.get("intended_side_reason"))
        if not issuer_id:
            _add(findings, path + ".issuer_id_required")
        elif issuer_id in by_issuer_id:
            _add(findings, path + ".issuer_id_duplicate:" + issuer_id)
        else:
            by_issuer_id[issuer_id] = identity
        if not legal_entity_id:
            _add(findings, path + ".legal_entity_id_required")
        elif legal_entity_id in legal_entity_owners:
            _add(
                findings,
                path + ".legal_entity_identity_collision:" + legal_entity_id,
            )
        else:
            legal_entity_owners[legal_entity_id] = issuer_id
        if not issuer_name:
            _add(findings, path + ".issuer_name_required")
        if intended_side not in INTENDED_SIDES:
            _add(findings, path + ".intended_side_invalid")
        if not reason:
            _add(findings, path + ".intended_side_reason_required")

        security_identifiers = [_text(item) for item in _items(identity.get("security_identifiers"))]
        if not security_identifiers or any(not item for item in security_identifiers):
            _add(findings, path + ".security_identifiers_required")
        for security_identifier in security_identifiers:
            canonical_security = _canonical_security_identifier(security_identifier)
            if not security_identifier:
                continue
            if not canonical_security:
                _add(
                    findings,
                    path + ".security_identifier_format_invalid:" + security_identifier,
                )
                continue
            if canonical_security in security_owners:
                _add(
                    findings,
                    path + ".security_identifier_identity_collision:" + canonical_security,
                )
            else:
                security_owners[canonical_security] = issuer_id

        aliases = [_text(item) for item in _items(identity.get("aliases"))]
        if any(not alias for alias in aliases) or len(aliases) != len(set(aliases)):
            _add(findings, path + ".aliases_invalid_or_duplicate")
        names = [issuer_name, *aliases]
        for name in names:
            normalized = _normal_name(name)
            if not normalized:
                _add(findings, path + ".issuer_name_or_alias_invalid")
                continue
            owner = name_owners.get(normalized)
            if owner is not None and owner != issuer_id:
                _add(findings, path + ".issuer_name_identity_collision:" + normalized)
            else:
                name_owners[normalized] = issuer_id
    return by_issuer_id


def _validate_exposures(
    raw: Any,
    *,
    identities: dict[str, dict[str, Any]],
    findings: list[str],
) -> dict[str, set[str]]:
    prior_roles: dict[str, set[str]] = {issuer_id: set() for issuer_id in identities}
    if not isinstance(raw, list):
        _add(findings, "exposures.must_be_array")
        return prior_roles
    seen_exposure_ids: set[str] = set()
    for index, raw_exposure in enumerate(raw):
        path = f"exposures[{index}]"
        exposure = _closed(raw_exposure, _EXPOSURE_FIELDS, path, findings)
        exposure_id = _text(exposure.get("exposure_id"))
        issuer_id = _text(exposure.get("issuer_id"))
        role = exposure.get("role")
        if not exposure_id:
            _add(findings, path + ".exposure_id_required")
        elif exposure_id in seen_exposure_ids:
            _add(findings, path + ".exposure_id_duplicate:" + exposure_id)
        else:
            seen_exposure_ids.add(exposure_id)
        if issuer_id not in identities:
            _add(findings, path + ".issuer_not_in_identity_ledger:" + issuer_id)
        if role not in EXPOSURE_ROLES:
            _add(findings, path + ".role_invalid")
        if not _local_reference(exposure.get("reference")):
            _add(findings, path + ".reference_must_be_local")
        if issuer_id in prior_roles and role in EXPOSURE_ROLES:
            prior_roles[issuer_id].add(str(role))
    return prior_roles


def validate_cohort_exposure_ledger(payload: Any) -> dict[str, Any]:
    """Validate issuer isolation before either panel is selected.

    The returned projection makes no selection.  In particular, a
    ``TEST_ACQUISITION`` identity is valid only when it has no prior Pack,
    teacher, holdout, target, or campaign exposure in this ledger.
    """

    findings: list[str] = []
    root = _closed(payload, _ROOT_FIELDS, "ledger", findings)
    if root.get("schema_version") != SCHEMA_VERSION:
        _add(findings, "ledger.schema_version_invalid")
    if not _text(root.get("ledger_id")):
        _add(findings, "ledger.ledger_id_required")
    if root.get("state") != _PRE_SELECTION_STATE:
        _add(findings, "ledger.state_must_be_pre_selection")
    scope = _validate_scope(root.get("scope"), findings)
    identities = _validate_identities(root.get("issuer_identities"), findings)
    prior_roles = _validate_exposures(
        root.get("exposures"), identities=identities, findings=findings,
    )
    for issuer_id, identity in identities.items():
        if identity.get("intended_side") == "TEST_ACQUISITION":
            if _text(identity.get("legal_entity_id")).startswith(
                _UNCONFIRMED_LEGAL_ENTITY_PREFIX
            ):
                _add(
                    findings,
                    "test_acquisition_legal_entity_unconfirmed:" + issuer_id,
                )
            for role in sorted(prior_roles.get(issuer_id, set())):
                _add(findings, "test_acquisition_prior_exposure:" + issuer_id + ":" + role)

    return {
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "state": "REVIEWABLE" if not findings else "INVALID",
        "ledger_id": _text(root.get("ledger_id")),
        "scope": scope,
        "issuer_count": len(identities),
        "intended_side_counts": {
            side: sum(
                1 for identity in identities.values()
                if identity.get("intended_side") == side
            )
            for side in sorted(INTENDED_SIDES)
        },
        "findings": findings,
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ledger", type=Path)
    args = parser.parse_args(argv)
    try:
        result = validate_cohort_exposure_ledger(_read_json(args.ledger))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        result = {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "state": "INVALID",
            "findings": [str(exc)],
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["state"] == "REVIEWABLE" else 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
