#!/usr/bin/env python3
"""Execution ledger and mutation guards for bounded judgment research tasks."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-research-execution.v1"
OUTCOMES = {"EVIDENCE_FOUND", "PUBLIC_INFO_UNAVAILABLE", "NO_DECISION_CHANGE", "DECISION_CHANGED"}
SOURCE_TOOLS = {
    "search_report", "read_section", "web_search", "web_fetch",
    "get_peer_comparison", "get_market_data", "get_financial_statement",
    "get_financial_trends", "read_zone_data",
}
INDEPENDENT_SOURCE_TOOLS = {"web_fetch", "get_peer_comparison"}
PRIMARY_SOURCE_TOOLS = {"search_report", "read_section", "get_financial_statement", "get_financial_trends", "read_zone_data"}
LEDGER_TOOL_MAP = {
    "write_claim_evidence_ledger": "claim_evidence",
    "write_valuation_model_ledger": "valuation_model",
    "write_decision_ledger": "decision",
    "write_decision_manifest": "decision",
    "write_thesis_test_ledger": "thesis_test",
    "write_insight_ledger": "insight",
    "write_judgment_review": "judgment_review",
}
LEDGER_FILES = {
    "claim_evidence": "claim_evidence.json",
    "valuation_model": "valuation_model.json",
    "decision": "decision_ledger.json",
    "thesis_test": "thesis_test.json",
    "insight": "insight_ledger.json",
    "judgment_review": "judgment_review.json",
}
CONTROL_TOOLS = {"begin_judgment_research_task", "complete_judgment_research_task", "plan_judgment_research"}


def _usable_source_result(tool_name: str, value: Any) -> tuple[bool, str]:
    """Distinguish a successful Python call from usable research evidence."""
    if tool_name not in SOURCE_TOOLS:
        return True, ""
    if not isinstance(value, dict):
        return False, "source_result_not_object"
    if value.get("error"):
        return False, "source_result_contains_error"
    if tool_name == "web_search":
        return (bool(value.get("results")), "web_search_no_results")
    if tool_name == "web_fetch":
        text = str(value.get("text") or value.get("content") or "").strip()
        return (bool(text) and int(value.get("char_count") or len(text)) > 0, "web_fetch_empty")
    if tool_name == "search_report":
        return (int(value.get("total_hits") or 0) > 0 and bool(value.get("hits")), "search_report_no_hits")
    if tool_name == "read_section":
        return (bool(str(value.get("text") or "").strip()), "read_section_empty")
    if tool_name == "get_peer_comparison":
        usable = int(value.get("peer_count_total") or value.get("peer_count") or 0) > 0 or bool(value.get("peers"))
        return (usable, "peer_comparison_empty")
    usable = bool(value)
    return (usable, "structured_source_empty")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _sha(path: Path) -> str | None:
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _plan_fingerprint(plan: dict[str, Any]) -> str:
    stable = {key: value for key, value in plan.items() if key != "generated_at"}
    raw = json.dumps(stable, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _chapter_path(output: Path, idx: int) -> Path:
    path = output / "chapters" / f"_ch{idx:02d}.md"
    return path if path.exists() else output / f"_ch{idx:02d}.md"


def _mutation_snapshot(output: Path) -> dict[str, str | None]:
    snapshot = {f"chapter:{idx}": _sha(_chapter_path(output, idx)) for idx in range(15)}
    snapshot.update({f"ledger:{name}": _sha(output / filename) for name, filename in LEDGER_FILES.items()})
    return snapshot


def _plan_task(plan: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next((item for item in plan.get("tasks") or [] if isinstance(item, dict) and item.get("task_id") == task_id), None)


def initialize_judgment_research_execution(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    existing = _load(output / "judgment_research_execution.json")
    plan_hash = _plan_fingerprint(plan)
    if existing and existing.get("plan_sha256") == plan_hash:
        return existing
    superseded_path = ""
    if existing:
        history_dir = output / "judgment_research_history"
        history_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        archive = history_dir / f"judgment_research_execution_{stamp}.json"
        counter = 1
        while archive.exists():
            archive = history_dir / f"judgment_research_execution_{stamp}_{counter}.json"
            counter += 1
        archive.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        superseded_path = str(archive)
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "report_id": plan.get("report_id") or output.name,
        "plan_sha256": plan_hash,
        "state": "PENDING" if plan.get("execution_queue") else "NO_ACTION",
        "active_task_id": None,
        "execution_queue": list(plan.get("execution_queue") or []),
        "tasks": {
            task_id: {
                "status": "PENDING", "started_at": None, "completed_at": None,
                "tool_calls": [], "source_ids": [], "outcome": None,
                "new_evidence_summary": "", "finding": {}, "finding_validation": {},
                "actual_changes": [], "violations": [],
            }
            for task_id in plan.get("execution_queue") or []
        },
        "created_at": _now(),
        "updated_at": _now(),
        "blocking": False,
        "supersedes_execution": superseded_path or None,
    }
    (output / "judgment_research_execution.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return ledger


def _persist(output: Path, ledger: dict[str, Any]) -> None:
    ledger["updated_at"] = _now()
    (output / "judgment_research_execution.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def restart_judgment_research_execution(
    output_dir: str | Path, *, reason: str, allowed_states: tuple[str, ...] = ("VIOLATION",)
) -> dict[str, Any]:
    """Archive a failed execution and restart the unchanged plan explicitly."""
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    existing = _load(output / "judgment_research_execution.json")
    if str(existing.get("state") or "") not in set(allowed_states):
        return {"restarted": False, "error": "execution_state_not_restartable", "state": existing.get("state")}
    if len(str(reason or "").strip()) < 12:
        return {"restarted": False, "error": "restart_reason_too_thin"}
    history_dir = output / "judgment_research_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = history_dir / f"judgment_research_execution_{stamp}.json"
    counter = 1
    while archive.exists():
        archive = history_dir / f"judgment_research_execution_{stamp}_{counter}.json"
        counter += 1
    archived = dict(existing)
    archived["superseded_reason"] = str(reason).strip()
    archived["superseded_at"] = _now()
    archive.write_text(json.dumps(archived, ensure_ascii=False, indent=2), encoding="utf-8")
    queue = list(plan.get("execution_queue") or [])
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "report_id": plan.get("report_id") or output.name,
        "plan_sha256": _plan_fingerprint(plan),
        "state": "PENDING" if queue else "NO_ACTION",
        "active_task_id": None,
        "execution_queue": queue,
        "tasks": {
            task_id: {
                "status": "PENDING", "started_at": None, "completed_at": None,
                "tool_calls": [], "source_ids": [], "outcome": None,
                "new_evidence_summary": "", "finding": {}, "finding_validation": {},
                "actual_changes": [], "violations": [],
            }
            for task_id in queue
        },
        "created_at": _now(), "updated_at": _now(), "blocking": False,
        "supersedes_execution": str(archive),
    }
    _persist(output, ledger)
    return {"restarted": True, "archive_path": str(archive), "execution": ledger}


def retry_violated_judgment_research_task(
    output_dir: str | Path, *, task_id: str, reason: str
) -> dict[str, Any]:
    """Retry one violated task while preserving all prior completed tasks."""
    output = Path(output_dir)
    ledger = _load(output / "judgment_research_execution.json")
    task_id = str(task_id)
    if ledger.get("state") != "VIOLATION" or ledger.get("active_task_id"):
        return {"retried": False, "error": "execution_not_in_retryable_violation_state"}
    entry = ((ledger.get("tasks") or {}).get(task_id) or {})
    if entry.get("status") != "VIOLATION":
        return {"retried": False, "error": "task_not_violated"}
    if len(str(reason or "").strip()) < 12:
        return {"retried": False, "error": "retry_reason_too_thin"}
    queue = list(ledger.get("execution_queue") or [])
    try:
        position = queue.index(task_id)
    except ValueError:
        return {"retried": False, "error": "task_not_in_execution_queue"}
    if any(((ledger.get("tasks") or {}).get(item) or {}).get("status") != "COMPLETE" for item in queue[:position]):
        return {"retried": False, "error": "prior_tasks_not_complete"}
    history_dir = output / "judgment_research_history"
    history_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    archive = history_dir / f"judgment_research_execution_{stamp}.json"
    counter = 1
    while archive.exists():
        archive = history_dir / f"judgment_research_execution_{stamp}_{counter}.json"
        counter += 1
    archived = dict(ledger)
    archived["superseded_reason"] = str(reason).strip()
    archived["superseded_at"] = _now()
    archive.write_text(json.dumps(archived, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger["tasks"][task_id] = {
        "status": "PENDING", "started_at": None, "completed_at": None,
        "tool_calls": [], "source_ids": [], "outcome": None,
        "new_evidence_summary": "", "finding": {}, "finding_validation": {},
        "actual_changes": [], "violations": [],
        "retry_of_archive": str(archive), "retry_reason": str(reason).strip(),
    }
    ledger["state"] = "PENDING"
    ledger["active_task_id"] = None
    ledger["blocking"] = False
    ledger["supersedes_execution"] = str(archive)
    _persist(output, ledger)
    return {
        "retried": True, "task_id": task_id, "archive_path": str(archive),
        "preserved_completed_tasks": queue[:position], "execution": ledger,
    }


def begin_judgment_research_task(output_dir: str | Path, task_id: str) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    ledger = initialize_judgment_research_execution(output)
    task_id = str(task_id)
    if ledger.get("active_task_id"):
        return {"started": False, "error": f"active_task_exists:{ledger['active_task_id']}"}
    queue = list(ledger.get("execution_queue") or [])
    pending = [item for item in queue if (ledger.get("tasks") or {}).get(item, {}).get("status") == "PENDING"]
    if not pending or task_id != pending[0]:
        return {"started": False, "error": "task_must_follow_execution_queue", "next_task_id": pending[0] if pending else None}
    task = _plan_task(plan, task_id)
    if task is None:
        return {"started": False, "error": "unknown_task_id"}
    entry = ledger["tasks"][task_id]
    entry["status"] = "ACTIVE"
    entry["started_at"] = _now()
    entry["before_snapshot"] = _mutation_snapshot(output)
    ledger["active_task_id"] = task_id
    ledger["state"] = "ACTIVE"
    _persist(output, ledger)
    return {"started": True, "task": task, "budget": task.get("stopping_rule"), "mutation_scope": task.get("mutation_scope")}


def preflight_judgment_tool_call(output_dir: str | Path, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir)
    ledger = _load(output / "judgment_research_execution.json")
    task_id = str(ledger.get("active_task_id") or "")
    if not task_id:
        if str(tool_name) == "assemble_report" and ledger.get("state") == "PENDING":
            return {
                "allowed": False,
                "enforced": True,
                "error": "queued_judgment_research_must_run_in_fresh_context_before_assembly",
            }
        return {"allowed": True, "enforced": False}
    plan = _load(output / "judgment_research_plan.json")
    task = _plan_task(plan, task_id) or {}
    entry = (ledger.get("tasks") or {}).get(task_id) or {}
    name = str(tool_name)
    if name in CONTROL_TOOLS:
        return {"allowed": True, "enforced": True, "task_id": task_id}
    max_calls = int(
        (task.get("stopping_rule") or {}).get("max_source_tool_calls")
        or (task.get("stopping_rule") or {}).get("max_tool_calls") or 0
    )
    calls = list(entry.get("tool_calls") or [])
    source_calls = [item for item in calls if str(item.get("tool")) in SOURCE_TOOLS]
    attempted = {str(item.get("tool")) for item in source_calls}
    required = set(task.get("required_tools") or [])
    unattempted_required = required - attempted
    remaining_slots = max(0, max_calls - len(source_calls))
    if str(tool_name) in SOURCE_TOOLS and len(source_calls) >= max_calls:
        return {"allowed": False, "enforced": True, "task_id": task_id, "error": "judgment_research_tool_budget_exhausted"}
    if (
        str(tool_name) in SOURCE_TOOLS
        and remaining_slots <= len(unattempted_required)
        and str(tool_name) not in unattempted_required
    ):
        return {
            "allowed": False, "enforced": True, "task_id": task_id,
            "error": "judgment_research_budget_reserved_for_unattempted_required_tools",
            "unattempted_required_tools": sorted(unattempted_required),
        }
    mutation_tools = {
        "write_chapter", "write_decision_manifest", *LEDGER_TOOL_MAP.keys()
    }
    mutation_calls = [item for item in calls if str(item.get("tool")) in mutation_tools]
    scope = task.get("mutation_scope") or {}
    max_mutation_calls = int(
        (task.get("stopping_rule") or {}).get("max_mutation_tool_calls")
        or max(2, len(scope.get("chapters") or []) + len(scope.get("ledgers") or []) + 2)
    )
    if str(tool_name) in mutation_tools and len(mutation_calls) >= max_mutation_calls:
        return {
            "allowed": False, "enforced": True, "task_id": task_id,
            "error": "judgment_research_mutation_call_budget_exhausted",
        }
    optional = set(task.get("optional_tools") or [])
    scope = task.get("mutation_scope") or {}
    allowed_ledgers = set(scope.get("ledgers") or [])
    if name in SOURCE_TOOLS and name not in required | optional:
        return {"allowed": False, "enforced": True, "task_id": task_id, "error": f"tool_outside_task_route:{name}"}
    if name == "write_chapter":
        chapter = int(arguments.get("chapter_index", -1))
        if chapter not in set(scope.get("chapters") or []):
            return {"allowed": False, "enforced": True, "task_id": task_id, "error": f"chapter_outside_mutation_scope:{chapter}"}
    if name in LEDGER_TOOL_MAP and LEDGER_TOOL_MAP[name] not in allowed_ledgers:
        return {"allowed": False, "enforced": True, "task_id": task_id, "error": f"ledger_outside_mutation_scope:{LEDGER_TOOL_MAP[name]}"}
    if name == "assemble_report":
        return {"allowed": False, "enforced": True, "task_id": task_id, "error": "active_judgment_research_task_must_be_completed_before_assembly"}
    return {"allowed": True, "enforced": True, "task_id": task_id}


def record_judgment_tool_call(
    output_dir: str | Path,
    tool_name: str,
    arguments: dict[str, Any],
    result: dict[str, Any],
    *,
    verifiable: bool = True,
) -> dict[str, Any]:
    if str(tool_name) in CONTROL_TOOLS:
        return {"recorded": False, "reason": "control_tool"}
    output = Path(output_dir)
    ledger = _load(output / "judgment_research_execution.json")
    task_id = str(ledger.get("active_task_id") or "")
    if not task_id:
        return {"recorded": False, "reason": "no_active_task"}
    entry = (ledger.get("tasks") or {}).get(task_id)
    if not isinstance(entry, dict):
        return {"recorded": False, "reason": "active_task_missing"}
    value = result.get("value") if isinstance(result, dict) else None
    summary_args = {
        key: arguments.get(key) for key in ("query", "url", "year", "section", "chapter_index", "ts_code", "code")
        if key in arguments
    }
    envelope_ok = bool(result.get("ok")) and bool(verifiable)
    usable, unusable_reason = _usable_source_result(str(tool_name), value)
    event = {
        "sequence": len(entry.get("tool_calls") or []) + 1,
        "tool": str(tool_name),
        "counts_toward_source_budget": str(tool_name) in SOURCE_TOOLS,
        "ok": envelope_ok and usable,
        "executed": bool(result.get("ok")),
        "verifiable": bool(verifiable),
        "unusable_reason": "" if envelope_ok and usable else unusable_reason or "tool_execution_failed_or_unverifiable",
        "arguments": summary_args,
        "result_chars": len(json.dumps(value, ensure_ascii=False, default=str)) if value is not None else 0,
        "called_at": _now(),
    }
    if str(tool_name) in SOURCE_TOOLS:
        event["source_id"] = f"{task_id}:S{event['sequence']:02d}:{tool_name}"
    entry.setdefault("tool_calls", []).append(event)
    _persist(output, ledger)
    return {
        "recorded": True, "task_id": task_id, "sequence": event["sequence"],
        "source_id": event.get("source_id"), "evidence_usable": event["ok"],
        "unusable_reason": event.get("unusable_reason"),
    }


def complete_judgment_research_task(
    output_dir: str | Path,
    task_id: str,
    outcome: str,
    source_ids: list[str],
    new_evidence_summary: str,
    finding: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    plan = _load(output / "judgment_research_plan.json")
    ledger = _load(output / "judgment_research_execution.json")
    requested_task_id = str(task_id or "").strip()
    active_task_id = str(ledger.get("active_task_id") or "").strip()
    # There can be only one ACTIVE task. Treat its persisted identity as the
    # canonical default when a provider drops a required tool argument; never
    # infer across pending tasks or override a conflicting explicit ID.
    task_id = requested_task_id or active_task_id
    task_id_inferred = bool(not requested_task_id and active_task_id)
    requested_outcome = str(outcome or "").upper().strip()
    outcome = requested_outcome
    outcome_inferred = False
    if not outcome:
        resolution = str((finding or {}).get("resolution") or "").upper().strip()
        if resolution == "PUBLIC_INFO_UNAVAILABLE":
            outcome = "PUBLIC_INFO_UNAVAILABLE"
        elif resolution in {"SUPPORTED", "CONTRADICTED", "MIXED"}:
            outcome = "EVIDENCE_FOUND"
        elif resolution == "UNRESOLVED":
            outcome = "NO_DECISION_CHANGE"
        outcome_inferred = bool(outcome)
    if active_task_id != task_id or not task_id:
        return {
            "completed": False, "error": "task_not_active",
            "requested_task_id": requested_task_id or None,
            "active_task_id": active_task_id or None,
        }
    if outcome not in OUTCOMES:
        return {
            "completed": False, "error": "outcome_invalid",
            "requested_outcome": requested_outcome or None,
            "finding_resolution": (finding or {}).get("resolution"),
        }
    task = _plan_task(plan, task_id) or {}
    entry = ledger["tasks"][task_id]
    calls = entry.get("tool_calls") or []
    successful = {item.get("tool") for item in calls if item.get("ok")}
    attempted = {item.get("tool") for item in calls if item.get("executed", True)}
    required_tools = set(task.get("required_tools") or [])
    missing_tools = sorted(
        required_tools - (attempted if outcome == "PUBLIC_INFO_UNAVAILABLE" else successful)
    )
    violations: list[str] = []
    if missing_tools:
        label = "required_tools_not_attempted" if outcome == "PUBLIC_INFO_UNAVAILABLE" else "required_tools_not_successful"
        violations.append(label + ":" + ",".join(missing_tools))
    if outcome == "EVIDENCE_FOUND" and not any(str(item).strip() for item in source_ids or []):
        violations.append("evidence_found_without_source_ids")
    known_source_ids = {
        str(item.get("source_id")) for item in calls
        if item.get("source_id") and (item.get("ok") or outcome == "PUBLIC_INFO_UNAVAILABLE")
    }
    unknown_declared_sources = sorted(
        {str(item) for item in source_ids or [] if str(item).strip()} - known_source_ids
    )
    if unknown_declared_sources:
        violations.append("unknown_or_unusable_source_ids:" + ",".join(unknown_declared_sources))
    try:
        from scripts.judgment_research_synthesis import normalize_judgment_research_finding, validate_judgment_research_finding
    except ModuleNotFoundError:
        from judgment_research_synthesis import normalize_judgment_research_finding, validate_judgment_research_finding
    finding_payload = normalize_judgment_research_finding(dict(finding or {}))
    finding_validation = validate_judgment_research_finding(
        finding_payload, task=task, outcome=outcome,
        source_ids=[str(item) for item in source_ids or []],
    )
    if finding_validation.get("state") != "VALID":
        violations.extend(
            "finding:" + str(item)
            for item in (
                list(finding_validation.get("invalid_findings") or [])
                + list(finding_validation.get("incomplete_findings") or [])
            )
        )
    minimum = task.get("minimum_evidence") or {}
    if outcome != "PUBLIC_INFO_UNAVAILABLE":
        primary_calls = sum(item.get("ok") and item.get("tool") in PRIMARY_SOURCE_TOOLS for item in calls)
        independent_calls = sum(item.get("ok") and item.get("tool") in INDEPENDENT_SOURCE_TOOLS for item in calls)
        if primary_calls < int(minimum.get("primary_sources") or 0):
            violations.append(f"primary_source_minimum_not_met:{primary_calls}/{int(minimum.get('primary_sources') or 0)}")
        if independent_calls < int(minimum.get("independent_sources") or 0):
            violations.append(f"independent_source_minimum_not_met:{independent_calls}/{int(minimum.get('independent_sources') or 0)}")
    before = entry.get("before_snapshot") or {}
    after = _mutation_snapshot(output)
    actual_changes = sorted(key for key, value in after.items() if before.get(key) != value)
    scope = task.get("mutation_scope") or {}
    allowed = {f"chapter:{idx}" for idx in scope.get("chapters") or []}
    allowed |= {f"ledger:{name}" for name in scope.get("ledgers") or []}
    outside = sorted(set(actual_changes) - allowed)
    if outside:
        violations.append("mutation_outside_scope:" + ",".join(outside))
    if outcome == "DECISION_CHANGED":
        if "ledger:decision" not in actual_changes:
            violations.append("decision_changed_without_decision_ledger_change")
        diff = _load(output / "decision_diff.json")
        if not diff or not diff.get("change_reason"):
            violations.append("decision_changed_without_explicit_decision_diff")
    changed_dimensions = set(finding_validation.get("changed_dimensions") or [])
    if "valuation_impact" in changed_dimensions and not (
        {"ledger:valuation_model", "ledger:decision"} & set(actual_changes)
    ):
        violations.append("valuation_changed_without_valuation_or_decision_ledger_change")
    if "action_impact" in changed_dimensions and "ledger:decision" not in actual_changes:
        violations.append("action_changed_without_decision_ledger_change")
    declared_chapter_changes = {
        f"chapter:{idx}" for idx in ((finding_payload.get("chapter_update") or {}).get("chapters") or [])
    }
    actual_chapter_changes = {item for item in actual_changes if item.startswith("chapter:")}
    if declared_chapter_changes != actual_chapter_changes:
        violations.append(
            "structured_chapter_update_mismatch:declared="
            + ",".join(sorted(declared_chapter_changes))
            + ";actual=" + ",".join(sorted(actual_chapter_changes))
        )
    for changed in sorted(actual_chapter_changes):
        try:
            chapter_index = int(changed.split(":", 1)[1])
            from scripts.decision_compiler import validate_chapter_decision_bindings
        except (ValueError, ModuleNotFoundError):
            try:
                from decision_compiler import validate_chapter_decision_bindings
                chapter_index = int(changed.split(":", 1)[1])
            except (ValueError, ModuleNotFoundError):
                continue
        binding = validate_chapter_decision_bindings(output, chapter_index)
        violations.extend(
            "chapter_decision_binding:" + str(item)
            for item in binding.get("invalid_findings") or []
        )
    entry["source_ids"] = list(dict.fromkeys(str(item) for item in source_ids or [] if str(item).strip()))
    entry["new_evidence_summary"] = str(new_evidence_summary or "").strip()
    entry["finding"] = finding_payload
    entry["finding_validation"] = finding_validation
    entry["outcome"] = outcome
    entry["actual_changes"] = actual_changes
    hard_violations = [
        item for item in violations
        if item.startswith("mutation_outside_scope:")
    ]
    if violations and not hard_violations:
        # A rejected completion submission is a repair prompt, not a terminal
        # execution violation. Keep the task ACTIVE so the same or a fresh
        # context can correct source IDs, structured fields, or scoped writes.
        entry["last_submission_errors"] = violations
        entry["submission_attempts"] = int(entry.get("submission_attempts") or 0) + 1
        entry["violations"] = []
        entry["completed_at"] = None
        entry["status"] = "ACTIVE"
        ledger["state"] = "ACTIVE"
        ledger["blocking"] = False
        _persist(output, ledger)
        return {
            "completed": False, "task_id": task_id, "state": "ACTIVE",
            "violations": violations, "actual_changes": actual_changes,
            "repairable_submission": True, "task_id_inferred": task_id_inferred,
            "outcome_inferred": outcome_inferred,
        }
    entry["last_submission_errors"] = []
    entry["violations"] = hard_violations
    entry["completed_at"] = _now()
    entry["status"] = "VIOLATION" if hard_violations else "COMPLETE"
    ledger["active_task_id"] = None
    pending = [item for item in ledger.get("execution_queue") or [] if ledger["tasks"][item]["status"] == "PENDING"]
    violated = [item for item in ledger.get("execution_queue") or [] if ledger["tasks"][item]["status"] == "VIOLATION"]
    ledger["state"] = "VIOLATION" if violated else "PENDING" if pending else "COMPLETE"
    ledger["blocking"] = bool(violated)
    _persist(output, ledger)
    try:
        from scripts.judgment_research_synthesis import build_judgment_research_synthesis
    except ModuleNotFoundError:
        from judgment_research_synthesis import build_judgment_research_synthesis
    synthesis = build_judgment_research_synthesis(output, persist=True)
    return {
        "completed": not hard_violations, "task_id": task_id, "state": entry["status"],
        "violations": hard_violations, "actual_changes": actual_changes,
        "task_id_inferred": task_id_inferred,
        "outcome_inferred": outcome_inferred,
        "next_task_id": pending[0] if pending else None,
        "synthesis_state": synthesis.get("state"),
    }


def evaluate_judgment_research_execution(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    ledger = _load(output / "judgment_research_execution.json")
    if not ledger:
        return {"state": "NOT_STARTED", "status": "SKIP", "blocking": False, "violations": []}
    violations = [
        violation
        for entry in (ledger.get("tasks") or {}).values() if isinstance(entry, dict)
        for violation in entry.get("violations") or []
    ]
    state = str(ledger.get("state") or "INVALID")
    return {
        "schema_version": "judgment-research-execution-validation.v1",
        "state": state,
        "status": "FAIL" if state == "VIOLATION" else "PASS" if state in {"COMPLETE", "NO_ACTION"} else "PENDING",
        "blocking": state == "VIOLATION",
        "active_task_id": ledger.get("active_task_id"),
        "completed_tasks": sum(entry.get("status") == "COMPLETE" for entry in (ledger.get("tasks") or {}).values() if isinstance(entry, dict)),
        "task_count": len(ledger.get("tasks") or {}),
        "violations": violations,
    }
