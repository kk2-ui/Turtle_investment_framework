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
ACTIONS = {"buy", "hold", "avoid", "unresolved"}
MIN_R_G_BUFFER_PCT = 3.0
HIGH_TERMINAL_SHARE_PCT = 70.0
_PERPETUITY_MODELS = {"DCF", "DDM", "EPV", "RNPV"}
_VALUATION_REF_RE = re.compile(r"\[valuation:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.MULTILINE)
_VALUE_BRIDGE_BEGIN = "<!-- TURTLE:VALUE_BRIDGE_BLOCK:BEGIN -->"
_VALUE_BRIDGE_END = "<!-- TURTLE:VALUE_BRIDGE_BLOCK:END -->"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _mapping(value: Any) -> dict[str, Any]:
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
    compiled_bridges = payload.get("value_bridge_models")
    if isinstance(compiled_bridges, dict):
        try:
            from scripts.valuation_value_bridges import validate_valuation_value_bridges
        except ModuleNotFoundError:
            from valuation_value_bridges import validate_valuation_value_bridges
        bridge_validation = validate_valuation_value_bridges(compiled_bridges)
        if bridge_validation.get("state") != "VALID":
            raise ValueError(
                "value_bridge_reader_binding_invalid:"
                + ",".join(bridge_validation.get("findings") or [])
            )
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
    bridge_surface = _mapping(payload.get("value_bridge_models"))
    conclusions = bridge_surface.get("reader_conclusions")
    slots = bridge_surface.get("reader_slots")
    value_bridge_bound = False
    reader_rows_by_chapter: dict[int, list[str]] = {}
    if isinstance(conclusions, list) and conclusions:
        if not all(isinstance(item, str) and item.strip() for item in conclusions):
            raise ValueError("value_bridge_reader_binding_invalid:reader_conclusions_invalid")
        reader_rows_by_chapter[12] = [item.strip() for item in conclusions]
    if isinstance(slots, list):
        for index, raw_slot in enumerate(slots):
            slot = _mapping(raw_slot)
            chapter = slot.get("target_chapter")
            sentence = slot.get("sentence")
            if (
                not isinstance(chapter, int)
                or isinstance(chapter, bool)
                or not isinstance(sentence, str)
                or not sentence.strip()
            ):
                raise ValueError(
                    f"value_bridge_reader_binding_invalid:reader_slots[{index}]_invalid"
                )
            reader_rows_by_chapter.setdefault(chapter, []).append(sentence.strip())

    for chapter, raw_rows in sorted(reader_rows_by_chapter.items()):
        value_path = chapter_dir / f"_ch{chapter:02d}.md"
        if not value_path.is_file():
            raise ValueError(
                f"value_bridge_reader_binding_invalid:target_chapter_missing:{chapter}"
            )
        rows = list(dict.fromkeys(raw_rows))
        body = "\n".join("- " + item for item in rows)
        protected = (
            _VALUE_BRIDGE_BEGIN
            + "\n### 价值桥的确定性结论\n\n"
            + body
            + "\n"
            + _VALUE_BRIDGE_END
        )
        text = value_path.read_text(encoding="utf-8")
        pattern = re.compile(
            re.escape(_VALUE_BRIDGE_BEGIN)
            + r"[\s\S]*?"
            + re.escape(_VALUE_BRIDGE_END)
        )
        rebound = (
            pattern.sub(protected, text)
            if pattern.search(text)
            else text.rstrip() + "\n\n" + protected + "\n"
        )
        if rebound != text:
            value_path.write_text(rebound, encoding="utf-8")
            changed.append(chapter)
        value_bridge_bound = True
    return {
        "changed_chapters": sorted(set(changed)),
        "anchors_inserted": sum(map(len, additions.values())),
        "value_bridge_conclusions_bound": value_bridge_bound,
        "reader_slots_bound": len(slots) if isinstance(slots, list) else 0,
    }


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
    require_value_bridge_models: bool = False,
    require_value_bridge_fact_bindings: bool = False,
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
        "require_value_bridge_models": bool(require_value_bridge_models),
        "require_value_bridge_fact_bindings": bool(require_value_bridge_fact_bindings),
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
    value_bridge_inputs: dict[str, Any] | None = None,
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
    if value_bridge_inputs:
        try:
            from scripts.valuation_value_bridges import compile_valuation_value_bridges
        except ModuleNotFoundError:
            from valuation_value_bridges import compile_valuation_value_bridges
        payload["value_bridge_models"] = compile_valuation_value_bridges(
            value_bridge_inputs
        )
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
    if left is None and right is None:
        return True
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


def _validate_cash_component_contract(
    *,
    payload: dict[str, Any],
    cash_result: dict[str, Any],
    cash_projection: dict[str, Any],
    active_models: list[dict[str, Any]],
    invalid: list[str],
    incomplete: list[str],
) -> None:
    """Prove that canonical cash enters ordinary-share value exactly once."""
    component_specs = (
        (
            "existing_excess_cash",
            "cash.existing_excess_cash_per_share",
        ),
        (
            "related_party_receivables",
            "cash.related_party_receivable_per_share",
        ),
    )
    component_amounts = {
        claim_id: _num(_mapping(cash_projection.get(projection_key)).get("adopted_per_share"))
        for projection_key, claim_id in component_specs
    }
    expected_ids = sorted(
        claim_id for claim_id, amount in component_amounts.items()
        if amount is not None and amount > 0
    )
    recognized = sum(component_amounts[claim_id] or 0.0 for claim_id in expected_ids)
    if recognized <= 0:
        return

    synthesis = _mapping(payload.get("synthesis"))
    contract = synthesis.get("cash_component_contract")
    if not isinstance(contract, dict):
        incomplete.append("cash_component_contract_missing")
        return
    allowed_fields = {
        "cash_model_id", "company_id", "operating_model_id", "position_as_of",
        "ordinary_share_claim_scope", "valuation_currency",
        "fx_source_per_valuation_currency", "shares", "component_claim_ids",
        "inclusion_location", "canonical_adopted_per_share",
        "primary_equity_bridge_cash_component_per_share",
        "separate_component_per_share",
    }
    if set(contract) - allowed_fields:
        invalid.append("cash_component_contract_unknown_fields")

    operating_model_id = str(contract.get("operating_model_id") or "")
    operating_model = next(
        (
            model for model in active_models
            if str(model.get("model_id") or "") == operating_model_id
        ),
        None,
    )
    if operating_model is None:
        invalid.append("cash_component_contract_operating_model_not_active")
        return
    basis = _mapping(operating_model.get("basis"))
    equity_bridge = _mapping(operating_model.get("equity_bridge"))
    submitted_ids = contract.get("component_claim_ids")
    if not isinstance(submitted_ids, list) or sorted(submitted_ids) != expected_ids:
        invalid.append("cash_component_contract_claim_ids_mismatch")
    identity_checks = {
        "cash_model_id": cash_result.get("model_id"),
        "company_id": cash_projection.get("company_id"),
        "operating_model_id": cash_projection.get("operating_model_id"),
        "position_as_of": cash_projection.get("position_as_of"),
        "ordinary_share_claim_scope": cash_projection.get("ordinary_share_claim_scope"),
        "valuation_currency": cash_projection.get("valuation_currency"),
    }
    for field, expected in identity_checks.items():
        if contract.get(field) != expected:
            invalid.append("cash_component_contract_" + field + "_mismatch")
    if not _same(
        contract.get("fx_source_per_valuation_currency"),
        cash_projection.get("fx_source_per_valuation_currency"),
    ):
        invalid.append("cash_component_contract_fx_mismatch")
    if not _same(contract.get("shares"), cash_projection.get("shares")):
        invalid.append("cash_component_contract_shares_mismatch")
    if basis.get("currency") != cash_projection.get("valuation_currency"):
        invalid.append("cash_component_contract_operating_currency_mismatch")
    if basis.get("as_of") != cash_projection.get("position_as_of"):
        invalid.append("cash_component_contract_operating_as_of_mismatch")
    if equity_bridge.get("currency") != cash_projection.get("valuation_currency"):
        invalid.append("cash_component_contract_equity_bridge_currency_mismatch")
    if equity_bridge.get("ordinary_share_claim_scope") != cash_projection.get(
        "ordinary_share_claim_scope"
    ):
        invalid.append("cash_component_contract_equity_scope_mismatch")
    if not _same(equity_bridge.get("shares"), cash_projection.get("shares")):
        invalid.append("cash_component_contract_equity_shares_mismatch")
    if not _same(contract.get("canonical_adopted_per_share"), recognized):
        invalid.append("cash_component_contract_canonical_amount_mismatch")

    primary_amount = _num(
        contract.get("primary_equity_bridge_cash_component_per_share")
    )
    separate_amount = _num(contract.get("separate_component_per_share"))
    equity_cash_amount = _num(equity_bridge.get("cash_component_per_share"))
    equity_cash_ids = equity_bridge.get("cash_component_claim_ids")
    location = str(contract.get("inclusion_location") or "")
    if None in {primary_amount, separate_amount, equity_cash_amount}:
        invalid.append("cash_component_contract_amounts_invalid")
        return
    if not _same(primary_amount + separate_amount, recognized):
        invalid.append("cash_component_contract_single_inclusion_mismatch")

    # A declared scalar cannot prove that cash actually enters (or stays out
    # of) the equity bridge.  Reconcile the bridge's non-operating-assets line
    # to named components, so a cash claim cannot be asserted beside an
    # unrelated aggregate total.
    non_operating_assets = _num(equity_bridge.get("non_operating_assets"))
    asset_components = equity_bridge.get("non_operating_asset_components")
    if non_operating_assets is None or not isinstance(asset_components, list):
        incomplete.append("cash_component_contract_non_operating_asset_components_missing")
        return
    component_total = 0.0
    cash_component_total = 0.0
    cash_component_ids: list[str] = []
    component_valid = True
    for index, raw_component in enumerate(asset_components):
        component = _mapping(raw_component)
        if set(component) - {"component_id", "kind", "amount", "claim_ids"}:
            invalid.append(
                "cash_component_contract_non_operating_asset_component_unknown_fields"
            )
            component_valid = False
            continue
        amount = _num(component.get("amount"))
        kind = str(component.get("kind") or "")
        claim_ids = component.get("claim_ids")
        if (
            not str(component.get("component_id") or "").strip()
            or amount is None
            or kind not in {"cash", "other"}
            or not isinstance(claim_ids, list)
            or not all(isinstance(item, str) and item.strip() for item in claim_ids)
        ):
            invalid.append(
                "cash_component_contract_non_operating_asset_component_invalid:"
                + str(index)
            )
            component_valid = False
            continue
        component_total += amount
        if kind == "cash":
            cash_component_total += amount
            cash_component_ids.extend(claim_ids)
    if component_valid and not _same(component_total, non_operating_assets):
        invalid.append("cash_component_contract_non_operating_assets_not_component_reconciled")

    if location == "PRIMARY_MODEL_EQUITY_BRIDGE":
        if (
            not _same(primary_amount, recognized)
            or not _same(separate_amount, 0)
            or not _same(equity_cash_amount, recognized)
            or not isinstance(equity_cash_ids, list)
            or sorted(equity_cash_ids) != expected_ids
        ):
            invalid.append("cash_component_contract_primary_inclusion_mismatch")
        if component_valid and (
            not _same(cash_component_total / float(cash_projection["shares"]), recognized)
            or sorted(cash_component_ids) != expected_ids
        ):
            invalid.append("cash_component_contract_primary_component_amount_mismatch")
    elif location == "SEPARATE_COMPONENT":
        if (
            not _same(primary_amount, 0)
            or not _same(separate_amount, recognized)
            or not _same(equity_cash_amount, 0)
            or equity_cash_ids not in ([], None)
        ):
            invalid.append("cash_component_contract_separate_inclusion_mismatch")
        if component_valid and (not _same(cash_component_total, 0) or cash_component_ids):
            invalid.append("cash_component_contract_separate_primary_cash_not_zero")
        bridge = _mapping(synthesis.get("value_realization_bridge"))
        bridge_amount = _num(bridge.get("cash_component_per_share"))
        bridge_ids = bridge.get("cash_component_claim_ids")
        if (
            bridge.get("method") != "separate_value_components"
            or not _same(bridge_amount, recognized)
            or not isinstance(bridge_ids, list)
            or sorted(bridge_ids) != expected_ids
        ):
            invalid.append("cash_component_contract_separate_component_not_claim_bound")
    else:
        invalid.append("cash_component_contract_inclusion_location_invalid")


def _active_epv_cross_check_values(
    model: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Return the only EPV range a replacement cross-check may cite.

    The replacement model may describe an EPV range for comparison, but it
    does not own that range.  It must be an exact projection of the active
    EPV model's equity bridge/result rather than a second hand-entered EPV.
    """
    findings: list[str] = []
    result = _mapping(model.get("result"))
    bridge = _mapping(model.get("equity_bridge"))
    shares = _num(bridge.get("shares"))
    low = _num(result.get("range_low"))
    high = _num(result.get("range_high"))
    if low is None or high is None:
        point = _num(result.get("value_per_share"))
        if point is None:
            point = _num(bridge.get("per_share_value"))
        low = point if low is None else low
        high = point if high is None else high
    if shares is None or shares <= 0:
        findings.append("shares_invalid")
    if low is None or high is None or low > high:
        findings.append("per_share_range_invalid")
    if findings:
        return {}, findings
    assert shares is not None and low is not None and high is not None
    return {
        "shares": shares,
        "per_share_low": low,
        "per_share_high": high,
        "equity_value_low": low * shares,
        "equity_value_high": high * shares,
    }, findings


_BRIDGE_BINDING_SKIP_KEYS = {"canonical_fact_bindings"}
_BRIDGE_BINDING_SOURCE_KEYS = {
    "source_fact_ids",
    "input_fact_ids",
    "identity_source_fact_ids",
    "evidence_ids",
}
_BRIDGE_PATH_PART_RE = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def _bridge_numeric_leaves(value: Any, prefix: str = "") -> dict[str, float]:
    """Return every submitted numeric operand, including explicit zeroes."""
    leaves: dict[str, float] = {}
    if isinstance(value, dict):
        for key, item in value.items():
            if key in _BRIDGE_BINDING_SKIP_KEYS:
                continue
            path = f"{prefix}.{key}" if prefix else str(key)
            leaves.update(_bridge_numeric_leaves(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            leaves.update(_bridge_numeric_leaves(item, f"{prefix}[{index}]"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        number = _num(value)
        if number is not None:
            leaves[prefix] = number
    return leaves


def _bridge_path_nodes(value: Any, path: str) -> list[dict[str, Any]]:
    """Return mapping ancestors for a submitted bridge operand path."""
    current: Any = value
    nodes: list[dict[str, Any]] = [current] if isinstance(current, dict) else []
    for key, index in _BRIDGE_PATH_PART_RE.findall(path):
        if key:
            if not isinstance(current, dict) or key not in current:
                return []
            current = current[key]
        else:
            if not isinstance(current, list):
                return []
            position = int(index)
            if position >= len(current):
                return []
            current = current[position]
        if isinstance(current, dict):
            nodes.append(current)
    return nodes


def _bridge_declared_evidence_ids(value: dict[str, Any], path: str) -> set[str]:
    ids: set[str] = set()
    for node in _bridge_path_nodes(value, path):
        for key in _BRIDGE_BINDING_SOURCE_KEYS:
            ids.update(
                str(item) for item in node.get(key) or []
                if isinstance(item, str) and item.strip()
            )
        for item in node.get("verified_facts") or []:
            if isinstance(item, dict) and str(item.get("status") or "").upper() == "VERIFIED":
                fact_id = str(item.get("fact_id") or "").strip()
                if fact_id:
                    ids.add(fact_id)
    return ids


def _bridge_operand_context(
    bridge_input: dict[str, Any], path: str,
) -> dict[str, str]:
    """Derive unit/date/context from the operand's owning specialist model."""
    parts = [key or index for key, index in _BRIDGE_PATH_PART_RE.findall(path)]
    if not parts:
        return {}
    wrapper_key = parts[0]
    wrapper = _mapping(bridge_input.get(wrapper_key))
    model = _mapping(wrapper.get("model_input"))
    basis = _mapping(model.get("basis"))
    leaf = str(parts[-1])
    currency = str(model.get("currency") or basis.get("currency") or "")
    unit = str(model.get("unit") or basis.get("unit") or "")
    as_of = str(model.get("position_as_of") or basis.get("as_of") or "")
    context: dict[str, str] = {
        "currency": currency,
        "unit": unit,
        "as_of": as_of,
        "cutoff_at": str(model.get("cutoff_at") or ""),
        "position_as_of": str(model.get("position_as_of") or basis.get("as_of") or ""),
        "economic_entity": str(basis.get("economic_entity") or ""),
        "operating_perimeter": str(basis.get("operating_perimeter") or ""),
    }
    if (
        leaf.endswith("rate")
        or leaf == "ordinary_share_economic_interest"
        or leaf == "fx_source_per_valuation_currency"
    ):
        context["unit"] = "ratio"
        context["currency"] = ""
    if leaf in {"shares", "shares_outstanding"}:
        context["unit"] = "million_shares"
        context["currency"] = ""
    if leaf in {"fraction_low", "fraction_high"}:
        context["unit"] = "ratio"
        context["currency"] = ""
    if (
        wrapper_key == "replacement_value"
        and (
            ".epv_cross_check.per_share_" in path
            or ".liquidation_floor_reference.per_share_" in path
        )
    ):
        context["unit"] = f"{currency}_per_share" if currency else "per_share"
    if wrapper_key == "cash_accessibility":
        if ".model_input.realization_periods[" in path:
            period_match = re.match(
                r"cash_accessibility\.model_input\.realization_periods\[(\d+)\]",
                path,
            )
            periods = model.get("realization_periods") or []
            period = (
                periods[int(period_match.group(1))]
                if period_match and int(period_match.group(1)) < len(periods)
                else {}
            )
            if isinstance(period, dict):
                if ".extraordinary_events[" in path:
                    event_match = re.search(r"\.extraordinary_events\[(\d+)\]", path)
                    events = period.get("extraordinary_events") or []
                    event = (
                        events[int(event_match.group(1))]
                        if event_match and int(event_match.group(1)) < len(events)
                        else {}
                    )
                    context["temporal_role"] = "EVENT"
                    if isinstance(event, dict):
                        context["event_date"] = str(event.get("event_date") or "")
                        context["observed_at"] = str(event.get("observed_at") or "")
                        context["as_of"] = context["event_date"]
                    context["post_position_event_required"] = "false"
                elif leaf == "opening_existing_excess_cash":
                    context["temporal_role"] = "POSITION_AS_OF"
                    context["as_of"] = str(
                        period.get("opening_position_as_of") or ""
                    )
                else:
                    context["temporal_role"] = "HISTORICAL_PERIOD"
                    context["period_start"] = str(period.get("period_start") or "")
                    context["period_end"] = str(period.get("period_end") or "")
                    context["as_of"] = context["period_end"]
        elif ".model_input.related_party_receivables[" in path and path.endswith(
            ".post_position_collections"
        ):
            context["temporal_role"] = "EVENT"
            context["as_of"] = ""
            context["post_position_event_required"] = "true"
        else:
            context["temporal_role"] = "POSITION_AS_OF"
    # Working-capital observations must be period-specific, not copied from
    # the model's latest balance-sheet date.
    match = re.match(r"working_capital\.model_input\.periods\[(\d+)\]", path)
    if match:
        periods = model.get("periods") or []
        period = periods[int(match.group(1))] if int(match.group(1)) < len(periods) else {}
        if isinstance(period, dict):
            context["period_start"] = str(period.get("period_start") or "")
            context["period_end"] = str(period.get("period_end") or "")
            context["as_of"] = context["period_end"] or as_of
        cohort_match = re.search(r"\.cohorts\[(\d+)\]", path)
        if cohort_match and isinstance(period, dict):
            cohorts = period.get("cohorts") or []
            cohort = cohorts[int(cohort_match.group(1))] if int(cohort_match.group(1)) < len(cohorts) else {}
            if isinstance(cohort, dict):
                context["cohort_id"] = str(cohort.get("cohort_id") or "")
    return context


def _bridge_date(value: Any) -> Any:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _validate_bridge_observation_temporal_contract(
    *,
    prefix: str,
    path: str,
    source: dict[str, Any],
    context: dict[str, str],
    documents: dict[str, dict[str, Any]],
    invalid: list[str],
) -> None:
    """Keep balance, historical-period and post-position event clocks apart."""
    expected_role = context.get("temporal_role")
    if not expected_role:
        return
    if source.get("temporal_role") != expected_role:
        invalid.append(prefix + ":temporal_role_mismatch:" + path)
        return

    cutoff = _bridge_date(context.get("cutoff_at"))
    if cutoff is None:
        invalid.append(prefix + ":cutoff_at_invalid:" + path)
        return

    doc_id = str(source.get("doc_id") or "")
    document = documents.get(doc_id)
    published_at = None
    if document is None:
        invalid.append(prefix + ":source_document_missing:" + path)
    else:
        published_at = _bridge_date(document.get("published_at"))
        if published_at is None:
            invalid.append(prefix + ":published_at_missing_or_invalid:" + path)
        elif published_at > cutoff:
            invalid.append(prefix + ":published_at_after_cutoff:" + path)

    if expected_role == "HISTORICAL_PERIOD":
        if not context.get("period_start") or not context.get("period_end"):
            invalid.append(prefix + ":model_period_bounds_missing:" + path)
        return
    if expected_role != "EVENT":
        return

    event_date = _bridge_date(source.get("event_date"))
    observed_at = _bridge_date(source.get("observed_at"))
    # ``position_as_of`` remains the specialist balance-sheet clock even
    # though an event operand deliberately carries its own later event date.
    model_position = _bridge_date(context.get("position_as_of"))
    if event_date is None or observed_at is None:
        invalid.append(prefix + ":event_clock_missing_or_invalid:" + path)
        return
    if _bridge_date(source.get("as_of")) != event_date:
        invalid.append(prefix + ":event_as_of_mismatch:" + path)
    expected_event_date = _bridge_date(context.get("event_date"))
    expected_observed_at = _bridge_date(context.get("observed_at"))
    if context.get("event_date") and event_date != expected_event_date:
        invalid.append(prefix + ":event_date_mismatch:" + path)
    if context.get("observed_at") and observed_at != expected_observed_at:
        invalid.append(prefix + ":event_observed_at_mismatch:" + path)
    if observed_at < event_date:
        invalid.append(prefix + ":event_observed_before_event_date:" + path)
    if published_at is not None and observed_at < published_at:
        invalid.append(prefix + ":event_observed_before_document_publication:" + path)
    if (
        context.get("post_position_event_required") == "true"
        and model_position is not None
        and event_date <= model_position
    ):
        invalid.append(prefix + ":event_not_after_position_as_of:" + path)
    if event_date > cutoff:
        invalid.append(prefix + ":event_date_after_cutoff:" + path)
    if observed_at > cutoff:
        invalid.append(prefix + ":observed_at_after_cutoff:" + path)


def _validate_value_bridge_fact_bindings(
    payload: dict[str, Any], output: Path | None,
    *, required: bool, invalid: list[str], incomplete: list[str],
) -> None:
    """Bind every value-bridge numeric operand to current VERIFIED evidence.

    A model's own ``verified_facts`` field is useful provenance, but is not a
    registry.  This gate resolves the exact operand paths against the current
    official fact/calculation registries, so a self-declared OBS id or a
    hand-altered value cannot acquire canonical status.
    """
    if not required:
        return
    compiled = _mapping(payload.get("value_bridge_models"))
    model_input = _mapping(compiled.get("model_input"))
    if not model_input:
        incomplete.append("value_bridge_fact_bindings_model_input_missing")
        return
    bindings = model_input.get("canonical_fact_bindings")
    if not isinstance(bindings, list):
        incomplete.append("value_bridge_fact_bindings_missing")
        return
    if output is None:
        incomplete.append("value_bridge_fact_bindings_output_registry_unavailable")
        return
    facts = _read_json(output / "fact_observations.json")
    calculations = _read_json(output / "calculation_observations.json")
    manifest = _read_json(output / "document_manifest.json")
    documents = {
        str(item.get("doc_id")): item
        for item in manifest.get("documents") or []
        if isinstance(item, dict)
    }
    fact_report_id = str(facts.get("report_id") or "").strip()
    ledger_report_id = str(payload.get("report_id") or "").strip()
    if fact_report_id and ledger_report_id and fact_report_id != ledger_report_id:
        invalid.append("value_bridge_fact_bindings_fact_registry_report_id_mismatch")
    observations = {
        str(item.get("observation_id")): item
        for item in facts.get("observations") or []
        if isinstance(item, dict) and str(item.get("status") or "").upper() == "VERIFIED"
    }
    calculations_by_id = {
        str(item.get("calculation_id")): item
        for item in calculations.get("calculations") or []
        if isinstance(item, dict) and str(item.get("status") or "").upper() == "VERIFIED"
    }
    if not observations and not calculations_by_id:
        incomplete.append("value_bridge_fact_bindings_verified_registry_empty")
        return
    _validate_replacement_non_numeric_fact_refs(
        model_input,
        observations=observations,
        calculations_by_id=calculations_by_id,
        invalid=invalid,
    )
    cash_input = _mapping(
        _mapping(model_input.get("cash_accessibility")).get("model_input")
    )
    for period_index, raw_period in enumerate(cash_input.get("realization_periods") or []):
        period = _mapping(raw_period)
        if not period.get("period_start") or not period.get("period_end"):
            invalid.append(
                "value_bridge_cash_realization_period_bounds_missing:"
                + str(period_index)
            )
    operands = _bridge_numeric_leaves(model_input)
    submitted: dict[str, str] = {}
    for index, raw in enumerate(bindings):
        prefix = f"value_bridge_fact_bindings[{index}]"
        binding = _mapping(raw)
        if set(binding) - {"path", "evidence_id"}:
            invalid.append(prefix + ":unknown_fields")
            continue
        path = str(binding.get("path") or "")
        evidence_id = str(binding.get("evidence_id") or "")
        if not path or not evidence_id:
            invalid.append(prefix + ":path_or_evidence_id_missing")
            continue
        if path in submitted:
            invalid.append(prefix + ":duplicate_operand_path:" + path)
            continue
        submitted[path] = evidence_id
        if path not in operands:
            invalid.append(prefix + ":unknown_operand_path:" + path)
            continue
        declared = _bridge_declared_evidence_ids(model_input, path)
        if evidence_id not in declared:
            invalid.append(prefix + ":evidence_not_declared_at_operand:" + path)
        context = _bridge_operand_context(model_input, path)
        if context.get("temporal_role") and evidence_id.startswith("CALC:"):
            invalid.append(
                prefix + ":cash_temporal_operand_calculation_evidence_forbidden:" + path
            )
            continue
        source = observations.get(evidence_id) or calculations_by_id.get(evidence_id)
        if source is None:
            invalid.append(prefix + ":unknown_or_unverified_evidence:" + evidence_id)
            continue
        source_value = _num(
            source.get("normalized_value")
            if evidence_id in observations else source.get("value")
        )
        if source_value is None or not _same(source_value, operands[path], tolerance=1e-9):
            invalid.append(prefix + ":numeric_value_mismatch:" + path)
            continue
        source_unit = str(source.get("unit") or "")
        if context.get("unit") and source_unit != context["unit"]:
            invalid.append(prefix + ":unit_mismatch:" + path)
        if evidence_id in observations:
            if context.get("currency") and source.get("currency") != context["currency"]:
                invalid.append(prefix + ":currency_mismatch:" + path)
            if context.get("as_of") and source.get("as_of") != context["as_of"]:
                invalid.append(prefix + ":as_of_mismatch:" + path)
            measurement = _mapping(source.get("measurement_context"))
            for field in (
                "economic_entity", "operating_perimeter", "period_start", "period_end", "cohort_id",
            ):
                expected = context.get(field)
                if expected and measurement.get(field) != expected:
                    invalid.append(prefix + ":measurement_context_mismatch:" + field)
            _validate_bridge_observation_temporal_contract(
                prefix=prefix,
                path=path,
                source=source,
                context=context,
                documents=documents,
                invalid=invalid,
            )
    missing = sorted(set(operands) - set(submitted))
    invalid.extend("value_bridge_fact_bindings_operand_unbound:" + path for path in missing)


def _validate_replacement_non_numeric_fact_refs(
    model_input: dict[str, Any],
    *,
    observations: dict[str, dict[str, Any]],
    calculations_by_id: dict[str, dict[str, Any]],
    invalid: list[str],
) -> None:
    """Resolve replacement evidence-role and exclusion proofs to current facts.

    These references justify capability coverage or an explicit destination,
    rather than a submitted numeric leaf, so they cannot appear in
    ``canonical_fact_bindings``.  The replacement core owns the role and
    destination semantics; this ledger layer proves the named facts or
    calculations exist in the current verified registry.
    """
    replacement = _mapping(_mapping(model_input.get("replacement_value")).get("model_input"))
    context = _mapping(replacement.get("model_context"))
    if context.get("purpose") != "COMPANY_ANALYSIS":
        return
    components = replacement.get("components") or []
    if not isinstance(components, list):
        return
    for component_index, raw_component in enumerate(components):
        component = _mapping(raw_component)
        component_id = str(component.get("component_id") or component_index)
        recognition = _mapping(component.get("recognition"))
        if recognition.get("status") == "RECOGNIZED":
            bindings = component.get("evidence_role_bindings") or []
            if isinstance(bindings, list):
                for binding_index, raw_binding in enumerate(bindings):
                    binding = _mapping(raw_binding)
                    role = str(binding.get("role") or binding_index)
                    for source_id in binding.get("source_fact_ids") or []:
                        source_key = str(source_id)
                        source = observations.get(source_key)
                        if source is None:
                            invalid.append(
                                "replacement_evidence_role_requires_verified_observation:"
                                + component_id
                                + ":"
                                + role
                                + ":"
                                + source_key
                            )
                        elif role not in set(
                            str(item)
                            for item in source.get("valuation_evidence_roles") or []
                        ):
                            invalid.append(
                                "replacement_evidence_role_source_role_mismatch:"
                                + component_id
                                + ":"
                                + role
                                + ":"
                                + source_key
                            )
        if recognition.get("status") == "EXCLUDED":
            treatment = _mapping(component.get("exclusion_treatment"))
            destination = str(treatment.get("destination") or "")
            for source_id in treatment.get("source_fact_ids") or []:
                source_key = str(source_id)
                source = observations.get(source_key)
                if source is None:
                    invalid.append(
                        "replacement_exclusion_requires_verified_observation:"
                        + component_id
                        + ":"
                        + source_key
                    )
                elif destination not in set(
                    str(item)
                    for item in source.get("valuation_exclusion_destinations") or []
                ):
                    invalid.append(
                        "replacement_exclusion_source_destination_mismatch:"
                        + component_id
                        + ":"
                        + destination
                        + ":"
                        + source_key
                    )


def _validate_value_bridge_models(
    payload: dict[str, Any],
    active_models: list[dict[str, Any]],
    *,
    required: bool,
    route_models: dict[str, dict[str, Any]],
    invalid: list[str],
    incomplete: list[str],
    warnings: list[str],
) -> None:
    """Bind fact-derived value bridges to the models that consume them.

    The bridge compiler recomputes all three specialist models.  This gate
    then checks their economic destinations: cash may enter value only at its
    calibrated realization, working capital may normalize owner cash once,
    and replacement value may only cross-check EPV.
    """
    compiled = payload.get("value_bridge_models")
    synthesis = _mapping(payload.get("synthesis"))
    needs_cash = any(
        model.get("model_type") == "RETURN_DECOMPOSITION"
        or "retained_value_realization" in _mapping(model.get("assumptions"))
        for model in active_models
    ) or isinstance(synthesis.get("value_realization_bridge"), dict)
    needs_working_capital = any(
        model.get("model_type") == "EPV" for model in active_models
    )
    compiled_results = _mapping(_mapping(compiled).get("result"))
    needs_replacement = "REPLACEMENT_VALUE" in route_models or any(
        model.get("route_model_id") == "REPLACEMENT_VALUE"
        for model in active_models
    ) or isinstance(compiled_results.get("replacement_value"), dict) or (
        _num(synthesis.get("joint_protection_price_ceiling")) is not None
    )
    required_keys = {
        key
        for key, needed in (
            ("cash_accessibility", needs_cash),
            ("working_capital", needs_working_capital),
            ("replacement_value", needs_replacement),
        )
        if required and needed
    }
    if not isinstance(compiled, dict):
        for key in sorted(required_keys):
            incomplete.append("value_bridge_models_missing:" + key)
        return
    bridge_method = str(
        _mapping(synthesis.get("value_realization_bridge")).get("method") or ""
    )
    results = _mapping(compiled.get("result"))
    if "replacement_value" in results and bridge_method in {
        "weighted_average", "additive", "sum", "combined"
    }:
        invalid.append("replacement_value_epv_cannot_be_weighted_or_added")
    try:
        from scripts.valuation_value_bridges import validate_valuation_value_bridges
    except ModuleNotFoundError:
        from valuation_value_bridges import validate_valuation_value_bridges
    validation = validate_valuation_value_bridges(compiled)
    if validation.get("state") != "VALID":
        invalid.extend(
            "value_bridge_models:" + str(finding)
            for finding in validation.get("findings") or []
        )
        return
    projections = _mapping(compiled.get("valuation_projection"))
    for key in sorted(required_keys - set(results)):
        incomplete.append("value_bridge_models_missing:" + key)

    cash = results.get("cash_accessibility")
    if isinstance(cash, dict):
        if isinstance(payload.get("cash_access_bridge"), dict):
            invalid.append("canonical_and_legacy_cash_bridges_mutually_exclusive")
        adopted_rate = _num(
            _mapping(cash.get("future_retained_cash_realization")).get(
                "adopted_realization_rate"
            )
        )
        for model in active_models:
            assumptions = _mapping(model.get("assumptions"))
            if model.get("model_type") != "RETURN_DECOMPOSITION" and (
                "retained_value_realization" not in assumptions
            ):
                continue
            model_id = str(model.get("model_id") or "unknown")
            submitted = _num(assumptions.get("retained_value_realization"))
            if submitted is None:
                incomplete.append(model_id + ":retained_value_realization_missing")
            elif adopted_rate is None or not _same(submitted, adopted_rate):
                invalid.append(
                    model_id + ":retained_value_realization_not_cash_model_derived"
                )
        _validate_cash_component_contract(
            payload=payload,
            cash_result=cash,
            cash_projection=_mapping(projections.get("cash_accessibility")),
            active_models=active_models,
            invalid=invalid,
            incomplete=incomplete,
        )

    working = results.get("working_capital")
    if isinstance(working, dict):
        reference = _mapping(working.get("reference_period_result"))
        adopted_owner_cash = _num(reference.get("adopted_normalized_owner_cash"))
        reference_period_id = str(reference.get("period_id") or "")
        working_model_id = str(working.get("model_id") or "")
        if adopted_owner_cash is None and needs_working_capital:
            incomplete.append("working_capital_normalized_owner_cash_unknown")
        for model in active_models:
            if model.get("model_type") != "EPV":
                continue
            model_id = str(model.get("model_id") or "unknown")
            bridge = _mapping(model.get("normalization_bridge"))
            if bridge.get("working_capital_model_id") != working_model_id:
                incomplete.append(model_id + ":working_capital_model_binding_missing")
            if bridge.get("working_capital_reference_period_id") != reference_period_id:
                incomplete.append(model_id + ":working_capital_reference_period_mismatch")
            normalized = _num(bridge.get("normalized_earnings_model_currency"))
            if (
                adopted_owner_cash is not None
                and normalized is not None
                and not _same(normalized, adopted_owner_cash, tolerance=5e-3)
            ):
                invalid.append(model_id + ":normalized_earnings_not_working_capital_derived")

    replacement = results.get("replacement_value")
    if isinstance(replacement, dict):
        projection = _mapping(projections.get("replacement_value"))
        replacement_input = _mapping(
            _mapping(_mapping(compiled).get("model_input")).get("replacement_value")
        )
        replacement_model_input = _mapping(replacement_input.get("model_input"))
        replacement_context = _mapping(replacement_model_input.get("model_context"))
        per_share = _mapping(replacement.get("per_share_range"))
        low = _num(per_share.get("range_low"))
        high = _num(per_share.get("range_high"))
        replacement_basis = _mapping(replacement.get("basis"))
        replacement_models = [
            model for model in active_models
            if model.get("route_model_id") == "REPLACEMENT_VALUE"
        ]
        if needs_replacement and not replacement_models:
            incomplete.append("replacement_value_routed_model_missing")
        routed_replacement = _mapping(route_models.get("REPLACEMENT_VALUE"))
        expected_archetype_id = str(
            routed_replacement.get("valuation_archetype_id") or ""
        )
        expected_archetype_version = str(
            routed_replacement.get("valuation_archetype_version") or ""
        )
        for model in replacement_models:
            model_id = str(model.get("model_id") or "unknown")
            # Older or isolated ledger tests may deliberately omit a route.
            # A production route policy separately makes that output
            # incomplete.  Do not upgrade that absence into an invalid card
            # mismatch; the replacement core still resolves its own active
            # card in every COMPANY_ANALYSIS input.
            if routed_replacement and (
                not expected_archetype_id or not expected_archetype_version
            ):
                invalid.append(model_id + ":replacement_value_route_archetype_missing")
            elif routed_replacement and (
                replacement_context.get("valuation_archetype_id")
                != expected_archetype_id
                or replacement_context.get("valuation_archetype_version")
                != expected_archetype_version
            ):
                invalid.append(model_id + ":replacement_value_archetype_mismatch")
            result = _mapping(model.get("result"))
            basis = _mapping(model.get("basis"))
            if model.get("role") != "corroborative":
                invalid.append(model_id + ":replacement_value_must_be_corroborative")
            if basis.get("currency") != replacement_basis.get("currency"):
                invalid.append(model_id + ":replacement_value_currency_mismatch")
            if basis.get("as_of") != replacement_basis.get("as_of"):
                invalid.append(model_id + ":replacement_value_as_of_mismatch")
            if low is None or high is None:
                if any(
                    _num(result.get(field)) is not None
                    for field in ("range_low", "range_high", "value_per_share")
                ):
                    invalid.append(
                        model_id + ":replacement_value_numeric_claim_for_incomplete_scope"
                    )
            else:
                if not _same(result.get("range_low"), low) or not _same(
                    result.get("range_high"), high
                ):
                    invalid.append(model_id + ":replacement_value_range_mismatch")
                if not _same(result.get("value_per_share"), low):
                    invalid.append(model_id + ":replacement_value_scalar_must_use_low_endpoint")
        epv_result = _mapping(replacement.get("epv_cross_check"))
        epv_check = _mapping(replacement_model_input.get("epv_cross_check"))
        if epv_result.get("status") == "COMPARABLE":
            epv_id = str(epv_check.get("model_id") or "")
            epv_model = next(
                (
                    model for model in active_models
                    if str(model.get("model_id") or "") == epv_id
                    and model.get("model_type") == "EPV"
                ),
                None,
            )
            if epv_model is None:
                invalid.append("replacement_value_epv_cross_check_model_not_active")
            else:
                epv_basis = _mapping(epv_model.get("basis"))
                if (
                    epv_basis.get("currency") != replacement_basis.get("currency")
                    or epv_basis.get("as_of") != replacement_basis.get("as_of")
                ):
                    invalid.append("replacement_value_epv_cross_check_basis_mismatch")
                context = _mapping(epv_model.get("cross_check_context"))
                for field in (
                    "economic_entity",
                    "operating_perimeter",
                    "ordinary_share_claim_scope",
                ):
                    if not str(context.get(field) or "").strip():
                        invalid.append(
                            "replacement_value_epv_cross_check_context_missing:" + field
                        )
                    elif context.get(field) != epv_check.get(field):
                        invalid.append(
                            "replacement_value_epv_cross_check_context_mismatch:" + field
                        )
                active_values, active_findings = _active_epv_cross_check_values(epv_model)
                if active_findings:
                    invalid.extend(
                        "replacement_value_epv_cross_check_active_epv_" + finding
                        for finding in active_findings
                    )
                else:
                    for field in (
                        "shares_outstanding",
                        "per_share_low",
                        "per_share_high",
                        "equity_value_low",
                        "equity_value_high",
                    ):
                        expected_field = {
                            "shares_outstanding": "shares",
                        }.get(field, field)
                        if not _same(epv_check.get(field), active_values[expected_field]):
                            invalid.append(
                                "replacement_value_epv_cross_check_not_active_epv_"
                                + field
                            )
        joint_ceiling = _num(
            _mapping(projection.get("joint_protection_price_ceiling")).get("value")
        )
        synthesis_ceiling = _num(
            _mapping(payload.get("synthesis")).get("joint_protection_price_ceiling")
        )
        if joint_ceiling is None:
            if synthesis_ceiling is not None:
                invalid.append("synthesis_joint_protection_price_not_supported")
            warnings.append("replacement_value_joint_protection_price_unresolved")
        elif synthesis_ceiling is None:
            incomplete.append("synthesis_joint_protection_price_ceiling_missing")
        elif not _same(joint_ceiling, synthesis_ceiling):
            invalid.append("synthesis_joint_protection_price_ceiling_mismatch")


def validate_valuation_model_ledger(
    payload: dict[str, Any], *, output_dir: str | Path | None = None, report_text: str = "",
    enforced: bool = False, min_independent_groups: int = 2,
    min_r_g_buffer_pct: float = MIN_R_G_BUFFER_PCT,
    require_normalization_bridge: bool | None = None,
    require_decay_treatment: bool | None = None,
    require_owner_earnings_normalization: bool | None = None,
    require_holding_period_return_bridge: bool | None = None,
    require_value_bridge_models: bool | None = None,
    require_value_bridge_fact_bindings: bool | None = None,
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

    synthesis = payload.get("synthesis")
    if not isinstance(synthesis, dict):
        invalid.append("synthesis_invalid")
        synthesis = {}
    action = str(synthesis.get("action") or "")
    valuation_unresolved = action == "unresolved"

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
    if require_value_bridge_models is None:
        require_value_bridge_models = bool(model_policy.get("require_value_bridge_models"))
    if require_value_bridge_fact_bindings is None:
        require_value_bridge_fact_bindings = bool(
            model_policy.get("require_value_bridge_fact_bindings")
        )
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
        canonical_replacement = _mapping(
            _mapping(_mapping(payload.get("value_bridge_models")).get("result")).get(
                "replacement_value"
            )
        )
        replacement_scope_incomplete = (
            route_model_id == "REPLACEMENT_VALUE"
            and role == "corroborative"
            and _mapping(canonical_replacement.get("economic_conclusion")).get(
                "replacement_range_status"
            ) != "AVAILABLE"
            and canonical_replacement.get("per_share_range") is None
        )
        if value is None or value <= 0:
            if not replacement_scope_incomplete:
                invalid.append(f"{mid}:value_per_share_invalid")
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

    _validate_value_bridge_models(
        payload,
        active,
        required=bool(require_value_bridge_models) and not valuation_unresolved,
        route_models=route_models,
        invalid=invalid,
        incomplete=incomplete,
        warnings=warnings,
    )
    _validate_value_bridge_fact_bindings(
        payload,
        output,
        required=bool(require_value_bridge_fact_bindings) and not valuation_unresolved,
        invalid=invalid,
        incomplete=incomplete,
    )

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
    if enforced and not primary and not valuation_unresolved: incomplete.append("primary_model_missing")
    if primary and all(m.get("model_type") == "RELATIVE" for m in primary): invalid.append("relative_valuation_cannot_be_sole_primary")
    if enforced and not valuation_unresolved and len(groups) < min_independent_groups:
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

    if action not in ACTIONS: invalid.append("synthesis_action_invalid")
    chosen = _num(synthesis.get("chosen_value_per_share")); low = _num(synthesis.get("range_low")); high = _num(synthesis.get("range_high"))
    if valuation_unresolved:
        if any(value is not None for value in (chosen, low, high)):
            invalid.append("unresolved_synthesis_must_not_state_value_range")
        raw_position = synthesis.get("position_pct")
        if raw_position is not None and _num(raw_position) != 0.0:
            invalid.append("unresolved_synthesis_position_invalid")
    elif None in {chosen, low, high} or not (low <= chosen <= high):
        invalid.append("synthesis_value_range_invalid")
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
    cash_projection = _mapping(
        _mapping(
            _mapping(payload.get("value_bridge_models")).get("valuation_projection")
        ).get("cash_accessibility")
    )
    recognized_cash_per_share = sum(
        _num(_mapping(cash_projection.get(component)).get("adopted_per_share")) or 0.0
        for component in ("existing_excess_cash", "related_party_receivables")
    )
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
                # operating value dividend-only.  Existing cash and related
                # receivables enter exactly once at their canonical adopted
                # per-share amounts, or remain inside the primary equity bridge.
                model_id = str(synthesis_bridge.get("operating_model_id") or "")
                operating = _num(synthesis_bridge.get("operating_value_per_share"))
                retained_growth = _num(synthesis_bridge.get("retained_growth_per_share"))
                realization = _num(synthesis_bridge.get("retained_growth_realization"))
                accessible_cash = _num(synthesis_bridge.get("accessible_cash_per_share"))
                cash_location = str(synthesis_bridge.get("cash_inclusion_location") or "")
                cash_contract = _mapping(synthesis.get("cash_component_contract"))
                contract_location = str(cash_contract.get("inclusion_location") or "")
                expected_separate_cash = 0.0
                cash_location_valid = True
                if recognized_cash_per_share > 0:
                    expected_separate_cash = (
                        _num(cash_contract.get("separate_component_per_share")) or 0.0
                    )
                    if cash_location != contract_location:
                        cash_location_valid = False
                elif cash_location not in {"", "NONE", "SEPARATE_COMPONENT"}:
                    cash_location_valid = False
                if (
                    primary_values.get(model_id) is None
                    or not _same(operating, primary_values.get(model_id))
                    or None in {operating, retained_growth, realization, accessible_cash}
                    or retained_growth < 0
                    or not 0 <= realization <= 1
                    or not cash_location_valid
                    or not _same(accessible_cash, expected_separate_cash)
                    or not _same(
                        operating + retained_growth * realization + accessible_cash,
                        chosen,
                    )
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
        if enforced and not ref and not valuation_unresolved: incomplete.append("synthesis_decision_entry_missing")
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
            "value_bridge_models",
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
                0 if model_count else 1, 9 - section_count, substantive_count,
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
