#!/usr/bin/env python3
"""Deterministic company-archetype classification and valuation-model routing."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_documents import _atomic_write_json
except ModuleNotFoundError:
    from evidence_documents import _atomic_write_json


ARCHETYPE_SCHEMA = "company-archetype.v1"
ROUTE_SCHEMA = "valuation-route.v1"
POLICY_SCHEMA = "valuation-route-policy.v1"
VALIDATION_SCHEMA = "valuation-route-validation.v1"
REGISTRY_RELATIVE_PATH = Path("config/archetype_valuation_registry.v1.json")
ALLOWED_SOURCE_FILES = {
    "analysis_contract.json", "report_context.json", "compute_bundle.json",
    "industry_context.json",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _stable_payload_hash(payload: dict[str, Any]) -> str:
    value = deepcopy(payload)
    for key in ("generated_at", "updated_at", "validation"):
        value.pop(key, None)
    return _hash(value)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path else _repo_root() / REGISTRY_RELATIVE_PATH
    registry = _read_json(target)
    if registry.get("schema_version") != "archetype-valuation-registry.v1":
        raise ValueError(f"invalid archetype valuation registry: {target}")
    return registry


def registry_fingerprint(registry: dict[str, Any]) -> str:
    return _hash(registry)


def _source_hash(path: Path, payload: dict[str, Any]) -> str:
    if path.name == "report_context.json":
        context_fingerprint = _nested(payload, "meta.context_fingerprint")
        if context_fingerprint:
            return str(context_fingerprint)
    value = deepcopy(payload)
    for key in ("generated_at", "updated_at"):
        value.pop(key, None)
    return _hash(value)


def routing_input_sources(output_dir: str | Path) -> dict[str, str]:
    output = Path(output_dir)
    result: dict[str, str] = {}
    for name in sorted(ALLOWED_SOURCE_FILES):
        payload = _read_json(output / name)
        if payload:
            result[name] = _source_hash(output / name, payload)
    return result


def _nested(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for key in path.split("."):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def _input_value(inputs: dict[str, dict[str, Any]], dotted_path: str) -> tuple[str, Any] | None:
    prefix_map = {
        "analysis_contract": "analysis_contract.json",
        "report_context": "report_context.json",
        "compute_bundle": "compute_bundle.json",
        "industry_context": "industry_context.json",
    }
    prefix, _, rest = dotted_path.partition(".")
    filename = prefix_map.get(prefix)
    if not filename:
        return None
    value = _nested(inputs.get(filename, {}), rest)
    return (filename, value) if value not in (None, "", [], {}) else None


def _identity_text(inputs: dict[str, dict[str, Any]]) -> str:
    contract = inputs.get("analysis_contract.json", {})
    industry = inputs.get("industry_context.json", {})
    values = [
        _nested(contract, "industry_classification.l1"),
        _nested(contract, "industry_classification.l2"),
        _nested(contract, "industry_classification.peer_group"),
        _nested(industry, "meta.industry_l1"),
        _nested(industry, "meta.industry_l2"),
        _nested(industry, "meta.industry_group"),
    ]
    return " | ".join(str(value) for value in values if value not in (None, ""))


def _score_archetypes(
    registry: dict[str, Any], inputs: dict[str, dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    identity = _identity_text(inputs)
    evidence: list[dict[str, Any]] = []
    counterevidence: list[dict[str, Any]] = []
    scored: list[dict[str, Any]] = []
    for archetype_id, spec in registry["archetypes"].items():
        matches = sorted({pattern for pattern in spec.get("industry_patterns") or [] if pattern and pattern.lower() in identity.lower()})
        counters = sorted({pattern for pattern in spec.get("counter_patterns") or [] if pattern and pattern.lower() in identity.lower()})
        score = min(0.98, (0.82 + 0.04 * (len(matches) - 1)) if matches else (0.32 if archetype_id == "general_operating" else 0.0))
        score = max(0.0, score - min(0.6, 0.3 * len(counters)))
        for pattern in matches:
            evidence.append({
                "archetype_id": archetype_id, "source_file": "analysis_contract.json|industry_context.json",
                "source_path": "industry_classification/meta", "observed_value": identity,
                "matched_rule": pattern, "effect": "+industry_match",
            })
        for pattern in counters:
            counterevidence.append({
                "archetype_id": archetype_id, "source_file": "analysis_contract.json|industry_context.json",
                "source_path": "industry_classification/meta", "observed_value": identity,
                "matched_rule": pattern, "effect": "-counter_pattern",
            })
        scored.append({"archetype_id": archetype_id, "score": round(score, 4), "matches": matches, "counters": counters})
    scored.sort(key=lambda item: (-item["score"], item["archetype_id"]))
    return scored, evidence, counterevidence


def validate_company_archetype(
    payload: dict[str, Any], registry: dict[str, Any], *, output_dir: str | Path | None = None
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != ARCHETYPE_SCHEMA:
        invalid.append("schema_version_invalid")
    if payload.get("registry_version") != registry.get("registry_version") or payload.get("registry_fingerprint") != registry_fingerprint(registry):
        invalid.append("registry_identity_mismatch")
    primary = payload.get("primary_archetype") if isinstance(payload.get("primary_archetype"), dict) else {}
    primary_id = str(primary.get("archetype_id") or "")
    if primary_id not in registry.get("archetypes", {}):
        invalid.append("primary_archetype_unknown")
    try:
        confidence = float(primary.get("confidence"))
        if not 0 <= confidence <= 1:
            raise ValueError
    except (TypeError, ValueError):
        invalid.append("primary_confidence_invalid")
        confidence = 0.0
    if confidence < 0.55:
        incomplete.append("primary_archetype_confidence_insufficient")
    evidence = payload.get("matching_evidence")
    if not isinstance(evidence, list) or (primary_id != "general_operating" and not any(item.get("archetype_id") == primary_id for item in evidence if isinstance(item, dict))):
        incomplete.append("primary_matching_evidence_missing")
    scores = payload.get("candidate_scores") or []
    if len(scores) >= 2:
        try:
            if float(scores[0]["score"]) - float(scores[1]["score"]) < 0.12:
                warnings.append("archetype_margin_narrow")
        except (KeyError, TypeError, ValueError):
            invalid.append("candidate_scores_invalid")
    missing = payload.get("missing_required_inputs")
    if not isinstance(missing, list):
        invalid.append("missing_required_inputs_not_array")
    elif missing:
        incomplete.extend("required_input_missing:" + str(item) for item in missing)
    sources = payload.get("input_sources")
    if not isinstance(sources, dict) or not sources:
        incomplete.append("input_sources_missing")
    elif payload.get("input_fingerprint") != _hash(sources):
        invalid.append("input_fingerprint_mismatch")
    if output_dir is not None and isinstance(sources, dict):
        current = routing_input_sources(output_dir)
        for name, expected in sources.items():
            if current.get(name) != expected:
                warnings.append("input_source_changed_after_routing:" + str(name))
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"schema_version": VALIDATION_SCHEMA, "state": state, "status": "PASS" if state == "REVIEWABLE" else "FAIL", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings}


def build_company_archetype(
    output_dir: str | Path, *, registry: dict[str, Any] | None = None, persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    registry = registry or load_registry()
    inputs = {name: _read_json(output / name) for name in ALLOWED_SOURCE_FILES}
    sources = routing_input_sources(output)
    scores, evidence, counterevidence = _score_archetypes(registry, inputs)
    primary_score = scores[0]
    primary_id = primary_score["archetype_id"]
    spec = registry["archetypes"][primary_id]
    required = []
    missing = []
    for path in spec.get("required_input_paths") or []:
        found = _input_value(inputs, path)
        required.append({"path": path, "present": bool(found), "source_file": found[0] if found else "", "value": found[1] if found else None})
        if not found:
            missing.append(path)
    secondaries = [
        {"archetype_id": item["archetype_id"], "confidence": item["score"], "reason": item["matches"]}
        for item in scores[1:3] if item["score"] >= 0.45
    ]
    report_id = str(_nested(inputs.get("analysis_contract.json", {}), "ts_code") or _nested(inputs.get("report_context.json", {}), "meta.report_id") or output.name)
    payload: dict[str, Any] = {
        "schema_version": ARCHETYPE_SCHEMA, "report_id": report_id,
        "registry_version": registry["registry_version"], "registry_fingerprint": registry_fingerprint(registry),
        "input_sources": sources, "input_fingerprint": _hash(sources), "generated_at": _now(),
        "primary_archetype": {"archetype_id": primary_id, "label": spec["label"], "confidence": primary_score["score"], "basis": "structured industry identity and explicit counter-rules"},
        "secondary_archetypes": secondaries,
        "candidate_scores": scores,
        "matching_evidence": evidence,
        "counterevidence": counterevidence,
        "conflicts": ["top-two archetypes are close"] if len(scores) > 1 and scores[0]["score"] - scores[1]["score"] < 0.12 else [],
        "required_inputs": required, "missing_required_inputs": missing,
        "research_requirements": list(spec.get("research_requirements") or []),
        "classification_limits": ["classification selects a model family; it does not prove company quality", "reference workbooks are not current-company facts"],
    }
    payload["validation"] = validate_company_archetype(payload, registry, output_dir=output)
    if persist:
        _atomic_write_json(output / "company_archetype.json", payload)
        _atomic_write_json(output / "company_archetype_validation.json", payload["validation"])
    return payload


def _route_model(model_id: str, role: str, registry: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    model = registry["models"][model_id]
    return {
        "route_model_id": model_id, "model_type": model["model_type"], "role": role,
        "value_scope": model["value_scope"], "cash_flow_scope": model["cash_flow_scope"],
        "discount_rate_kind": model["discount_rate_kind"], "independence_group": model["independence_group"],
        "fragilities": list(model.get("fragilities") or []),
        "use": "决策主锚" if role == "primary" else "独立边界校验" if role == "corroborative" else "下行或口径压力测试",
        "required_conditions": list(spec.get("research_requirements") or []),
    }


def validate_valuation_route(
    payload: dict[str, Any], archetype: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != ROUTE_SCHEMA:
        invalid.append("schema_version_invalid")
    if payload.get("registry_fingerprint") != registry_fingerprint(registry):
        invalid.append("registry_identity_mismatch")
    primary_id = str((archetype.get("primary_archetype") or {}).get("archetype_id") or "")
    if payload.get("archetype_id") != primary_id:
        invalid.append("route_archetype_mismatch")
    if payload.get("archetype_fingerprint") != _stable_payload_hash(archetype):
        invalid.append("archetype_fingerprint_mismatch")
    spec = registry.get("archetypes", {}).get(primary_id, {})
    models = payload.get("models")
    if not isinstance(models, list):
        invalid.append("models_not_array"); models = []
    seen: set[str] = set(); roles: dict[str, set[str]] = {}
    for item in models:
        if not isinstance(item, dict):
            invalid.append("model_not_object"); continue
        model_id = str(item.get("route_model_id") or "")
        if model_id in seen:
            invalid.append("duplicate_route_model:" + model_id)
        seen.add(model_id)
        if model_id not in registry.get("models", {}):
            invalid.append("unknown_route_model:" + model_id); continue
        role = str(item.get("role") or "")
        if role not in {"primary", "corroborative", "stress"}:
            invalid.append(model_id + ":role_invalid")
        roles.setdefault(role, set()).add(model_id)
        canonical = registry["models"][model_id]
        for field in ("model_type", "value_scope", "cash_flow_scope", "discount_rate_kind", "independence_group"):
            if item.get(field) != canonical.get(field):
                invalid.append(model_id + ":basis_drift:" + field)
        if not item.get("fragilities") or not item.get("required_conditions"):
            incomplete.append(model_id + ":fragility_or_conditions_missing")
    for role, field in (("primary", "primary_models"), ("corroborative", "corroborative_models"), ("stress", "stress_models")):
        expected = set(spec.get(field) or [])
        if roles.get(role, set()) != expected:
            invalid.append(role + "_model_set_mismatch")
    rejected = payload.get("rejected_models")
    if not isinstance(rejected, list):
        invalid.append("rejected_models_not_array"); rejected = []
    rejected_ids = {str(item.get("route_model_id")) for item in rejected if isinstance(item, dict)}
    if rejected_ids != set(spec.get("rejected_models") or []):
        invalid.append("rejected_model_set_mismatch")
    for item in rejected:
        if not isinstance(item, dict) or not str(item.get("rejection_reason") or "").strip():
            incomplete.append("rejected_model_reason_missing")
    synthesis = payload.get("synthesis_policy") if isinstance(payload.get("synthesis_policy"), dict) else {}
    if synthesis.get("method") != "role_based_decision_not_weighted_average":
        invalid.append("unjustified_weighted_average_not_prohibited")
    if not synthesis.get("decision_rule") or not synthesis.get("divergence_rule"):
        incomplete.append("synthesis_policy_incomplete")
    terminal = payload.get("terminal_policy") if isinstance(payload.get("terminal_policy"), dict) else {}
    if terminal.get("minimum_r_g_buffer_pct") != registry.get("model_policy", {}).get("minimum_r_g_buffer_pct"):
        invalid.append("terminal_r_g_policy_drift")
    if not terminal.get("required_stress_cases"):
        incomplete.append("terminal_stress_policy_missing")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {"schema_version": VALIDATION_SCHEMA, "state": state, "status": "PASS" if state == "REVIEWABLE" else "FAIL", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings}


def build_valuation_route(
    output_dir: str | Path, archetype: dict[str, Any] | None = None, *, registry: dict[str, Any] | None = None, persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    registry = registry or load_registry()
    archetype = archetype or _read_json(output / "company_archetype.json") or build_company_archetype(output, registry=registry, persist=persist)
    primary_id = str((archetype.get("primary_archetype") or {}).get("archetype_id") or "")
    spec = registry["archetypes"].get(primary_id, registry["archetypes"]["general_operating"])
    models = []
    for role, field in (("primary", "primary_models"), ("corroborative", "corroborative_models"), ("stress", "stress_models")):
        models.extend(_route_model(model_id, role, registry, spec) for model_id in spec.get(field) or [])
    rejected = [
        {"route_model_id": model_id, "model_type": registry["models"][model_id]["model_type"], "role": "rejected", "rejection_reason": (spec.get("rejection_reasons") or {}).get(model_id, "与该原型的现金流或资产归属不匹配")}
        for model_id in spec.get("rejected_models") or []
    ]
    policy = registry["model_policy"]
    payload: dict[str, Any] = {
        "schema_version": ROUTE_SCHEMA, "report_id": archetype.get("report_id"),
        "registry_version": registry["registry_version"], "registry_fingerprint": registry_fingerprint(registry),
        "archetype_id": primary_id, "archetype_fingerprint": _stable_payload_hash(archetype),
        "route_id": f"VR:{primary_id}:{registry['registry_version']}", "generated_at": _now(),
        "legacy_company_profile": {"business_type": spec["legacy_business_type"], "asset_intensity": spec["asset_intensity"]},
        "models": models, "rejected_models": rejected,
        "synthesis_policy": {
            "method": "role_based_decision_not_weighted_average",
            "decision_rule": "primary model determines the decision range only after required conditions pass; corroborative models test independent boundaries",
            "divergence_rule": "explain cash-flow ownership, normalization and terminal assumptions; do not average unresolved divergence",
            "relative_valuation_role": "context_only",
        },
        "terminal_policy": {
            "minimum_r_g_buffer_pct": policy["minimum_r_g_buffer_pct"],
            "high_terminal_share_pct": policy["high_terminal_share_pct"],
            "required_stress_cases": policy["required_stress_cases"],
            "fragile_output_action": "range_only_and_lower_confidence",
        },
        "required_research": list(spec.get("research_requirements") or []),
        "reference_policy": {"index": "config/valuation_reference_index.json", "use": "mechanism_reference_only", "company_fact_eligible": False},
    }
    payload["validation"] = validate_valuation_route(payload, archetype, registry)
    if persist:
        _atomic_write_json(output / "valuation_route.json", payload)
        _atomic_write_json(output / "valuation_route_validation.json", payload["validation"])
    return payload


def initialize_valuation_route_policy(output_dir: str | Path, *, run_id: str, enforced: bool) -> dict[str, Any]:
    registry = load_registry()
    payload = {"schema_version": POLICY_SCHEMA, "run_id": str(run_id), "enforced": bool(enforced), "registry_version": registry["registry_version"], "registry_fingerprint": registry_fingerprint(registry), "created_at": _now()}
    _atomic_write_json(Path(output_dir) / "valuation_route_policy.json", payload)
    return payload


def evaluate_output_valuation_route(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _read_json(output / "valuation_route_policy.json")
    if not policy:
        return {"schema_version": VALIDATION_SCHEMA, "state": "SKIP", "status": "SKIP", "invalid_findings": [], "incomplete_findings": [], "warnings": [], "enforced": False}
    registry = load_registry()
    archetype = _read_json(output / "company_archetype.json")
    route = _read_json(output / "valuation_route.json")
    if not archetype or not route:
        result = {"schema_version": VALIDATION_SCHEMA, "state": "INCOMPLETE", "status": "FAIL", "invalid_findings": [], "incomplete_findings": ["company_archetype_missing" if not archetype else "valuation_route_missing"], "warnings": [], "enforced": bool(policy.get("enforced"))}
    else:
        archetype_result = validate_company_archetype(archetype, registry, output_dir=output)
        route_result = validate_valuation_route(route, archetype, registry)
        invalid = archetype_result["invalid_findings"] + route_result["invalid_findings"]
        incomplete = archetype_result["incomplete_findings"] + route_result["incomplete_findings"]
        warnings = archetype_result["warnings"] + route_result["warnings"]
        state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
        result = {"schema_version": VALIDATION_SCHEMA, "state": state, "status": "PASS" if state == "REVIEWABLE" else "FAIL", "invalid_findings": list(dict.fromkeys(invalid)), "incomplete_findings": list(dict.fromkeys(incomplete)), "warnings": list(dict.fromkeys(warnings)), "enforced": bool(policy.get("enforced")), "archetype_id": route.get("archetype_id"), "route_id": route.get("route_id")}
    if persist:
        _atomic_write_json(output / "valuation_route_validation.json", result)
    return result


def build_reference_index(source_root: str | Path, output_path: str | Path) -> dict[str, Any]:
    root = Path(source_root).resolve()
    files = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        lowered = relative.lower()
        tags = [
            tag for tag, patterns in {
                "property": ("房地产", "物业", "reit"), "financial": ("银行", "保险", "证券"),
                "consumer": ("茅台", "海底捞", "农夫", "麦当劳", "星巴克", "安踏"),
                "technology_platform": ("腾讯", "阿里", "百度", "京东", "软件", "互联网"),
                "cyclical_infrastructure": ("石油", "煤", "水电", "高速", "汽车", "物流"),
                "healthcare": ("医药", "生物", "药", "gild"), "generic_template": ("模板", "速算", "德勤")
            }.items() if any(pattern.lower() in lowered for pattern in patterns)
        ]
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        files.append({"relative_path": relative, "sha256": digest, "size_bytes": path.stat().st_size, "extension": path.suffix.lower(), "collection": relative.split("/", 1)[0], "mechanism_tags": tags, "usage": "mechanism_reference_only", "company_fact_eligible": False})
    extensions = Counter(item["extension"] or "no_extension" for item in files)
    collections = Counter(item["collection"] for item in files)
    payload = {"schema_version": "valuation-reference-index.v1", "generated_at": _now(), "source_root_label": root.name, "source_root_fingerprint": _hash([(item["relative_path"], item["sha256"]) for item in files]), "policy": {"company_fact_eligible": False, "parameter_copying_forbidden": True, "use": "mechanism_and_model_structure_reference"}, "summary": {"file_count": len(files), "extension_counts": dict(sorted(extensions.items())), "collection_counts": dict(sorted(collections.items()))}, "files": files}
    _atomic_write_json(Path(output_path), payload)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="生成公司原型、估值路由或模型资料索引")
    parser.add_argument("--output-dir")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--enforced", action="store_true")
    parser.add_argument("--reference-root", default="")
    parser.add_argument("--reference-index", default="config/valuation_reference_index.json")
    args = parser.parse_args()
    if args.reference_root:
        result = build_reference_index(args.reference_root, args.reference_index)
        print(json.dumps(result["summary"], ensure_ascii=False)); return 0
    if not args.output_dir:
        parser.error("--output-dir or --reference-root is required")
    archetype = build_company_archetype(args.output_dir, persist=True)
    route = build_valuation_route(args.output_dir, archetype, persist=True)
    if args.run_id:
        initialize_valuation_route_policy(args.output_dir, run_id=args.run_id, enforced=args.enforced)
    print(json.dumps({"archetype": archetype["primary_archetype"], "route_id": route["route_id"], "state": route["validation"]["state"]}, ensure_ascii=False))
    return 0 if route["validation"]["state"] != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
