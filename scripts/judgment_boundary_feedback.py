#!/usr/bin/env python3
"""Build feedback for a frozen NO_PRIMARY boundary replay.

Boundary feedback answers a different question from selection feedback: did
the frozen evidence contract remain insufficient to identify a primary path,
and did the case expose a reusable measurement or abstention rule?  It never
produces a path-choice score, return, probability, or selection verdict.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "judgment-boundary-feedback-card.v1"


class BoundaryFeedbackError(ValueError):
    pass


def _read(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BoundaryFeedbackError(f"cannot read boundary outcome: {path}") from exc
    if not isinstance(value, dict):
        raise BoundaryFeedbackError("boundary outcome must be an object")
    return value


def validate_boundary_outcome(outcome: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(outcome, dict):
        return {"state": "INVALID", "findings": ["outcome_not_object"]}
    if outcome.get("schema_version") != "judgment-boundary-outcome.v1":
        findings.append("schema_version_invalid")
    for field in ("case_id", "freeze_id", "settlement_id", "settlement_as_of"):
        if not str(outcome.get(field) or "").strip():
            findings.append(field + "_missing")
    if outcome.get("selection_status") != "NO_PRIMARY":
        findings.append("selection_status_must_be_no_primary")
    clocks = outcome.get("clocks")
    if not isinstance(clocks, list) or len(clocks) != 5:
        findings.append("clocks_must_contain_d1_to_d5")
        clocks = []
    seen: set[str] = set()
    for index, clock in enumerate(clocks):
        prefix = f"clocks[{index}]"
        if not isinstance(clock, dict):
            findings.append(prefix + ":not_object")
            continue
        clock_id = str(clock.get("clock") or "")
        if clock_id not in {"D1", "D2", "D3", "D4", "D5"}:
            findings.append(prefix + ":clock_invalid")
        if clock_id in seen:
            findings.append(prefix + ":clock_duplicate")
        seen.add(clock_id)
        if clock.get("status") not in {"OBSERVED", "NOT_DIAGNOSTIC", "UNKNOWN", "MEASUREMENT_MISMATCH"}:
            findings.append(prefix + ":status_invalid")
        for field in ("measurement_scope", "missing_facts", "prohibited_substitutes", "source_ids"):
            value = clock.get(field)
            if field == "source_ids":
                if not isinstance(value, list) or not value:
                    findings.append(prefix + ":source_ids_missing")
            elif not str(value or "").strip():
                findings.append(prefix + ":" + field + "_missing")
    if seen != {"D1", "D2", "D3", "D4", "D5"}:
        findings.append("clocks_incomplete")
    sources = outcome.get("sources")
    if not isinstance(sources, list) or not sources:
        findings.append("sources_missing")
    else:
        source_ids = {str(item.get("source_id") or "") for item in sources if isinstance(item, dict)}
        referenced = {str(source_id) for clock in clocks if isinstance(clock, dict) for source_id in clock.get("source_ids") or []}
        if referenced - source_ids:
            findings.append("clock_source_not_in_inventory")
    return {"schema_version": "judgment-boundary-outcome-validation.v1", "state": "INVALID" if findings else "REVIEWABLE", "findings": findings}


def build_boundary_feedback(outcome: dict[str, Any]) -> dict[str, Any]:
    validation = validate_boundary_outcome(outcome)
    if validation["state"] != "REVIEWABLE":
        raise BoundaryFeedbackError("invalid boundary outcome: " + "; ".join(validation["findings"]))
    clocks = sorted(outcome["clocks"], key=lambda item: item["clock"])
    claims = []
    for clock in clocks:
        claim_id = str(clock.get("claim_id") or f"{outcome['case_id']}:{clock['clock']}")
        claims.append({
            "claim_id": claim_id,
            "forward_judgment_id": f"FJ:{outcome['case_id']}:{clock['clock']}",
            "statement": "NO_PRIMARY remains the correct state until the required responsibility-unit evidence is observable.",
            "settlement_status": "CALCULATED",
            "actual_observation": {"status": clock["status"], "measurement_scope": clock["measurement_scope"], "source_ids": deepcopy(clock["source_ids"])},
            "judgment_outcome": {"status": "BOUNDARY_PRESERVED", "clock": clock["clock"]},
            "baseline": {"status": "NOT_APPLICABLE_TO_SELECTION"},
            "increment_vs_baseline": "BOUNDARY_RULE_ONLY",
            "rival_hypothesis_feedback": {"state": "BOUNDARY_NOT_SELECTION", "signal_verdict": "NOT_DIAGNOSTIC"},
            "boundary_diagnostic": {
                "missing_facts": clock["missing_facts"],
                "prohibited_substitutes": clock["prohibited_substitutes"],
            },
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": outcome["case_id"],
        "freeze_id": outcome["freeze_id"],
        "settlement_id": outcome["settlement_id"],
        "settlement_as_of": outcome["settlement_as_of"],
        "selection_status": "NO_PRIMARY",
        "settlement_status": "CALCULATED",
        "cards": claims,
        "learning_scope": "BOUNDARY_OR_ABSTENTION",
        "prohibited_outputs": ["selection_accuracy", "probability", "win_rate", "investment_return", "portfolio_conclusion"],
    }


def build_boundary_feedback_from_path(outcome_ref: str | Path, output_ref: str | Path) -> dict[str, Any]:
    feedback = build_boundary_feedback(_read(outcome_ref))
    path = Path(output_ref)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(feedback, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return feedback
