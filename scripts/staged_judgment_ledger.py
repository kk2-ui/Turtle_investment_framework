#!/usr/bin/env python3
"""Price-free staged judgment ledger (v1).

The ledger is an intentionally small authoring format.  Validation checks the
shape and boundaries; :func:`compile_staged_judgment_ledger` only copies values
into an ``enterprise-underwriting-episode.v2`` object and runs the existing
Episode validators.  No economic inference, numeric defaults, or price data is
created here.
"""
from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

from scripts.enterprise_underwriting_episode import (
    EPISODE_SCHEMA,
    TREATMENTS,
    ECONOMIC_DIRECTIONS,
    COMPONENT_DECISION_SCOPES,
    EARNINGS_AND_CASH_USES,
    FINANCING_PRESSURE_EFFECTS,
    PERMANENT_LOSS_USES,
    VALUATION_USES,
    validate_enterprise_underwriting_episode,
    validate_price_free_underwriting_thesis_projection,
    validate_underwriting_projection_bundle,
    compile_underwriting_projections,
    derive_component_decision_summary,
)
from scripts.enterprise_underwriting_training import validate_training_episode

LEDGER_SCHEMA = "staged-judgment-ledger.v1"
DIAGNOSTICS_SCHEMA = "staged-ledger-diagnostics.v1"
SAMPLE_IDENTITIES = {"WORKED_CASE", "BLIND_REPLAY", "PROSPECTIVE_EPISODE"}
LEDGER_STATUSES = {"DRAFT", "FROZEN", "COMPILED", "DIAGNOSTIC_ONLY", "REJECTED"}
CLAIM_SURFACES = {
    "SURVIVAL", "BUSINESS_POSITION", "ADAPTATION", "NORMALIZATION",
    "PERMANENT_LOSS", "VALUE_ROUTE", "INDUSTRY_FUTURE", "INVESTMENT_TREATMENT",
}
CLAIM_TREATMENTS = TREATMENTS
COMPONENT_SCOPES = COMPONENT_DECISION_SCOPES

_TOP_KEYS = {
    "schema_version", "ledger_id", "company_id", "company_name", "cutoff_at",
    "sample_identity", "status", "decision_frame", "underwriting_route", "claims",
    "components", "industry_future", "reversal_observations", "evidence_refs",
    "diagnostics", "normal_earnings_bridge", "driver_sensitivities",
}
_CLAIM_KEYS = {
    "claim_id", "surface", "statement", "direction", "mechanism", "treatment",
    "evidence_ids", "strongest_rival", "reversal_observations", "unknown",
}
_COMPONENT_KEYS = {
    "component_id", "economic_scope", "treatment", "normal_earnings_use", "owner_cash_use",
    "financing_pressure_effect", "permanent_loss_use", "valuation_use",
    "valuation_route_bindings", "reason", "promotion_test", "invalidation_test", "evidence_ids",
}
_FORBIDDEN = {
    "price", "market_price", "share_price", "stock_price", "entry_price", "buyband",
    "buy_band", "return", "expected_return", "valuation_result", "investment_action",
    "portfolio_action", "action", "position", "outcome", "outcome_value", "yield",
}
_MATERIAL_SURFACES = {
    "SURVIVAL", "BUSINESS_POSITION", "ADAPTATION", "NORMALIZATION", "PERMANENT_LOSS",
    "VALUE_ROUTE", "INDUSTRY_FUTURE", "INVESTMENT_TREATMENT",
}


def _obj(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def _text(v: Any) -> bool:
    return isinstance(v, str) and bool(v.strip())


def _diag(code: str, path: str, *, severity: str = "BLOCKING_MATERIAL",
          missing_fact: str = "", economic_impact: str = "", prohibited_assumption: str = "",
          remediation: str = "", acceptance_criterion: str = "", root_cause: str = "REASONING") -> dict[str, Any]:
    return {
        "code": code, "path": path, "severity": severity, "root_cause": root_cause,
        "economic_impact": economic_impact or "未说明",
        "missing_fact": missing_fact or path,
        "prohibited_assumption": prohibited_assumption or "不得用空值、零值或代理替代",
        "remediation": remediation or "补齐该字段并重新编译",
        "acceptance_criterion": acceptance_criterion or "字段满足 v1 合同且可重编译",
    }


def _forbidden_paths(value: Any, path: str = "$") -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            key = str(k).lower()
            child = f"{path}.{k}"
            if key in _FORBIDDEN:
                found.append(child)
            found.extend(_forbidden_paths(v, child))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            found.extend(_forbidden_paths(v, f"{path}[{i}]"))
    return found


def validate_staged_judgment_ledger(ledger: Any, source_index: Any | None = None,
                                    contract: Any | None = None) -> dict[str, Any]:
    """Return deterministic validation findings for a staged ledger."""
    value = _obj(ledger)
    findings: list[dict[str, Any]] = []
    if value.get("schema_version") != LEDGER_SCHEMA:
        findings.append(_diag("SCHEMA_VERSION_INVALID", "schema_version"))
    extras = sorted(set(value) - _TOP_KEYS)
    for key in extras:
        findings.append(_diag("UNAPPROVED_FIELD", key, root_cause="MODEL"))
    for field in ("ledger_id", "company_id", "company_name", "cutoff_at", "decision_frame", "underwriting_route"):
        if not _text(value.get(field)):
            findings.append(_diag("IDENTITY_MISSING", field))
    if value.get("sample_identity") not in SAMPLE_IDENTITIES:
        findings.append(_diag("SAMPLE_IDENTITY_INVALID", "sample_identity"))
    if value.get("status") not in LEDGER_STATUSES:
        findings.append(_diag("STATUS_INVALID", "status"))
    if value.get("status") != "FROZEN":
        findings.append(_diag("LEDGER_NOT_FROZEN", "status", economic_impact="未冻结账本不得投影下游 Episode"))
    if isinstance(contract, dict):
        try:
            from scripts.enterprise_underwriting_training import validate_training_contract
            cval = validate_training_contract(contract)
            if cval.get("state") != "REVIEWABLE":
                findings.append(_diag("CONTRACT_INVALID", "contract", root_cause="MODEL"))
        except Exception:
            findings.append(_diag("CONTRACT_INVALID", "contract", root_cause="MODEL"))
        for f in ("company_id", "company_name", "cutoff_at", "sample_identity"):
            if f in contract and value.get(f) != contract.get(f):
                findings.append(_diag("CONTRACT_IDENTITY_MISMATCH", f, root_cause="MODEL", missing_fact=f"contract.{f}"))
        allowed = contract.get("allowed_sources") or []
        allowed_refs = {str(_obj(x).get("source_ref")) for x in allowed}
        memory_refs = {str(_obj(x).get("source_ref")) for x in allowed
                       if _obj(x).get("time_role") == "TRAINING_MEMORY"}
        for i, raw in enumerate(_list(value.get("evidence_refs"))):
            ref = _obj(raw).get("source_ref")
            if ref and allowed_refs and str(ref) not in allowed_refs:
                findings.append(_diag("EVIDENCE_NOT_ALLOWED", f"evidence_refs[{i}]", root_cause="MODEL"))
            if ref and str(ref) in memory_refs:
                findings.append(_diag("TRAINING_MEMORY_EVIDENCE_FORBIDDEN", f"evidence_refs[{i}]", root_cause="MODEL"))
    for path in _forbidden_paths(value):
        findings.append(_diag("PRICE_FIREWALL", path, root_cause="MODEL",
                              prohibited_assumption="不得写入价格、收益、估值结果或动作"))

    claims = _list(value.get("claims"))
    claim_ids: set[str] = set(); surfaces: set[str] = set()
    for i, raw in enumerate(claims):
        path = f"claims[{i}]"; item = _obj(raw)
        if set(item) != _CLAIM_KEYS:
            findings.append(_diag("CLAIM_FIELDS_INVALID", path, root_cause="MODEL"))
        cid, surface = item.get("claim_id"), item.get("surface")
        if not _text(cid) or cid in claim_ids:
            findings.append(_diag("CLAIM_ID_MISSING_OR_DUPLICATE", path))
        claim_ids.add(str(cid))
        if surface not in CLAIM_SURFACES:
            findings.append(_diag("CLAIM_SURFACE_INVALID", path + ".surface"))
        if str(surface) in surfaces:
            findings.append(_diag("CLAIM_SURFACE_DUPLICATE", path + ".surface", economic_impact="同一经济面多条主判断会导致编译歧义"))
        surfaces.add(str(surface))
        for f in ("statement", "mechanism", "strongest_rival"):
            if not _text(item.get(f)):
                findings.append(_diag("CLAIM_FIELD_MISSING", path + "." + f))
        if item.get("direction") not in ECONOMIC_DIRECTIONS:
            findings.append(_diag("CLAIM_DIRECTION_INVALID", path + ".direction"))
        if item.get("treatment") not in CLAIM_TREATMENTS:
            findings.append(_diag("CLAIM_TREATMENT_INVALID", path + ".treatment"))
        if not isinstance(item.get("evidence_ids"), list):
            findings.append(_diag("CLAIM_EVIDENCE_IDS_INVALID", path + ".evidence_ids"))
        if not isinstance(item.get("reversal_observations"), list) or not item.get("reversal_observations"):
            findings.append(_diag("REVERSAL_MISSING", path + ".reversal_observations"))
        unknown = item.get("unknown")
        if item.get("direction") == "UNKNOWN":
            if not isinstance(unknown, dict) or set(unknown) != {"status", "reason", "conservative_treatment", "next_observation", "materiality"}:
                findings.append(_diag("UNKNOWN_UNBOUNDED", path + ".unknown", root_cause="DATA_COVERAGE"))
            elif unknown.get("status") != "UNKNOWN" or unknown.get("materiality") not in {"MATERIAL", "NON_MATERIAL"} or any(not _text(unknown.get(k)) for k in ("reason", "conservative_treatment", "next_observation")):
                findings.append(_diag("UNKNOWN_UNBOUNDED", path + ".unknown", root_cause="DATA_COVERAGE"))
        elif unknown is not None and not isinstance(unknown, dict):
            findings.append(_diag("UNKNOWN_INVALID", path + ".unknown"))
        if surface == "INVESTMENT_TREATMENT" and re.search(r"(?i)(price|return|buyband|action|收益|价格|买入|卖出|回报)", str(item.get("statement", ""))):
            findings.append(_diag("PRICE_FIREWALL", path + ".statement", root_cause="MODEL"))

    missing_surfaces = sorted(_MATERIAL_SURFACES - surfaces)
    for surface in missing_surfaces:
        findings.append(_diag("CLAIM_MISSING", f"claims[{surface}]", missing_fact=f"surface={surface}"))

    components = _list(value.get("components")); component_ids: set[str] = set()
    for i, raw in enumerate(components):
        path = f"components[{i}]"; item = _obj(raw)
        if set(item) != _COMPONENT_KEYS:
            findings.append(_diag("COMPONENT_FIELDS_INVALID", path, root_cause="MODEL"))
        cid = item.get("component_id")
        if not _text(cid) or cid in component_ids:
            findings.append(_diag("COMPONENT_DUPLICATE", path))
        component_ids.add(str(cid))
        if item.get("economic_scope") not in COMPONENT_SCOPES:
            findings.append(_diag("COMPONENT_SCOPE_INVALID", path + ".economic_scope"))
        if item.get("treatment") not in TREATMENTS:
            findings.append(_diag("COMPONENT_TREATMENT_INVALID", path + ".treatment"))
        for f, allowed in (("normal_earnings_use", EARNINGS_AND_CASH_USES), ("owner_cash_use", EARNINGS_AND_CASH_USES), ("financing_pressure_effect", FINANCING_PRESSURE_EFFECTS), ("permanent_loss_use", PERMANENT_LOSS_USES), ("valuation_use", VALUATION_USES)):
            if item.get(f) not in allowed:
                findings.append(_diag("COMPONENT_USE_INVALID", path + "." + f))
        if not isinstance(item.get("valuation_route_bindings"), list):
            findings.append(_diag("ROUTE_BINDING_INVALID", path + ".valuation_route_bindings"))
        for f in ("reason", "promotion_test", "invalidation_test"):
            if not _text(item.get(f)):
                findings.append(_diag("COMPONENT_FIELD_MISSING", path + "." + f))
        if not isinstance(item.get("evidence_ids"), list) or not item.get("evidence_ids"):
            findings.append(_diag("COMPONENT_EVIDENCE_MISSING", path + ".evidence_ids", root_cause="DATA_COVERAGE"))
        if item.get("treatment") in {"SCENARIO_ONLY", "EXCLUDE_FROM_BASE", "CANNOT_BOUND"} and (item.get("normal_earnings_use") == "BASE_RANGE" or item.get("owner_cash_use") == "BASE_RANGE" or item.get("valuation_use") == "PRIMARY_INPUT"):
            findings.append(_diag("COMPONENT_PERMISSION_CONFLICT", path, economic_impact="组件权限会改变基准或主价值路线"))

    rev = _list(value.get("reversal_observations"))
    if not rev or any(not _text(x) for x in rev):
        findings.append(_diag("REVERSAL_MISSING", "reversal_observations"))
    industry = _obj(value.get("industry_future"))
    for f in ("horizon", "most_likely_regime", "profit_pool_transmission", "company_exposure", "adaptation", "normal_economics", "permanent_loss", "valuation_treatment", "strongest_rival"):
        if not _text(industry.get(f)):
            findings.append(_diag("INDUSTRY_FIELD_MISSING", "industry_future." + f))
    if industry.get("reversal_observations") is not None and industry.get("reversal_observations") != rev:
        findings.append(_diag("REVERSAL_CONFLICT", "industry_future.reversal_observations"))

    # Evidence references are index-only; TRAINING_MEMORY can never be target evidence.
    refs = _list(value.get("evidence_refs")); ref_ids = set()
    idx = source_index if isinstance(source_index, dict) else {}
    for i, raw in enumerate(refs):
        item = _obj(raw) if isinstance(raw, dict) else {"evidence_id": raw}
        eid = item.get("evidence_id") or item.get("id")
        if not _text(eid) or eid in ref_ids:
            findings.append(_diag("EVIDENCE_UNRESOLVED", f"evidence_refs[{i}]", root_cause="DATA_COVERAGE"))
        ref_ids.add(str(eid))
        # A canonical source index is mandatory for compilation, but the
        # shape-only validator remains useful for authoring a ledger before
        # J0 has attached its index.  When an index is supplied it is the
        # sole authority and every id/ref must resolve exactly.
        if source_index is not None and (not isinstance(idx, dict) or eid not in idx):
            findings.append(_diag("EVIDENCE_INDEX_MISSING", f"evidence_refs[{i}]", root_cause="DATA_COVERAGE"))
        canonical = _obj(idx.get(eid)) if isinstance(idx, dict) else {}
        if source_index is not None and canonical:
            for required in ("source_ref", "available_at", "time_role"):
                if not _text(canonical.get(required)):
                    findings.append(_diag("EVIDENCE_INDEX_INCOMPLETE", f"evidence_refs[{i}].{required}", root_cause="DATA_COVERAGE"))
            if canonical.get("time_role") == "TRAINING_MEMORY":
                findings.append(_diag("TRAINING_MEMORY_EVIDENCE_FORBIDDEN", f"evidence_refs[{i}]", root_cause="MODEL"))
        source = item.get("source_ref") or (_obj(idx.get(eid)).get("source_ref") if isinstance(idx, dict) else None)
        if isinstance(idx, dict) and eid in idx and item.get("source_ref") and str(item.get("source_ref")) != str(_obj(idx.get(eid)).get("source_ref")):
            findings.append(_diag("EVIDENCE_INDEX_MISMATCH", f"evidence_refs[{i}].source_ref", root_cause="MODEL"))
        if isinstance(contract, dict) and isinstance(idx, dict) and eid in idx:
            canonical = _obj(idx.get(eid))
            allowed_match = next((
                _obj(s) for s in _list(contract.get("allowed_sources"))
                if str(_obj(s).get("source_ref")) == str(canonical.get("source_ref"))
            ), None)
            if allowed_match is None:
                findings.append(_diag("EVIDENCE_NOT_ALLOWED", f"evidence_refs[{i}]", root_cause="ACQUISITION_MODULE"))
            else:
                for field in ("available_at", "time_role"):
                    if str(canonical.get(field)) != str(allowed_match.get(field)):
                        findings.append(_diag("EVIDENCE_CONTRACT_METADATA_MISMATCH", f"evidence_refs[{i}].{field}", root_cause="ACQUISITION_MODULE"))
        if (str(item.get("provenance", "")).upper() == "TRAINING_MEMORY"
                or str(_obj(idx.get(eid)).get("provenance", "")).upper() == "TRAINING_MEMORY"
                or (isinstance(contract, dict) and any(
                    str(_obj(s).get("source_ref")) == str(source)
                    and _obj(s).get("time_role") == "TRAINING_MEMORY"
                    for s in _list(contract.get("allowed_sources"))))):
            findings.append(_diag("TRAINING_MEMORY_EVIDENCE_FORBIDDEN", f"evidence_refs[{i}]", root_cause="MODEL", prohibited_assumption="TRAINING_MEMORY 只能影响提问顺序，不能作为公司证据"))
        elif not _text(source):
            findings.append(_diag("EVIDENCE_UNRESOLVED", f"evidence_refs[{i}]", root_cause="DATA_COVERAGE"))
    for i, claim in enumerate(claims):
        for eid in _list(_obj(claim).get("evidence_ids")):
            if eid not in ref_ids:
                findings.append(_diag("EVIDENCE_UNRESOLVED", f"claims[{i}].evidence_ids", root_cause="DATA_COVERAGE"))
    for i, comp in enumerate(components):
        for eid in _list(_obj(comp).get("evidence_ids")):
            if eid not in ref_ids:
                findings.append(_diag("EVIDENCE_UNRESOLVED", f"components[{i}].evidence_ids", root_cause="DATA_COVERAGE"))
    return {"schema_version": DIAGNOSTICS_SCHEMA, "state": "VALID" if not findings else "INVALID", "findings": findings}


def _evidence_trace(ledger: dict[str, Any], source_index: Any, contract: Any | None = None) -> list[dict[str, Any]]:
    idx = source_index if isinstance(source_index, dict) else {}
    out = []
    for raw in ledger.get("evidence_refs", []):
        item = _obj(raw) if isinstance(raw, dict) else {"evidence_id": raw}
        eid = item.get("evidence_id") or item.get("id")
        src = _obj(idx.get(eid)).get("source_ref") if eid in idx else item.get("source_ref")
        memory = (str(item.get("provenance", "")).upper() == "TRAINING_MEMORY"
                  or str(_obj(idx.get(eid)).get("provenance", "")).upper() == "TRAINING_MEMORY"
                  or (isinstance(contract, dict) and any(
                      str(_obj(s).get("source_ref")) == str(src)
                      and _obj(s).get("time_role") == "TRAINING_MEMORY"
                      for s in _list(contract.get("allowed_sources")))))
        if memory:
            continue
        out.append({"evidence_id": str(eid), "source_ref": src or str(eid), "locator": item.get("locator", "ledger reference"), "scope": item.get("scope", "source index"), "used_for": item.get("used_for", "judgment claim")})
    return out


def compile_staged_judgment_ledger(ledger: Any, source_index: Any | None = None, contract: Any | None = None) -> dict[str, Any]:
    """Compile a ledger into an Episode and diagnostics sidecar.

    Returned ``episode`` is omitted when blocking diagnostics exist.  The input
    ledger is never mutated.
    """
    value = deepcopy(_obj(ledger)); validation = validate_staged_judgment_ledger(value, source_index, contract)
    if contract is None:
        validation["findings"].append(_diag("CONTRACT_REQUIRED", "contract", root_cause="MODEL", economic_impact="缺少训练合同无法确认身份、截止时间和来源权限"))
    if not isinstance(source_index, dict):
        validation["findings"].append(_diag("SOURCE_INDEX_REQUIRED", "source_index", root_cause="ACQUISITION_MODULE", economic_impact="缺少 canonical source index 无法确认 evidence_id 的来源、时点和责任边界"))
    diagnostics = validation["findings"]
    blocking = [d for d in diagnostics if d.get("severity") == "BLOCKING_MATERIAL"]
    if blocking:
        return {"episode": None, "diagnostics": {"schema_version": DIAGNOSTICS_SCHEMA, "state": "DIAGNOSTIC_ONLY", "findings": diagnostics}}
    claims = {str(c.get("surface")): c for c in _list(value.get("claims"))}
    def stmt(surface: str) -> str:
        return str(_obj(claims.get(surface)).get("statement", ""))
    industry = _obj(value.get("industry_future")); rev = list(value.get("reversal_observations", []))
    episode_id = str(value.get("ledger_id"));
    if not episode_id.startswith("EUE:"): episode_id = "EUE:" + episode_id
    situation = {"summary": stmt("INDUSTRY_FUTURE"), "industry_future_thesis": {
        "horizon": industry.get("horizon", ""), "most_likely_regime": industry.get("most_likely_regime", ""), "profit_pool_transmission": industry.get("profit_pool_transmission", ""), "company_exposure": industry.get("company_exposure", ""), "adaptation": industry.get("adaptation", ""), "normal_economics": industry.get("normal_economics", ""), "permanent_loss": industry.get("permanent_loss", ""), "valuation_treatment": industry.get("valuation_treatment", ""), "strongest_rival": industry.get("strongest_rival", ""), "reversal_observations": rev}}
    comps = []
    decisions = []
    for c in _list(value.get("components")):
        c = _obj(c); cid = c.get("component_id")
        comps.append({"component_id": cid, "treatment": c.get("treatment"), "reason": c.get("reason", ""), "investment_consequence": c.get("reason", ""), "promotion_or_resolution_condition": c.get("promotion_test", ""), "evidence_ids": list(c.get("evidence_ids", []))})
        decisions.append({k: c.get(k) for k in ("component_id", "economic_scope", "normal_earnings_use", "owner_cash_use", "financing_pressure_effect", "permanent_loss_use", "valuation_use", "valuation_route_bindings", "promotion_test", "invalidation_test")})
    value_claim = _obj(claims.get("VALUE_ROUTE")); route_bindings = []
    for d in decisions: route_bindings.extend(_list(d.get("valuation_route_bindings")))
    primary = [str(b.get("route_id")) for b in route_bindings if b.get("use") in {"PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT"}]
    excluded = [str(b.get("route_id")) for b in route_bindings if b.get("use") in {"EXCLUDED", "NOT_APPLICABLE"}]
    corrob = [str(b.get("route_id")) for b in route_bindings if b.get("use") == "CORROBORATIVE_INPUT"]
    stress = [str(b.get("route_id")) for b in route_bindings if b.get("use") == "STRESS_ONLY"]
    req_map: dict[str, dict[str, list[str]]] = {}
    for d in decisions:
        for b in _list(d.get("valuation_route_bindings")):
            rid, use = b.get("route_id"), b.get("use")
            if not rid:
                continue
            row = req_map.setdefault(str(rid), {"required_component_ids": [], "optional_component_ids": []})
            # Every explicit binding is a required component for that route;
            # this keeps the existing Episode contract's non-empty requirement
            # and preserves the declared use (primary/corroborative/excluded).
            if d.get("component_id") not in row["required_component_ids"]:
                row["required_component_ids"].append(d.get("component_id"))
    if not excluded:
        excluded = ["UNRESOLVED"]
        req_map.setdefault("UNRESOLVED", {"required_component_ids": [], "optional_component_ids": []})
    route = {"primary_routes": primary or ["UNRESOLVED"], "excluded_routes": excluded or ["UNRESOLVED"], "route_component_requirements": [{"route_id": rid, **vals} for rid, vals in sorted(req_map.items())], "route_reasoning": stmt("VALUE_ROUTE"), "valuation_model_roles": {"primary": primary or ["UNRESOLVED"], "corroborative": corrob, "stress": stress}}
    thesis = {"thesis_id": "UWT:" + episode_id.removeprefix("EUE:"), "central_path": stmt("SURVIVAL"), "normal_earnings_treatment": stmt("NORMALIZATION"), "owner_cash_treatment": stmt("SURVIVAL"), "permanent_loss_treatment": stmt("PERMANENT_LOSS"), "value_route_treatment": stmt("VALUE_ROUTE"), "economic_directions": {k: _obj(claims.get(s)).get("direction", "UNKNOWN") for k, s in (("normal_earnings", "NORMALIZATION"), ("owner_cash", "SURVIVAL"), ("permanent_loss", "PERMANENT_LOSS"))}, "strongest_rival": industry.get("strongest_rival", ""), "monitoring": "；".join(rev)}
    evidence_trace = _evidence_trace(value, source_index, contract)
    existing_refs = [{"kind": "LEDGER_EVIDENCE", "ref": e.get("source_ref"), "role": "staged ledger source"} for e in evidence_trace if e.get("source_ref")]
    episode = {"schema_version": EPISODE_SCHEMA, "episode_id": episode_id, "company_id": value.get("company_id"), "company_name": value.get("company_name"), "cutoff_at": value.get("cutoff_at"), "sample_identity": value.get("sample_identity"), "decision_frame": value.get("decision_frame"), "underwriting_route": value.get("underwriting_route"), "situation_model": situation, "business_position": stmt("BUSINESS_POSITION"), "survival_case": stmt("SURVIVAL"), "adaptation_case": stmt("ADAPTATION"), "normalization_case": stmt("NORMALIZATION"), "permanent_loss_map": stmt("PERMANENT_LOSS"), "value_route": route, "strongest_rival": industry.get("strongest_rival", ""), "reversal_observations": rev, "component_treatments": comps, "component_decisions": decisions, "evidence_trace": evidence_trace, "existing_object_refs": existing_refs, "underwriting_thesis": thesis, "investment_treatment": stmt("INVESTMENT_TREATMENT")}
    episode["component_decision_summary"] = derive_component_decision_summary(decisions)
    if isinstance(value.get("normal_earnings_bridge"), dict) or isinstance(value.get("driver_sensitivities"), list):
        episode["economic_derivation"] = {
            "schema_version": "enterprise-underwriting-economic-derivation.v1",
            "normal_earnings_bridge": deepcopy(value.get("normal_earnings_bridge") or {}),
            "driver_sensitivity_specs": deepcopy(value.get("driver_sensitivities") or []),
        }
        from scripts.enterprise_underwriting_episode import derive_economic_derivation_summary
        episode["economic_derivation_summary"] = derive_economic_derivation_summary(episode)
    ev = validate_enterprise_underwriting_episode(episode)
    training_ev = None
    if isinstance(contract, dict):
        training_ev = validate_training_episode(contract, episode)
        if training_ev.get("state") != "REVIEWABLE":
            diagnostics.extend(_diag("TRAINING_EPISODE_INVALID", p, economic_impact="训练合同绑定或下游契约失败", remediation="修复 contract identity/source/economic derivation 绑定") for p in training_ev.get("findings", []))
    if ev.get("state") != "REVIEWABLE":
        diagnostics.extend(_diag("EPISODE_INVALID", p, economic_impact="下游 Episode 无法消费", remediation="修复 Episode validator 指出的字段后重编译") for p in ev.get("findings", []))
    combined_ok = ev.get("state") == "REVIEWABLE" and (
        training_ev is None or training_ev.get("state") == "REVIEWABLE"
    )
    projection_validation = None
    if combined_ok:
        try:
            projections = compile_underwriting_projections(episode)
            projection_validation = validate_underwriting_projection_bundle(episode, projections)
            if projection_validation.get("state") != "REVIEWABLE":
                combined_ok = False
                diagnostics.extend(_diag("PROJECTION_INVALID", p, economic_impact="下游投影无法消费", remediation="修复 projection validator 指出的字段后重编译") for p in projection_validation.get("findings", []))
        except Exception as exc:
            combined_ok = False
            diagnostics.append(_diag("PROJECTION_INVALID", "projections", economic_impact="下游投影编译失败", remediation="修复 projection 编译错误后重编译"))
    return {"episode": episode if combined_ok else None, "diagnostics": {"schema_version": DIAGNOSTICS_SCHEMA, "state": "COMPILED" if combined_ok else "DIAGNOSTIC_ONLY", "findings": diagnostics}, "episode_validation": ev, "training_episode_validation": training_ev, "projection_validation": projection_validation}


# Short aliases used by callers and tests.
validate_ledger = validate_staged_judgment_ledger
compile = compile_staged_judgment_ledger
