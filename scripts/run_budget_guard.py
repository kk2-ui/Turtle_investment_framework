#!/usr/bin/env python3
"""Preflight and progress circuit breakers for expensive real-report runs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


def _blocking_signature(findings: Iterable[Any]) -> tuple[str, ...]:
    normalized = []
    for item in findings or []:
        if isinstance(item, dict):
            value = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        else:
            value = " ".join(str(item).split())
        if value:
            normalized.append(value)
    return tuple(sorted(set(normalized)))


@dataclass
class NoProgressCircuitBreaker:
    """Trips when consecutive repair passes leave exactly the same blockers."""

    max_no_progress_passes: int = 2
    previous: tuple[str, ...] = ()
    streak: int = 0

    def observe(self, findings: Iterable[Any]) -> dict[str, Any]:
        current = _blocking_signature(findings)
        before = set(self.previous)
        after = set(current)
        if current and current == self.previous:
            self.streak += 1
        else:
            self.streak = 0
        result = {
            "blocker_count": len(current),
            "resolved_count": len(before - after),
            "introduced_count": len(after - before),
            "no_progress_streak": self.streak,
            "tripped": bool(current) and self.streak >= max(1, int(self.max_no_progress_passes)),
        }
        self.previous = current
        return result


def build_run_preflight(
    *, output_dir: str | Path, max_iterations: int, repair_passes: int,
    repair_max_iterations: int, repair_only: bool, dry_run: bool,
    approved: bool, policy: dict[str, Any],
) -> dict[str, Any]:
    """Estimate an upper bound before the first paid model call."""
    build_calls = 0 if repair_only else max(0, int(max_iterations))
    repair_calls = max(0, int(repair_passes)) * max(0, int(repair_max_iterations))
    estimated_calls = 0 if dry_run else build_calls + repair_calls
    seconds_per_call = float(policy.get("estimated_seconds_per_llm_call", 12.0))
    estimated_wall_minutes = round(estimated_calls * seconds_per_call / 60.0, 1)

    prior_real_runs = 0
    for path in Path(output_dir).glob("run_manifests/*.json"):
        try:
            manifest = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if int((manifest.get("usage") or {}).get("calls", 0) or 0) > 0:
            prior_real_runs += 1

    reasons: list[str] = []
    if estimated_calls > int(policy.get("preflight_approval_call_threshold", 120)):
        reasons.append("estimated_llm_calls_exceed_approval_threshold")
    if estimated_wall_minutes > float(policy.get("preflight_approval_wall_minutes", 20)):
        reasons.append("estimated_wall_time_exceeds_approval_threshold")
    # A zero-call validation-only closeout has no paid-model exposure.  Prior
    # paid runs remain relevant for any new model call, but must not turn an
    # idempotent machine revalidation into a fake human-approval checkpoint.
    if (
        estimated_calls > 0
        and prior_real_runs >= int(policy.get("max_unapproved_real_runs_per_output", 1))
    ):
        reasons.append("real_run_already_attempted_for_output")
    status = "DRY_RUN" if dry_run else "APPROVED" if approved else "APPROVAL_REQUIRED" if reasons else "SAFE"
    payload = {
        "schema_version": "run-budget-preflight.v1",
        "status": status,
        "approved": bool(approved),
        "estimate": {
            "max_llm_calls": estimated_calls,
            "estimated_wall_minutes": estimated_wall_minutes,
            "prior_real_runs_for_output": prior_real_runs,
        },
        "limits": policy,
        "reasons": reasons,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["preflight_fingerprint"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload
