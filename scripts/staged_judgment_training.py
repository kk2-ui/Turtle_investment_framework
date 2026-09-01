#!/usr/bin/env python3
"""Run the price-free J0 -> J1 -> J2 judgment protocol.

Each stage has a small authoring contract.  The compiler is the only code that
assembles a staged ledger and projects it to an EnterpriseUnderwritingEpisode;
it validates identity, source permissions, component/route compatibility and
downstream projections, but never invents a fact, range, sensitivity, price or
action.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

try:
    from scripts.enterprise_underwriting_training import (
        _canonical_ref,
        _mapping,
        _items,
        _text,
        validate_training_contract,
        _source_materials,
    )
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts.enterprise_underwriting_training import (
    _canonical_ref,
    _mapping,
    _items,
    _text,
    validate_training_contract,
    _source_materials,
    )
from scripts.staged_judgment_ledger import (
    COMPONENT_SCOPES,
    CLAIM_TREATMENTS,
    LEDGER_SCHEMA,
    compile_staged_judgment_ledger,
    validate_staged_judgment_ledger,
)

ROOT = Path(__file__).resolve().parents[1]
J0_SCHEMA = "staged-judgment-j0.v1"
J1_SCHEMA = "staged-judgment-j1.v1"
J2_SCHEMA = "staged-judgment-j2.v1"
TASK_SCHEMA = "staged-judgment-fresh-task.v1"
STAGE_SCHEMAS = {"J0": J0_SCHEMA, "J1": J1_SCHEMA, "J2": J2_SCHEMA}
J1_SURFACES = {"SURVIVAL", "BUSINESS_POSITION", "ADAPTATION", "NORMALIZATION", "PERMANENT_LOSS", "VALUE_ROUTE"}
J2_SURFACES = {"INDUSTRY_FUTURE", "INVESTMENT_TREATMENT"}
CLAIM_KEYS = {"claim_id", "surface", "statement", "direction", "mechanism", "treatment", "evidence_ids", "strongest_rival", "reversal_observations", "unknown"}
J0_COMPONENT_KEYS = {"component_id", "economic_scope", "question", "evidence_ids"}
J0_EVIDENCE_KEYS = {"evidence_id", "source_ref", "locator", "scope", "used_for"}
J2_INDUSTRY_KEYS = {"horizon", "most_likely_regime", "profit_pool_transmission", "company_exposure", "adaptation", "normal_economics", "permanent_loss", "valuation_treatment", "strongest_rival"}


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
    return parsed.astimezone(timezone.utc).replace(microsecond=0) if parsed.tzinfo else None


def _forbidden(value: Any, path: str = "$") -> list[str]:
    keys = {"price", "market_price", "share_price", "entry_price", "buyband", "buy_band", "expected_return", "realized_return", "outcome", "settlement", "investment_action", "portfolio_action", "action", "decision", "valuation_result", "position"}
    found: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            child_path = f"{path}.{key}"
            if str(key).lower() in keys:
                found.append(child_path)
            found.extend(_forbidden(child, child_path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(_forbidden(child, f"{path}[{index}]"))
    return found


def _allowed_sources(contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {_canonical_ref(item.get("source_ref")): item for item in _items(contract.get("allowed_sources")) if isinstance(item, dict)}


def _contract_findings(contract: Any) -> list[str]:
    result = validate_training_contract(contract)
    return [str(x) for x in result.get("findings", [])]


def _base_identity_findings(value: dict[str, Any], contract: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    for field in ("ledger_id", "company_id", "company_name", "cutoff_at"):
        if not _text(value.get(field)):
            findings.append(f"{field}_missing")
    for field in ("company_id", "company_name", "cutoff_at"):
        if value.get(field) != contract.get(field):
            findings.append(f"{field}_contract_mismatch")
    if value.get("sample_identity") != contract.get("sample_identity"):
        findings.append("sample_identity_contract_mismatch")
    if _instant(value.get("cutoff_at")) is None:
        findings.append("cutoff_at_invalid")
    findings.extend("price_firewall:" + path for path in _forbidden(value))
    return findings


def _evidence_findings(refs: Any, contract: dict[str, Any], *, require_source_ref: bool = True) -> list[str]:
    findings: list[str] = []
    allowed = _allowed_sources(contract)
    cutoff = _instant(contract.get("cutoff_at"))
    seen: set[str] = set()
    if not isinstance(refs, list) or not refs:
        return ["evidence_refs_missing"]
    for index, raw in enumerate(refs):
        item = _mapping(raw)
        if set(item) != J0_EVIDENCE_KEYS:
            findings.append(f"evidence[{index}]_fields_invalid")
        eid = item.get("evidence_id")
        source_ref = _canonical_ref(item.get("source_ref"))
        if not _text(eid) or eid in seen:
            findings.append(f"evidence[{index}]_id_missing_or_duplicate")
        seen.add(str(eid))
        if require_source_ref and source_ref not in allowed:
            findings.append(f"evidence[{index}]_source_not_allowed")
        source = allowed.get(source_ref, {})
        if source.get("time_role") == "TRAINING_MEMORY":
            findings.append(f"evidence[{index}]_training_memory_forbidden")
        available = _instant(source.get("available_at"))
        if cutoff and available and available > cutoff:
            findings.append(f"evidence[{index}]_available_after_cutoff")
        for field in ("source_ref", "locator", "scope", "used_for"):
            if not _text(item.get(field)):
                findings.append(f"evidence[{index}]_{field}_missing")
    return findings


def _evidence_id_findings(ids: Any, ref_ids: set[str], path: str) -> list[str]:
    if not isinstance(ids, list) or not ids:
        return [path + "_missing"]
    return [path + "_unresolved"] if any(str(item) not in ref_ids for item in ids) else []


def validate_stage(stage: str, payload: Any, contract: Any) -> dict[str, Any]:
    stage = str(stage).upper()
    value = _mapping(payload)
    c = _mapping(contract)
    findings: list[str] = _contract_findings(c) if c else ["contract_missing"]
    if stage not in STAGE_SCHEMAS:
        findings.append("stage_invalid")
        return {"schema_version": TASK_SCHEMA, "stage": stage, "state": "INVALID", "findings": list(dict.fromkeys(findings))}
    if value.get("schema_version") != STAGE_SCHEMAS[stage]:
        findings.append("schema_version_invalid")
    if value.get("stage") != stage:
        findings.append("stage_mismatch")
    findings.extend(_base_identity_findings(value, c))
    if stage == "J0":
        expected = {"schema_version", "stage", "stage_id", "ledger_id", "company_id", "company_name", "cutoff_at", "sample_identity", "decision_frame", "underwriting_route", "industry_company_questions", "components", "evidence_refs"}
        if set(value) != expected:
            findings.append("j0_fields_invalid")
        if not isinstance(value.get("industry_company_questions"), list) or not value["industry_company_questions"] or any(not _text(x) for x in value["industry_company_questions"]):
            findings.append("j0_questions_missing")
        refs = value.get("evidence_refs")
        findings.extend(_evidence_findings(refs, c))
        ref_ids = {str(_mapping(x).get("evidence_id")) for x in _items(refs)}
        components = _items(value.get("components")); ids: set[str] = set()
        if not components:
            findings.append("j0_components_missing")
        for index, component in enumerate(components):
            item = _mapping(component)
            if set(item) != J0_COMPONENT_KEYS:
                findings.append(f"j0_component[{index}]_fields_invalid")
            cid = str(item.get("component_id"))
            if not _text(item.get("component_id")) or cid in ids:
                findings.append(f"j0_component[{index}]_id_missing_or_duplicate")
            ids.add(cid)
            if item.get("economic_scope") not in COMPONENT_SCOPES:
                findings.append(f"j0_component[{index}]_scope_invalid")
            if not _text(item.get("question")):
                findings.append(f"j0_component[{index}]_question_missing")
            findings.extend(_evidence_id_findings(item.get("evidence_ids"), ref_ids, f"j0_component[{index}].evidence_ids"))
    elif stage == "J1":
        expected = {"schema_version", "stage", "stage_id", "ledger_id", "company_id", "company_name", "cutoff_at", "sample_identity", "components", "claims"}
        if set(value) != expected:
            findings.append("j1_fields_invalid")
        components = _items(value.get("components")); ids: set[str] = set()
        if not components:
            findings.append("j1_components_missing")
        has_excluded_route = False
        for index, item in enumerate(components):
            item = _mapping(item); cid = str(item.get("component_id"))
            required = {"component_id", "economic_scope", "treatment", "normal_earnings_use", "owner_cash_use", "financing_pressure_effect", "permanent_loss_use", "valuation_use", "valuation_route_bindings", "reason", "promotion_test", "invalidation_test", "evidence_ids"}
            if set(item) != required:
                findings.append(f"j1_component[{index}]_fields_invalid")
            if not _text(item.get("component_id")) or cid in ids:
                findings.append(f"j1_component[{index}]_id_missing_or_duplicate")
            ids.add(cid)
            if item.get("economic_scope") not in COMPONENT_SCOPES:
                findings.append(f"j1_component[{index}]_scope_invalid")
            for field in ("treatment", "normal_earnings_use", "owner_cash_use", "financing_pressure_effect", "permanent_loss_use", "valuation_use"):
                if not _text(item.get(field)):
                    findings.append(f"j1_component[{index}]_{field}_missing")
            if item.get("treatment") not in CLAIM_TREATMENTS:
                findings.append(f"j1_component[{index}]_treatment_invalid")
            if item.get("normal_earnings_use") not in {"BASE_RANGE", "CONDITIONAL_RANGE", "SCENARIO_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE"}:
                findings.append(f"j1_component[{index}]_normal_earnings_use_invalid")
            if item.get("owner_cash_use") not in {"BASE_RANGE", "CONDITIONAL_RANGE", "SCENARIO_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE"}:
                findings.append(f"j1_component[{index}]_owner_cash_use_invalid")
            if item.get("financing_pressure_effect") not in {"REDUCES", "NEUTRAL", "INCREASES", "CONDITIONAL", "UNRESOLVED", "NOT_APPLICABLE"}:
                findings.append(f"j1_component[{index}]_financing_pressure_effect_invalid")
            if item.get("permanent_loss_use") not in {"BASE_PATH", "CONDITIONAL_PATH", "STRESS_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE"}:
                findings.append(f"j1_component[{index}]_permanent_loss_use_invalid")
            if item.get("valuation_use") not in {"PRIMARY_INPUT", "CONDITIONAL_PRIMARY_INPUT", "CORROBORATIVE_INPUT", "SCENARIO_ONLY", "STRESS_ONLY", "EXCLUDED", "UNRESOLVED", "NOT_APPLICABLE"}:
                findings.append(f"j1_component[{index}]_valuation_use_invalid")
            for field in ("reason", "promotion_test", "invalidation_test"):
                if not _text(item.get(field)):
                    findings.append(f"j1_component[{index}]_{field}_missing")
            if not isinstance(item.get("valuation_route_bindings"), list):
                findings.append(f"j1_component[{index}]_route_bindings_invalid")
            else:
                has_excluded_route = has_excluded_route or any(
                    _mapping(binding).get("use") in {"EXCLUDED", "SCENARIO_ONLY", "UNRESOLVED", "NOT_APPLICABLE"}
                    for binding in _items(item.get("valuation_route_bindings"))
                )
        if not has_excluded_route:
            findings.append("j1_excluded_route_missing")
        claims = _items(value.get("claims")); surfaces: set[str] = set(); claim_ids: set[str] = set()
        if len(claims) != len(J1_SURFACES):
            findings.append("j1_claims_cardinality_invalid")
        if not claims:
            findings.append("j1_claims_missing")
        for index, claim in enumerate(claims):
            item = _mapping(claim)
            if set(item) != CLAIM_KEYS:
                findings.append(f"j1_claim[{index}]_fields_invalid")
            claim_id = str(item.get("claim_id"));
            if not _text(item.get("claim_id")) or claim_id in claim_ids:
                findings.append(f"j1_claim[{index}]_id_missing_or_duplicate")
            claim_ids.add(claim_id)
            surface = str(item.get("surface"));
            if surface in surfaces:
                findings.append(f"j1_claim[{index}]_surface_duplicate")
            surfaces.add(surface)
            if surface not in J1_SURFACES:
                findings.append(f"j1_claim[{index}]_surface_invalid")
            for field in ("claim_id", "statement", "mechanism", "strongest_rival"):
                if not _text(item.get(field)):
                    findings.append(f"j1_claim[{index}]_{field}_missing")
            if not isinstance(item.get("evidence_ids"), list) or not item.get("evidence_ids"):
                findings.append(f"j1_claim[{index}]_evidence_ids_missing")
            if not isinstance(item.get("reversal_observations"), list) or not item.get("reversal_observations"):
                findings.append(f"j1_claim[{index}]_reversal_missing")
            if item.get("direction") not in {"IMPROVES", "DETERIORATES", "MIXED", "UNKNOWN", "NONE"}:
                findings.append(f"j1_claim[{index}]_direction_invalid")
            if item.get("treatment") not in CLAIM_TREATMENTS:
                findings.append(f"j1_claim[{index}]_treatment_invalid")
        findings.extend(f"j1_claim_surface_missing:{surface}" for surface in sorted(J1_SURFACES - surfaces))
    else:
        expected = {"schema_version", "stage", "stage_id", "ledger_id", "company_id", "company_name", "cutoff_at", "sample_identity", "industry_future", "claims", "reversal_observations", "monitoring"}
        if set(value) != expected:
            findings.append("j2_fields_invalid")
        industry = _mapping(value.get("industry_future"))
        if set(industry) != J2_INDUSTRY_KEYS:
            findings.append("j2_industry_fields_invalid")
        for field in ("horizon", "most_likely_regime", "profit_pool_transmission", "company_exposure", "adaptation", "normal_economics", "permanent_loss", "valuation_treatment", "strongest_rival"):
            if not _text(industry.get(field)):
                findings.append(f"j2_industry_{field}_missing")
        if not _text(value.get("monitoring")):
            findings.append("j2_monitoring_missing")
        reversals = value.get("reversal_observations")
        if not isinstance(reversals, list) or not reversals or any(not _text(x) for x in reversals):
            findings.append("j2_reversal_missing")
        claims = _items(value.get("claims")); surfaces: set[str] = set(); claim_ids: set[str] = set()
        if len(claims) != len(J2_SURFACES):
            findings.append("j2_claims_cardinality_invalid")
        # J2 may only cite the evidence IDs established by J0.
        # The prior ledger is supplied by the caller during validation.
        for index, claim in enumerate(claims):
            item = _mapping(claim); claim_id = str(item.get("claim_id")); surface = str(item.get("surface"))
            if not _text(item.get("claim_id")) or claim_id in claim_ids:
                findings.append(f"j2_claim[{index}]_id_missing_or_duplicate")
            claim_ids.add(claim_id)
            if surface in surfaces:
                findings.append(f"j2_claim[{index}]_surface_duplicate")
            surfaces.add(surface)
            if set(item) != CLAIM_KEYS or surface not in J2_SURFACES:
                findings.append(f"j2_claim[{index}]_invalid")
            for field in ("claim_id", "statement", "mechanism", "strongest_rival"):
                if not _text(item.get(field)):
                    findings.append(f"j2_claim[{index}]_{field}_missing")
            if not isinstance(item.get("evidence_ids"), list) or not item.get("evidence_ids"):
                findings.append(f"j2_claim[{index}]_evidence_ids_missing")
            if not isinstance(item.get("reversal_observations"), list) or not item.get("reversal_observations"):
                findings.append(f"j2_claim[{index}]_reversal_missing")
            if item.get("direction") not in {"IMPROVES", "DETERIORATES", "MIXED", "UNKNOWN", "NONE"}:
                findings.append(f"j2_claim[{index}]_direction_invalid")
            if item.get("treatment") not in CLAIM_TREATMENTS:
                findings.append(f"j2_claim[{index}]_treatment_invalid")
        findings.extend(f"j2_claim_surface_missing:{surface}" for surface in sorted(J2_SURFACES - surfaces))
    return {"schema_version": TASK_SCHEMA, "stage": stage, "state": "REVIEWABLE" if not findings else "INVALID", "findings": list(dict.fromkeys(findings))}


def _stage_system(stage: str) -> str:
    if stage == "J0":
        return """你只负责 J0 上下文账本，不生成完整 Episode，也不要输出 staged-judgment-ledger.v1。输出必须严格是 staged-judgment-j0.v1，且只能有这些键：schema_version、stage、stage_id、ledger_id、company_id、company_name、cutoff_at、sample_identity、decision_frame、underwriting_route、industry_company_questions、components、evidence_refs。components 的每项只能有 component_id、economic_scope、question、evidence_ids；economic_scope 必须逐字使用以下枚举之一：SURVIVAL_FINANCING、MATURE_CORE_NORMAL_EARNINGS、ORDINARY_SHARE_OWNER_CASH、GROWTH_CAPITAL_RETURN、NONCORE_OR_OPTIONAL_ASSET、OTHER_MATERIAL_COMPONENT，不能把自然语言说明放进 economic_scope（说明写入 question）。evidence_refs 的每项只能有 evidence_id、source_ref、locator、scope、used_for。只用 packet 中截止前公司来源；TRAINING_MEMORY 只能改变问题顺序，不能进入 evidence_refs。不要写 claims、industry_future、component_treatments、component_decisions、价格、收益、估值结果、行动或 outcome。"""
    if stage == "J1":
        return """你只负责 J1 经济判断账本，不生成完整 Episode，也不要输出 staged-judgment-ledger.v1。输出必须严格是 staged-judgment-j1.v1，顶层只能有 schema_version、stage、stage_id、ledger_id、company_id、company_name、cutoff_at、sample_identity、components、claims。components 必须逐一复用 J0 的 component_id；每项只能有 component_id、economic_scope（SURVIVAL_FINANCING/MATURE_CORE_NORMAL_EARNINGS/ORDINARY_SHARE_OWNER_CASH/GROWTH_CAPITAL_RETURN/NONCORE_OR_OPTIONAL_ASSET/OTHER_MATERIAL_COMPONENT）、treatment（UNDERWRITE/CONDITIONALLY_UNDERWRITE/SCENARIO_ONLY/EXCLUDE_FROM_BASE/CANNOT_BOUND）、normal_earnings_use 与 owner_cash_use（BASE_RANGE/CONDITIONAL_RANGE/SCENARIO_ONLY/EXCLUDED/UNRESOLVED/NOT_APPLICABLE）、financing_pressure_effect（REDUCES/NEUTRAL/INCREASES/CONDITIONAL/UNRESOLVED/NOT_APPLICABLE）、permanent_loss_use（BASE_PATH/CONDITIONAL_PATH/STRESS_ONLY/EXCLUDED/UNRESOLVED/NOT_APPLICABLE）、valuation_use（PRIMARY_INPUT/CONDITIONAL_PRIMARY_INPUT/CORROBORATIVE_INPUT/SCENARIO_ONLY/STRESS_ONLY/EXCLUDED/UNRESOLVED/NOT_APPLICABLE）、valuation_route_bindings（每项 route_id + use，use 使用同一 valuation_use 枚举）、reason、promotion_test、invalidation_test、evidence_ids。claims 必须是数组（不能是按 surface 索引的对象），恰好六项覆盖 SURVIVAL、BUSINESS_POSITION、ADAPTATION、NORMALIZATION、PERMANENT_LOSS、VALUE_ROUTE；每项必须恰好有以下十个键：claim_id、surface、statement、direction、mechanism、treatment、evidence_ids、strongest_rival、reversal_observations、unknown。direction 只能 IMPROVES/DETERIORATES/MIXED/UNKNOWN/NONE，treatment 使用上述五值；statement、mechanism、strongest_rival、reversal_observations 都必须是非空投资语义。确定性编译器检查 ID、路线兼容和覆盖；不要补写桥接数值、价格、收益、估值结果、行动或 outcome。"""
    return """你只负责 J2 投资论点账本，不生成完整 Episode，也不要输出 staged-judgment-ledger.v1。输出必须严格是 staged-judgment-j2.v1，顶层只能有 schema_version、stage、stage_id、ledger_id、company_id、company_name、cutoff_at、sample_identity、industry_future、claims、reversal_observations、monitoring。industry_future 只包含 horizon、most_likely_regime、profit_pool_transmission、company_exposure、adaptation、normal_economics、permanent_loss、valuation_treatment、strongest_rival；claims 必须是数组（不能是按 surface 索引的对象），恰好两项覆盖 INDUSTRY_FUTURE、INVESTMENT_TREATMENT，每项必须恰好有 claim_id、surface、statement、direction、mechanism、treatment、evidence_ids、strongest_rival、reversal_observations、unknown，direction 只能 IMPROVES/DETERIORATES/MIXED/UNKNOWN/NONE，treatment 使用 UNDERWRITE/CONDITIONALLY_UNDERWRITE/SCENARIO_ONLY/EXCLUDE_FROM_BASE/CANNOT_BOUND。不要写 component_decisions、economic_derivation、价格、收益、估值结果、行动或 outcome。"""


def render_stage_task(contract: Any, stage: str, *, j0: Any | None = None, j1: Any | None = None) -> dict[str, Any]:
    c = _mapping(contract); stage = str(stage).upper()
    validation = validate_training_contract(c)
    if validation.get("state") != "REVIEWABLE":
        raise ValueError("training_contract_invalid:" + ",".join(validation.get("findings", [])))
    if stage in {"J1", "J2"}:
        if j0 is None:
            raise ValueError("prior_stage_missing:J0")
        j0_validation = validate_stage("J0", j0, c)
        if j0_validation.get("state") != "REVIEWABLE":
            raise ValueError("prior_stage_not_accepted:J0:" + ",".join(j0_validation.get("findings", [])))
    if stage == "J2":
        if j1 is None:
            raise ValueError("prior_stage_missing:J1")
        j1_validation = validate_stage("J1", j1, c)
        if j1_validation.get("state") != "REVIEWABLE":
            raise ValueError("prior_stage_not_accepted:J1:" + ",".join(j1_validation.get("findings", [])))
    materials = _source_materials(c)
    blocks = []
    for item in materials:
        source = next((s for s in _items(c.get("allowed_sources")) if _canonical_ref(s.get("source_ref")) == _canonical_ref(item.get("source_ref"))), {})
        blocks.append("\n".join(["<source>", "source_ref=" + str(item.get("source_ref")), "time_role=" + str(source.get("time_role")), str(item.get("content")), "</source>"]))
    prior = ""
    if stage == "J1":
        prior = "\nAccepted J0 ledger (read-only context; do not rewrite its evidence):\n" + json.dumps(j0, ensure_ascii=False, indent=2)
    elif stage == "J2":
        prior = "\nAccepted J0 ledger:\n" + json.dumps(j0, ensure_ascii=False, indent=2) + "\nAccepted J1 ledger:\n" + json.dumps(j1, ensure_ascii=False, indent=2)
    user = "\n".join(["按以下合同生成本阶段唯一 JSON。", json.dumps(c, ensure_ascii=False, indent=2, sort_keys=True), prior, "\n来源材料：", "\n\n".join(blocks), "\n只返回本阶段 JSON 对象。"])
    return {"schema_version": TASK_SCHEMA, "execution_mode": "CODEX_FRESH_SUBAGENT", "stage": stage, "contract_id": c.get("contract_id"), "required_context": "fork_turns=none; read only this packet", "messages": [{"role": "system", "content": _stage_system(stage)}, {"role": "user", "content": user}], "response_contract": {"schema_version": STAGE_SCHEMAS[stage], "must_not_read": ["parent_context", "sibling_outputs", "outcome", "price", "external_model_api"]}, "state": "FRESH_STAGE_TASK_READY"}


def _source_index(j0: dict[str, Any], contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    allowed = _allowed_sources(contract)
    out = {}
    for raw in _items(j0.get("evidence_refs")):
        item = _mapping(raw); ref = _canonical_ref(item.get("source_ref")); source = allowed.get(ref, {})
        out[str(item.get("evidence_id"))] = {"source_ref": ref, "available_at": source.get("available_at"), "time_role": source.get("time_role"), "locator": item.get("locator"), "scope": item.get("scope"), "used_for": item.get("used_for")}
    return out


def compile_stages(contract: Any, j0: Any, j1: Any, j2: Any) -> dict[str, Any]:
    c = _mapping(contract); v0 = validate_stage("J0", j0, c); v1 = validate_stage("J1", j1, c); v2 = validate_stage("J2", j2, c)
    stage_validations = {"J0": v0, "J1": v1, "J2": v2}
    if any(v.get("state") != "REVIEWABLE" for v in stage_validations.values()):
        return {"state": "DIAGNOSTIC_ONLY", "stage_validations": stage_validations, "diagnostics": {"root_cause": "MODEL", "message": "stage ledger validation failed"}, "episode": None}
    a, b, d = _mapping(j0), _mapping(j1), _mapping(j2)
    j0_ids = {str(_mapping(item).get("component_id")) for item in _items(a.get("components"))}
    j1_ids = {str(_mapping(item).get("component_id")) for item in _items(b.get("components"))}
    j0_scopes = {str(_mapping(item).get("component_id")): _mapping(item).get("economic_scope") for item in _items(a.get("components"))}
    j1_scopes = {str(_mapping(item).get("component_id")): _mapping(item).get("economic_scope") for item in _items(b.get("components"))}
    if j0_ids != j1_ids:
        return {"state": "DIAGNOSTIC_ONLY", "stage_validations": stage_validations, "diagnostics": {"root_cause": "MODEL", "message": "J1 component IDs do not exactly match J0"}, "episode": None}
    if j0_scopes != j1_scopes:
        return {"state": "DIAGNOSTIC_ONLY", "stage_validations": stage_validations, "diagnostics": {"root_cause": "MODEL", "message": "J1 component economic_scope does not exactly match J0"}, "episode": None}
    evidence_ids = {str(_mapping(item).get("evidence_id")) for item in _items(a.get("evidence_refs"))}
    referenced_ids = {
        str(eid)
        for item in _items(b.get("components")) + _items(b.get("claims")) + _items(d.get("claims"))
        for eid in _items(_mapping(item).get("evidence_ids"))
    }
    unresolved = sorted(referenced_ids - evidence_ids)
    if unresolved:
        return {"state": "DIAGNOSTIC_ONLY", "stage_validations": stage_validations, "diagnostics": {"root_cause": "ACQUISITION_MODULE", "message": "J1/J2 cite evidence IDs not established by J0: " + ",".join(unresolved)}, "episode": None}
    claims = deepcopy(_items(b.get("claims"))) + deepcopy(_items(d.get("claims")))
    industry = deepcopy(_mapping(d.get("industry_future"))); industry["reversal_observations"] = deepcopy(_items(d.get("reversal_observations")))
    ledger = {"schema_version": LEDGER_SCHEMA, "ledger_id": a.get("ledger_id"), "company_id": a.get("company_id"), "company_name": a.get("company_name"), "cutoff_at": a.get("cutoff_at"), "sample_identity": a.get("sample_identity"), "status": "FROZEN", "decision_frame": a.get("decision_frame"), "underwriting_route": a.get("underwriting_route"), "claims": claims, "components": deepcopy(_items(b.get("components"))), "industry_future": industry, "reversal_observations": deepcopy(_items(d.get("reversal_observations"))), "evidence_refs": deepcopy(_items(a.get("evidence_refs"))), "diagnostics": []}
    # Optional derivation keys are omitted when the contract does not authorize them.
    result = compile_staged_judgment_ledger(ledger, _source_index(a, c), c)
    result["stage_validations"] = stage_validations
    result["ledger"] = ledger
    result["state"] = result.get("diagnostics", {}).get("state", "DIAGNOSTIC_ONLY")
    return result


def _load(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    render = sub.add_parser("render-task"); render.add_argument("contract"); render.add_argument("stage", choices=["J0", "J1", "J2"]); render.add_argument("--output", required=True); render.add_argument("--j0"); render.add_argument("--j1")
    validate = sub.add_parser("validate-stage"); validate.add_argument("contract"); validate.add_argument("stage", choices=["J0", "J1", "J2"]); validate.add_argument("response")
    compile_cmd = sub.add_parser("compile"); compile_cmd.add_argument("contract"); compile_cmd.add_argument("--j0", required=True); compile_cmd.add_argument("--j1", required=True); compile_cmd.add_argument("--j2", required=True); compile_cmd.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    if args.command == "render-task":
        task = render_stage_task(_load(args.contract), args.stage, j0=_load(args.j0) if args.j0 else None, j1=_load(args.j1) if args.j1 else None)
        Path(args.output).write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"state": "FRESH_STAGE_TASK_READY", "stage": args.stage, "task_path": str(Path(args.output).resolve())}, ensure_ascii=False))
        return 0
    if args.command == "validate-stage":
        result = validate_stage(args.stage, _load(args.response), _load(args.contract)); print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if result["state"] == "REVIEWABLE" else 1
    result = compile_stages(_load(args.contract), _load(args.j0), _load(args.j1), _load(args.j2))
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    (output / "staged_judgment_ledger.json").write_text(json.dumps(result.get("ledger"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "stage_validations.json").write_text(json.dumps(result.get("stage_validations"), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "staged_compile_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result.get("episode") is not None:
        (output / "enterprise_underwriting_episode.json").write_text(json.dumps(result["episode"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"state": result.get("state"), "output_dir": str(output.resolve()), "episode": bool(result.get("episode"))}, ensure_ascii=False))
    return 0 if result.get("state") == "COMPILED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
