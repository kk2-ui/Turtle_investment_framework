#!/usr/bin/env python3
"""Build tamper-evident identities for allow-listed deterministic calculations."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


SCHEMA_VERSION = "calculation-observations.v1"
_INPUT_FILES = ("compute_bundle.json", "financial_trends.json")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tools() -> dict[str, Callable[[str], dict[str, Any]]]:
    scripts = str(Path(__file__).resolve().parent)
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from turtle_agent.tools.calc_tools import compute_aa, compute_gg
    return {"compute_aa": compute_aa, "compute_gg": compute_gg}


def _numeric_leaves(value: Any, prefix: str = "") -> list[tuple[str, int | float]]:
    rows: list[tuple[str, int | float]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_numeric_leaves(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_numeric_leaves(item, f"{prefix}[{index}]"))
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        rows.append((prefix, value))
    return rows


def _scalar_leaves(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key in sorted(value):
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.extend(_scalar_leaves(value[key], path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_scalar_leaves(item, f"{prefix}[{index}]"))
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        if not isinstance(value, float) or math.isfinite(value):
            rows.append((prefix, value))
    return rows


def _unit_for(path: str, result: dict[str, Any]) -> str:
    if path.endswith(".value"):
        parent = result
        for part in path.rsplit(".", 1)[0].split("."):
            parent = parent.get(part, {}) if isinstance(parent, dict) else {}
        if isinstance(parent, dict) and parent.get("unit"):
            return str(parent["unit"])
    lowered = path.lower()
    leaf = lowered.rsplit(".", 1)[-1]
    percentage_paths = {
        "gg_base", "gg_fcfe", "ii", "rf", "hh",
        "gg_normalized.base", "gg_discounted.base",
        "gg_discounted.pessimistic", "gg_discounted.optimistic",
    }
    if (
        lowered in percentage_paths
        or "pct" in leaf
        or leaf.endswith("_pct")
        or leaf.endswith("_pct_point")
    ):
        return "pct_or_pct_point"
    if "ratio" in leaf or leaf in {"g_coef", "m", "q"}:
        return "ratio"
    return "source_native"


def _payload_core(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    value.pop("generated_at", None)
    value.pop("payload_hash", None)
    value.pop("validation", None)
    return value


def build_calculation_observations(
    output_dir: str | Path, *, persist: bool = True
) -> dict[str, Any]:
    output = Path(output_dir)
    inputs = {
        name: _file_hash(output / name)
        for name in _INPUT_FILES if (output / name).is_file()
    }
    input_fingerprint = _hash(inputs)
    calculations: list[dict[str, Any]] = []
    for tool_name, function in _tools().items():
        result = function(str(output))
        output_fingerprint = _hash(result)
        for metric_path, value in _numeric_leaves(result):
            identity = {
                "tool": tool_name, "metric_path": metric_path,
                "value": value, "input_fingerprint": input_fingerprint,
                "output_fingerprint": output_fingerprint,
            }
            calculations.append({
                "calculation_id": "CALC:" + _hash(identity)[:24],
                "tool": tool_name,
                "metric_path": metric_path,
                "value": value,
                "unit": _unit_for(metric_path, result),
                "input_fingerprint": input_fingerprint,
                "output_fingerprint": output_fingerprint,
                "status": "VERIFIED",
            })
    plan_path = output / "decisive_question_plan.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        plan = {}
    plan_fingerprint = str(plan.get("input_fingerprint") or "")
    for question in plan.get("selected_questions") or []:
        if not isinstance(question, dict):
            continue
        question_id = str(question.get("question_id") or "")
        sensitivity = (
            (question.get("decision_link") or {}).get("sensitivity_basis")
            if isinstance(question.get("decision_link"), dict) else {}
        ) or {}
        premise_fingerprint = _hash({
            "plan_input_fingerprint": plan_fingerprint,
            "question_id": question_id,
            "sensitivity_basis": sensitivity,
        })
        for premise_path, value in _scalar_leaves(sensitivity):
            metric_path = f"{question_id}.sensitivity_basis.{premise_path}"
            identity = {
                "tool": "decisive_plan", "metric_path": metric_path,
                "value": value, "plan_input_fingerprint": plan_fingerprint,
                "output_fingerprint": premise_fingerprint,
            }
            calculations.append({
                "calculation_id": "CALC:" + _hash(identity)[:24],
                "tool": "decisive_plan", "metric_path": metric_path,
                "value": value,
                "unit": _unit_for(premise_path, sensitivity) if isinstance(value, (int, float)) else "categorical",
                "input_fingerprint": plan_fingerprint,
                "output_fingerprint": premise_fingerprint,
                "status": "VERIFIED",
            })
    calculations.sort(key=lambda item: (item["tool"], item["metric_path"], item["calculation_id"]))
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "input_files": inputs,
        "input_fingerprint": input_fingerprint,
        "allowed_tools": sorted([*_tools(), "decisive_plan"]),
        "calculations": calculations,
    }
    payload["payload_hash"] = _hash(_payload_core(payload))
    payload["validation"] = validate_calculation_observations(payload, output, rebuild=False)
    if persist:
        (output / "calculation_observations.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        payload["claim_rebinding"] = rebind_reviewable_claim_calculations(
            output, payload
        )
    return payload


def rebind_reviewable_claim_calculations(
    output_dir: str | Path, calculation_payload: dict[str, Any]
) -> dict[str, Any]:
    """Migrate stale CALC ids by tool, value and semantic metric identity.

    CALC ids intentionally include the input fingerprint.  Recomputing an
    otherwise unchanged bundle therefore changes the id.  Reviewable claim
    ledgers may be rebound deterministically; frozen ledgers remain immutable
    and must go through an explicit decision revision.
    """
    output = Path(output_dir)
    path = output / "claim_evidence.json"
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"updated": False, "reason": "claim_evidence_missing"}
    if bool((ledger.get("freeze") or {}).get("frozen")):
        return {"updated": False, "reason": "claim_evidence_frozen"}
    calculations = [
        row for row in calculation_payload.get("calculations") or []
        if isinstance(row, dict) and row.get("calculation_id")
        and str(row.get("status") or "").upper() == "VERIFIED"
    ]
    current_ids = {str(row["calculation_id"]) for row in calculations}

    def fact_numbers(text: str) -> list[float]:
        return [
            float(value.replace(",", ""))
            for value in re.findall(
                r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])",
                str(text or ""),
            )
        ]

    def score(metric_path: str, fact: str) -> int:
        metric = str(metric_path or "").lower()
        text = str(fact or "").lower().replace(" ", "")
        value = sum(2 for token in re.split(r"[._]", metric) if len(token) > 1 and token in text)
        rules = (
            ("aa_avg", "ingredients.aa_avg", 20),
            ("gg(fcfe)", "gg_fcfe.base", 20),
            ("gg(aa)", "gg_base", 20),
            ("净现金(broad)", "cash_structure.net_cash_broad", 20),
            ("净现金/市值", "net_cash_pct_mc", 20),
            ("现金(narrow)", "cash_structure.bb_narrow", 20),
            ("g_adj", "ingredients.g_adj.value", 20),
            ("mc=", "ingredients.mc.value", 20),
            ("m=", "ingredients.m.value", 20),
            ("ii=", "ii", 20),
        )
        for marker, expected, bonus in rules:
            if marker in text and metric == expected:
                value += bonus
        if any(bad in metric for bad in ("high_count", "low_count", ".samples")):
            value -= 10
        return value

    changed: list[dict[str, str]] = []
    unresolved: list[str] = []
    for claim in ledger.get("claims") or []:
        if not isinstance(claim, dict):
            continue
        for evidence in claim.get("raw_facts") or []:
            if not isinstance(evidence, dict):
                continue
            old_id = str(evidence.get("calculation_id") or "")
            if not old_id or old_id in current_ids:
                continue
            numbers = fact_numbers(str(evidence.get("fact") or ""))
            source = str(evidence.get("source_id") or "")
            candidates = []
            for row in calculations:
                try:
                    numeric = float(row.get("value"))
                except (TypeError, ValueError):
                    continue
                if row.get("tool") == source and any(
                    math.isclose(numeric, number, rel_tol=1e-9, abs_tol=1e-9)
                    for number in numbers
                ):
                    candidates.append(row)
            ranked = sorted(
                candidates,
                key=lambda row: score(str(row.get("metric_path") or ""), str(evidence.get("fact") or "")),
                reverse=True,
            )
            if not ranked:
                unresolved.append(str(evidence.get("evidence_id") or old_id))
                continue
            top_score = score(str(ranked[0].get("metric_path") or ""), str(evidence.get("fact") or ""))
            second_score = score(str(ranked[1].get("metric_path") or ""), str(evidence.get("fact") or "")) if len(ranked) > 1 else -10**6
            if len(ranked) > 1 and top_score <= second_score:
                unresolved.append(str(evidence.get("evidence_id") or old_id))
                continue
            new_id = str(ranked[0]["calculation_id"])
            evidence["calculation_id"] = new_id
            evidence["calculation_metric_path"] = str(ranked[0].get("metric_path") or "")
            changed.append({"old": old_id, "new": new_id})
    if changed:
        path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"updated": bool(changed), "changes": changed, "unresolved": unresolved}


def validate_calculation_observations(
    payload: dict[str, Any], output_dir: str | Path, *, rebuild: bool = True
) -> dict[str, Any]:
    invalid: list[str] = []
    output = Path(output_dir)
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if payload.get("allowed_tools") != sorted([*_tools(), "decisive_plan"]):
        invalid.append("allowed_tools_mismatch")
    if payload.get("payload_hash") != _hash(_payload_core(payload)):
        invalid.append("payload_hash_mismatch")
    for name, digest in (payload.get("input_files") or {}).items():
        path = output / str(name)
        if not path.is_file() or _file_hash(path) != digest:
            invalid.append(f"input_hash_mismatch:{name}")
    calculations = payload.get("calculations")
    if not isinstance(calculations, list) or not calculations:
        invalid.append("calculations_missing")
        calculations = []
    ids = [str(item.get("calculation_id") or "") for item in calculations if isinstance(item, dict)]
    if any(not value.startswith("CALC:") for value in ids) or len(ids) != len(set(ids)):
        invalid.append("calculation_ids_invalid_or_duplicate")
    if rebuild and not invalid:
        expected = build_calculation_observations(output, persist=False)
        if _payload_core(payload) != _payload_core(expected):
            invalid.append("calculation_rebuild_mismatch")
    return {
        "schema_version": "calculation-observations-validation.v1",
        "state": "INVALID" if invalid else "VERIFIED",
        "status": "FAIL" if invalid else "PASS",
        "invalid_findings": invalid,
        "calculation_count": len(calculations),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    payload = build_calculation_observations(args.output_dir, persist=True)
    print(json.dumps(payload["validation"], ensure_ascii=False, indent=2))
    return 0 if payload["validation"]["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
