#!/usr/bin/env python3
"""Compile canonical decision ledgers into tamper-evident report sections."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.decision_ledger import (
        CANONICAL_METRIC_IDS, _METRIC_PATTERNS, _NUMBER_RE, _line_supports_value,
        ledger_fingerprint,
    )
    from scripts.evidence_documents import _atomic_write_json
except ModuleNotFoundError:
    from decision_ledger import CANONICAL_METRIC_IDS, _METRIC_PATTERNS, _NUMBER_RE, _line_supports_value, ledger_fingerprint
    from evidence_documents import _atomic_write_json


SCHEMA_VERSION = "decision-compilation.v1"
POLICY_VERSION = "decision-compiler-policy.v1"
VALIDATION_VERSION = "decision-compiler-validation.v1"
COMPILER_VERSION = "decision-compiler.v1"
PROTECTED_CHAPTERS = (0, 9, 12, 13, 14)
SOURCE_FILES = (
    "decision_manifest.json", "decision_ledger.json", "valuation_model.json",
    "claim_evidence.json", "thesis_test.json", "insight_ledger.json",
)
_REF_RE = re.compile(r"\[decision:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I)
_STRUCTURED_MODEL_REF_RE = re.compile(
    r"\[(valuation|threshold|thesis-test|probability):\s*([A-Za-z0-9_.:@/-]+)\s*\]",
    re.I,
)
_CLAIM_REF_RE = re.compile(r"\[claim:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I)
_BLOCK_RE = re.compile(
    r"<!-- TURTLE:DECISION_BLOCK:Ch(?P<chapter>\d+):BEGIN fingerprint=(?P<fingerprint>[^\s>]+) -->\n"
    r"(?P<body>.*?)\n<!-- TURTLE:DECISION_BLOCK:Ch(?P=chapter):END -->",
    re.S,
)
_ACTION_SIGNAL = re.compile(r"\d|[<>≤≥=]|买入|减仓|退出|清仓|仓位")
_REVALUATION_SUBJECTS = (
    "大股东减持", "控股股东减持", "非主业收购", "关联方存款",
    "财务公司存款", "商誉减值", "审计意见", "审计变更",
)
_DIRECT_EXIT_SIGNAL = re.compile(r"立即平仓|直接平仓|平仓|清仓|立即退出|直接退出|事件止损")
_REVALUATION_GUARD = re.compile(r"重估|重新估值|仅在.+才退出|只有.+才退出")
_COMBINED_RETURN_GUARD = re.compile(
    r"回报安全边际|综合回报|return[_\s-]*margin|r\s*\*\s*\+\s*(?:decay|护城河衰减)",
    re.I,
)
_EXISTING_HOLDER_GUARD = re.compile(r"已持有|既有持仓|现有持仓|existing\s+holder", re.I)
_DIRECT_BUY_SIGNAL = re.compile(r"可买|买入触发|才买|加仓|等回落|主买价|首次买入价", re.I)
_V_CASH_RE = re.compile(r"V[_\s]*cash", re.I)
_SEMANTIC_SYMBOLS = {
    "valuation.v_distribution": re.compile(r"V[_\s]*distribution", re.I),
    "balance_sheet.net_cash_broad": re.compile(r"net[_\s]*cash[_\s]*broad", re.I),
    "balance_sheet.cash_and_bank_balances": re.compile(r"cash[_\s]*and[_\s]*bank[_\s]*balances", re.I),
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _hash_bytes(raw)


def _day(value: Any) -> date | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _numeric_trigger(entry: dict[str, Any]) -> float | None:
    value = entry.get("value")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    match = _NUMBER_RE.search(str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(1).replace("−", "-"))
    except ValueError:
        return None


def _market_freshness(
    selected: dict[str, dict[str, Any]], policy: dict[str, Any],
) -> list[str]:
    entry = selected.get("market.price.current") or {}
    market_day = _day(entry.get("as_of"))
    decision_day = _day(policy.get("decision_as_of") or policy.get("created_at"))
    if market_day is None:
        return ["market_price_as_of_invalid"]
    if decision_day is None:
        return ["decision_as_of_invalid"]
    try:
        max_age = int(policy.get("max_market_age_days", 7))
    except (TypeError, ValueError):
        return ["max_market_age_days_invalid"]
    if max_age < 0:
        return ["max_market_age_days_invalid"]
    age = (decision_day - market_day).days
    if age < 0:
        return [f"market_price_after_decision_as_of:market={market_day}:decision={decision_day}"]
    if age > max_age:
        return [f"stale_market_price:age_days={age}:max_days={max_age}:as_of={market_day}"]
    return []


def _assigned_symbol_value(line: str, pattern: re.Pattern[str]) -> float | None:
    match = pattern.search(line)
    if not match:
        return None
    symbol = re.escape(match.group(0))
    table = re.search(rf"\|\s*{symbol}\s*\|\s*\**\s*([0-9][0-9,]*(?:\.\d+)?)", line, re.I)
    if table:
        return float(table.group(1).replace(",", ""))
    tail = line[match.end():]
    tail = re.split(r"\[(?:source|decision|valuation|claim):", tail, maxsplit=1, flags=re.I)[0]
    if not re.match(r"\s*(?:=|≈|：|:)", tail):
        return None
    equals = re.findall(r"(?:=|≈|：|:)\s*\**\s*([0-9][0-9,]*(?:\.\d+)?)", tail)
    return float(equals[-1].replace(",", "")) if equals else None


def _scan_metric_identity_conflicts(output: Path) -> list[str]:
    observations: dict[str, list[tuple[int, int, float]]] = {
        "valuation.v_cash": [], **{key: [] for key in _SEMANTIC_SYMBOLS},
    }
    chapter_dir = _chapter_dir(output)
    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            value = _assigned_symbol_value(line, _V_CASH_RE)
            if value is not None:
                observations["valuation.v_cash"].append((chapter, line_number, value))
            for metric_id, pattern in _SEMANTIC_SYMBOLS.items():
                value = _assigned_symbol_value(line, pattern)
                if value is not None:
                    observations[metric_id].append((chapter, line_number, value))
    findings: list[str] = []
    for metric_id, rows in observations.items():
        distinct: list[float] = []
        for _, _, value in rows:
            if not any(math.isclose(value, prior, rel_tol=1e-6, abs_tol=1e-6) for prior in distinct):
                distinct.append(value)
        locations = ",".join(f"Ch{chapter}:L{line}={value:g}" for chapter, line, value in rows)
        if len(distinct) > 1:
            findings.append("metric_identity_conflict:" + metric_id + ":" + locations)
        elif metric_id == "valuation.v_cash" and rows:
            findings.append("ambiguous_metric_symbol:valuation.v_cash:" + locations)
    return findings


def _source_fingerprints(output: Path) -> dict[str, str]:
    return {
        name: _hash_bytes((output / name).read_bytes())
        for name in SOURCE_FILES if (output / name).is_file()
    }


def _chapter_dir(output: Path) -> Path:
    chapters = output / "chapters"
    return chapters if chapters.is_dir() else output


def _entry_map(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("entry_id")): item for item in ledger.get("entries") or []
        if isinstance(item, dict) and item.get("entry_id")
    }


def select_canonical_entries(ledger: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], list[str]]:
    selected: dict[str, dict[str, Any]] = {}
    findings: list[str] = []
    active = [item for item in ledger.get("entries") or [] if isinstance(item, dict) and item.get("status") == "active"]
    for metric_id in sorted(CANONICAL_METRIC_IDS):
        candidates = [item for item in active if item.get("metric_id") == metric_id]
        explicit = [item for item in candidates if item.get("canonical") is True]
        if len(explicit) == 1:
            selected[metric_id] = explicit[0]; continue
        if len(explicit) > 1:
            findings.append("multiple_explicit_canonical_entries:" + metric_id); continue
        # A single active identity is unambiguous even when its natural
        # scenario is "pessimistic" (typical for reduce/exit triggers).
        if len(candidates) == 1:
            selected[metric_id] = candidates[0]; continue
        base = [item for item in candidates if str(item.get("scenario") or "").strip().lower() in {"base", "current", "base.current"}]
        if not base:
            findings.append("canonical_base_entry_missing:" + metric_id); continue
        latest_as_of = max(str(item.get("as_of") or "") for item in base)
        latest = [item for item in base if str(item.get("as_of") or "") == latest_as_of]
        preferred = [item for item in latest if str(item.get("basis") or "").strip().lower() in {"canonical", "final", "synthesis"}]
        winner = preferred if preferred else latest
        if len(winner) != 1:
            findings.append("canonical_entry_ambiguous:" + metric_id); continue
        selected[metric_id] = winner[0]
    return selected, findings


_LABELS = {
    "market.price.current": "当前市场价格", "return.gg.base": "GG（AA口径）",
    "return.gg.fcfe": "GG（FCFE口径）", "return.gg.normalized": "GG（Normalized口径）",
    "hurdle.ii": "资本门槛II", "valuation.v_final": "最终内在价值V_final",
    "moat.lambda": "护城河折价λ", "return.required": "要求回报率r*",
    "moat.decay": "护城河衰减", "margin.price": "价格安全边际",
    "margin.return": "回报安全边际", "decision.position.recommended": "建议仓位",
    "trigger.buy": "首次买入条件", "trigger.reduce": "减仓触发",
    "trigger.exit": "退出条件",
}

_CHAPTER_METRICS = {
    0: ("market.price.current", "return.gg.normalized", "hurdle.ii", "valuation.v_final", "margin.price", "margin.return", "decision.position.recommended", "trigger.buy"),
    9: ("trigger.reduce", "trigger.exit"),
    12: ("market.price.current", "valuation.v_final", "moat.lambda", "moat.decay", "margin.price", "margin.return"),
    13: ("market.price.current", "return.required", "decision.position.recommended", "trigger.buy", "trigger.reduce", "trigger.exit"),
    14: ("valuation.v_final", "return.gg.normalized", "hurdle.ii", "margin.price", "margin.return", "decision.position.recommended", "trigger.buy", "trigger.reduce", "trigger.exit"),
}


def _format_value(entry: dict[str, Any]) -> str:
    value = entry.get("value")
    if isinstance(value, float):
        rendered = f"{value:.6f}".rstrip("0").rstrip(".")
    else:
        rendered = str(value)
    unit = str(entry.get("unit") or "").strip()
    return rendered + ((" " + unit) if unit else "")


def render_protected_block(
    chapter: int, selected: dict[str, dict[str, Any]], manifest: dict[str, Any], input_fingerprint: str
) -> str:
    title = {
        0: "Canonical decision snapshot", 9: "Canonical risk actions",
        12: "Canonical valuation synthesis", 13: "Canonical execution rules",
        14: "Canonical final decision",
    }[chapter]
    lines = [
        f"<!-- TURTLE:DECISION_BLOCK:Ch{chapter}:BEGIN fingerprint={input_fingerprint} -->",
        f"### {title}", "",
    ]
    if chapter in {0, 14}:
        lines.append(
            f"- **统一判断**：{manifest.get('display_label')} / 目标仓位 {manifest.get('position_pct')}%"
        )
    for metric_id in _CHAPTER_METRICS[chapter]:
        entry = selected[metric_id]
        source_ids = [
            str(value).strip() for value in entry.get("source_ids") or []
            if str(value).strip()
        ]
        # Evidence anchors use ``|`` as their component delimiter.  Joining
        # source identities with commas makes the registry treat the whole
        # list as one unknown source and can falsely block an otherwise valid
        # compiled report.
        source_suffix = f" [source: {' | '.join(source_ids)}]" if source_ids else ""
        display_label = str(entry.get("display_label") or _LABELS[metric_id]).strip()
        lines.append(
            f"- **{display_label}**：{_format_value(entry)} "
            f"[decision: {entry['entry_id']}]{source_suffix}"
        )
    lines.append(f"<!-- TURTLE:DECISION_BLOCK:Ch{chapter}:END -->")
    return "\n".join(lines)


def _extract_blocks(text: str) -> list[re.Match[str]]:
    return list(_BLOCK_RE.finditer(text))


def preserve_protected_blocks(existing: str, proposed: str, chapter: int) -> str:
    """Keep compiler-owned bytes when an agent rewrites explanatory prose."""
    blocks = [match.group(0) for match in _extract_blocks(existing) if int(match.group("chapter")) == int(chapter)]
    if not blocks:
        return proposed
    cleaned = _BLOCK_RE.sub("", proposed).rstrip()
    heading = re.search(r"^##\s+[^\n]+", cleaned, re.M)
    if not heading:
        return cleaned + "\n\n" + blocks[0] + "\n"
    return cleaned[:heading.end()] + "\n\n" + blocks[0] + cleaned[heading.end():] + ("" if cleaned.endswith("\n") else "\n")


def _insert_or_replace_block(text: str, chapter: int, block: str, prior_hash: str | None) -> tuple[str, str | None]:
    matches = [match for match in _extract_blocks(text) if int(match.group("chapter")) == chapter]
    if len(matches) > 1:
        return text, "protected_block_duplicate"
    if matches:
        existing = matches[0].group(0)
        if prior_hash and _hash_bytes(existing.encode("utf-8")) != prior_hash:
            return text, "protected_block_tampered"
        return text[:matches[0].start()] + block + text[matches[0].end():], None
    if prior_hash:
        return text, "protected_block_removed"
    heading = re.search(r"^##\s+[^\n]+", text, re.M)
    if not heading:
        return text, "chapter_heading_missing"
    return text[:heading.end()] + "\n\n" + block + text[heading.end():], None


def _action_consistency(selected: dict[str, dict[str, Any]], manifest: dict[str, Any]) -> list[str]:
    findings: list[str] = []
    action = str(manifest.get("quantitative_decision") or "")
    def number(metric: str) -> float | None:
        try:
            value = float(selected[metric].get("value"))
        except (KeyError, TypeError, ValueError):
            return None
        return value if math.isfinite(value) else None
    position = number("decision.position.recommended")
    current_price = number("market.price.current")
    buy_trigger = selected.get("trigger.buy") or {}
    buy_price = _numeric_trigger(buy_trigger)
    buy_contract = " ".join(
        str(buy_trigger.get(key) or "") for key in ("value", "basis", "rationale")
    )
    if action == "buy":
        if (number("margin.price") or 0) <= 0: findings.append("buy_without_positive_price_margin")
        if (number("margin.return") or 0) < 0: findings.append("buy_without_nonnegative_return_margin")
        if position is None or position <= 0: findings.append("buy_without_positive_position")
    if action == "avoid" and position is not None and position > 0:
        findings.append("avoid_with_material_position")
    if (number("margin.return") or 0) < 0 and not _COMBINED_RETURN_GUARD.search(buy_contract):
        findings.append("buy_trigger_ignores_active_return_hurdle")
    position_entry = selected.get("decision.position.recommended") or {}
    position_contract = " ".join(
        str(position_entry.get(key) or "") for key in ("value", "basis", "rationale")
    )
    if (
        action == "hold" and position is not None and position > 0
        and current_price is not None and buy_price is not None and current_price > buy_price
        and not _EXISTING_HOLDER_GUARD.search(position_contract)
    ):
        findings.append("positive_position_above_buy_trigger_without_existing_holder_scope")
    return findings


def _manifest_reevaluation_subjects(manifest: dict[str, Any]) -> set[str]:
    """Return event subjects whose canonical action is revaluation, not exit."""
    subjects: set[str] = set()
    for value in manifest.get("exit_conditions") or []:
        rule = str(value or "")
        if not re.search(r"→\s*(?:先)?重估|先触发重估|只触发重估", rule):
            continue
        subjects.update(subject for subject in _REVALUATION_SUBJECTS if subject in rule)
    if "大股东减持" in subjects or "控股股东减持" in subjects:
        subjects.update({"大股东减持", "控股股东减持"})
    return subjects


def _entry_value_supported(line: str, entry: dict[str, Any]) -> bool:
    """Match canonical values including decimal representations of percentages."""
    value = entry.get("value")
    if _line_supports_value(line, value):
        return True
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    unit = str(entry.get("unit") or "").strip().lower()
    if unit not in {"percent", "percentage", "pct", "%"}:
        return False
    fraction = float(value) / 100.0
    return any(
        math.isclose(float(raw.replace("−", "-")), fraction, rel_tol=1e-6, abs_tol=1e-6)
        for raw in _NUMBER_RE.findall(line)
    )


def _scan_manifest_action_conflicts(
    output: Path, manifest: dict[str, Any], *, chapters: tuple[int, ...] | None = None,
) -> list[str]:
    """Reject stale direct-exit prose for events canonicalized as revaluation."""
    subjects = _manifest_reevaluation_subjects(manifest)
    if not subjects:
        return []
    invalid: list[str] = []
    chapter_dir = _chapter_dir(output)
    for chapter in (chapters if chapters is not None else tuple(range(15))):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        text = _BLOCK_RE.sub("", path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(text.splitlines(), 1):
            matching = sorted(subject for subject in subjects if subject in line)
            if not matching or not _DIRECT_EXIT_SIGNAL.search(line):
                continue
            if _REVALUATION_GUARD.search(line):
                continue
            invalid.append(
                f"stale_action_conflict:Ch{chapter}:L{line_number}:"
                + ",".join(matching)
                + ":canonical_action=REVALUE"
            )
    return invalid


def migrate_manifest_action_conflicts(
    output_dir: str | Path, *, apply: bool = False,
) -> dict[str, Any]:
    """Mechanically downgrade stale direct-exit wording to canonical revaluation.

    Only subjects explicitly written as ``→重估`` in the current manifest are
    eligible.  The transform never invents a trigger, threshold, or action.
    """
    output = Path(output_dir)
    manifest = _load(output / "decision_manifest.json")
    subjects = _manifest_reevaluation_subjects(manifest)
    changes: list[dict[str, Any]] = []
    pending: dict[Path, str] = {}
    chapter_dir = _chapter_dir(output)
    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        rewritten: list[str] = []
        inside = False
        for line_number, line in enumerate(original.splitlines(), 1):
            if f"TURTLE:DECISION_BLOCK:Ch{chapter}:BEGIN" in line:
                inside = True
            if inside:
                rewritten.append(line)
                if f"TURTLE:DECISION_BLOCK:Ch{chapter}:END" in line:
                    inside = False
                continue
            matching = sorted(subject for subject in subjects if subject in line)
            if (
                matching and _DIRECT_EXIT_SIGNAL.search(line)
                and not _REVALUATION_GUARD.search(line)
            ):
                new_line = _DIRECT_EXIT_SIGNAL.sub("触发重估", line)
                if new_line != line:
                    changes.append({
                        "chapter": chapter, "line": line_number,
                        "subjects": matching, "before": line, "after": new_line,
                    })
                    line = new_line
            rewritten.append(line)
        new_text = "\n".join(rewritten) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            pending[path] = new_text
    if apply:
        for path, value in pending.items():
            path.write_text(value, encoding="utf-8")
    result = {
        "schema_version": "manifest-action-migration.v1", "generated_at": _now(),
        "applied": bool(apply), "changed_lines": changes,
        "state": "MIGRATED" if changes else "NO_CHANGE",
    }
    if apply:
        _atomic_write_json(output / "manifest_action_migration.json", result)
    return result


def _scan_free_critical_values(
    output: Path, selected: dict[str, dict[str, Any]], ledger: dict[str, Any],
    *, chapters: tuple[int, ...] | None = None,
) -> list[str]:
    invalid: list[str] = []
    entries = _entry_map(ledger)
    valuation = _load(output / "valuation_model.json")
    thesis = _load(output / "thesis_test.json")
    claim_evidence = _load(output / "claim_evidence.json")
    structured_ids = {
        "valuation": {str(item.get("model_id")) for item in valuation.get("models") or [] if isinstance(item, dict) and item.get("model_id")},
        "threshold": {str(item.get("threshold_id")) for item in thesis.get("thresholds") or [] if isinstance(item, dict) and item.get("threshold_id")},
        "thesis-test": {str(item.get("test_id")) for item in thesis.get("competitive_tests") or [] if isinstance(item, dict) and item.get("test_id")},
        "probability": {str(item.get("set_id")) for item in thesis.get("probability_sets") or [] if isinstance(item, dict) and item.get("set_id")},
    }
    claim_decisions = {
        str(item.get("claim_id")): {str(entry_id) for entry_id in item.get("decision_entry_ids") or []}
        for item in claim_evidence.get("claims") or []
        if isinstance(item, dict) and item.get("claim_id")
    }
    chapter_dir = _chapter_dir(output)
    for chapter in (chapters if chapters is not None else tuple(range(15))):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        text = _BLOCK_RE.sub("", path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith(("#", "<!--")):
                continue
            refs = _REF_RE.findall(line)
            for metric_id, pattern in _METRIC_PATTERNS.items():
                match = pattern.search(line)
                if not match or not _ACTION_SIGNAL.search(line):
                    continue
                expected = selected.get(metric_id, {})
                canonical_on_line = bool(expected and _entry_value_supported(line, expected))
                if metric_id == "moat.decay" and isinstance(expected.get("value"), (int, float)):
                    canonical_on_line = canonical_on_line or any(
                        math.isclose(abs(number), abs(float(expected["value"])), rel_tol=1e-6, abs_tol=1e-6)
                        for number in (float(raw.replace("−", "-")) for raw in _NUMBER_RE.findall(line))
                    )
                if (
                    metric_id == "moat.decay"
                    and not canonical_on_line
                    and re.search(
                        r"(?:r\s*\*|要求回报率)\s*\+\s*(?:护城河衰减|decay)"
                        r"|(?:护城河衰减|decay)\s*\+\s*(?:r\s*\*|要求回报率)",
                        line,
                        re.IGNORECASE,
                    )
                ):
                    # ``r* + decay = 13.2%`` states a combined hurdle, not a
                    # second moat-decay value.  Binding it to D009 would itself
                    # be a false identity.
                    continue
                # Do not turn a mere textual mention plus an unrelated date or
                # table count into a critical value.  Unknown values must be
                # syntactically adjacent to the metric identity.
                tail = line[match.end():min(len(line), match.end() + 24)]
                adjacent_number = bool(re.match(r"^[\s*|（(\[=:：为约~<>≤≥+\-−]*\d", tail))
                trigger_payload = metric_id in {"trigger.buy", "trigger.reduce", "trigger.exit"} and bool(
                    re.search(r"审计|违约|减持|毛利率|股价|价格|收购|分红|现金流|利润", line)
                )
                if not canonical_on_line and not adjacent_number and not trigger_payload:
                    continue
                bound_metrics = {
                    str(entries.get(ref, {}).get("metric_id") or "") for ref in refs
                    if entries.get(ref, {}).get("status") in {"active", "deprecated"}
                }
                if canonical_on_line and str(expected.get("entry_id") or "") not in refs:
                    invalid.append(f"free_critical_value:Ch{chapter}:L{line_number}:{metric_id}")
                    continue
                if not canonical_on_line and metric_id not in bound_metrics:
                    # Sensitivity/scenario outputs belong to valuation or
                    # thesis ledgers rather than the final decision identity.
                    if any(ref_id in structured_ids.get(ref_type.lower(), set()) for ref_type, ref_id in _STRUCTURED_MODEL_REF_RE.findall(line)):
                        continue
                    selected_id = str(expected.get("entry_id") or "")
                    if selected_id and any(selected_id in claim_decisions.get(claim_id, set()) for claim_id in _CLAIM_REF_RE.findall(line)):
                        continue
                    invalid.append(f"free_critical_value:Ch{chapter}:L{line_number}:{metric_id}")
                    continue
                for ref in refs:
                    entry = entries.get(ref)
                    if entry and entry.get("metric_id") == metric_id and isinstance(entry.get("value"), (int, float)) and not isinstance(entry.get("value"), bool):
                        supported = _entry_value_supported(line, entry)
                        if metric_id == "moat.decay":
                            supported = supported or any(
                                math.isclose(abs(number), abs(float(entry["value"])), rel_tol=1e-6, abs_tol=1e-6)
                                for number in (float(raw.replace("−", "-")) for raw in _NUMBER_RE.findall(line))
                            )
                        if not supported:
                            invalid.append(f"bound_value_mismatch:Ch{chapter}:L{line_number}:{ref}")
                    if entry and entry.get("metric_id") == metric_id and entry.get("status") == "deprecated" and not re.search(r"旧|历史|废弃|不再采用|已取代", line):
                        invalid.append(f"deprecated_value_not_labeled:Ch{chapter}:L{line_number}:{ref}")
    return invalid


def _scan_noncanonical_action_prices(
    output: Path, selected: dict[str, dict[str, Any]], *, chapters: tuple[int, ...] | None = None,
) -> list[str]:
    """Reject prose that turns a noncanonical scenario/theoretical price into an action."""
    canonical = _numeric_trigger(selected.get("trigger.buy") or {})
    if canonical is None:
        return []
    invalid: list[str] = []
    chapter_dir = _chapter_dir(output)
    candidate_patterns = (
        re.compile(r"^\s*\|\s*\**([0-9]+(?:\.[0-9]+)?)\s*(?:HKD|RMB|元)", re.I),
        re.compile(r"(?:P_buy|主买价|首次买入价|买入触发价)\s*(?:[=(：:]|≤|<)*\s*([0-9]+(?:\.[0-9]+)?)", re.I),
        re.compile(r"(?:价|价格)\s*≤\s*(?:P_buy\s*[=(：:]?\s*)?([0-9]+(?:\.[0-9]+)?)", re.I),
        re.compile(r"回落至\s*≤?\s*([0-9]+(?:\.[0-9]+)?)", re.I),
        re.compile(r"P_DDM\s*=\s*([0-9]+(?:\.[0-9]+)?)[^。；|]*买入触发", re.I),
    )
    for chapter in chapters if chapters is not None else tuple(range(15)):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        text = _BLOCK_RE.sub("", path.read_text(encoding="utf-8"))
        for line_number, line in enumerate(text.splitlines(), 1):
            if not _DIRECT_BUY_SIGNAL.search(line):
                continue
            values: list[float] = []
            for pattern in candidate_patterns:
                values.extend(float(match.group(1)) for match in pattern.finditer(line))
            for value in values:
                if not math.isclose(value, canonical, rel_tol=1e-6, abs_tol=0.011):
                    invalid.append(
                        f"noncanonical_action_price:Ch{chapter}:L{line_number}:{value:g}!={canonical:g}"
                    )
    return list(dict.fromkeys(invalid))


def validate_chapter_decision_bindings(
    output_dir: str | Path, chapter: int
) -> dict[str, Any]:
    """Validate canonical metric identities immediately after a chapter write."""
    output = Path(output_dir)
    ledger = _load(output / "decision_ledger.json")
    policy = _load(output / "decision_compiler_policy.json")
    if not ledger or not policy.get("enforced"):
        return {
            "state": "SKIP", "status": "SKIP", "invalid_findings": [],
            "chapter": int(chapter),
        }
    selected, findings = select_canonical_entries(ledger)
    invalid = list(findings)
    if not invalid:
        invalid.extend(
            _scan_free_critical_values(
                output, selected, ledger, chapters=(int(chapter),)
            )
        )
        invalid.extend(
            _scan_noncanonical_action_prices(
                output, selected, chapters=(int(chapter),)
            )
        )
    chapter_path = _chapter_dir(output) / f"_ch{int(chapter):02d}.md"
    if chapter_path.is_file():
        try:
            from scripts.decision_ledger import validate_chapter_decision_references
        except ModuleNotFoundError:
            from decision_ledger import validate_chapter_decision_references
        reference_validation = validate_chapter_decision_references(
            ledger,
            chapter_text=chapter_path.read_text(encoding="utf-8"),
            chapter=int(chapter),
            enforced=True,
        )
        invalid.extend(reference_validation.get("invalid_findings") or [])
    invalid = list(dict.fromkeys(invalid))
    return {
        "state": "INVALID" if invalid else "DECISION_READY",
        "status": "FAIL" if invalid else "PASS",
        "invalid_findings": invalid,
        "chapter": int(chapter),
    }


def migrate_legacy_decision_values(
    output_dir: str | Path, *, apply: bool = False
) -> dict[str, Any]:
    """Mechanically bind known legacy values; never guess an unknown identity.

    Active canonical values receive their entry ID.  A uniquely matching
    deprecated value is retained only as explicitly historical text.  Unknown
    or ambiguous values are reported for research review and left untouched.
    """
    output = Path(output_dir)
    ledger = _load(output / "decision_ledger.json")
    entries = [item for item in ledger.get("entries") or [] if isinstance(item, dict)]
    chapter_dir = _chapter_dir(output)
    changes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    pending: dict[Path, str] = {}
    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines()
        inside = False
        rewritten: list[str] = []
        for line_number, line in enumerate(lines, 1):
            if f"TURTLE:DECISION_BLOCK:Ch{chapter}:BEGIN" in line:
                inside = True
            if inside:
                rewritten.append(line)
                if f"TURTLE:DECISION_BLOCK:Ch{chapter}:END" in line:
                    inside = False
                continue
            if line.lstrip().startswith(("#", "<!--")):
                rewritten.append(line)
                continue
            additions: list[str] = []
            refs = set(_REF_RE.findall(line))
            for metric_id, pattern in _METRIC_PATTERNS.items():
                if not pattern.search(line) or not _ACTION_SIGNAL.search(line):
                    continue
                if any(str(item.get("entry_id")) in refs and item.get("metric_id") == metric_id for item in entries):
                    continue
                matches = [
                    item for item in entries
                    if item.get("metric_id") == metric_id and _entry_value_supported(line, item)
                ]
                if metric_id == "moat.decay" and not matches:
                    numbers = [float(raw.replace("−", "-")) for raw in _NUMBER_RE.findall(line)]
                    matches = [
                        item for item in entries
                        if item.get("metric_id") == metric_id
                        and isinstance(item.get("value"), (int, float))
                        and any(math.isclose(abs(number), abs(float(item["value"])), rel_tol=1e-6, abs_tol=1e-6) for number in numbers)
                    ]
                if len(matches) != 1:
                    unresolved.append({
                        "chapter": chapter, "line": line_number, "metric_id": metric_id,
                        "text": line, "candidate_entry_ids": [str(item.get("entry_id")) for item in matches],
                    })
                    continue
                entry = matches[0]
                suffix = f"[decision: {entry['entry_id']}]"
                if entry.get("status") == "deprecated":
                    suffix += "（已废弃口径，不参与最终决策）"
                additions.append(suffix)
                changes.append({"chapter": chapter, "line": line_number, "metric_id": metric_id, "entry_id": entry["entry_id"], "status": entry.get("status")})
            rewritten.append(line + ((" " + " ".join(additions)) if additions else ""))
        new_text = "\n".join(rewritten) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            pending[path] = new_text
    if apply:
        for path, text_value in pending.items():
            path.write_text(text_value, encoding="utf-8")
    result = {
        "schema_version": "decision-migration-report.v1", "generated_at": _now(),
        "applied": bool(apply), "changed_lines": changes,
        "unresolved_lines": unresolved,
        "state": "INCOMPLETE" if unresolved else "MIGRATED",
    }
    _atomic_write_json(output / "decision_migration_report.json", result)
    return result


def migrate_canonical_decision_summaries(
    output_dir: str | Path, *, apply: bool = False,
) -> dict[str, Any]:
    """Rewrite only uniquely labeled summary rows from the frozen ledger.

    This is intentionally narrower than prose rewriting: it accepts Markdown
    table rows whose first cell is the canonical label and bold ``**label**``
    summary lines.  Free-form analysis remains untouched and unresolved.
    """
    output = Path(output_dir)
    ledger = _load(output / "decision_ledger.json")
    selected, selection_findings = select_canonical_entries(ledger)
    if selection_findings:
        return {
            "schema_version": "canonical-summary-migration.v1", "applied": False,
            "state": "BLOCKED", "blocking_findings": selection_findings,
            "changed_lines": [], "unresolved_lines": [],
        }
    locations: dict[tuple[int, int], str] = {}
    for finding in _scan_free_critical_values(output, selected, ledger):
        match = re.fullmatch(r"free_critical_value:Ch(\d+):L(\d+):(.+)", finding)
        if match:
            locations[(int(match.group(1)), int(match.group(2)))] = match.group(3)
    changes: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    pending: dict[Path, str] = {}
    chapter_dir = _chapter_dir(output)

    def display(entry: dict[str, Any]) -> str:
        value = entry.get("value")
        rendered = f"{float(value):g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)
        unit = str(entry.get("unit") or "").lower()
        if unit in {"percent", "percentage", "pct", "%"}:
            return rendered + "%"
        if unit in {"pp", "pct_point", "percentage_point"}:
            return rendered + "pct"
        if unit in {"rule", "condition"}:
            return rendered
        return rendered + ((" " + str(entry.get("unit"))) if entry.get("unit") else "")

    for chapter in range(15):
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            continue
        original = path.read_text(encoding="utf-8")
        lines = original.splitlines()
        for line_index, line in enumerate(lines):
            metric_id = locations.get((chapter, line_index + 1))
            if not metric_id or metric_id not in selected:
                continue
            entry = selected[metric_id]
            label = _LABELS[metric_id]
            ref = f"[decision: {entry['entry_id']}]"
            new_line = line
            cells = line.split("|")
            if len(cells) >= 4 and cells[1].strip().strip("*") == label:
                cells[2] = " " + display(entry) + " "
                new_line = "|".join(cells)
                if ref not in new_line:
                    new_line = new_line.rstrip() + " " + ref
            elif re.match(rf"^\s*\*\*{re.escape(label)}\*\*[：:]", line):
                new_line = f"**{label}**：{display(entry)}。 {ref}"
            if new_line == line:
                unresolved.append({
                    "chapter": chapter, "line": line_index + 1,
                    "metric_id": metric_id, "text": line,
                })
                continue
            lines[line_index] = new_line
            changes.append({
                "chapter": chapter, "line": line_index + 1,
                "metric_id": metric_id, "entry_id": entry["entry_id"],
                "before": line, "after": new_line,
            })
        new_text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
        if new_text != original:
            pending[path] = new_text
    if apply:
        for path, value in pending.items():
            path.write_text(value, encoding="utf-8")
    result = {
        "schema_version": "canonical-summary-migration.v1", "generated_at": _now(),
        "applied": bool(apply), "changed_lines": changes,
        "unresolved_lines": unresolved,
        "state": "INCOMPLETE" if unresolved else "MIGRATED" if changes else "NO_CHANGE",
    }
    if apply:
        _atomic_write_json(output / "canonical_summary_migration.json", result)
    return result


def approve_decision_diff(
    output_dir: str | Path, *, approved_by: str, rationale: str,
    evidence_ids: list[str],
) -> dict[str, Any]:
    """Record explicit human/reviewer approval for an action-changing diff."""
    output = Path(output_dir)
    diff = _load(output / "decision_diff.json")
    if not diff:
        return {"written": False, "error": "decision_diff_missing"}
    if diff.get("status") != "APPLIED" or not diff.get("changes_action"):
        return {"written": False, "error": "decision_diff_does_not_require_approval"}
    ledger = _load(output / "decision_ledger.json")
    if diff.get("new_fingerprint") != ledger_fingerprint(ledger):
        return {"written": False, "error": "decision_diff_ledger_fingerprint_mismatch"}
    if not str(approved_by).strip() or not str(rationale).strip() or not evidence_ids:
        return {"written": False, "error": "approval_identity_rationale_and_evidence_required"}
    diff["approval_status"] = "APPROVED"
    diff["approval"] = {
        "approved_by": str(approved_by).strip(), "approved_at": _now(),
        "rationale": str(rationale).strip(),
        "evidence_ids": [str(item).strip() for item in evidence_ids if str(item).strip()],
    }
    _atomic_write_json(output / "decision_diff.json", diff)
    return {"written": True, "diff": diff}


def validate_compilation(output_dir: str | Path, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    output = Path(output_dir)
    payload = payload or _load(output / "decision_compilation.json")
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if payload.get("compiler_version") != COMPILER_VERSION:
        invalid.append("compiler_version_invalid")
    current_sources = _source_fingerprints(output)
    expected_sources = payload.get("source_fingerprints") if isinstance(payload.get("source_fingerprints"), dict) else {}
    for name in SOURCE_FILES:
        if name not in expected_sources:
            incomplete.append("compiler_source_missing:" + name)
        elif current_sources.get(name) != expected_sources.get(name):
            invalid.append("compiler_source_changed:" + name)
    ledger = _load(output / "decision_ledger.json")
    manifest = _load(output / "decision_manifest.json")
    policy = _load(output / "decision_compiler_policy.json")
    selected, selection_findings = select_canonical_entries(ledger)
    incomplete.extend(selection_findings)
    selected_ids = {metric: str(entry.get("entry_id")) for metric, entry in selected.items()}
    if selected_ids != payload.get("selected_entry_ids"):
        invalid.append("compiled_entry_selection_mismatch")
    input_fingerprint = _canonical_hash(expected_sources)
    if payload.get("input_fingerprint") != input_fingerprint:
        invalid.append("compilation_input_fingerprint_mismatch")
    if len(selected) == len(CANONICAL_METRIC_IDS):
        invalid.extend(_market_freshness(selected, policy))
        invalid.extend(_action_consistency(selected, manifest))
        for chapter in PROTECTED_CHAPTERS:
            path = _chapter_dir(output) / f"_ch{chapter:02d}.md"
            if not path.is_file():
                incomplete.append(f"compiled_chapter_missing:Ch{chapter}"); continue
            text = path.read_text(encoding="utf-8")
            matches = [match for match in _extract_blocks(text) if int(match.group("chapter")) == chapter]
            if len(matches) != 1:
                invalid.append(f"protected_block_count:Ch{chapter}:{len(matches)}"); continue
            expected = render_protected_block(chapter, selected, manifest, input_fingerprint)
            if matches[0].group(0) != expected:
                invalid.append(f"protected_block_content_mismatch:Ch{chapter}")
            expected_hash = str((payload.get("blocks") or {}).get(str(chapter), {}).get("sha256") or "")
            if _hash_bytes(matches[0].group(0).encode("utf-8")) != expected_hash:
                invalid.append(f"protected_block_hash_mismatch:Ch{chapter}")
        invalid.extend(_scan_free_critical_values(output, selected, ledger))
        invalid.extend(_scan_noncanonical_action_prices(output, selected))
        invalid.extend(_scan_manifest_action_conflicts(output, manifest))
        invalid.extend(_scan_metric_identity_conflicts(output))
    diff = _load(output / "decision_diff.json")
    if diff.get("status") == "APPLIED" and diff.get("new_fingerprint") != ledger_fingerprint(ledger):
        invalid.append("decision_diff_ledger_fingerprint_mismatch")
    if diff.get("changes_action") and diff.get("status") == "APPLIED" and diff.get("approval_status") != "APPROVED":
        incomplete.append("decision_diff_approval_pending")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete)); warnings = list(dict.fromkeys(warnings))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "DECISION_READY"
    return {"schema_version": VALIDATION_VERSION, "state": state, "status": "PASS" if state == "DECISION_READY" else "FAIL", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings, "selected_entry_ids": selected_ids}


def compile_decision_sections(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    ledger = _load(output / "decision_ledger.json")
    manifest = _load(output / "decision_manifest.json")
    policy = _load(output / "decision_compiler_policy.json")
    def stop(state: str, *, invalid: list[str] | None = None, incomplete: list[str] | None = None) -> dict[str, Any]:
        result = {
            "schema_version": VALIDATION_VERSION, "written": False,
            "state": state, "status": "FAIL",
            "invalid_findings": list(invalid or []),
            "incomplete_findings": list(incomplete or []), "warnings": [],
        }
        if persist:
            _atomic_write_json(output / "decision_compiler_validation.json", result)
        return result
    missing = [name for name in SOURCE_FILES if not (output / name).is_file()]
    if missing:
        return stop("INCOMPLETE", incomplete=["compiler_source_missing:" + name for name in missing])
    selected, findings = select_canonical_entries(ledger)
    if findings or len(selected) != len(CANONICAL_METRIC_IDS):
        return stop("INCOMPLETE", incomplete=findings)
    action_findings = _market_freshness(selected, policy)
    action_findings.extend(_action_consistency(selected, manifest))
    action_findings.extend(_scan_free_critical_values(output, selected, ledger))
    action_findings.extend(_scan_noncanonical_action_prices(output, selected))
    action_findings.extend(_scan_manifest_action_conflicts(output, manifest))
    action_findings.extend(_scan_metric_identity_conflicts(output))
    if action_findings:
        return stop("INVALID", invalid=action_findings)
    diff = _load(output / "decision_diff.json")
    if diff.get("status") == "APPLIED" and diff.get("new_fingerprint") != ledger_fingerprint(ledger):
        return stop("INVALID", invalid=["decision_diff_ledger_fingerprint_mismatch"])
    if diff.get("changes_action") and diff.get("status") == "APPLIED" and diff.get("approval_status") != "APPROVED":
        return stop("INCOMPLETE", incomplete=["decision_diff_approval_pending"])
    sources = _source_fingerprints(output)
    input_fingerprint = _canonical_hash(sources)
    prior = _load(output / "decision_compilation.json")
    prior_blocks = prior.get("blocks") if isinstance(prior.get("blocks"), dict) else {}
    blocks: dict[str, dict[str, Any]] = {}
    changed: list[int] = []
    invalid: list[str] = []
    pending_writes: dict[Path, str] = {}
    chapter_dir = _chapter_dir(output)
    for chapter in PROTECTED_CHAPTERS:
        path = chapter_dir / f"_ch{chapter:02d}.md"
        if not path.is_file():
            invalid.append(f"compiled_chapter_missing:Ch{chapter}"); continue
        block = render_protected_block(chapter, selected, manifest, input_fingerprint)
        prior_hash = str((prior_blocks.get(str(chapter)) or {}).get("sha256") or "") or None
        new_text, error = _insert_or_replace_block(path.read_text(encoding="utf-8"), chapter, block, prior_hash)
        if error:
            invalid.append(f"{error}:Ch{chapter}"); continue
        blocks[str(chapter)] = {"sha256": _hash_bytes(block.encode("utf-8")), "entry_ids": [selected[metric]["entry_id"] for metric in _CHAPTER_METRICS[chapter]]}
        if new_text != path.read_text(encoding="utf-8"):
            pending_writes[path] = new_text; changed.append(chapter)
    if invalid:
        result = stop("INVALID", invalid=invalid)
        result["changed_chapters"] = []
        return result
    if persist:
        for path, new_text in pending_writes.items():
            path.write_text(new_text, encoding="utf-8")
    payload = {
        "schema_version": SCHEMA_VERSION, "compiler_version": COMPILER_VERSION,
        "report_id": ledger.get("report_id"), "generated_at": prior.get("generated_at") or _now(),
        "source_fingerprints": sources, "input_fingerprint": input_fingerprint,
        "decision_ledger_fingerprint": ledger_fingerprint(ledger),
        "selected_entry_ids": {metric: entry["entry_id"] for metric, entry in selected.items()},
        "protected_chapters": list(PROTECTED_CHAPTERS), "blocks": blocks,
    }
    payload["validation"] = validate_compilation(output, payload)
    if persist:
        if not prior or prior.get("input_fingerprint") != input_fingerprint or prior.get("blocks") != blocks:
            _atomic_write_json(output / "decision_compilation.json", payload)
        _atomic_write_json(output / "decision_compiler_validation.json", payload["validation"])
    return {"written": True, "idempotent": not changed and bool(prior), "changed_chapters": changed, "compilation": payload, "validation": payload["validation"]}


def initialize_decision_compiler_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool,
    decision_as_of: str = "", max_market_age_days: int = 7,
) -> dict[str, Any]:
    created_at = _now()
    payload = {
        "schema_version": POLICY_VERSION, "compiler_version": COMPILER_VERSION,
        "run_id": str(run_id), "enforced": bool(enforced),
        "protected_chapters": list(PROTECTED_CHAPTERS), "created_at": created_at,
        "decision_as_of": str(decision_as_of or created_at[:10]),
        "max_market_age_days": int(max_market_age_days),
    }
    _atomic_write_json(Path(output_dir) / "decision_compiler_policy.json", payload)
    return payload


def evaluate_output_decision_compiler(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _load(output / "decision_compiler_policy.json")
    if not policy:
        return {"schema_version": VALIDATION_VERSION, "state": "SKIP", "status": "SKIP", "invalid_findings": [], "incomplete_findings": [], "warnings": [], "enforced": False}
    payload = _load(output / "decision_compilation.json")
    if not payload:
        prior_validation = _load(output / "decision_compiler_validation.json")
        if prior_validation.get("state") in {"INVALID", "INCOMPLETE"}:
            result = prior_validation
        else:
            result = {"schema_version": VALIDATION_VERSION, "state": "INCOMPLETE", "status": "FAIL", "invalid_findings": [], "incomplete_findings": ["decision_compilation_missing"], "warnings": []}
        result["enforced"] = bool(policy.get("enforced"))
    else:
        result = validate_compilation(output, payload); result["enforced"] = bool(policy.get("enforced"))
    if persist:
        _atomic_write_json(output / "decision_compiler_validation.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="编译并验证关键章节的canonical决策区块")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--enforced", action="store_true")
    parser.add_argument("--migrate", action="store_true")
    parser.add_argument("--apply-migration", action="store_true")
    args = parser.parse_args()
    if args.run_id:
        initialize_decision_compiler_policy(args.output_dir, run_id=args.run_id, enforced=args.enforced)
    if args.migrate or args.apply_migration:
        result = migrate_legacy_decision_values(args.output_dir, apply=args.apply_migration)
        print(json.dumps(result, ensure_ascii=False, default=str))
        return 0 if result.get("state") == "MIGRATED" else 2
    result = compile_decision_sections(args.output_dir, persist=True)
    print(json.dumps(result, ensure_ascii=False, default=str))
    return 0 if result.get("written") and (result.get("validation") or {}).get("state") != "INVALID" else 2


if __name__ == "__main__":
    raise SystemExit(main())
