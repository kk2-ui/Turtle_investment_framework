#!/usr/bin/env python3
"""V3 Phase D valuation-model applicability, fragility and decision gate."""

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
except ModuleNotFoundError:
    from evidence_citation import EvidenceRegistry


SCHEMA_VERSION = "valuation-model-ledger.v1"
POLICY_VERSION = "valuation-model-policy.v1"
MODEL_TYPES = {
    "DCF", "DDM", "EPV", "ASSET_VALUE", "NAV", "SOTP",
    "RETURN_DECOMPOSITION", "RELATIVE", "RESIDUAL_INCOME", "RNPV",
}
BUSINESS_TYPES = {
    "general_operating", "bank", "insurer", "property_developer", "asset_holding",
    "cyclical", "utility", "pre_revenue_biotech", "conglomerate",
}
ROLES = {"primary", "corroborative", "stress"}
ACTIONS = {"buy", "hold", "avoid"}
MIN_R_G_BUFFER_PCT = 3.0
HIGH_TERMINAL_SHARE_PCT = 70.0
_PERPETUITY_MODELS = {"DCF", "DDM", "EPV", "RNPV"}
_VALUATION_REF_RE = re.compile(r"\[valuation:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.MULTILINE)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _canonical(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at"):
        value.pop(key, None)
    return value


def valuation_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def bind_valuation_references(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Append compiler-owned model anchors without rewriting analytical prose."""
    output = Path(output_dir); chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    additions: dict[int, list[str]] = {}
    for model in payload.get("models") or []:
        if not isinstance(model, dict) or model.get("status", "active") != "active": continue
        model_id = str(model.get("model_id") or "").strip()
        if not model_id: continue
        for chapter in model.get("chapters") or []:
            if not isinstance(chapter, int): continue
            path = chapter_dir / f"_ch{chapter:02d}.md"
            if not path.is_file(): continue
            text = path.read_text(encoding="utf-8")
            if model_id in _VALUATION_REF_RE.findall(text): continue
            additions.setdefault(chapter, []).append(f"- 估值模型引用：[valuation: {model_id}]")
    changed: list[int] = []
    for chapter, rows in additions.items():
        path = chapter_dir / f"_ch{chapter:02d}.md"; text = path.read_text(encoding="utf-8")
        block = "\n\n### Canonical valuation bindings\n\n" + "\n".join(rows) + "\n"
        path.write_text(text.rstrip() + block, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": sorted(changed), "anchors_inserted": sum(map(len, additions.values()))}


def promote_reviewable_valuation_model(output_dir: str | Path, *, report_text: str) -> dict[str, Any]:
    output = Path(output_dir); payload = _read_json(output / "valuation_model.json")
    if not payload: return {"promoted": False, "error": "valuation_model_missing"}
    policy = _read_json(output / "valuation_model_policy.json")
    validation = validate_valuation_model_ledger(
        payload, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
        min_independent_groups=int(policy.get("min_independent_groups") or 2),
        min_r_g_buffer_pct=float(policy.get("min_r_g_buffer_pct") or MIN_R_G_BUFFER_PCT),
    )
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "validation": validation}
    promoted = deepcopy(payload); promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = valuation_fingerprint(promoted)
    result = persist_valuation_model_ledger(
        output, promoted, report_text=report_text, allow_frozen_update=True
    )
    result["promoted"] = bool(result.get("written"))
    if result["promoted"]:
        semantic_path = output / "valuation_semantic_resolution.json"
        semantic = _read_json(semantic_path)
        previous_fingerprint = valuation_fingerprint(payload)
        semantic_validation = semantic.get("validation") if isinstance(semantic.get("validation"), dict) else {}
        if (
            semantic
            and semantic.get("valuation_fingerprint") == previous_fingerprint
            and semantic_validation.get("state") == "REVIEWABLE"
        ):
            semantic["valuation_fingerprint"] = valuation_fingerprint(promoted)
            semantic_path.write_text(
                json.dumps(semantic, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result["semantic_resolution_fingerprint_synced"] = True
    return result


def initialize_valuation_model_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool, min_independent_groups: int = 2,
    require_normalization_bridge: bool = False,
    require_decay_treatment: bool = False,
    require_owner_earnings_normalization: bool = False,
    require_holding_period_return_bridge: bool = False,
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        "min_independent_groups": max(1, int(min_independent_groups)),
        "min_r_g_buffer_pct": MIN_R_G_BUFFER_PCT,
        "high_terminal_share_pct": HIGH_TERMINAL_SHARE_PCT,
        "require_normalization_bridge": bool(require_normalization_bridge),
        "require_decay_treatment": bool(require_decay_treatment),
        "require_owner_earnings_normalization": bool(require_owner_earnings_normalization),
        "require_holding_period_return_bridge": bool(require_holding_period_return_bridge),
        "created_at": _now(),
    }
    path = Path(output_dir) / "valuation_model_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_valuation_model_ledger(
    output_dir: str | Path,
    company_profile: dict[str, Any],
    models: list[dict[str, Any]],
    synthesis: dict[str, Any],
    *, change_reason: str,
    freeze: bool = True,
    cash_access_bridge: dict[str, Any] | None = None,
    parameter_calibrations: list[dict[str, Any]] | None = None,
    model_comparisons: list[dict[str, Any]] | None = None,
    joint_stress_tests: list[dict[str, Any]] | None = None,
    action_policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    contract = _read_json(output / "analysis_contract.json")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(contract.get("ts_code") or contract.get("code") or output.name),
        "revision": 1,
        "lifecycle": "decision_ready" if freeze else "reviewable",
        "change_reason": str(change_reason or "").strip(),
        "company_profile": deepcopy(company_profile),
        "models": deepcopy(models),
        "synthesis": deepcopy(synthesis),
        "cash_access_bridge": deepcopy(cash_access_bridge),
        "parameter_calibrations": deepcopy(parameter_calibrations or []),
        "model_comparisons": deepcopy(model_comparisons or []),
        "joint_stress_tests": deepcopy(joint_stress_tests or []),
        "action_policy": deepcopy(action_policy),
        "generated_at": _now(),
    }
    payload["freeze"] = {
        "frozen": bool(freeze),
        "fingerprint": valuation_fingerprint(payload) if freeze else "",
        "frozen_at": _now() if freeze else None,
    }
    return payload


def _num(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _same(left: Any, right: Any, tolerance: float = 1e-4) -> bool:
    lval, rval = _num(left), _num(right)
    return lval is not None and rval is not None and math.isclose(lval, rval, rel_tol=tolerance, abs_tol=tolerance)


def _validate_normalization_bridge(
    model_id: str,
    model: dict[str, Any],
    basis: dict[str, Any],
    result: dict[str, Any],
) -> list[str]:
    """Validate the auditable earnings-to-EPV arithmetic bridge."""
    findings: list[str] = []
    bridge = model.get("normalization_bridge")
    if not isinstance(bridge, dict):
        return [f"{model_id}:normalization_bridge_missing"]

    source_currency = str(bridge.get("source_currency") or "").strip()
    model_currency = str(bridge.get("model_currency") or "").strip()
    if not source_currency or not model_currency:
        findings.append(f"{model_id}:normalization_bridge_currency_missing")
    elif model_currency != basis.get("currency"):
        findings.append(f"{model_id}:normalization_bridge_model_currency_mismatch")

    numeric_fields = (
        "source_normalized_earnings",
        "fx_source_per_model",
        "normalized_earnings_model_currency",
        "capitalization_rate_pct",
        "capitalized_value",
        "shares",
        "per_share_value",
    )
    numbers = {key: _num(bridge.get(key)) for key in numeric_fields}
    if any(value is None or value <= 0 for value in numbers.values()):
        findings.append(f"{model_id}:normalization_bridge_numeric_fields_invalid")
    else:
        source_earnings = numbers["source_normalized_earnings"]
        fx_source_per_model = numbers["fx_source_per_model"]
        model_earnings = numbers["normalized_earnings_model_currency"]
        capitalization_rate = numbers["capitalization_rate_pct"]
        capitalized_value = numbers["capitalized_value"]
        shares = numbers["shares"]
        per_share_value = numbers["per_share_value"]
        if source_currency == model_currency and not _same(fx_source_per_model, 1.0):
            findings.append(f"{model_id}:normalization_bridge_same_currency_fx_invalid")
        if not _same(source_earnings / fx_source_per_model, model_earnings):
            findings.append(f"{model_id}:normalization_bridge_fx_arithmetic_mismatch")
        if not _same(
            model_earnings / (capitalization_rate / 100.0), capitalized_value
        ):
            findings.append(f"{model_id}:normalization_bridge_capitalization_mismatch")
        if not _same(capitalized_value / shares, per_share_value, tolerance=5e-3):
            findings.append(f"{model_id}:normalization_bridge_per_share_mismatch")
        if not _same(per_share_value, result.get("value_per_share"), tolerance=5e-3):
            findings.append(f"{model_id}:normalization_bridge_result_mismatch")

    if not str(bridge.get("non_operating_income_treatment") or "").strip():
        findings.append(
            f"{model_id}:normalization_bridge_non_operating_income_treatment_missing"
        )
    adjustments = bridge.get("adjustments")
    if not isinstance(adjustments, list) or not adjustments:
        findings.append(f"{model_id}:normalization_bridge_adjustments_missing")
    source_ids = bridge.get("source_ids")
    if (
        not isinstance(source_ids, list)
        or not source_ids
        or any(not str(source_id or "").strip() for source_id in source_ids)
    ):
        findings.append(f"{model_id}:normalization_bridge_source_ids_missing")
    return findings


def _validate_decay_treatment(
    model_id: str,
    model: dict[str, Any],
    result: dict[str, Any],
) -> list[str]:
    """Ensure moat decay is applied once and reconciles to the reported margin."""
    findings: list[str] = []
    treatment = model.get("decay_treatment")
    if not isinstance(treatment, dict):
        return [f"{model_id}:decay_treatment_missing"]
    mode = str(treatment.get("mode") or "").strip()
    allowed_modes = {"scenario_only", "incremental_hurdle", "cash_flow_adjustment"}
    if mode not in allowed_modes:
        findings.append(f"{model_id}:decay_treatment_mode_invalid")
    if not str(treatment.get("double_count_check") or "").strip():
        findings.append(f"{model_id}:decay_treatment_double_count_check_missing")

    if mode not in {"scenario_only", "incremental_hurdle"}:
        return findings
    gross = _num(result.get("gross_return_pct"))
    required = _num(result.get("required_return_pct"))
    margin = _num(result.get("return_safety_margin_pct"))
    if None in {gross, required, margin}:
        findings.append(f"{model_id}:decay_treatment_return_fields_invalid")
        return findings

    excludes_decay = treatment.get("base_margin_excludes_decay")
    if mode == "scenario_only":
        if excludes_decay is not True:
            findings.append(f"{model_id}:scenario_only_must_exclude_decay_from_base_margin")
        if not _same(gross - required, margin):
            findings.append(f"{model_id}:scenario_only_margin_mismatch")
    else:
        decay = _num(result.get("decay_pct"))
        if decay is None or decay < 0:
            findings.append(f"{model_id}:incremental_hurdle_decay_invalid")
        elif not _same(gross - required - decay, margin):
            findings.append(f"{model_id}:incremental_hurdle_margin_mismatch")
        if excludes_decay is not False:
            findings.append(f"{model_id}:incremental_hurdle_must_include_decay_in_base_margin")
    return findings


def _validate_owner_earnings_normalization(model_id: str, model: dict[str, Any]) -> list[str]:
    bridge = model.get("normalization_bridge") or {}
    findings: list[str] = []
    try:
        window = int(bridge.get("normalization_window_years"))
    except (TypeError, ValueError):
        window = 0
    if window < 3:
        findings.append(f"{model_id}:normalization_window_too_short")
    for field in ("maintenance_capex_treatment", "working_capital_treatment"):
        if not str(bridge.get(field) or "").strip():
            findings.append(f"{model_id}:{field}_missing")
    return findings


def _validate_holding_period_return_bridge(model_id: str, model: dict[str, Any]) -> list[str]:
    bridge = model.get("holding_period_return_bridge")
    if not isinstance(bridge, dict):
        return [f"{model_id}:holding_period_return_bridge_missing"]
    findings: list[str] = []
    years = _num(bridge.get("years"))
    entry = _num(bridge.get("entry_price"))
    dividend = _num(bridge.get("annual_dividend_per_share"))
    if years is None or years < 1 or not float(years).is_integer():
        findings.append(f"{model_id}:holding_period_years_invalid")
    if entry is None or entry <= 0 or dividend is None or dividend < 0:
        findings.append(f"{model_id}:holding_period_inputs_invalid")
    rows = bridge.get("scenarios")
    if not isinstance(rows, list) or len(rows) < 3:
        findings.append(f"{model_id}:holding_period_scenarios_insufficient")
        return findings
    roles: set[str] = set()
    base_irr: float | None = None
    for index, row in enumerate(rows):
        prefix = f"{model_id}:holding_period_scenarios[{index}]"
        if not isinstance(row, dict):
            findings.append(prefix + ":invalid")
            continue
        role = str(row.get("role") or "").strip()
        terminal = _num(row.get("terminal_price"))
        irr_pct = _num(row.get("irr_pct"))
        scenario_dividend = _num(row.get("annual_dividend_per_share"))
        if scenario_dividend is None:
            scenario_dividend = dividend
        if role not in {"downside", "base", "upside"}:
            findings.append(prefix + ":role_invalid")
        else:
            roles.add(role)
        if None in {terminal, irr_pct} or terminal < 0 or irr_pct <= -100:
            findings.append(prefix + ":inputs_invalid")
            continue
        if scenario_dividend is not None and scenario_dividend < 0:
            findings.append(prefix + ":dividend_invalid")
            continue
        if years is not None and entry is not None and scenario_dividend is not None:
            rate = irr_pct / 100.0
            npv = -entry + sum(scenario_dividend / ((1 + rate) ** t) for t in range(1, int(years) + 1))
            npv += terminal / ((1 + rate) ** int(years))
            if abs(npv) > max(0.005, entry * 0.005):
                findings.append(prefix + ":irr_arithmetic_mismatch")
        if role == "base":
            base_irr = irr_pct
    if roles != {"downside", "base", "upside"}:
        findings.append(f"{model_id}:holding_period_roles_incomplete")
    result_return = _num((model.get("result") or {}).get("gross_return_pct"))
    if base_irr is None or result_return is None or not _same(base_irr, result_return, tolerance=5e-3):
        findings.append(f"{model_id}:holding_period_base_return_mismatch")
    if not isinstance(bridge.get("source_ids"), list) or not bridge.get("source_ids"):
        findings.append(f"{model_id}:holding_period_source_ids_missing")
    return findings


def _active_decision_entries(output: Path) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("entry_id")): item
        for item in (_read_json(output / "decision_ledger.json").get("entries") or [])
        if isinstance(item, dict) and item.get("entry_id") and item.get("status") == "active"
    }


def _chapter_texts(report_text: str) -> dict[int, str]:
    matches = list(_CHAPTER_RE.finditer(report_text)); result: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        result[int(match.group(1))] = report_text[match.start():end]
    return result


def _route_allows(business_type: str, model_type: str) -> bool:
    allowed = {
        "bank": {"DDM", "RESIDUAL_INCOME", "RELATIVE"},
        "insurer": {"DDM", "RESIDUAL_INCOME", "SOTP", "RELATIVE"},
        "property_developer": {"NAV", "SOTP", "ASSET_VALUE", "RELATIVE"},
        "asset_holding": {"NAV", "SOTP", "ASSET_VALUE"},
        "pre_revenue_biotech": {"RNPV", "SOTP", "ASSET_VALUE"},
        "utility": {"DCF", "DDM", "EPV", "ASSET_VALUE", "RETURN_DECOMPOSITION"},
    }
    return model_type in allowed.get(business_type, MODEL_TYPES)


def validate_valuation_model_ledger(
    payload: dict[str, Any], *, output_dir: str | Path | None = None, report_text: str = "",
    enforced: bool = False, min_independent_groups: int = 2,
    min_r_g_buffer_pct: float = MIN_R_G_BUFFER_PCT,
    require_normalization_bridge: bool | None = None,
    require_decay_treatment: bool | None = None,
    require_owner_earnings_normalization: bool | None = None,
    require_holding_period_return_bridge: bool | None = None,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or "").strip(): invalid.append("report_id_missing")
    if not str(payload.get("change_reason") or "").strip(): incomplete.append("change_reason_missing")
    profile = payload.get("company_profile")
    if not isinstance(profile, dict):
        invalid.append("company_profile_invalid"); profile = {}
    business_type = str(profile.get("business_type") or "")
    if business_type not in BUSINESS_TYPES: invalid.append("business_type_invalid")
    if profile.get("asset_intensity") not in {"asset_light", "asset_heavy", "mixed"}:
        invalid.append("asset_intensity_invalid")
    if not str(profile.get("valuation_route") or "").strip(): incomplete.append("valuation_route_missing")
    if not str(profile.get("route_reasoning") or "").strip(): incomplete.append("route_reasoning_missing")

    models = payload.get("models")
    if not isinstance(models, list): invalid.append("models_not_array"); models = []
    seen: set[str] = set(); active: list[dict[str, Any]] = []
    groups: set[str] = set(); fragile_primary = False
    output = Path(output_dir) if output_dir is not None else None
    model_policy = _read_json(output / "valuation_model_policy.json") if output is not None else {}
    if require_normalization_bridge is None:
        require_normalization_bridge = bool(
            model_policy.get("require_normalization_bridge")
        )
    if require_decay_treatment is None:
        require_decay_treatment = bool(model_policy.get("require_decay_treatment"))
    if require_owner_earnings_normalization is None:
        require_owner_earnings_normalization = bool(model_policy.get("require_owner_earnings_normalization"))
    if require_holding_period_return_bridge is None:
        require_holding_period_return_bridge = bool(model_policy.get("require_holding_period_return_bridge"))
    route_policy = _read_json(output / "valuation_route_policy.json") if output is not None else {}
    route = _read_json(output / "valuation_route.json") if output is not None else {}
    route_enforced = bool(route_policy.get("enforced"))
    route_models = {
        str(item.get("route_model_id")): item for item in route.get("models") or []
        if isinstance(item, dict) and item.get("route_model_id")
    }
    rejected_route_models = {
        str(item.get("route_model_id")): item for item in route.get("rejected_models") or []
        if isinstance(item, dict) and item.get("route_model_id")
    }
    if route_enforced:
        if not route:
            incomplete.append("valuation_route_missing")
        else:
            expected_profile = route.get("legacy_company_profile") or {}
            if business_type != expected_profile.get("business_type"):
                invalid.append("company_profile_business_type_route_mismatch")
            if profile.get("asset_intensity") != expected_profile.get("asset_intensity"):
                invalid.append("company_profile_asset_intensity_route_mismatch")
            if profile.get("archetype_id") != route.get("archetype_id"):
                invalid.append("company_profile_archetype_route_mismatch")
            if profile.get("valuation_route_id") != route.get("route_id"):
                invalid.append("company_profile_route_id_mismatch")
            if profile.get("registry_version") != route.get("registry_version"):
                invalid.append("company_profile_registry_version_mismatch")
    decisions = _active_decision_entries(output) if output is not None else {}
    registry = EvidenceRegistry()
    if output is not None and output.is_dir(): registry.register_from_output_dir(str(output))
    group_assumptions: dict[str, set[str]] = {}
    chapter_texts = _chapter_texts(report_text)
    for idx, model in enumerate(models):
        prefix = f"models[{idx}]"
        if not isinstance(model, dict): invalid.append(prefix + ":not_object"); continue
        mid = str(model.get("model_id") or "").strip()
        mtype = str(model.get("model_type") or "").strip()
        role = str(model.get("role") or "").strip()
        status = str(model.get("status") or "active")
        route_model_id = str(model.get("route_model_id") or "").strip()
        if not mid: invalid.append(prefix + ":model_id_missing")
        elif mid in seen: invalid.append("duplicate_model_id:" + mid)
        seen.add(mid)
        if mtype not in MODEL_TYPES: invalid.append(f"{mid or prefix}:model_type_invalid")
        if status not in {"active", "rejected"}: invalid.append(f"{mid or prefix}:status_invalid")
        if status == "rejected":
            if role not in {*ROLES, "rejected"}: invalid.append(f"{mid or prefix}:role_invalid")
            if not str(model.get("rejection_reason") or "").strip(): incomplete.append(f"{mid}:rejection_reason_missing")
            if route_enforced:
                if route_model_id not in rejected_route_models:
                    invalid.append(f"{mid}:rejected_model_not_in_route:{route_model_id}")
                elif mtype != rejected_route_models[route_model_id].get("model_type"):
                    invalid.append(f"{mid}:rejected_model_type_route_mismatch")
            continue
        if role not in ROLES: invalid.append(f"{mid or prefix}:role_invalid")
        active.append(model)
        if route_enforced:
            routed = route_models.get(route_model_id)
            if not routed:
                invalid.append(f"{mid}:active_model_not_in_route:{route_model_id}")
            else:
                if mtype != routed.get("model_type"): invalid.append(f"{mid}:model_type_route_mismatch")
                if role != routed.get("role"): invalid.append(f"{mid}:model_role_route_mismatch")
        chapters = model.get("chapters")
        if not isinstance(chapters, list) or not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters):
            invalid.append(f"{mid}:chapters_invalid"); chapters = []
        if enforced:
            for chapter in chapters:
                if mid not in _VALUATION_REF_RE.findall(chapter_texts.get(chapter, "")):
                    incomplete.append(f"valuation_reference_missing:Ch{chapter}:{mid}")
        group = str(model.get("independence_group_id") or "").strip()
        if not group: incomplete.append(f"{mid}:independence_group_id_missing")
        else: groups.add(group)
        if route_enforced and route_model_id in route_models and group != route_models[route_model_id].get("independence_group"):
            invalid.append(f"{mid}:independence_group_route_mismatch")
        shared_ids = model.get("shared_assumption_ids")
        if not isinstance(shared_ids, list): invalid.append(f"{mid}:shared_assumption_ids_invalid"); shared_ids = []
        if group: group_assumptions.setdefault(group, set()).update(str(item) for item in shared_ids if str(item))
        if not isinstance(model.get("source_ids"), list) or not model.get("source_ids"):
            incomplete.append(f"{mid}:source_ids_missing")
        else:
            for source_id in model.get("source_ids"):
                canonical, unresolved = registry.canonicalize_anchor(str(source_id))
                if output is not None and (unresolved or not canonical): invalid.append(f"{mid}:source_unresolved:{source_id}")
        applicability = model.get("applicability")
        if not isinstance(applicability, dict): invalid.append(f"{mid}:applicability_invalid"); applicability = {}
        for key in ("business_fit", "cash_flow_fit", "capital_structure_fit", "payout_fit", "rationale"):
            if not str(applicability.get(key) or "").strip(): incomplete.append(f"{mid}:applicability_{key}_missing")
        disqualifiers = applicability.get("disqualifiers") or []
        if not isinstance(disqualifiers, list): invalid.append(f"{mid}:disqualifiers_invalid"); disqualifiers = []
        if role == "primary" and disqualifiers: invalid.append(f"{mid}:primary_model_disqualified")
        if role == "primary" and not _route_allows(business_type, mtype):
            invalid.append(f"{mid}:model_not_applicable_to_{business_type}")
        if role == "primary" and mtype == "DDM" and applicability.get("payout_fit") not in {"stable", "normalized"}:
            invalid.append(f"{mid}:ddm_payout_unfit")
        if role == "primary" and mtype == "DCF" and applicability.get("cash_flow_fit") in {"negative", "unavailable"}:
            invalid.append(f"{mid}:dcf_cash_flow_unfit")
        if role == "primary" and mtype in {"NAV", "ASSET_VALUE"} and profile.get("asset_intensity") == "asset_light" and business_type not in {"asset_holding", "property_developer"}:
            invalid.append(f"{mid}:asset_method_primary_for_asset_light_business")

        basis = model.get("basis")
        if not isinstance(basis, dict): invalid.append(f"{mid}:basis_invalid"); basis = {}
        for key in ("value_scope", "cash_flow_scope", "currency", "as_of"):
            if not str(basis.get(key) or "").strip(): invalid.append(f"{mid}:basis_{key}_missing")
        if basis.get("tax_basis") not in {"pre_tax", "post_tax", "not_applicable"}: invalid.append(f"{mid}:basis_tax_basis_invalid")
        if route_enforced and route_model_id in route_models:
            routed = route_models[route_model_id]
            for field in ("value_scope", "cash_flow_scope"):
                if basis.get(field) != routed.get(field):
                    invalid.append(f"{mid}:route_basis_mismatch:{field}")
        assumptions = model.get("assumptions")
        if not isinstance(assumptions, dict):
            invalid.append(f"{mid}:assumptions_invalid")
            assumptions = {}
        rate = assumptions.get("discount_rate") or {}
        growth = assumptions.get("terminal_growth") or {}
        if not isinstance(rate, dict):
            invalid.append(f"{mid}:discount_rate_invalid")
            rate = {}
        if not isinstance(growth, dict):
            invalid.append(f"{mid}:terminal_growth_invalid")
            growth = {}
        if route_enforced and route_model_id in route_models:
            required_rate_kind = route_models[route_model_id].get("discount_rate_kind")
            if required_rate_kind in {"WACC", "cost_of_equity"} and rate.get("kind") != required_rate_kind:
                invalid.append(f"{mid}:discount_rate_kind_route_mismatch")
        if mtype == "DCF" and basis.get("cash_flow_scope") == "FCFF" and (basis.get("value_scope") != "enterprise" or rate.get("kind") != "WACC"):
            invalid.append(f"{mid}:fcff_requires_enterprise_wacc")
        if mtype == "DCF" and basis.get("cash_flow_scope") == "FCFE" and (basis.get("value_scope") != "equity" or rate.get("kind") != "cost_of_equity"):
            invalid.append(f"{mid}:fcfe_requires_equity_cost_of_equity")
        if mtype == "DDM" and (basis.get("value_scope") != "equity" or basis.get("cash_flow_scope") != "dividend" or rate.get("kind") != "cost_of_equity"):
            invalid.append(f"{mid}:ddm_basis_mismatch")
        if mtype in _PERPETUITY_MODELS:
            for key in ("value_pct", "kind", "inflation_basis", "tax_basis"):
                if rate.get(key) in {None, ""}: incomplete.append(f"{mid}:discount_rate_{key}_missing")
        if mtype == "DCF" and _num(assumptions.get("forecast_years")) is None:
            incomplete.append(f"{mid}:forecast_years_missing")
        if role == "primary" and business_type == "cyclical" and applicability.get("cash_flow_fit") != "normalized":
            invalid.append(f"{mid}:cyclical_cash_flow_not_normalized")
        if rate and basis.get("tax_basis") and rate.get("tax_basis") != basis.get("tax_basis"):
            invalid.append(f"{mid}:tax_basis_mismatch")
        if growth and rate.get("inflation_basis") != growth.get("inflation_basis"):
            invalid.append(f"{mid}:nominal_real_mismatch")
        r, g = _num(rate.get("value_pct")), _num(growth.get("value_pct"))
        if mtype in _PERPETUITY_MODELS and growth:
            if r is None or g is None: incomplete.append(f"{mid}:r_or_g_missing")
            elif r <= g: invalid.append(f"{mid}:r_not_greater_than_g")
            elif r - g < min_r_g_buffer_pct:
                if role == "primary": invalid.append(f"{mid}:r_g_buffer_too_small:{r-g:.2f}pp")
                else: warnings.append(f"{mid}:r_g_buffer_small:{r-g:.2f}pp")

        result = model.get("result")
        if not isinstance(result, dict): invalid.append(f"{mid}:result_invalid"); result = {}
        value = _num(result.get("value_per_share"))
        if value is None or value <= 0: invalid.append(f"{mid}:value_per_share_invalid")
        if role == "primary" and mtype == "EPV" and require_normalization_bridge:
            invalid.extend(_validate_normalization_bridge(mid, model, basis, result))
        if role == "primary" and mtype == "EPV" and require_owner_earnings_normalization:
            invalid.extend(_validate_owner_earnings_normalization(mid, model))
        if role == "primary" and mtype == "RETURN_DECOMPOSITION" and require_decay_treatment:
            invalid.extend(_validate_decay_treatment(mid, model, result))
        if role == "primary" and mtype == "RETURN_DECOMPOSITION" and require_holding_period_return_bridge:
            invalid.extend(_validate_holding_period_return_bridge(mid, model))
        bridge = model.get("equity_bridge")
        if basis.get("value_scope") == "enterprise":
            if not isinstance(bridge, dict): invalid.append(f"{mid}:enterprise_equity_bridge_missing")
        if isinstance(bridge, dict):
            required = ["enterprise_value", "non_operating_assets", "debt", "minority_interest", "other_adjustments", "equity_value", "shares", "per_share_value"]
            if any(_num(bridge.get(key)) is None for key in required): invalid.append(f"{mid}:equity_bridge_fields_invalid")
            else:
                expected = _num(bridge["enterprise_value"]) + _num(bridge["non_operating_assets"]) - _num(bridge["debt"]) - _num(bridge["minority_interest"]) + _num(bridge["other_adjustments"])
                if not _same(expected, bridge["equity_value"]): invalid.append(f"{mid}:enterprise_to_equity_bridge_mismatch")
                if not _same(_num(bridge["equity_value"]) / _num(bridge["shares"]), bridge["per_share_value"], tolerance=5e-3): invalid.append(f"{mid}:per_share_bridge_mismatch")
                if value is not None and not _same(value, bridge["per_share_value"]):
                    realization = model.get("value_realization_bridge")
                    if not isinstance(realization, dict):
                        invalid.append(f"{mid}:result_bridge_mismatch")
                    else:
                        gross = _num(realization.get("gross_per_share"))
                        payout = _num(realization.get("payout_ratio"))
                        retained = _num(realization.get("retained_value_realization"))
                        realized = _num(realization.get("realized_per_share"))
                        if None in {gross, payout, retained, realized} or not (
                            0 <= payout <= 1 and 0 <= retained <= 1
                        ):
                            invalid.append(f"{mid}:value_realization_bridge_invalid")
                        else:
                            if (
                                not str(bridge.get("currency") or "").strip()
                                or bridge.get("currency") != basis.get("currency")
                            ):
                                invalid.append(f"{mid}:value_realization_bridge_currency_mismatch")
                            if not isinstance(realization.get("payout_source_ids"), list) or not realization.get("payout_source_ids"):
                                incomplete.append(f"{mid}:value_realization_payout_source_missing")
                            if not _same(gross, bridge["per_share_value"]):
                                invalid.append(f"{mid}:value_realization_gross_mismatch")
                            assumption_retained = _num(
                                assumptions.get("retained_value_realization")
                            )
                            if assumption_retained is None or not _same(retained, assumption_retained):
                                invalid.append(f"{mid}:value_realization_parameter_mismatch")
                            expected_realized = gross * (
                                payout + retained * (1 - payout)
                            )
                            if not _same(expected_realized, realized) or not _same(realized, value):
                                invalid.append(f"{mid}:value_realization_arithmetic_mismatch")
        terminal = model.get("terminal_value") or {}
        share = _num(terminal.get("share_pct"))
        tests = model.get("sensitivity_tests") or []
        if mtype in _PERPETUITY_MODELS:
            if share is None: incomplete.append(f"{mid}:terminal_share_missing")
            terminal_pv, total_value = _num(terminal.get("present_value")), _num(terminal.get("total_model_value"))
            if terminal_pv is None or total_value is None or total_value <= 0:
                incomplete.append(f"{mid}:terminal_value_components_missing")
            elif share is not None and not _same(terminal_pv / total_value * 100, share, tolerance=1e-3):
                invalid.append(f"{mid}:terminal_share_mismatch")
            if not isinstance(tests, list): invalid.append(f"{mid}:sensitivity_tests_invalid"); tests = []
            case_ids = {str(item.get("case_id")) for item in tests if isinstance(item, dict)}
            for required_case in ("discount_rate_up_1pp", "growth_down_1pp", "combined_stress"):
                if required_case not in case_ids: incomplete.append(f"{mid}:sensitivity_case_missing:{required_case}")
            base_action = str((payload.get("synthesis") or {}).get("action") or "")
            flips = [item for item in tests if isinstance(item, dict) and item.get("action") in ACTIONS and item.get("action") != base_action]
            if role == "primary" and ((share is not None and share > HIGH_TERMINAL_SHARE_PCT) or flips):
                fragile_primary = True
                warnings.append(f"{mid}:fragile_primary_model")
                if not str(model.get("fragility_mitigation") or "").strip():
                    incomplete.append(f"{mid}:fragility_mitigation_missing")

        refs = model.get("decision_entry_ids")
        if enforced and (not isinstance(refs, list) or not refs): incomplete.append(f"{mid}:decision_entry_ids_missing")
        for ref in refs or []:
            if output is not None and str(ref) not in decisions: invalid.append(f"{mid}:unknown_decision_entry:{ref}")

    primary = [m for m in active if m.get("role") == "primary"]
    if route_enforced:
        submitted_rejected = {
            str(item.get("route_model_id")) for item in models
            if isinstance(item, dict) and item.get("status") == "rejected"
        }
        for route_model_id in sorted(set(rejected_route_models) - submitted_rejected):
            incomplete.append("routed_rejection_not_recorded:" + route_model_id)
    known_model_ids = {str(m.get("model_id")) for m in models if isinstance(m, dict)}
    for ref in sorted(set(_VALUATION_REF_RE.findall(report_text)) - known_model_ids): invalid.append("unknown_valuation_reference:" + ref)
    if enforced and not primary: incomplete.append("primary_model_missing")
    if primary and all(m.get("model_type") == "RELATIVE" for m in primary): invalid.append("relative_valuation_cannot_be_sole_primary")
    if enforced and len(groups) < min_independent_groups:
        incomplete.append(f"independent_model_groups_insufficient:{len(groups)}/{min_independent_groups}")
    group_names = sorted(group_assumptions)
    for i, left in enumerate(group_names):
        for right in group_names[i + 1:]:
            lset, rset = group_assumptions[left], group_assumptions[right]
            if lset and lset == rset:
                invalid.append(f"false_independence_shared_assumptions:{left}:{right}")
            elif lset and rset and len(lset & rset) / min(len(lset), len(rset)) >= 0.75:
                # Dependence is itself useful disclosure.  It becomes a hard
                # failure only when the comparison ledger mislabels the pair
                # as independent corroboration (checked by decision reliability).
                # Other genuinely independent groups must not be blocked merely
                # because an extra diagnostic model shares most inputs.
                warnings.append(f"model_groups_highly_dependent:{left}:{right}")
    if fragile_primary and len(groups) < 2:
        incomplete.append("fragile_primary_without_independent_corroboration")

    synthesis = payload.get("synthesis")
    if not isinstance(synthesis, dict): invalid.append("synthesis_invalid"); synthesis = {}
    action = str(synthesis.get("action") or "")
    if action not in ACTIONS: invalid.append("synthesis_action_invalid")
    chosen = _num(synthesis.get("chosen_value_per_share")); low = _num(synthesis.get("range_low")); high = _num(synthesis.get("range_high"))
    if None in {chosen, low, high} or not (low <= chosen <= high): invalid.append("synthesis_value_range_invalid")
    if not str(synthesis.get("decision_rule") or "").strip(): incomplete.append("synthesis_decision_rule_missing")
    values = [_num((m.get("result") or {}).get("value_per_share")) for m in active]
    values = [v for v in values if v is not None and v > 0]
    primary_values = {
        str(m.get("model_id")): _num((m.get("result") or {}).get("value_per_share"))
        for m in active if m.get("role") == "primary"
    }
    active_values = {
        str(m.get("model_id")): _num((m.get("result") or {}).get("value_per_share"))
        for m in active
    }
    if chosen is not None and not any(_same(chosen, value) for value in primary_values.values()):
        synthesis_bridge = synthesis.get("value_realization_bridge")
        if not isinstance(synthesis_bridge, dict):
            invalid.append("synthesis_not_reconciled_to_primary_model")
        else:
            method = str(synthesis_bridge.get("method") or "")
            output_value = _num(synthesis_bridge.get("output_value_per_share"))
            if output_value is None or not _same(output_value, chosen):
                invalid.append("synthesis_bridge_output_mismatch")
            elif method == "weighted_average":
                inputs = synthesis_bridge.get("inputs") or []
                weighted = 0.0; weight_sum = 0.0; usable = True
                for row in inputs if isinstance(inputs, list) else []:
                    model_id = str((row or {}).get("model_id") or "")
                    weight = _num((row or {}).get("weight"))
                    model_value = active_values.get(model_id)
                    if weight is None or model_value is None or weight < 0:
                        usable = False; break
                    weighted += weight * model_value; weight_sum += weight
                if not usable or not _same(weight_sum, 1.0) or not _same(weighted, chosen):
                    invalid.append("synthesis_weighted_bridge_arithmetic_mismatch")
            elif method == "retained_value_realization":
                model_id = str(synthesis_bridge.get("gross_model_id") or "")
                gross = _num(synthesis_bridge.get("gross_per_share"))
                payout = _num(synthesis_bridge.get("payout_ratio"))
                retained = _num(synthesis_bridge.get("retained_value_realization"))
                if (
                    primary_values.get(model_id) is None
                    or not _same(gross, primary_values.get(model_id))
                    or None in {gross, payout, retained}
                    or not (0 <= payout <= 1 and 0 <= retained <= 1)
                    or not _same(gross * (payout + retained * (1 - payout)), chosen)
                ):
                    invalid.append("synthesis_realization_bridge_arithmetic_mismatch")
                if not isinstance(synthesis_bridge.get("payout_source_ids"), list) or not synthesis_bridge.get("payout_source_ids"):
                    incomplete.append("synthesis:value_realization_payout_source_missing")
            elif method == "separate_value_components":
                # EPV is the value of the existing earning machine.  Missing
                # proof of high-return retention can eliminate only the
                # incremental growth component; it must not make the whole
                # operating value dividend-only.  Cash remains zero here until
                # it is reconciled separately to the audited cash bridge.
                model_id = str(synthesis_bridge.get("operating_model_id") or "")
                operating = _num(synthesis_bridge.get("operating_value_per_share"))
                retained_growth = _num(synthesis_bridge.get("retained_growth_per_share"))
                realization = _num(synthesis_bridge.get("retained_growth_realization"))
                accessible_cash = _num(synthesis_bridge.get("accessible_cash_per_share"))
                if (
                    primary_values.get(model_id) is None
                    or not _same(operating, primary_values.get(model_id))
                    or None in {operating, retained_growth, realization, accessible_cash}
                    or retained_growth < 0
                    or not 0 <= realization <= 1
                    or not _same(accessible_cash, 0.0)
                    or not _same(operating + retained_growth * realization, chosen)
                ):
                    invalid.append("synthesis_separate_components_bridge_arithmetic_mismatch")
                elif retained_growth > 0 and not (
                    isinstance(synthesis_bridge.get("growth_source_ids"), list)
                    and synthesis_bridge.get("growth_source_ids")
                ):
                    incomplete.append("synthesis:retained_growth_source_missing")
            else:
                invalid.append("synthesis_bridge_method_invalid")
    if len(values) >= 2 and max(values) / min(values) >= 2 and not str(synthesis.get("divergence_explanation") or "").strip():
        incomplete.append("model_divergence_unexplained")
    if output is not None:
        manifest = _read_json(output / "decision_manifest.json")
        if manifest and action != manifest.get("quantitative_decision"): invalid.append("synthesis_manifest_action_mismatch")
        if manifest and not _same(synthesis.get("position_pct"), manifest.get("position_pct")): invalid.append("synthesis_manifest_position_mismatch")
        ref = str(synthesis.get("decision_entry_id") or "")
        entry = decisions.get(ref)
        if enforced and not ref: incomplete.append("synthesis_decision_entry_missing")
        elif ref and entry is None: invalid.append("synthesis_unknown_decision_entry")
        elif entry and entry.get("metric_id") != "valuation.v_final": invalid.append("synthesis_decision_entry_not_v_final")
        elif entry and chosen is not None and not _same(chosen, entry.get("value")): invalid.append("synthesis_v_final_mismatch")

    frozen = bool((payload.get("freeze") or {}).get("frozen"))
    if frozen and (payload.get("freeze") or {}).get("fingerprint") != valuation_fingerprint(payload): invalid.append("freeze_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING" if payload.get("lifecycle") == "monitoring" else "DECISION_READY" if frozen else "REVIEWABLE"
    return {"schema_version": "valuation-model-validation.v1", "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings, "active_model_ids": [m.get("model_id") for m in active], "independent_groups": sorted(groups), "enforced": bool(enforced)}


def record_rejected_valuation_candidate(
    output_dir: str | Path, payload: dict[str, Any], *, report_text: str = "",
    structural_validation: dict[str, Any] | None = None,
    reliability_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep the best complete non-authoritative valuation repair candidate."""
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    policy = _read_json(output / "valuation_model_policy.json")

    def assessed(candidate: dict[str, Any]) -> dict[str, Any]:
        try:
            from scripts.decision_reliability import validate_decision_reliability
        except ModuleNotFoundError:
            from decision_reliability import validate_decision_reliability
        structural = structural_validation if candidate is payload and structural_validation else validate_valuation_model_ledger(
            candidate, output_dir=output, report_text=report_text,
            enforced=bool(policy.get("enforced")),
            min_independent_groups=int(policy.get("min_independent_groups") or 2),
            min_r_g_buffer_pct=float(policy.get("min_r_g_buffer_pct") or MIN_R_G_BUFFER_PCT),
        )
        reliability = reliability_validation if candidate is payload and reliability_validation else validate_decision_reliability(
            output, report_text=report_text, enforced=True, valuation_override=candidate,
        )
        model_count = len(candidate.get("models") or []) if isinstance(candidate, dict) else 0
        section_count = sum(bool(candidate.get(key)) for key in (
            "company_profile", "models", "synthesis", "cash_access_bridge",
            "parameter_calibrations", "model_comparisons", "joint_stress_tests", "action_policy",
        )) if isinstance(candidate, dict) else 0
        structural_invalid = list(structural.get("invalid_findings") or [])
        structural_incomplete = list(structural.get("incomplete_findings") or [])
        reliability_invalid = list(reliability.get("invalid_findings") or [])
        reliability_incomplete = list(reliability.get("incomplete_findings") or [])
        decision_revision = {
            "synthesis_manifest_action_mismatch",
            "synthesis_manifest_position_mismatch",
            "synthesis_v_final_mismatch",
        }
        substantive_count = (
            sum(item not in decision_revision for item in structural_invalid)
            + len(structural_incomplete)
            + len(reliability_invalid)
            + len(reliability_incomplete)
        )
        return {
            "schema_version": "valuation-rejected-candidate.v1", "candidate": candidate,
            "structural_validation": structural, "reliability_validation": reliability,
            "score": [
                0 if model_count else 1, 8 - section_count, substantive_count,
                len(reliability_invalid) + len(reliability_incomplete),
                sum(item in decision_revision for item in structural_invalid),
                len(structural_invalid) + len(structural_incomplete),
            ],
        }

    latest = assessed(payload)
    best_path = output / "valuation_model_best_rejected.json"
    best = _read_json(best_path)
    best_candidate = best.get("candidate") if isinstance(best.get("candidate"), dict) else {}
    prior = assessed(best_candidate) if best_candidate else {}
    winner = latest if not prior or tuple(latest["score"]) < tuple(prior["score"]) else prior
    (output / "valuation_model_last_rejected.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "valuation_model_last_rejected_validation.json").write_text(json.dumps(latest["structural_validation"], ensure_ascii=False, indent=2), encoding="utf-8")
    best_path.write_text(json.dumps(winner, ensure_ascii=False, indent=2), encoding="utf-8")
    return winner


def persist_valuation_model_ledger(output_dir: str | Path, payload: dict[str, Any], *, report_text: str = "", allow_frozen_update: bool = False) -> dict[str, Any]:
    output = Path(output_dir); output.mkdir(parents=True, exist_ok=True)
    path = output / "valuation_model.json"; diff_path = output / "valuation_model_diff.json"
    old = _read_json(path); policy = _read_json(output / "valuation_model_policy.json")
    validation = validate_valuation_model_ledger(payload, output_dir=output, report_text=report_text, enforced=bool(policy.get("enforced")), min_independent_groups=int(policy.get("min_independent_groups") or 2), min_r_g_buffer_pct=float(policy.get("min_r_g_buffer_pct") or MIN_R_G_BUFFER_PCT))
    if validation["state"] == "INVALID" or (validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen"))):
        record_rejected_valuation_candidate(
            output, payload, report_text=report_text,
            structural_validation=validation,
        )
        return {"written": False, "path": str(path), "validation": validation, "error": "invalid or incomplete valuation model cannot be frozen"}
    changed = bool(old) and valuation_fingerprint(old) != valuation_fingerprint(payload)
    diff = {"schema_version": "valuation-model-diff.v1", "generated_at": _now(), "old_fingerprint": valuation_fingerprint(old) if old else None, "new_fingerprint": valuation_fingerprint(payload), "change_reason": payload.get("change_reason"), "before": old.get("synthesis") if old else None, "after": payload.get("synthesis")}
    if old and bool((old.get("freeze") or {}).get("frozen")) and changed and not allow_frozen_update:
        diff["status"] = "REJECTED_FROZEN"; diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "diff_path": str(diff_path), "valuation_frozen": True, "validation": validation, "error": "frozen valuation model rejected update"}
    diff["status"] = "NO_CHANGE" if old and not changed else "APPLIED" if old else "INITIALIZED"
    ledger = old if old and not changed else payload
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"); diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path), "diff_path": str(diff_path), "ledger": ledger, "validation": validation, "diff": diff}


def evaluate_output_valuation_model(output_dir: str | Path, *, report_text: str = "", persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir); policy = _read_json(output / "valuation_model_policy.json"); ledger = _read_json(output / "valuation_model.json")
    enforced = bool(policy.get("enforced"))
    if not ledger:
        state = "INCOMPLETE" if enforced else "SKIP"
        result = {"schema_version": "valuation-model-validation.v1", "state": state, "status": "FAIL" if enforced else "SKIP", "invalid_findings": [], "incomplete_findings": ["valuation_model_missing"] if enforced else [], "warnings": [], "enforced": enforced, "policy": policy}
    else:
        result = validate_valuation_model_ledger(ledger, output_dir=output, report_text=report_text, enforced=enforced, min_independent_groups=int(policy.get("min_independent_groups") or 2), min_r_g_buffer_pct=float(policy.get("min_r_g_buffer_pct") or MIN_R_G_BUFFER_PCT)); result["policy"] = policy
    if persist: (output / "valuation_model_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
