#!/usr/bin/env python3
"""Rebind structured research artifacts after an approved market-only refresh.

The refresh is allowed only when decisive-question identities and qualitative
research semantics are unchanged.  Numeric premises, opaque calculation IDs,
and directly dependent prose are then rebuilt from deterministic sources.
"""

from __future__ import annotations

import argparse
import json
import shutil
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.claim_evidence import claim_ledger_fingerprint, persist_claim_evidence_ledger
    from scripts.computation_evidence import build_calculation_observations
    from scripts.decisive_question import persist_decisive_question_findings
    from scripts.market_refresh_promotion import _at, _entry_value, _load, _replace_contextual_market_values
    from scripts.insight_ledger import insight_fingerprint, persist_insight_ledger
    from scripts.thesis_test_gate import persist_thesis_test_ledger, thesis_test_fingerprint
    from scripts.valuation_model_gate import persist_valuation_model_ledger, valuation_fingerprint
except ModuleNotFoundError:
    from claim_evidence import claim_ledger_fingerprint, persist_claim_evidence_ledger
    from computation_evidence import build_calculation_observations
    from decisive_question import persist_decisive_question_findings
    from market_refresh_promotion import _at, _entry_value, _load, _replace_contextual_market_values
    from insight_ledger import insight_fingerprint, persist_insight_ledger
    from thesis_test_gate import persist_thesis_test_ledger, thesis_test_fingerprint
    from valuation_model_gate import persist_valuation_model_ledger, valuation_fingerprint


SCHEMA_VERSION = "market-refresh-structured.v1"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _refresh_return_decomposition_model(
    model: dict[str, Any], *, dividend_yield_pct: float
) -> None:
    """Refresh M003 without re-adding already-derived decision-ledger margins."""
    assumptions = model.setdefault("assumptions", {})
    assumptions["dividend_yield_pct"] = dividend_yield_pct
    growth_return = float(assumptions.get("growth_value_return_pct") or 0)
    required_return = float(assumptions.get("required_return_pct") or 0)
    moat_decay = float(assumptions.get("moat_decay_pct") or 0)
    gross_return = float(dividend_yield_pct) + growth_return
    result = model.setdefault("result", {})
    result["gross_return_pct"] = round(gross_return, 1)
    result["return_safety_margin_pct"] = round(
        gross_return - required_return - moat_decay, 1
    )


def _plan_invariants(plan: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(plan)
    for key in ("generated_at", "input_sources", "input_fingerprint", "validation"):
        value.pop(key, None)
    for group in ("selected_questions", "rejected_candidates"):
        for item in value.get(group) or []:
            if not isinstance(item, dict):
                continue
            item.pop("question", None)
            score = item.get("score")
            if isinstance(score, dict):
                score.pop("basis", None)
            link = item.get("decision_link")
            if isinstance(link, dict):
                link.pop("sensitivity_basis", None)
                for policy in (link.get("premise_assessment_policy") or {}).values():
                    if isinstance(policy, dict):
                        policy.pop("interpretation_rule", None)
    return value


def _calculation_map(payload: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[tuple[str, str], dict[str, Any]]]:
    by_id: dict[str, dict[str, Any]] = {}
    by_path: dict[tuple[str, str], dict[str, Any]] = {}
    for item in payload.get("calculations") or []:
        if not isinstance(item, dict):
            continue
        by_id[str(item.get("calculation_id") or "")] = item
        by_path[(str(item.get("tool") or ""), str(item.get("metric_path") or ""))] = item
    return by_id, by_path


def _premise_values(plan: dict[str, Any]) -> dict[tuple[str, str], Any]:
    values: dict[tuple[str, str], Any] = {}
    for question in plan.get("selected_questions") or []:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("question_id") or "")
        sensitivity = ((question.get("decision_link") or {}).get("sensitivity_basis") or {})

        def walk(value: Any, prefix: str = "") -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{prefix}.{key}" if prefix else str(key))
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{prefix}[{index}]")
            else:
                values[(question_id, prefix)] = value

        walk(sensitivity)
    return values


def _rewrite_tree(value: Any, rewrite_text) -> Any:
    if isinstance(value, dict):
        return {key: _rewrite_tree(item, rewrite_text) for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_tree(item, rewrite_text) for item in value]
    return rewrite_text(value) if isinstance(value, str) else value


def refresh_structured_dependencies(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    promotion = _load(output / "market_refresh_promotion.json")
    old_plan = _load(output / "decisive_question_plan.json")
    candidate_plan = _load(output / "decisive_question_plan_candidate.json")
    old_calculations = _load(output / "calculation_observations.json")
    old_findings = _load(output / "decisive_question_findings.json")
    old_claims = _load(output / "claim_evidence.json")
    if promotion.get("state") not in {"PROMOTED_PENDING_VALIDATION", "PROMOTED_VALIDATED"}:
        return {"state": "BLOCKED", "findings": ["market_promotion_missing"]}
    if not all((old_plan, candidate_plan, old_calculations, old_findings, old_claims)):
        return {"state": "BLOCKED", "findings": ["structured_refresh_input_missing"]}
    old_ids = [item.get("question_id") for item in old_plan.get("selected_questions") or []]
    new_ids = [item.get("question_id") for item in candidate_plan.get("selected_questions") or []]
    if old_ids != new_ids or _plan_invariants(old_plan) != _plan_invariants(candidate_plan):
        return {"state": "BLOCKED", "findings": ["decisive_plan_semantic_change_requires_research"]}

    archive = Path(str(promotion.get("archive_dir") or "")) / "structured"
    archive.mkdir(parents=True, exist_ok=True)
    for name in (
        "decisive_question_plan.json", "decisive_question_findings.json",
        "calculation_observations.json", "claim_evidence.json",
    ):
        source = output / name
        if source.is_file() and not (archive / name).exists():
            shutil.copy2(source, archive / name)

    candidate_plan["validation"]["enforced"] = True
    _write(output / "decisive_question_plan.json", candidate_plan)
    _write(output / "decisive_question_validation.json", candidate_plan["validation"])
    new_calculations = build_calculation_observations(output, persist=True)
    old_by_id, _ = _calculation_map(old_calculations)
    _, new_by_path = _calculation_map(new_calculations)
    id_remap: dict[str, str] = {}
    for old_id, old_row in old_by_id.items():
        new_row = new_by_path.get((str(old_row.get("tool") or ""), str(old_row.get("metric_path") or "")))
        if new_row:
            id_remap[old_id] = str(new_row.get("calculation_id") or old_id)

    old_bundle = _load(Path(str(promotion.get("archive_dir"))) / "compute_bundle.json")
    new_bundle = _load(output / "compute_bundle.json")
    old_ledger = _load(Path(str(promotion.get("archive_dir"))) / "decision_ledger.json")
    new_ledger = _load(output / "decision_ledger.json")

    old_error_min = _at(old_bundle, "factor3.error_propagation.gg_min")
    new_error_min = _at(new_bundle, "factor3.error_propagation.gg_min")
    old_error_max = _at(old_bundle, "factor3.error_propagation.gg_max")
    new_error_max = _at(new_bundle, "factor3.error_propagation.gg_max")

    def rewrite_text(text: str) -> str:
        result = _replace_contextual_market_values(
            text, old_ledger=old_ledger, new_ledger=new_ledger,
            old_bundle=old_bundle, new_bundle=new_bundle,
        )
        if "误差" in result or "error_range" in result:
            if isinstance(old_error_min, (int, float)) and isinstance(new_error_min, (int, float)):
                result = result.replace(str(old_error_min), str(new_error_min))
            if isinstance(old_error_max, (int, float)) and isinstance(new_error_max, (int, float)):
                result = result.replace(str(old_error_max), str(new_error_max))
        for old_id, new_id in id_remap.items():
            result = result.replace(old_id, new_id)
        return result

    claims = _rewrite_tree(deepcopy(old_claims), rewrite_text)
    new_by_id, _ = _calculation_map(new_calculations)
    for claim in claims.get("claims") or []:
        for evidence in claim.get("raw_facts") or []:
            if not isinstance(evidence, dict) or not evidence.get("calculation_id"):
                continue
            row = new_by_id.get(str(evidence.get("calculation_id")))
            if not row:
                continue
            evidence["fact"] = f"{row.get('metric_path')}={row.get('value')} {row.get('unit')}"
            evidence["source_group_id"] = f"derived:{row.get('tool')}:{row.get('input_fingerprint')}"
    claims["change_reason"] = "Approved market refresh: deterministic calculation identity and dependent numeric-text rebind"
    if isinstance(claims.get("freeze"), dict) and claims["freeze"].get("frozen"):
        claims["freeze"]["fingerprint"] = claim_ledger_fingerprint(claims)
    claim_result = persist_claim_evidence_ledger(
        output, claims,
        report_text="\n\n".join((output / "chapters" / f"_ch{i:02d}.md").read_text(encoding="utf-8") for i in range(15)),
        allow_frozen_update=True,
    )
    if not claim_result.get("written"):
        return {"state": "INVALID", "findings": ["claim_rebind_failed"], "claim": claim_result}

    findings = _rewrite_tree(deepcopy(old_findings), rewrite_text)
    findings["plan_input_fingerprint"] = candidate_plan.get("input_fingerprint")
    findings["change_reason"] = "Approved market refresh: deterministic premise value and CALC identity rebind"
    current_premises = _premise_values(candidate_plan)
    for finding in findings.get("findings") or []:
        question_id = str(finding.get("question_id") or "")
        assessment = finding.get("resolution_assessment") or {}
        for premise in assessment.get("premise_resolution") or []:
            key = str(premise.get("premise_key") or "")
            if (question_id, key) in current_premises:
                premise["plan_value"] = current_premises[(question_id, key)]
    findings_result = persist_decisive_question_findings(output, findings)
    if not findings_result.get("written"):
        return {"state": "INVALID", "findings": ["decisive_findings_rebind_failed"], "decisive": findings_result}

    report_text = "\n\n".join(
        (output / "chapters" / f"_ch{i:02d}.md").read_text(encoding="utf-8")
        for i in range(15)
    )
    for name in ("valuation_model.json", "thesis_test.json", "insight_ledger.json"):
        source = output / name
        if source.is_file() and not (archive / name).exists():
            shutil.copy2(source, archive / name)

    valuation = _load(output / "valuation_model.json")
    for model in valuation.get("models") or []:
        if not isinstance(model, dict) or model.get("model_id") != "M003":
            continue
        _refresh_return_decomposition_model(
            model,
            dividend_yield_pct=float(_at(new_bundle, "factor4.dps_yield_pretax")),
        )
    valuation["change_reason"] = "Approved market refresh: M003 market-dependent return decomposition updated"
    if isinstance(valuation.get("freeze"), dict) and valuation["freeze"].get("frozen"):
        valuation["freeze"]["fingerprint"] = valuation_fingerprint(valuation)
    valuation_result = persist_valuation_model_ledger(
        output, valuation, report_text=report_text, allow_frozen_update=True,
    )
    if not valuation_result.get("written"):
        return {"state": "INVALID", "findings": ["valuation_rebind_failed"], "valuation": valuation_result}

    thesis = _load(output / "thesis_test.json")
    for threshold in thesis.get("thresholds") or []:
        if not isinstance(threshold, dict) or threshold.get("threshold_id") != "TH004":
            continue
        threshold["current_value"] = _entry_value(new_ledger, "D001")
        threshold["threshold_value"] = _entry_value(new_ledger, "D013")
        threshold["basis_description"] = (
            "由DPS_native+g×V_final_native的综合回报分子与r*+decay门槛反推；"
            "只有基本面阈值均未恶化才允许买入。"
        )
        threshold["source_ids"] = ["compute_bundle.json", "market_snapshot.json"]
    thesis["change_reason"] = "Approved market refresh: TH004 rebound to canonical combined-return buy trigger"
    if isinstance(thesis.get("freeze"), dict) and thesis["freeze"].get("frozen"):
        thesis["freeze"]["fingerprint"] = thesis_test_fingerprint(thesis)
    thesis_result = persist_thesis_test_ledger(
        output, thesis, report_text=report_text, allow_frozen_update=True,
    )
    if not thesis_result.get("written"):
        return {"state": "INVALID", "findings": ["thesis_rebind_failed"], "thesis": thesis_result}

    insight = _load(output / "insight_ledger.json")
    insight = _rewrite_tree(insight, rewrite_text)
    question_id = str((insight.get("question_basis") or {}).get("question_id") or "")
    current_question = next((
        str(item.get("question")) for item in candidate_plan.get("selected_questions") or []
        if isinstance(item, dict) and str(item.get("question_id")) == question_id
    ), "")
    if current_question:
        insight["decisive_question"] = current_question
    old_buy = float(_entry_value(old_ledger, "D013"))
    new_buy = float(_entry_value(new_ledger, "D013"))
    old_market_price = float(_entry_value(old_ledger, "D001"))
    new_market_price = float(_entry_value(new_ledger, "D001"))

    def rewrite_actions(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: rewrite_actions(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite_actions(item) for item in value]
        if not isinstance(value, str):
            return value
        result = value
        if any(token in result for token in ("买入", "加仓", "门槛", "TH004", "升级")):
            result = result.replace(f"{old_buy:.2f}", f"{new_buy:.2f}")
        result = result.replace("维持1.5%观察仓", "既有持仓维持1.5%；未持有者在P_buy以上保持0%")
        return result

    insight = rewrite_actions(insight)
    reverse = insight.setdefault("reverse_expectations", {})
    reverse["current_price"] = new_market_price
    epv = next((
        float((model.get("result") or {}).get("unadjusted_epv_rmb_m"))
        for model in valuation.get("models") or []
        if isinstance(model, dict) and model.get("model_id") == "M001"
    ), 0.0)
    payout = next((
        float((model.get("assumptions") or {}).get("payout_ratio"))
        for model in valuation.get("models") or []
        if isinstance(model, dict) and model.get("model_id") == "M001"
    ), 0.0)
    old_mc, new_mc = float(_at(old_bundle, "market.mc_rmb")), float(_at(new_bundle, "market.mc_rmb"))
    old_ratio = old_mc / epv if epv else 0.0
    new_ratio = new_mc / epv if epv else 0.0
    old_lambda = (old_ratio - payout) / (1 - payout) if payout < 1 else 0.0
    new_lambda = (new_ratio - payout) / (1 - payout) if payout < 1 else 0.0
    old_floor = old_mc * float(_entry_value(old_ledger, "D008")) / 100
    new_floor = new_mc * float(_entry_value(new_ledger, "D008")) / 100

    def rewrite_reverse(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: rewrite_reverse(item) for key, item in value.items()}
        if isinstance(value, list):
            return [rewrite_reverse(item) for item in value]
        if not isinstance(value, str):
            return value
        result = value.replace(f"{old_ratio * 100:.2f}", f"{new_ratio * 100:.2f}")
        if "市场隐含" in result or "反推λ" in result or "认可约" in result:
            result = result.replace(f"{old_lambda:.2f}", f"{new_lambda:.2f}")
            result = result.replace(f"{old_lambda * 100:.0f}%", f"{new_lambda * 100:.0f}%")
        if "正常化利润" in result or "当前市值" in result:
            result = result.replace(f"{old_floor:.1f}", f"{new_floor:.1f}")
        return result

    insight["reverse_expectations"] = rewrite_reverse(reverse)
    insight["change_reason"] = "Approved market refresh: decisive question, reverse expectation and action dependencies updated"
    insight["updated_at"] = _now()
    if isinstance(insight.get("freeze"), dict) and insight["freeze"].get("frozen"):
        insight["freeze"]["fingerprint"] = insight_fingerprint(insight)
    insight_result = persist_insight_ledger(
        output, insight, report_text=report_text, allow_frozen_update=True,
    )
    if not insight_result.get("written"):
        return {"state": "INVALID", "findings": ["insight_rebind_failed"], "insight": insight_result}

    overlay = {
        "schema_version": "market-refresh-judgment-overlay.v1", "state": "CURRENT",
        "generated_at": _now(), "historical_artifacts": [
            "judgment_review.json", "judgment_research_plan.json",
            "judgment_research_execution.json", "judgment_research_synthesis.json",
        ],
        "note": "Historical research evidence remains immutable; all embedded prices/actions are superseded by this canonical overlay.",
        "canonical": {
            "market_price": new_market_price, "buy_trigger": new_buy,
            "position_scope": "existing_holders_only_above_buy_trigger",
            "position_pct": _entry_value(new_ledger, "D012"),
            "price_margin_pct": _entry_value(new_ledger, "D010"),
            "return_margin_pct_point": _entry_value(new_ledger, "D011"),
            "decision_ledger_fingerprint": promotion.get("promoted_ledger_fingerprint"),
        },
    }
    _write(output / "market_refresh_judgment_overlay.json", overlay)

    result = {
        "schema_version": SCHEMA_VERSION, "state": "REFRESHED",
        "status": "PASS", "generated_at": _now(),
        "archive_dir": str(archive), "question_ids": new_ids,
        "calculation_id_remap_count": len(id_remap),
        "claim_state": claim_result["validation"].get("state"),
        "decisive_state": findings_result["validation"].get("state"),
        "valuation_state": valuation_result["validation"].get("state"),
        "thesis_state": thesis_result["validation"].get("state"),
        "insight_state": insight_result.get("state"),
    }
    _write(output / "market_refresh_structured_validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    result = refresh_structured_dependencies(args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("state") == "REFRESHED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
