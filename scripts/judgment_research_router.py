#!/usr/bin/env python3
"""Route judgment-review gaps into bounded, company-agnostic research tasks."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-research-plan.v2"
LEGACY_SCHEMA_VERSIONS = {"judgment-research-plan.v1"}
ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route": "governance_and_value_realization",
        "pattern": r"控制|治理|董事|关联|财务公司|分红|派息|回购|资金迁移|资本配置|股东",
        "tools": ["search_report", "read_section"],
        "sections": ["GOV", "NOTES", "RISK", "AUDIT"],
        "source_types": ["annual_report", "company_announcement", "transaction_or_deposit_terms"],
        "ledgers": ["claim_evidence", "thesis_test", "insight", "judgment_review"],
    },
    {
        "route": "peer_and_base_rate",
        "pattern": r"同类|同业|可比|行业|基准率|分布|历史样本|竞争对手",
        "tools": ["get_peer_comparison", "web_search", "web_fetch"],
        "sections": [],
        "source_types": ["peer_primary_filings", "official_industry_data", "independent_dataset"],
        "ledgers": ["claim_evidence", "thesis_test", "insight", "judgment_review"],
    },
    {
        "route": "market_implied_expectations",
        "pattern": r"市场参与者|市场共识|卖方|分析师|预期|定价|估值反应|股价反应",
        "tools": ["get_market_data", "web_search", "web_fetch"],
        "sections": [],
        "source_types": ["dated_market_data", "public_research", "event_timeline"],
        "ledgers": ["claim_evidence", "valuation_model", "insight", "judgment_review"],
    },
    {
        "route": "operating_model_rebuild",
        "pattern": r"正常化|分部|利润|收入|毛利|费用率|现金流|资本开支|敏感性|模型|桥",
        "tools": ["get_financial_statement", "get_financial_trends", "search_report", "read_section"],
        "sections": ["MDA", "SEG", "STMT", "NOTES"],
        "source_types": ["annual_report", "segment_note", "financial_statement"],
        "ledgers": ["claim_evidence", "valuation_model", "decision", "insight", "judgment_review"],
    },
    {
        "route": "contract_and_regulation",
        "pattern": r"合同|协议|条款|监管|牌照|诉讼|担保|期限|违约|支取",
        "tools": ["search_report", "read_section", "web_search", "web_fetch"],
        "sections": ["NOTES", "RISK", "GOV", "AUDIT"],
        "source_types": ["contract_or_agreement", "regulatory_document", "annual_report"],
        "ledgers": ["claim_evidence", "thesis_test", "decision", "insight", "judgment_review"],
    },
)
DEFAULT_ROUTE = {
    "route": "primary_source_gap",
    "tools": ["search_report", "read_section"],
    "sections": ["MDA", "NOTES", "RISK"],
    "source_types": ["annual_report", "company_announcement"],
    "ledgers": ["claim_evidence", "insight", "judgment_review"],
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _route(text: str) -> dict[str, Any]:
    # Preserve mixed research needs rather than forcing a governance/model/peer
    # question into a single bucket. One primary route drives the label; tools,
    # source types and ledgers are the bounded union of all relevant routes.
    ranked: list[tuple[int, int, dict[str, Any]]] = []
    for idx, spec in enumerate(ROUTES):
        hits = len(set(re.findall(spec["pattern"], text, re.I)))
        if hits:
            ranked.append((hits, -idx, spec))
    if not ranked:
        return {**DEFAULT_ROUTE, "secondary_routes": []}
    ranked.sort(key=lambda item: (-item[0], -item[1]))
    primary = ranked[0][2]
    # Strongly explicit document/base-rate/market/model wording outranks a
    # larger number of generic governance words in the same sentence.
    overrides = (
        (r"协议|合同|条款|提前支取|担保|监管文件", "contract_and_regulation"),
        (r"同类|同业|可比|基准率|样本分布", "peer_and_base_rate"),
        (r"市场参与者|市场共识|卖方|分析师|估值反应|股价反应", "market_implied_expectations"),
        (r"正常化|分部重建|利润桥|现金流桥|模型敏感性", "operating_model_rebuild"),
    )
    matched_specs = [item[2] for item in ranked]
    hit_counts = {item[2]["route"]: item[0] for item in ranked}
    for pattern, route_name in overrides:
        candidate = next((spec for spec in matched_specs if spec["route"] == route_name), None)
        if (
            candidate is not None
            and re.search(pattern, text, re.I)
            and (hit_counts.get(route_name, 0) >= 2 or ranked[0][0] <= 1)
        ):
            primary = candidate
            break
    ordered = [primary] + [spec for spec in matched_specs if spec["route"] != primary["route"]]
    merged: dict[str, Any] = {
        "route": primary["route"],
        "secondary_routes": [spec["route"] for spec in ordered[1:]],
        "tools": list(primary["tools"]),
        "optional_tools": list(dict.fromkeys(
            value for spec in ordered[1:] for value in spec["tools"]
            if value not in primary["tools"]
        )),
    }
    for key in ("sections", "source_types", "ledgers"):
        merged[key] = list(dict.fromkeys(value for spec in ordered for value in spec[key]))
    return merged


def route_research_need(text: str) -> dict[str, Any]:
    """Public, side-effect-free route shared by pre-writing question planning."""
    return dict(_route(str(text or "")))


def _priority(text: str, verdict: str, *, fragile: bool) -> str:
    decision_words = r"估值|价值|仓位|买入|卖出|退出|减仓|回报|永久损失|结论|动作"
    if fragile and re.search(decision_words, text):
        return "critical"
    if verdict == "FRAGILE" or re.search(decision_words, text):
        return "high"
    return "normal"


def _impacted_chapters(insight_ledger: dict[str, Any], insight_id: str) -> list[int]:
    for item in insight_ledger.get("insights") or []:
        if isinstance(item, dict) and str(item.get("insight_id")) == insight_id:
            chapters = sorted({int(ch) for ch in item.get("chapters") or [] if isinstance(ch, int) and 0 <= ch <= 14})
            if chapters:
                return chapters[:6]
    return [0, 14]


def _task(
    task_id: str,
    origin: str,
    question: str,
    needed_evidence: str,
    consequence: str,
    verdict: str,
    chapters: list[int],
    *,
    fragile: bool,
) -> dict[str, Any]:
    route = _route(" ".join((question, needed_evidence, consequence)))
    priority = _priority(consequence + " " + needed_evidence, verdict, fragile=fragile)
    required_primary = 1
    required_independent = 1 if route["route"] in {"peer_and_base_rate", "market_implied_expectations"} else 0
    return {
        "task_id": task_id,
        "origin": origin,
        "priority": priority,
        "research_question": question,
        "why_it_matters": consequence,
        "needed_evidence": needed_evidence,
        "route": route["route"],
        "secondary_routes": route.get("secondary_routes", []),
        "required_tools": route["tools"],
        "optional_tools": route.get("optional_tools", []),
        "annual_report_sections": route["sections"],
        "required_source_types": route["source_types"],
        "minimum_evidence": {
            "primary_sources": required_primary,
            "independent_sources": required_independent,
            "same_origin_reprints_count_as_one": True,
        },
        "stopping_rule": {
            "max_tool_calls": 8,
            "max_source_tool_calls": 8,
            "max_mutation_tool_calls": max(2, len(chapters) + len(route["ledgers"]) + 2),
            "stop_when": "The evidence can discriminate the core claim from its strongest alternative, or primary sources explicitly show the requested information is unavailable.",
            "unavailable_is_a_valid_outcome": True,
        },
        "mutation_scope": {
            "chapters": chapters,
            "ledgers": route["ledgers"],
            "decision_change_requires_explicit_diff": "decision" in route["ledgers"],
        },
    }


def build_judgment_research_plan(output_dir: str | Path, *, max_tasks_per_run: int = 3) -> dict[str, Any]:
    output = Path(output_dir)
    review = _load(output / "judgment_review.json")
    insight = _load(output / "insight_ledger.json")
    verdict = str(review.get("ceiling_verdict") or "NOT_ASSESSABLE").upper()
    distinctive = review.get("distinctive_insight") or {}
    insight_id = str(distinctive.get("insight_id") or "")
    chapters = _impacted_chapters(insight, insight_id)
    tasks: list[dict[str, Any]] = []
    sequence = 1
    for item in review.get("fragile_leaps") or []:
        if not isinstance(item, dict):
            continue
        tasks.append(_task(
            f"JR{sequence:03d}", "fragile_leap", str(item.get("claim") or ""),
            str(item.get("needed_evidence") or ""), str(item.get("decision_consequence") or ""),
            verdict, chapters, fragile=True,
        ))
        sequence += 1
    for item in review.get("missing_information") or []:
        text = str(item or "").strip()
        if not text:
            continue
        tasks.append(_task(
            f"JR{sequence:03d}", "missing_information", f"Can the missing information be established: {text}",
            text, str((review.get("decision_dependency") or {}).get("conclusion") or review.get("verdict_basis") or ""),
            verdict, chapters, fragile=False,
        ))
        sequence += 1
    rank = {"critical": 0, "high": 1, "normal": 2}
    tasks.sort(key=lambda item: (rank[item["priority"]], item["task_id"]))
    cap = max(0, min(int(max_tasks_per_run), 3))
    queue = [item["task_id"] for item in tasks[:cap]]
    plan = {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(review.get("report_id") or insight.get("report_id") or output.name),
        "generated_at": _now(),
        "source_review_verdict": verdict,
        "state": "PLANNED" if tasks else "NO_ACTION",
        "execution_policy": {
            "max_tasks_per_run": cap,
            "max_tool_calls_per_task": 8,
            "execute_in_priority_order": True,
            "rerun_judgment_review_after_execution": bool(queue),
            "structured_findings_required": bool(queue),
            "independent_synthesis_context": bool(queue),
            "stop_if_no_new_evidence": True,
        },
        "execution_queue": queue,
        "backlog_task_ids": [item["task_id"] for item in tasks[cap:]],
        "tasks": tasks,
        "allowed_mutations": [
            "append new source artifacts", "update affected structured ledgers",
            "rewrite only mutation_scope.chapters when evidence changes a claim",
        ],
        "forbidden_mutations": [
            "rewrite_all_chapters", "expand_unaffected_chapters", "optimize_score_or_length",
            "change_canonical_decision_without_decision_diff", "treat_missing_public_information_as_positive_evidence",
        ],
        "policy_note": "This plan improves the framework's research selectivity; it is not a request to lengthen the report.",
    }
    return plan


def validate_judgment_research_plan(payload: dict[str, Any]) -> dict[str, Any]:
    invalid: list[str] = []
    schema_version = str(payload.get("schema_version") or "")
    if schema_version not in LEGACY_SCHEMA_VERSIONS | {SCHEMA_VERSION}:
        invalid.append("schema_version_invalid")
    tasks = payload.get("tasks")
    if not isinstance(tasks, list):
        invalid.append("tasks_not_array")
        tasks = []
    known_routes = {item["route"] for item in ROUTES} | {DEFAULT_ROUTE["route"]}
    ids: list[str] = []
    for idx, task in enumerate(tasks):
        if not isinstance(task, dict):
            invalid.append(f"tasks[{idx}]:not_object")
            continue
        task_id = str(task.get("task_id") or "")
        ids.append(task_id)
        if not task_id:
            invalid.append(f"tasks[{idx}]:task_id_missing")
        if task.get("route") not in known_routes:
            invalid.append(f"{task_id}:route_invalid")
        scope = task.get("mutation_scope") or {}
        chapters = scope.get("chapters") or []
        if len(chapters) > 6 or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters):
            invalid.append(f"{task_id}:chapter_scope_too_broad_or_invalid")
        stopping = task.get("stopping_rule") or {}
        if not 1 <= int(stopping.get("max_source_tool_calls") or stopping.get("max_tool_calls") or 0) <= 8:
            invalid.append(f"{task_id}:tool_budget_invalid")
    if len(ids) != len(set(ids)):
        invalid.append("duplicate_task_ids")
    queue = payload.get("execution_queue") or []
    if len(queue) > 3 or any(item not in ids for item in queue):
        invalid.append("execution_queue_invalid")
    policy = payload.get("execution_policy") or {}
    if schema_version == SCHEMA_VERSION and queue and not policy.get("structured_findings_required"):
        invalid.append("structured_findings_policy_missing")
    if schema_version == SCHEMA_VERSION and queue and not policy.get("independent_synthesis_context"):
        invalid.append("independent_synthesis_policy_missing")
    forbidden = set(payload.get("forbidden_mutations") or [])
    for required in ("rewrite_all_chapters", "optimize_score_or_length", "change_canonical_decision_without_decision_diff"):
        if required not in forbidden:
            invalid.append(f"forbidden_mutation_guard_missing:{required}")
    return {
        "schema_version": "judgment-research-plan-validation.v1",
        "state": "INVALID" if invalid else "READY",
        "status": "FAIL" if invalid else "PASS",
        "invalid_findings": list(dict.fromkeys(invalid)),
        "task_count": len(tasks),
        "queued_task_count": len(queue),
        "blocking": False,
    }


def persist_judgment_research_plan(output_dir: str | Path, *, max_tasks_per_run: int = 3) -> dict[str, Any]:
    output = Path(output_dir)
    plan = build_judgment_research_plan(output, max_tasks_per_run=max_tasks_per_run)
    validation = validate_judgment_research_plan(plan)
    (output / "judgment_research_plan_validation.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if validation["state"] == "INVALID":
        return {"written": False, "validation": validation, "error": "invalid_judgment_research_plan"}
    path = output / "judgment_research_plan.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        from scripts.judgment_research_execution import initialize_judgment_research_execution
    except ModuleNotFoundError:
        from judgment_research_execution import initialize_judgment_research_execution
    execution = initialize_judgment_research_execution(output)
    return {"written": True, "path": str(path), "plan": plan, "validation": validation, "execution": execution}


def evaluate_output_judgment_research_plan(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    payload = _load(output / "judgment_research_plan.json")
    if not payload:
        return {
            "schema_version": "judgment-research-plan-validation.v1", "state": "NOT_PLANNED",
            "status": "SKIP", "invalid_findings": [], "task_count": 0,
            "queued_task_count": 0, "blocking": False,
        }
    return validate_judgment_research_plan(payload)
