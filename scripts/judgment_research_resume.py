#!/usr/bin/env python3
"""Select the next bounded judgment-research pass without replaying prior work."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


LEDGER_WRITE_TOOLS = {
    "claim_evidence": "write_claim_evidence_ledger",
    "valuation_model": "write_valuation_model_ledger",
    "decision": "write_decision_ledger",
    "thesis_test": "write_thesis_test_ledger",
    "insight": "write_insight_ledger",
    "judgment_review": "write_judgment_review",
}


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def next_judgment_research_pass(output_dir: str | Path) -> dict[str, Any] | None:
    """Return the active task, otherwise the first pending task.

    The returned object is deliberately self-contained so a caller can create a
    brand-new ``TurtleAgent`` context.  Completed task transcripts are excluded;
    only their compact execution events remain in the on-disk ledger.
    """
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    if not plan:
        return None
    try:
        from scripts.judgment_research_execution import initialize_judgment_research_execution
    except ModuleNotFoundError:
        from judgment_research_execution import initialize_judgment_research_execution
    ledger = initialize_judgment_research_execution(output)
    if ledger.get("state") in {"COMPLETE", "NO_ACTION", "VIOLATION"}:
        return None
    active = str(ledger.get("active_task_id") or "")
    queue = [str(item) for item in ledger.get("execution_queue") or []]
    if active:
        task_id = active
        resume = True
    else:
        pending = [
            item for item in queue
            if ((ledger.get("tasks") or {}).get(item) or {}).get("status") == "PENDING"
        ]
        if not pending:
            return None
        task_id = pending[0]
        resume = False
    task = next(
        (item for item in plan.get("tasks") or [] if isinstance(item, dict) and item.get("task_id") == task_id),
        None,
    )
    if not isinstance(task, dict):
        return None
    entry = ((ledger.get("tasks") or {}).get(task_id) or {})
    calls = list(entry.get("tool_calls") or [])
    usable_sources = [
        {
            "source_id": str(item.get("source_id")),
            "tool": str(item.get("tool")),
            "arguments": dict(item.get("arguments") or {}),
        }
        for item in calls
        if item.get("source_id") and item.get("ok")
    ]
    completion_repair = {
        "submission_attempts": int(entry.get("submission_attempts") or 0),
        "last_submission_errors": list(entry.get("last_submission_errors") or []),
        "previous_source_ids": list(entry.get("source_ids") or []),
        "previous_finding": dict(entry.get("finding") or {}),
        "actual_changes": list(entry.get("actual_changes") or []),
        "usable_sources": usable_sources,
    }
    max_calls = int(
        (task.get("stopping_rule") or {}).get("max_source_tool_calls")
        or (task.get("stopping_rule") or {}).get("max_tool_calls") or 0
    )
    successful = sorted({str(item.get("tool")) for item in calls if item.get("ok")})
    attempted = sorted({str(item.get("tool")) for item in calls if item.get("executed", True)})
    required = [str(item) for item in task.get("required_tools") or []]
    remaining_required = [item for item in required if item not in successful]
    unattempted_required = [item for item in required if item not in attempted]
    scope = task.get("mutation_scope") or {}
    if not resume:
        # Before activation there is exactly one legal action. Narrow schemas
        # prevent models from racing ahead with source or mutation calls.
        allowed_tools = {"begin_judgment_research_task"}
    else:
        allowed_tools = {
            "complete_judgment_research_task",
            "read_chapter",
            "read_report_contract_pack",
            *required,
            *(str(item) for item in task.get("optional_tools") or []),
        }
        # Mutations become visible only after every required route has really
        # been attempted. This keeps evidence acquisition and writeback phases
        # distinct without preventing PUBLIC_INFO_UNAVAILABLE completion.
        if not unattempted_required:
            if scope.get("chapters"):
                allowed_tools.add("write_chapter")
            for ledger_name in scope.get("ledgers") or []:
                tool = LEDGER_WRITE_TOOLS.get(str(ledger_name))
                if tool:
                    allowed_tools.add(tool)
            if "decision" in set(scope.get("ledgers") or []):
                allowed_tools.add("write_decision_manifest")
    return {
        "task_id": task_id,
        "resume": resume,
        "task": task,
        "entry": entry,
        "successful_tools": successful,
        "attempted_tools": attempted,
        "remaining_required_tools": remaining_required,
        "unattempted_required_tools": unattempted_required,
        "remaining_tool_calls": max(
            0, max_calls - sum(
                bool(item.get("counts_toward_source_budget", str(item.get("tool")) in {
                    "search_report", "read_section", "web_search", "web_fetch",
                    "get_peer_comparison", "get_market_data", "get_financial_statement",
                    "get_financial_trends", "read_zone_data",
                }))
                for item in calls
            )
        ),
        "allowed_tools": sorted(allowed_tools),
        "completion_repair": completion_repair,
    }


def judgment_task_iteration_budget(context: dict[str, Any], cap: int = 14) -> int:
    """Bound LLM turns independently from the task's verified tool-call budget."""
    remaining = max(0, int(context.get("remaining_tool_calls") or 0))
    # Source turns plus a bounded post-research phase for contract read, scoped
    # mutations, structured completion, and one correction turn.
    return max(6, min(max(6, int(cap)), remaining + 6))
