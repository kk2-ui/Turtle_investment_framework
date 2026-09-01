#!/usr/bin/env python3
"""Conservatively bind a legacy valuation ledger to the canonical route.

The canonical ``valuation_model.json`` is never overwritten while building a
candidate.  Only route identities are added mechanically.  Any role, cash-flow
scope, independence-group, discount-rate-kind, model-type, value-scope or
synthesis change is a semantic frontier and requires a bounded valuation
research pass.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_documents import _atomic_write_json
    from scripts.valuation_model_gate import (
        persist_valuation_model_ledger,
        validate_valuation_model_ledger,
        valuation_fingerprint,
    )
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json
    from valuation_model_gate import (
        persist_valuation_model_ledger,
        validate_valuation_model_ledger,
        valuation_fingerprint,
    )


SCHEMA_VERSION = "valuation-model-migration.v1"
_PROTECTED_ACTIVE_FIELDS = (
    "model_id", "model_type", "role", "status", "chapters",
    "independence_group_id", "shared_assumption_ids", "applicability", "basis",
    "assumptions", "result", "equity_bridge", "terminal_value",
    "sensitivity_tests", "fragility_mitigation", "source_ids", "decision_entry_ids",
)
_SEMANTIC_RESOLUTION_TEXT_FIELDS = (
    "research_basis", "mechanism", "valuation_impact", "decision_impact",
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _file_sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _report_text(output: Path) -> str:
    chapters = sorted((output / "chapters").glob("_ch*.md"))
    if chapters:
        return "\n\n".join(path.read_text(encoding="utf-8") for path in chapters)
    for name in ("最新_分析报告_v13.md", "最新_分析报告_v12.md"):
        path = output / "reports" / name
        if path.is_file():
            return path.read_text(encoding="utf-8")
    return ""


def _active_semantics(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for model in payload.get("models") or []:
        if not isinstance(model, dict) or model.get("status", "active") != "active":
            continue
        result.append({field: deepcopy(model.get(field)) for field in _PROTECTED_ACTIVE_FIELDS})
    return result


def _migration_body(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at", "change_reason", "lifecycle"):
        value.pop(key, None)
    return value


def sync_semantic_resolution_fingerprint(
    output_dir: str | Path, *, previous_fingerprint: str, current_fingerprint: str,
) -> bool:
    """Rebind a passed semantic audit only across a semantics-preserving promotion."""
    path = Path(output_dir) / "valuation_semantic_resolution.json"
    semantic = _read(path)
    validation = semantic.get("validation") if isinstance(semantic.get("validation"), dict) else {}
    if (
        not semantic
        or semantic.get("valuation_fingerprint") != previous_fingerprint
        or validation.get("state") != "REVIEWABLE"
    ):
        return False
    semantic["valuation_fingerprint"] = current_fingerprint
    _atomic_write_json(path, semantic)
    return True


def _verified_research_evidence(output: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for filename, collection, identity in (
        ("fact_observations.json", "observations", "observation_id"),
        ("calculation_observations.json", "calculations", "calculation_id"),
    ):
        for item in _read(output / filename).get(collection) or []:
            if (
                isinstance(item, dict)
                and str(item.get("status") or "").upper() == "VERIFIED"
                and item.get(identity)
            ):
                row = deepcopy(item)
                row["evidence_kind"] = "calculation" if identity == "calculation_id" else "observation"
                result[str(item[identity])] = row
    return result


def _semantic_evidence_fit(
    frontier: dict[str, Any],
    proposed_model: dict[str, Any],
    evidence_rows: list[dict[str, Any]],
) -> str | None:
    """Return a precise gap when evidence identity is valid but semantically remote."""
    field = str(frontier.get("field") or "")
    required = str(frontier.get("required") or "")
    model_type = str(proposed_model.get("model_type") or "")
    observations = [row for row in evidence_rows if row.get("evidence_kind") == "observation"]
    calculations = [row for row in evidence_rows if row.get("evidence_kind") == "calculation"]
    has_dividend = any(
        str(row.get("fact_name") or "") in {"dividend_payout_ratio_pct", "dividend_per_share"}
        or str(row.get("domain") or "") == "capital_allocation"
        for row in observations
    )
    has_owner_fact = any(
        str(row.get("fact_name") or "").startswith((
            "net_profit_parent", "cash_and_cash_equivalents", "restricted_bank_deposits",
        ))
        for row in observations
    )
    has_governance_fact = has_dividend or any(
        str(row.get("domain") or "") == "governance" for row in observations
    )
    has_aa = any(
        row.get("tool") == "compute_aa"
        and str(row.get("metric_path") or "").startswith("aa_")
        for row in calculations
    )
    has_gg = any(row.get("tool") == "compute_gg" for row in calculations)

    if field == "basis.cash_flow_scope" and required == "normalized_owner_earnings":
        if not (has_aa and has_owner_fact):
            return "owner_earnings_requires_compute_aa_and_official_owner_cash_fact"
    if field == "independence_group_id" and required == "distribution" and not has_dividend:
        return "distribution_group_requires_official_dividend_evidence"
    if required == "owner_return" and not (has_gg and has_governance_fact):
        return "owner_return_requires_compute_gg_and_official_distribution_or_governance_evidence"
    if field == "role" and model_type == "RETURN_DECOMPOSITION" and not (has_gg and has_governance_fact):
        return "return_decomposition_primary_role_requires_return_calculation_and_owner_access_evidence"
    if field == "role" and model_type == "DDM" and not has_dividend:
        return "ddm_primary_role_requires_official_dividend_evidence"
    if field == "assumptions.discount_rate.kind" and required == "required_return" and not has_gg:
        return "required_return_kind_requires_compute_gg_evidence"
    return None


def _set_frontier_value(model: dict[str, Any], field: str, value: Any) -> None:
    target: dict[str, Any] = model
    parts = field.split(".")
    for part in parts[:-1]:
        child = target.get(part)
        if not isinstance(child, dict):
            child = {}
            target[part] = child
        target = child
    target[parts[-1]] = deepcopy(value)


def validate_valuation_semantic_research(
    output_dir: str | Path,
    proposed: dict[str, Any],
    resolutions: list[dict[str, Any]] | None,
) -> dict[str, Any]:
    """Require evidence-backed, exactly-scoped research before semantic migration.

    Route conformance alone cannot prove that earnings are owner earnings or
    that a stress model should become a primary decision anchor.  This guard
    compares the proposal with the deterministic migration candidate and only
    permits the declared frontier fields to change.
    """
    output = Path(output_dir)
    original = _read(output / "valuation_model.json")
    candidate = _read(output / "valuation_model_migration_candidate.json")
    report = _read(output / "valuation_model_migration_report.json")
    frontier = [item for item in report.get("semantic_frontier") or [] if isinstance(item, dict)]
    if not frontier:
        return {
            "schema_version": "valuation-semantic-research-validation.v1",
            "state": "NOT_REQUIRED", "status": "PASS",
            "invalid_findings": [], "incomplete_findings": [],
        }

    invalid: list[str] = []
    incomplete: list[str] = []
    if not original or not candidate:
        invalid.append("valuation_migration_artifacts_missing")
    elif report.get("source_ledger_fingerprint") != valuation_fingerprint(original):
        invalid.append("valuation_migration_candidate_stale")

    expected_keys = {
        (str(item.get("model_id") or ""), str(item.get("field") or ""))
        for item in frontier
    }
    resolution_map: dict[tuple[str, str], dict[str, Any]] = {}
    for idx, item in enumerate(resolutions or []):
        if not isinstance(item, dict):
            invalid.append(f"semantic_resolutions[{idx}]:not_object")
            continue
        key = (str(item.get("model_id") or ""), str(item.get("field") or ""))
        if key in resolution_map:
            invalid.append(f"semantic_resolution_duplicate:{key[0]}:{key[1]}")
        resolution_map[key] = item
    for key in sorted(expected_keys - set(resolution_map)):
        incomplete.append(f"semantic_resolution_missing:{key[0]}:{key[1]}")
    for key in sorted(set(resolution_map) - expected_keys):
        invalid.append(f"semantic_resolution_not_in_frontier:{key[0]}:{key[1]}")

    verified_evidence = _verified_research_evidence(output)
    for key in sorted(expected_keys & set(resolution_map)):
        item = resolution_map[key]
        evidence_ids = item.get("evidence_ids")
        if not isinstance(evidence_ids, list) or not evidence_ids:
            incomplete.append(f"semantic_resolution_evidence_missing:{key[0]}:{key[1]}")
        else:
            for evidence_id in evidence_ids:
                if str(evidence_id) not in verified_evidence:
                    invalid.append(
                        f"semantic_resolution_evidence_unverified:{key[0]}:{key[1]}:{evidence_id}"
                    )
        for field in _SEMANTIC_RESOLUTION_TEXT_FIELDS:
            if len(str(item.get(field) or "").strip()) < 20:
                incomplete.append(f"semantic_resolution_{field}_weak:{key[0]}:{key[1]}")
        frontier_item = next(
            item for item in frontier
            if (str(item.get("model_id") or ""), str(item.get("field") or "")) == key
        )
        proposed_model = next(
            (item for item in proposed.get("models") or []
             if isinstance(item, dict) and str(item.get("model_id") or "") == key[0]),
            {},
        )
        semantic_gap = _semantic_evidence_fit(
            frontier_item,
            proposed_model,
            [verified_evidence[str(eid)] for eid in evidence_ids or [] if str(eid) in verified_evidence],
        )
        if semantic_gap:
            incomplete.append(f"semantic_resolution_evidence_mismatch:{key[0]}:{key[1]}:{semantic_gap}")

    expected = deepcopy(candidate)
    expected_models = {
        str(item.get("model_id") or ""): item
        for item in expected.get("models") or [] if isinstance(item, dict)
    }
    proposed_models = {
        str(item.get("model_id") or ""): item
        for item in proposed.get("models") or [] if isinstance(item, dict)
    }
    for item in frontier:
        model_id = str(item.get("model_id") or "")
        field = str(item.get("field") or "")
        expected_model = expected_models.get(model_id)
        proposed_model = proposed_models.get(model_id)
        if expected_model is None or proposed_model is None:
            invalid.append(f"semantic_frontier_model_missing:{model_id}")
            continue
        if field == "assumptions.discount_rate.kind":
            rate = ((proposed_model.get("assumptions") or {}).get("discount_rate"))
            basis = proposed_model.get("basis") or {}
            required_return = (proposed_model.get("assumptions") or {}).get("required_return_pct")
            if not isinstance(rate, dict):
                invalid.append(f"semantic_discount_rate_invalid:{model_id}")
                continue
            if rate.get("kind") != item.get("required"):
                invalid.append(f"semantic_frontier_required_value_mismatch:{model_id}:{field}")
            if rate.get("value_pct") != required_return:
                invalid.append(f"semantic_required_return_value_mismatch:{model_id}")
            if rate.get("tax_basis") != basis.get("tax_basis"):
                invalid.append(f"semantic_required_return_tax_basis_mismatch:{model_id}")
            if rate.get("inflation_basis") not in {"nominal", "real"}:
                invalid.append(f"semantic_required_return_inflation_basis_missing:{model_id}")
            (expected_model.setdefault("assumptions", {}))["discount_rate"] = deepcopy(rate)
        else:
            _set_frontier_value(expected_model, field, item.get("required"))

    if proposed.get("company_profile") != expected.get("company_profile"):
        invalid.append("semantic_research_company_profile_out_of_scope_change")
    if proposed.get("synthesis") != expected.get("synthesis"):
        invalid.append("semantic_research_synthesis_out_of_scope_change")
    if proposed.get("models") != expected.get("models"):
        invalid.append("semantic_research_model_out_of_scope_change")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": "valuation-semantic-research-validation.v1",
        "state": state,
        "status": "PASS" if state == "REVIEWABLE" else "FAIL",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "frontier_count": len(frontier),
        "resolution_count": len(resolution_map),
        "verified_evidence_ids": sorted({
            str(evidence_id)
            for item in resolution_map.values()
            for evidence_id in (item.get("evidence_ids") or [])
            if str(evidence_id) in verified_evidence
        }),
    }


def _route_candidates(model: dict[str, Any], route_models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [
        item for item in route_models
        if isinstance(item, dict) and item.get("model_type") == model.get("model_type")
    ]
    if len(candidates) <= 1:
        return candidates
    basis = model.get("basis") if isinstance(model.get("basis"), dict) else {}
    exact = [
        item for item in candidates
        if item.get("value_scope") == basis.get("value_scope")
        and item.get("cash_flow_scope") == basis.get("cash_flow_scope")
    ]
    return exact if exact else candidates


def _frontier_for_mapping(model: dict[str, Any], routed: dict[str, Any]) -> list[dict[str, Any]]:
    mid = str(model.get("model_id") or "")
    basis = model.get("basis") if isinstance(model.get("basis"), dict) else {}
    assumptions = model.get("assumptions") if isinstance(model.get("assumptions"), dict) else {}
    discount_rate = assumptions.get("discount_rate") if isinstance(assumptions.get("discount_rate"), dict) else {}
    comparisons = (
        ("role", model.get("role"), routed.get("role")),
        ("independence_group_id", model.get("independence_group_id"), routed.get("independence_group")),
        ("basis.value_scope", basis.get("value_scope"), routed.get("value_scope")),
        ("basis.cash_flow_scope", basis.get("cash_flow_scope"), routed.get("cash_flow_scope")),
        ("assumptions.discount_rate.kind", discount_rate.get("kind"), routed.get("discount_rate_kind")),
    )
    result = []
    for field, current, required in comparisons:
        if required == "not_applicable" and current in {None, "", "not_applicable"}:
            continue
        if current != required:
            result.append({
                "model_id": mid,
                "route_model_id": routed.get("route_model_id"),
                "field": field,
                "current": current,
                "required": required,
                "reason": "semantic_change_requires_valuation_research",
            })
    return result


def migrate_valuation_model(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    original = _read(output / "valuation_model.json")
    route = _read(output / "valuation_route.json")
    policy = _read(output / "valuation_model_policy.json")
    if not original:
        raise ValueError("valuation_model.json is missing or invalid")
    if not route:
        raise ValueError("valuation_route.json is missing or invalid")

    candidate = deepcopy(original)
    candidate.pop("freeze", None)
    candidate["lifecycle"] = "reviewable"
    candidate["change_reason"] = (
        "Deterministic route-identity migration candidate; valuation values, active model "
        "semantics, synthesis, action and position remain unchanged"
    )
    candidate["generated_at"] = _now()
    profile = candidate.get("company_profile")
    if not isinstance(profile, dict):
        profile = {}
        candidate["company_profile"] = profile
    profile["archetype_id"] = route.get("archetype_id")
    profile["valuation_route_id"] = route.get("route_id")
    profile["registry_version"] = route.get("registry_version")

    route_models = [item for item in route.get("models") or [] if isinstance(item, dict)]
    safe_bindings: list[dict[str, Any]] = []
    frontier: list[dict[str, Any]] = []
    for model in candidate.get("models") or []:
        if not isinstance(model, dict) or model.get("status", "active") != "active":
            continue
        matches = _route_candidates(model, route_models)
        if len(matches) != 1:
            frontier.append({
                "model_id": model.get("model_id"),
                "field": "route_model_id",
                "current": model.get("route_model_id"),
                "required": [item.get("route_model_id") for item in matches],
                "reason": "route_mapping_ambiguous_or_missing",
            })
            continue
        routed = matches[0]
        model["route_model_id"] = routed.get("route_model_id")
        safe_bindings.append({
            "model_id": model.get("model_id"),
            "route_model_id": routed.get("route_model_id"),
            "model_type": model.get("model_type"),
        })
        frontier.extend(_frontier_for_mapping(model, routed))

    existing_rejected = {
        str(item.get("route_model_id")) for item in candidate.get("models") or []
        if isinstance(item, dict) and item.get("status") == "rejected"
    }
    added_rejections: list[str] = []
    for routed in route.get("rejected_models") or []:
        if not isinstance(routed, dict):
            continue
        route_model_id = str(routed.get("route_model_id") or "")
        if not route_model_id or route_model_id in existing_rejected:
            continue
        candidate.setdefault("models", []).append({
            "model_id": "ROUTE_REJECTED:" + route_model_id,
            "route_model_id": route_model_id,
            "model_type": routed.get("model_type"),
            "role": "rejected",
            "status": "rejected",
            "rejection_reason": routed.get("rejection_reason"),
        })
        added_rejections.append(route_model_id)

    candidate["freeze"] = {"frozen": False, "fingerprint": "", "frozen_at": None}
    validation = validate_valuation_model_ledger(
        candidate,
        output_dir=output,
        report_text=_report_text(output),
        enforced=bool(policy.get("enforced")),
        min_independent_groups=int(policy.get("min_independent_groups") or 2),
        min_r_g_buffer_pct=float(policy.get("min_r_g_buffer_pct") or 3.0),
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source_ledger_fingerprint": valuation_fingerprint(original),
        "candidate_fingerprint": valuation_fingerprint(candidate),
        "canonical_ledger_unchanged": True,
        "route_id": route.get("route_id"),
        "registry_version": route.get("registry_version"),
        "safe_bindings": safe_bindings,
        "added_route_rejections": added_rejections,
        "migration_required": _migration_body(original) != _migration_body(candidate),
        "semantic_frontier": frontier,
        "candidate_validation": validation,
        "protected_invariants": {
            "active_model_semantics_unchanged": _active_semantics(original) == _active_semantics(candidate),
            "synthesis_unchanged": original.get("synthesis") == candidate.get("synthesis"),
            "decision_ledger_sha256": _file_sha256(output / "decision_ledger.json"),
            "decision_diff_sha256": _file_sha256(output / "decision_diff.json"),
        },
    }
    if persist:
        _atomic_write_json(output / "valuation_model_migration_candidate.json", candidate)
        _atomic_write_json(output / "valuation_model_migration_report.json", report)
    return {"candidate": candidate, "report": report}


def promote_valuation_model_migration(output_dir: str | Path) -> dict[str, Any]:
    """Promote only a route-identity-only, fully reviewable candidate."""
    output = Path(output_dir)
    original = _read(output / "valuation_model.json")
    candidate = _read(output / "valuation_model_migration_candidate.json")
    report = _read(output / "valuation_model_migration_report.json")
    if not original or not candidate or not report:
        return {"promoted": False, "error": "migration_artifacts_missing"}
    if report.get("source_ledger_fingerprint") != valuation_fingerprint(original):
        return {"promoted": False, "error": "canonical_changed_since_migration"}
    if report.get("semantic_frontier"):
        return {"promoted": False, "error": "semantic_change_requires_valuation_research",
                "semantic_frontier": report.get("semantic_frontier")}
    if not report.get("migration_required"):
        return {"promoted": False, "already_compatible": True}
    invariants = report.get("protected_invariants") or {}
    if not invariants.get("active_model_semantics_unchanged") or not invariants.get("synthesis_unchanged"):
        return {"promoted": False, "error": "protected_valuation_semantics_changed"}
    if invariants.get("decision_ledger_sha256") != _file_sha256(output / "decision_ledger.json"):
        return {"promoted": False, "error": "decision_ledger_changed_since_migration"}
    if invariants.get("decision_diff_sha256") != _file_sha256(output / "decision_diff.json"):
        return {"promoted": False, "error": "decision_diff_changed_since_migration"}
    validation = report.get("candidate_validation") or {}
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "error": "candidate_not_reviewable", "validation": validation}

    promoted = deepcopy(candidate)
    promoted["lifecycle"] = "decision_ready"
    promoted["change_reason"] = (
        "Deterministic route-identity-only migration; active valuation model semantics, "
        "results, synthesis, action, position and decision artifacts unchanged"
    )
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = valuation_fingerprint(promoted)
    result = persist_valuation_model_ledger(
        output, promoted, report_text=_report_text(output), allow_frozen_update=True
    )
    promoted_ok = bool(result.get("written")) and result.get("validation", {}).get("state") == "DECISION_READY"
    if promoted_ok:
        result["semantic_resolution_fingerprint_synced"] = sync_semantic_resolution_fingerprint(
            output,
            previous_fingerprint=str(report.get("source_ledger_fingerprint") or ""),
            current_fingerprint=valuation_fingerprint(promoted),
        )
    report["canonical_ledger_unchanged"] = not promoted_ok
    report["promotion"] = {
        "promoted": promoted_ok,
        "promoted_at": _now() if promoted_ok else None,
        "error": result.get("error"),
        "validation": result.get("validation"),
    }
    _atomic_write_json(output / "valuation_model_migration_report.json", report)
    return {"promoted": promoted_ok, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--promote-if-reviewable", action="store_true")
    args = parser.parse_args()
    result = migrate_valuation_model(args.output_dir, persist=not args.no_persist)
    report = result["report"]
    summary = {
        "candidate_state": (report.get("candidate_validation") or {}).get("state"),
        "safe_bindings": len(report.get("safe_bindings") or []),
        "semantic_frontier": len(report.get("semantic_frontier") or []),
        "canonical_ledger_unchanged": report.get("canonical_ledger_unchanged"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.promote_if_reviewable and not args.no_persist:
        promotion = promote_valuation_model_migration(args.output_dir)
        print(json.dumps({"promotion": promotion.get("promoted"), "error": promotion.get("error")}, ensure_ascii=False, indent=2))
        return 0 if promotion.get("promoted") else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
