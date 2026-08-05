#!/usr/bin/env python3
"""V3 canonical decision ledger and cross-chapter consistency gate.

The ledger is the structured source of truth for decision-changing metrics.  It
does not try to judge whether an investment thesis is good; it prevents one
report from silently using incompatible prices, valuation inputs, margins or
actions.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SCHEMA_VERSION = "decision-ledger.v1"
POLICY_VERSION = "decision-ledger-policy.v1"

CANONICAL_METRIC_IDS = {
    "market.price.current",
    "return.gg.base",
    "return.gg.fcfe",
    "return.gg.normalized",
    "hurdle.ii",
    "valuation.v_final",
    "moat.lambda",
    "return.required",
    "moat.decay",
    "margin.price",
    "margin.return",
    "decision.position.recommended",
    "trigger.buy",
    "trigger.reduce",
    "trigger.exit",
}

REQUIRED_METRIC_IDS = frozenset(CANONICAL_METRIC_IDS)
ACTION_METRIC_IDS = {
    "valuation.v_final",
    "return.required",
    "moat.decay",
    "margin.price",
    "margin.return",
    "decision.position.recommended",
    "trigger.buy",
    "trigger.reduce",
    "trigger.exit",
}

_DECISION_REF_RE = re.compile(r"\[decision:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])([+\-−]?\d+(?:\.\d+)?)")
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.MULTILINE)

# These patterns deliberately cover only decision-changing identities.  Broad
# financial-number extraction belongs to the evidence layer, not this gate.
_METRIC_PATTERNS: dict[str, re.Pattern[str]] = {
    "market.price.current": re.compile(r"当前价|现价|当前股价|市场价格"),
    "return.gg.base": re.compile(r"GG\s*(?:\(\s*AA口径\s*\)|\(\s*base口径\s*\)|_base)", re.IGNORECASE),
    "return.gg.fcfe": re.compile(r"GG\s*(?:\(\s*FCFE口径\s*\)|_FCFE)", re.IGNORECASE),
    "return.gg.normalized": re.compile(r"GG\s*(?:\(\s*Normalized口径\s*\)|_NORMALIZED|_Normalized)", re.IGNORECASE),
    "hurdle.ii": re.compile(r"(?<![A-Za-z])II\s*(?:[=＝:：]|为)", re.IGNORECASE),
    "valuation.v_final": re.compile(r"V[_\s]*final", re.IGNORECASE),
    # Generic λ in factor3 is an operating-sensitivity slope, not the moat
    # retention/decay multiplier used by V_final.  Require moat/V_final context
    # here so the two identities can never be silently collapsed again.
    "moat.lambda": re.compile(
        r"(?:护城河|经济特许权|V[_\s]*final|五档)[^\n]{0,28}(?:λ|lambda)"
        r"|(?:λ|lambda)[^\n]{0,18}(?:护城河|特许权|折价乘数|五档)",
        re.IGNORECASE,
    ),
    "return.required": re.compile(r"(?<![A-Za-z])r\s*\*|要求回报率|目标回报率", re.IGNORECASE),
    "moat.decay": re.compile(r"护城河衰减|经济特许权衰减|\bdecay\b", re.IGNORECASE),
    "margin.price": re.compile(r"价格安全边际"),
    "margin.return": re.compile(r"回报安全边际"),
    "decision.position.recommended": re.compile(r"建议仓位|标准仓位|仓位建议"),
    "trigger.buy": re.compile(r"首次买入条件|首次买入价|买入触发价"),
    "trigger.reduce": re.compile(r"减仓触发|减仓条件"),
    "trigger.exit": re.compile(r"退出触发|清仓条件|退出条件"),
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    value.pop("freeze", None)
    value.pop("generated_at", None)
    value.pop("updated_at", None)
    return value


def ledger_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(
        _canonical_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _values_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    try:
        lval = float(left)
        rval = float(right)
    except (TypeError, ValueError):
        return str(left).strip() == str(right).strip()
    if not math.isfinite(lval) or not math.isfinite(rval):
        return False
    return math.isclose(lval, rval, rel_tol=1e-6, abs_tol=1e-6)


def _number_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _manifest_decision(manifest: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "qualitative_decision",
        "quantitative_decision",
        "unified_decision",
        "display_label",
        "decision_family",
        "position_pct",
    )
    return {key: manifest.get(key) for key in keys}


def initialize_decision_ledger_policy(
    output_dir: str | Path,
    *,
    run_id: str,
    enforced: bool,
    required_metric_ids: set[str] | frozenset[str] = REQUIRED_METRIC_IDS,
) -> dict[str, Any]:
    """Bind V3 enforcement to a concrete unified run.

    Old output directories without this policy remain readable.  New unified
    runs write the policy before generation, so a missing ledger cannot be
    mistaken for a publishable report.
    """
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        "required_metric_ids": sorted(required_metric_ids),
        "created_at": _utc_now(),
    }
    path = Path(output_dir) / "decision_ledger_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_decision_ledger(
    output_dir: str | Path,
    entries: list[dict[str, Any]],
    *,
    change_reason: str,
    freeze: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    manifest = _read_json(output / "decision_manifest.json")
    contract = _read_json(output / "analysis_contract.json")
    report_id = str(contract.get("ts_code") or contract.get("code") or output.name)
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": report_id,
        "revision": 1,
        "lifecycle": "decision_ready" if freeze else "reviewable",
        "change_reason": str(change_reason or "").strip(),
        "decision": _manifest_decision(manifest),
        "entries": deepcopy(entries),
        "generated_at": _utc_now(),
    }
    fingerprint = ledger_fingerprint(payload)
    payload["freeze"] = {
        "frozen": bool(freeze),
        "fingerprint": fingerprint if freeze else "",
        "frozen_at": _utc_now() if freeze else None,
    }
    return payload


def _chapter_texts(report_text: str) -> dict[int, str]:
    matches = list(_CHAPTER_RE.finditer(report_text))
    result: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        result[int(match.group(1))] = report_text[match.start():end]
    return result


def _entry_map(entries: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(entry.get("entry_id")): entry
        for entry in entries
        if isinstance(entry, dict) and entry.get("entry_id")
    }


def _line_numbers(line: str) -> list[float]:
    values: list[float] = []
    for raw in _NUMBER_RE.findall(line):
        try:
            values.append(float(raw.replace("−", "-")))
        except ValueError:
            continue
    return values


def _line_supports_value(line: str, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return any(_values_equal(number, expected) for number in _line_numbers(line))
    expected_text = str(expected or "").strip()
    return bool(expected_text and expected_text in line)


def _line_supports_entry(line: str, entry: dict[str, Any]) -> bool:
    """Match one canonical entry across equivalent report representations."""
    expected = entry.get("value")
    if _line_supports_value(line, expected):
        return True
    if not isinstance(expected, (int, float)) or isinstance(expected, bool):
        return False
    numbers = _line_numbers(line)
    metric_id = str(entry.get("metric_id") or "")
    if metric_id == "moat.decay" and any(
        _values_equal(abs(number), abs(float(expected))) for number in numbers
    ):
        return True
    unit = str(entry.get("unit") or "").strip().lower()
    if unit in {"percent", "percentage", "pct", "%"}:
        fraction = float(expected) / 100.0
        return any(_values_equal(number, fraction) for number in numbers)
    return False


def validate_decision_ledger(
    payload: dict[str, Any],
    *,
    report_text: str = "",
    manifest: dict[str, Any] | None = None,
    enforced: bool = False,
    required_metric_ids: set[str] | frozenset[str] = REQUIRED_METRIC_IDS,
) -> dict[str, Any]:
    """Validate schema, active identities, report references and manifest alignment."""
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []

    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list):
        invalid.append("entries_not_array")
        entries = []
    decision = payload.get("decision") if isinstance(payload, dict) else None
    if not isinstance(decision, dict):
        invalid.append("decision_not_object")
        decision = {}
    if not str(payload.get("report_id") or "").strip():
        invalid.append("report_id_missing")
    if not str(payload.get("change_reason") or "").strip():
        incomplete.append("change_reason_missing")

    seen_ids: set[str] = set()
    active_by_identity: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    active_by_metric_id: dict[str, dict[str, Any]] = {}
    active_metrics: set[str] = set()
    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            invalid.append(prefix + ":not_object")
            continue
        entry_id = str(entry.get("entry_id") or "").strip()
        metric_id = str(entry.get("metric_id") or "").strip()
        status = str(entry.get("status") or "").strip().lower()
        if not entry_id:
            invalid.append(prefix + ":entry_id_missing")
        elif entry_id in seen_ids:
            invalid.append(f"duplicate_entry_id:{entry_id}")
        seen_ids.add(entry_id)
        if metric_id not in CANONICAL_METRIC_IDS:
            invalid.append(f"unknown_metric_id:{metric_id or '<empty>'}")
        for field in ("scenario", "basis", "as_of", "unit"):
            if not str(entry.get(field) or "").strip():
                invalid.append(f"{entry_id or prefix}:{field}_missing")
        try:
            version = int(entry.get("version"))
            if version < 1:
                raise ValueError
        except (TypeError, ValueError):
            invalid.append(f"{entry_id or prefix}:version_invalid")
        chapters = entry.get("chapters")
        if not isinstance(chapters, list) or any(
            not isinstance(chapter, int) or chapter < 0 or chapter > 14 for chapter in chapters
        ):
            invalid.append(f"{entry_id or prefix}:chapters_invalid")
        if not isinstance(entry.get("source_ids"), list) or not entry.get("source_ids"):
            incomplete.append(f"{entry_id or prefix}:source_ids_missing")
        if status not in {"active", "deprecated"}:
            invalid.append(f"{entry_id or prefix}:status_invalid")
            continue
        if status == "deprecated":
            if not str(entry.get("deprecation_reason") or "").strip():
                invalid.append(f"{entry_id}:deprecation_reason_missing")
            if not str(entry.get("superseded_by") or "").strip():
                invalid.append(f"{entry_id}:superseded_by_missing")
            continue
        if "value" not in entry:
            invalid.append(f"{entry_id}:value_missing")
            continue
        trigger_text = " ".join(
            str(entry.get(field) or "") for field in ("scenario", "rationale", "display_label")
        ).lower()
        if metric_id == "trigger.reduce" and any(
            phrase in trigger_text for phrase in ("不是减仓", "not a reduce", "not reduce")
        ):
            invalid.append(f"{entry_id}:reduce_trigger_semantics_contradict_metric")
        if metric_id == "trigger.exit" and any(
            phrase in trigger_text for phrase in ("不是退出", "不是止损", "not an exit", "not exit", "not a stop")
        ):
            invalid.append(f"{entry_id}:exit_trigger_semantics_contradict_metric")
        active_metrics.add(metric_id)
        active_by_metric_id[metric_id] = entry
        identity = (
            metric_id,
            str(entry.get("scenario") or "").strip().lower(),
            str(entry.get("basis") or "").strip().lower(),
            str(entry.get("as_of") or "").strip(),
        )
        previous = active_by_identity.get(identity)
        if previous is not None:
            if _values_equal(previous.get("value"), entry.get("value")):
                invalid.append(
                    f"duplicate_active_identity:{metric_id}:{previous.get('entry_id')}:{entry_id}"
                )
            else:
                invalid.append(
                    f"unexplained_conflict:{metric_id}:{previous.get('entry_id')}={previous.get('value')}:"
                    f"{entry_id}={entry.get('value')}"
                )
        active_by_identity[identity] = entry

    # A downside stop/reduce price above the only permitted entry price makes
    # the policy impossible: every compliant purchase would already have
    # triggered the stop.  Do not reject valuation-driven profit taking above
    # the entry line; this check is limited to explicitly downside language.
    buy_entry = active_by_metric_id.get("trigger.buy") or {}
    reduce_entry = active_by_metric_id.get("trigger.reduce") or {}
    buy_value = _number_or_none(buy_entry.get("value"))
    reduce_value = _number_or_none(reduce_entry.get("value"))
    reduce_text = " ".join(
        str(reduce_entry.get(field) or "")
        for field in ("basis", "rationale", "scenario", "display_label")
    ).lower()
    downside_reduce = any(
        phrase in reduce_text
        for phrase in ("跌破", "低于", "向下", "止损", "stop", "below", "downside")
    )
    if (
        buy_value is not None
        and reduce_value is not None
        and downside_reduce
        and reduce_value > buy_value
    ):
        invalid.append(
            "downside_reduce_price_above_buy_price:"
            f"{reduce_entry.get('entry_id')}={reduce_value}>"
            f"{buy_entry.get('entry_id')}={buy_value}"
        )

    if enforced:
        missing_metrics = sorted(set(required_metric_ids) - active_metrics)
        incomplete.extend(f"required_metric_missing:{metric_id}" for metric_id in missing_metrics)

    if manifest:
        expected_decision = _manifest_decision(manifest)
        for field, expected in expected_decision.items():
            actual = decision.get(field)
            if field == "position_pct":
                same = _values_equal(actual, expected)
            else:
                same = str(actual or "").strip() == str(expected or "").strip()
            if not same:
                invalid.append(f"manifest_mismatch:{field}:{actual!r}!={expected!r}")
        position_entries = [
            entry for entry in entries
            if isinstance(entry, dict)
            and entry.get("metric_id") == "decision.position.recommended"
            and entry.get("status") == "active"
            and str(entry.get("scenario") or "").lower() == "base"
        ]
        if position_entries and not any(
            _values_equal(entry.get("value"), manifest.get("position_pct"))
            for entry in position_entries
        ):
            invalid.append("position_metric_manifest_mismatch")

    freeze = payload.get("freeze") if isinstance(payload, dict) else None
    if not isinstance(freeze, dict):
        incomplete.append("freeze_missing")
    elif freeze.get("frozen"):
        expected_fingerprint = ledger_fingerprint(payload)
        if freeze.get("fingerprint") != expected_fingerprint:
            invalid.append("frozen_fingerprint_mismatch")
    elif payload.get("lifecycle") == "decision_ready":
        incomplete.append("decision_ready_not_frozen")
    elif enforced:
        incomplete.append("enforced_ledger_not_frozen")

    if report_text:
        entries_by_id = _entry_map(entries)
        active_by_metric = {
            str(entry.get("metric_id")): entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("status") == "active"
        }
        chapters = _chapter_texts(report_text)
        lines = report_text.splitlines()
        for line_number, line in enumerate(lines, 1):
            references = _DECISION_REF_RE.findall(line)
            for entry_id in references:
                entry = entries_by_id.get(entry_id)
                if entry is None:
                    invalid.append(f"unknown_decision_reference:L{line_number}:{entry_id}")
                    continue
                if entry.get("status") != "active":
                    invalid.append(f"deprecated_decision_reference:L{line_number}:{entry_id}")
                    continue
                if not _line_supports_entry(line, entry):
                    invalid.append(
                        f"decision_value_mismatch:L{line_number}:{entry_id}:expected={entry.get('value')}"
                    )
            if enforced:
                for metric_id, pattern in _METRIC_PATTERNS.items():
                    if not pattern.search(line):
                        continue
                    # A metric name in a heading, mechanism discussion or
                    # sensitivity case is not itself a canonical claim. Only
                    # require a binding when the active canonical value is
                    # stated too. Declared chapter coverage is checked below.
                    canonical_entry = active_by_metric.get(metric_id)
                    if canonical_entry is None or not _line_supports_entry(
                        line, canonical_entry
                    ):
                        continue
                    bound_metrics = {
                        str(entries_by_id.get(ref, {}).get("metric_id") or "") for ref in references
                    }
                    if metric_id not in bound_metrics:
                        incomplete.append(f"unbound_critical_claim:L{line_number}:{metric_id}")

        for entry in entries:
            if not isinstance(entry, dict) or entry.get("status") != "active":
                continue
            entry_id = str(entry.get("entry_id") or "")
            for chapter in entry.get("chapters") or []:
                chapter_text = chapters.get(int(chapter), "")
                if f"[decision: {entry_id}]" not in chapter_text and f"[decision:{entry_id}]" not in chapter_text:
                    incomplete.append(f"decision_reference_missing:Ch{chapter}:{entry_id}")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    warnings = list(dict.fromkeys(warnings))
    if invalid:
        state = "INVALID"
    elif incomplete:
        state = "INCOMPLETE"
    elif payload.get("lifecycle") == "monitoring":
        state = "MONITORING"
    elif payload.get("freeze", {}).get("frozen"):
        state = "DECISION_READY"
    else:
        state = "REVIEWABLE"
    return {
        "schema_version": "decision-ledger-validation.v1",
        "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": warnings,
        "active_metric_ids": sorted(active_metrics),
        "required_metric_ids": sorted(required_metric_ids) if enforced else [],
        "enforced": bool(enforced),
    }


def validate_chapter_decision_references(
    payload: dict[str, Any], *, chapter_text: str, chapter: int, enforced: bool = True
) -> dict[str, Any]:
    """Validate decision references for one freshly written chapter only.

    This is the immediate-write counterpart of ``validate_decision_ledger``.
    It deliberately avoids whole-report coverage checks while still rejecting
    unknown IDs, IDs attached to the wrong value, and missing canonical anchors
    declared for the current chapter.
    """
    entries = [
        item for item in payload.get("entries") or [] if isinstance(item, dict)
    ]
    entries_by_id = _entry_map(entries)
    active_by_metric = {
        str(item.get("metric_id")): item
        for item in entries if item.get("status") == "active"
    }
    findings: list[str] = []
    for line_number, line in enumerate(str(chapter_text or "").splitlines(), 1):
        references = _DECISION_REF_RE.findall(line)
        for entry_id in references:
            entry = entries_by_id.get(entry_id)
            if entry is None:
                findings.append(
                    f"unknown_decision_reference:Ch{int(chapter)}:L{line_number}:{entry_id}"
                )
            elif entry.get("status") != "active":
                findings.append(
                    f"deprecated_decision_reference:Ch{int(chapter)}:L{line_number}:{entry_id}"
                )
            elif not _line_supports_entry(line, entry):
                findings.append(
                    f"decision_value_mismatch:Ch{int(chapter)}:L{line_number}:"
                    f"{entry_id}:expected={entry.get('value')}"
                )
        if enforced:
            for metric_id, pattern in _METRIC_PATTERNS.items():
                canonical_entry = active_by_metric.get(metric_id)
                if (
                    canonical_entry is None
                    or not pattern.search(line)
                    or not _line_supports_entry(line, canonical_entry)
                ):
                    continue
                bound_metrics = {
                    str(entries_by_id.get(ref, {}).get("metric_id") or "")
                    for ref in references
                }
                if metric_id not in bound_metrics:
                    findings.append(
                        f"unbound_critical_claim:Ch{int(chapter)}:L{line_number}:{metric_id}"
                    )
    for entry in entries:
        if entry.get("status") != "active" or int(chapter) not in (entry.get("chapters") or []):
            continue
        entry_id = str(entry.get("entry_id") or "")
        if (
            f"[decision: {entry_id}]" not in chapter_text
            and f"[decision:{entry_id}]" not in chapter_text
        ):
            findings.append(f"decision_reference_missing:Ch{int(chapter)}:{entry_id}")
    findings = list(dict.fromkeys(findings))
    return {
        "state": "INVALID" if findings else "DECISION_READY",
        "status": "FAIL" if findings else "PASS",
        "invalid_findings": findings,
        "chapter": int(chapter),
    }


def decision_diff(old: dict[str, Any], new: dict[str, Any], *, change_reason: str) -> dict[str, Any]:
    old_entries = _entry_map(old.get("entries") or [])
    new_entries = _entry_map(new.get("entries") or [])
    changes: list[dict[str, Any]] = []
    for entry_id in sorted(set(old_entries) | set(new_entries)):
        before = old_entries.get(entry_id)
        after = new_entries.get(entry_id)
        if before == after:
            continue
        metric_id = str((after or before or {}).get("metric_id") or "")
        changes.append({
            "entry_id": entry_id,
            "metric_id": metric_id,
            "before": before,
            "after": after,
            "affected_chapters": sorted(set((before or {}).get("chapters") or []) | set((after or {}).get("chapters") or [])),
            "changes_action": metric_id in ACTION_METRIC_IDS or bool((before or after or {}).get("affects_action")),
        })
    decision_changed = old.get("decision") != new.get("decision")
    metadata_changed = bool(old) and _canonical_payload(old) != _canonical_payload(new) and not (
        changes or decision_changed
    )
    return {
        "schema_version": "decision-diff.v1",
        "generated_at": _utc_now(),
        "change_reason": str(change_reason or "").strip(),
        "old_fingerprint": ledger_fingerprint(old) if old else None,
        "new_fingerprint": ledger_fingerprint(new) if new else None,
        "decision_changed": decision_changed,
        "metadata_changed": metadata_changed,
        "changes_action": decision_changed or any(item["changes_action"] for item in changes),
        "changes": changes,
    }


def preview_decision_revision(
    output_dir: str | Path,
    *,
    manifest: dict[str, Any],
    entries: list[dict[str, Any]],
    change_reason: str,
    report_text: str = "",
) -> dict[str, Any]:
    """Build a non-persistent decision-revision transaction preview.

    A changed manifest and its ledger cannot safely be written one at a time:
    a later chapter/identity failure would leave the output internally split.
    This helper exposes the exact proposed ledger, full decision diff, and
    current prose conflicts without changing either canonical file.
    """
    output = Path(output_dir)
    old = _read_json(output / "decision_ledger.json")
    policy = _read_json(output / "decision_ledger_policy.json")
    enforced = bool(policy.get("enforced"))
    required = set(policy.get("required_metric_ids") or REQUIRED_METRIC_IDS)
    candidate = deepcopy(old) if old else {
        "schema_version": SCHEMA_VERSION,
        "report_id": output.name,
        "revision": 1,
    }
    candidate.update({
        "lifecycle": "reviewable",
        "change_reason": str(change_reason or "").strip(),
        "decision": _manifest_decision(manifest),
        "entries": deepcopy(entries),
        "generated_at": _utc_now(),
        "freeze": {"frozen": False, "fingerprint": "", "frozen_at": None},
    })
    candidate["freeze"]["fingerprint"] = ledger_fingerprint(candidate)
    validation = validate_decision_ledger(
        candidate, report_text=report_text, manifest=manifest,
        enforced=enforced, required_metric_ids=required,
    )
    diff = decision_diff(old, candidate, change_reason=change_reason)
    return {
        "schema_version": "decision-revision-preview.v1",
        "state": "READY" if validation.get("state") == "DECISION_READY" else "CONTENT_PROPAGATION_REQUIRED",
        "canonical_files_written": False,
        "current_ledger_fingerprint": ledger_fingerprint(old) if old else None,
        "candidate_ledger_fingerprint": ledger_fingerprint(candidate),
        "candidate_manifest": deepcopy(manifest),
        "candidate_ledger": candidate,
        "diff": diff,
        "validation": validation,
    }


def bind_decision_references(
    output_dir: str | Path,
    payload: dict[str, Any],
    *,
    chapters: Iterable[int] | None = None,
) -> dict[str, Any]:
    """Mechanically bind canonical values in chapter files after a reviewable draft.

    The model owns metric identity, value, basis and scenario.  Repeating an ID
    beside every canonical occurrence is deterministic clerical work and should
    not consume reasoning context.  Missing declared chapter references receive
    a compact canonical-binding table; no prose conclusion is changed.
    """
    output = Path(output_dir)
    chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    active = [item for item in payload.get("entries") or [] if isinstance(item, dict) and item.get("status") == "active" and item.get("entry_id")]
    by_metric = {str(item.get("metric_id")): item for item in active}
    changed: list[int] = []; inserted = 0
    target_chapters = tuple(range(15)) if chapters is None else tuple(dict.fromkeys(
        int(item) for item in chapters if 0 <= int(item) <= 14
    ))
    for chapter in target_chapters:
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file(): continue
        lines = path.read_text(encoding="utf-8").splitlines()
        seen = set(_DECISION_REF_RE.findall("\n".join(lines)))
        rebound: list[str] = []
        for line in lines:
            additions: list[str] = []
            existing = set(_DECISION_REF_RE.findall(line))
            for metric_id, pattern in _METRIC_PATTERNS.items():
                entry = by_metric.get(metric_id)
                if entry is None or not pattern.search(line) or not _line_supports_entry(line, entry):
                    continue
                entry_id = str(entry["entry_id"])
                if entry_id not in existing:
                    additions.append(f"[decision: {entry_id}]"); existing.add(entry_id); seen.add(entry_id); inserted += 1
            rebound.append(line + ((" " + " ".join(additions)) if additions else ""))
        missing = [item for item in active if chapter in (item.get("chapters") or []) and str(item["entry_id"]) not in seen]
        if missing:
            rebound += ["", "### Canonical parameter bindings", "", "| 指标 | 本章采用值 | 绑定 |", "|---|---:|---|"]
            for item in missing:
                rebound.append(f"| {item.get('metric_id')} | {item.get('value')} {item.get('unit') or ''} | [decision: {item['entry_id']}] |")
                inserted += 1
        new_text = "\n".join(rebound).rstrip() + "\n"
        old_text = path.read_text(encoding="utf-8")
        if new_text != old_text:
            path.write_text(new_text, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": changed, "anchors_inserted": inserted}


def repair_chapter_decision_references(
    output_dir: str | Path,
    payload: dict[str, Any],
    *,
    chapters: Iterable[int],
) -> dict[str, Any]:
    """Deterministically remove false D-id anchors and restore canonical ones.

    This function never changes prose or numeric values.  It is safe clerical
    work for binding-only repair and intentionally leaves non-canonical scenario
    identity to the valuation/claim ledgers or a bounded model repair.
    """
    output = Path(output_dir)
    chapter_dir = output / "chapters"
    if not chapter_dir.is_dir():
        chapter_dir = output
    target_chapters = tuple(dict.fromkeys(
        int(item) for item in chapters if 0 <= int(item) <= 14
    ))
    entries_by_id = _entry_map(payload.get("entries") or [])
    removed = 0
    sanitized_chapters: list[int] = []
    for chapter in target_chapters:
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        rewritten: list[str] = []
        for line in original.splitlines():
            def keep_or_remove(match: re.Match[str]) -> str:
                nonlocal removed
                entry = entries_by_id.get(match.group(1))
                if (
                    entry is not None
                    and entry.get("status") == "active"
                    and _line_supports_entry(line, entry)
                ):
                    return match.group(0)
                removed += 1
                return ""

            cleaned = _DECISION_REF_RE.sub(keep_or_remove, line)
            cleaned = re.sub(r"[ \t]+([，。；、,.!?])", r"\1", cleaned)
            cleaned = cleaned.rstrip()
            rewritten.append(cleaned)
        new_text = "\n".join(rewritten) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            path.write_text(new_text, encoding="utf-8")
            sanitized_chapters.append(chapter)
    rebound = bind_decision_references(
        output, payload, chapters=target_chapters
    )
    validations = {
        str(chapter): validate_chapter_decision_references(
            payload,
            chapter_text=(chapter_dir / f"_ch{chapter:02d}.md").read_text(encoding="utf-8"),
            chapter=chapter,
            enforced=True,
        )
        for chapter in target_chapters
        if (chapter_dir / f"_ch{chapter:02d}.md").is_file()
    }
    return {
        "chapters": list(target_chapters),
        "removed_invalid_anchors": removed,
        "anchors_inserted": int(rebound.get("anchors_inserted", 0) or 0),
        "changed_chapters": sorted(set(sanitized_chapters) | set(rebound.get("changed_chapters") or [])),
        "validations": validations,
        "passed": all(item.get("state") == "DECISION_READY" for item in validations.values()),
    }


def promote_reviewable_decision_ledger(
    output_dir: str | Path,
    *,
    report_text: str,
) -> dict[str, Any]:
    """Freeze a draft only when binding is its final completed operation.

    This is intentionally clerical: it never invents or changes an entry.  A
    draft with any identity, source, manifest or chapter-coverage problem stays
    reviewable and is returned to the research agent.
    """
    output = Path(output_dir)
    payload = _read_json(output / "decision_ledger.json")
    if not payload:
        return {"promoted": False, "error": "decision_ledger_missing"}
    manifest = _read_json(output / "decision_manifest.json")
    policy = _read_json(output / "decision_ledger_policy.json")
    validation = validate_decision_ledger(
        payload,
        report_text=report_text,
        manifest=manifest,
        enforced=bool(policy.get("enforced")),
        required_metric_ids=set(policy.get("required_metric_ids") or REQUIRED_METRIC_IDS),
    )
    allowed = {"enforced_ledger_not_frozen", "decision_ready_not_frozen"}
    remaining = set(validation.get("incomplete_findings") or []) - allowed
    if validation.get("invalid_findings") or remaining:
        return {"promoted": False, "validation": validation}

    promoted = deepcopy(payload)
    promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {
        "frozen": True,
        "fingerprint": "",
        "frozen_at": _utc_now(),
    }
    promoted["freeze"]["fingerprint"] = ledger_fingerprint(promoted)
    result = persist_decision_ledger(
        output,
        promoted,
        report_text=report_text,
        allow_frozen_update=False,
    )
    result["promoted"] = bool(result.get("written"))
    return result


def persist_decision_ledger(
    output_dir: str | Path,
    payload: dict[str, Any],
    *,
    report_text: str = "",
    allow_frozen_update: bool = False,
) -> dict[str, Any]:
    """Validate, diff and atomically persist a ledger.

    A changed frozen ledger is rejected by default.  The attempted diff is
    still persisted, making silent local-repair drift observable.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "decision_ledger.json"
    diff_path = output / "decision_diff.json"
    old = _read_json(path)
    manifest = _read_json(output / "decision_manifest.json")
    policy = _read_json(output / "decision_ledger_policy.json")
    enforced = bool(policy.get("enforced"))
    required = set(policy.get("required_metric_ids") or REQUIRED_METRIC_IDS)
    validation = validate_decision_ledger(
        payload,
        report_text=report_text,
        manifest=manifest,
        enforced=enforced,
        required_metric_ids=required,
    )
    if validation["state"] == "INVALID":
        return {
            "written": False,
            "path": str(path),
            "validation": validation,
            "error": "decision ledger schema/identity validation failed",
        }
    if validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen")):
        return {
            "written": False,
            "path": str(path),
            "validation": validation,
            "error": "incomplete decision ledger cannot be frozen; complete identities/references and retry",
        }

    diff = decision_diff(old, payload, change_reason=str(payload.get("change_reason") or ""))
    old_frozen = bool((old.get("freeze") or {}).get("frozen"))
    changed = bool(old) and ledger_fingerprint(old) != ledger_fingerprint(payload)
    if old and old_frozen and changed and not allow_frozen_update:
        diff["status"] = "REJECTED_FROZEN"
        diff["approval_status"] = "REJECTED"
        diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "written": False,
            "path": str(path),
            "diff_path": str(diff_path),
            "decision_frozen": True,
            "validation": validation,
            "error": "frozen decision ledger rejected a decision-changing update",
        }
    if old and not changed:
        diff["status"] = "NO_CHANGE"
        diff["approval_status"] = "NOT_REQUIRED"
    elif old:
        diff["status"] = "APPLIED"
        diff["approval_status"] = "PENDING" if diff.get("changes_action") else "NOT_REQUIRED"
        payload["revision"] = max(int(old.get("revision") or 1) + 1, int(payload.get("revision") or 1))
        payload["freeze"]["fingerprint"] = ledger_fingerprint(payload)
        diff["new_fingerprint"] = ledger_fingerprint(payload)
    else:
        diff["status"] = "INITIALIZED"
        diff["approval_status"] = "NOT_REQUIRED"
    ledger_to_write = old if old and not changed else payload
    path.write_text(json.dumps(ledger_to_write, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "written": True,
        "path": str(path),
        "diff_path": str(diff_path),
        "ledger": ledger_to_write,
        "validation": validation,
        "diff": diff,
    }


def evaluate_output_decision_ledger(
    output_dir: str | Path,
    *,
    report_text: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _read_json(output / "decision_ledger_policy.json")
    ledger = _read_json(output / "decision_ledger.json")
    manifest = _read_json(output / "decision_manifest.json")
    enforced = bool(policy.get("enforced"))
    required = set(policy.get("required_metric_ids") or REQUIRED_METRIC_IDS)
    if not ledger:
        state = "INCOMPLETE" if enforced else "SKIP"
        result = {
            "schema_version": "decision-ledger-validation.v1",
            "state": state,
            "status": "FAIL" if enforced else "SKIP",
            "invalid_findings": [],
            "incomplete_findings": ["decision_ledger_missing"] if enforced else [],
            "warnings": [],
            "enforced": enforced,
            "policy": policy,
        }
    else:
        result = validate_decision_ledger(
            ledger,
            report_text=report_text,
            manifest=manifest,
            enforced=enforced,
            required_metric_ids=required,
        )
        result["policy"] = policy
    if persist:
        (output / "decision_ledger_validation.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result
