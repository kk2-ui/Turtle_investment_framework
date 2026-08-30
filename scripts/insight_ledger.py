#!/usr/bin/env python3
"""Case-calibrated insight gate and compact investment-memo renderer."""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "insight-ledger.v1"
POLICY_VERSION = "insight-policy.v1"
READY_STATES = {"DECISION_READY", "MONITORING"}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}
ARCHETYPES = {
    "asset_catalyst", "distressed_survival", "franchise_customer_lockin",
    "technology_transition", "mature_cash_return", "compounder_reinvestment",
    "regulated_financial", "operating_transition",
}
_ANCHOR = re.compile(r"\[insight:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.I)
_PRICE_STOP = re.compile(r"(?:股价|价格)[^。；\n]{0,25}(?:跌破|低于)[^。；\n]{0,25}(?:清仓|退出|止损)")
_FULLY_PRICED = re.compile(r"(?:风险|利空).{0,12}(?:充分|完全|已经)定价|(?:低\s*P[EB]|低估值).{0,16}(?:充分|完全|已经)定价", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load(path: Path) -> dict[str, Any]:
    try: value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return {}
    return value if isinstance(value, dict) else {}


def _analysis_purpose(payload: dict[str, Any], output_dir: str | Path | None = None) -> str:
    """Keep legacy ledgers investment-scoped unless CJO is explicit in a contract."""
    declared = str(payload.get("analysis_purpose") or "").strip()
    if declared:
        return declared
    if output_dir is not None:
        contract = _load(Path(output_dir) / "analysis_contract.json")
        contract_purpose = str(contract.get("analysis_purpose") or "").strip()
        if contract_purpose:
            return contract_purpose
    return "INVESTMENT_DECISION"


def _canonical(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    for key in ("freeze", "generated_at", "updated_at"): value.pop(key, None)
    return value


def insight_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(_canonical(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


_QUESTION_IDENTITY_TERMS = {
    "cash_value_realization": ("净现金", "现金", "市值", "外部股东", "分配", "兑现", "留存价值"),
    "owner_return_hurdle": ("GG", "II", "回报", "要求回报", "穿透回报", "正常化"),
    "operating_transition": ("收入", "利润", "毛利率", "周期", "结构", "转折", "lambda", "λ"),
    "valuation_model_applicability": ("估值", "模型", "终值", "折现", "现金流"),
    "market_implied_path": ("市场隐含", "价格", "反推", "路径"),
}


def _report_text(output: Path) -> str:
    chapter_dir = output / "chapters"
    if not chapter_dir.is_dir():
        chapter_dir = output
    return "\n\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(chapter_dir.glob("_ch*.md"))
    )


def build_insight_question_identity_migration(
    output_dir: str | Path, *, persist: bool = True
) -> dict[str, Any]:
    """Prepare a no-LLM identity-only migration for a legacy frozen insight.

    The candidate is never authoritative.  It may copy the exact selected
    question and add its ID only when the old question has one unambiguous topic
    match and the old ledger's sole validation gap is that missing identity.
    """
    output = Path(output_dir)
    source = _load(output / "insight_ledger.json")
    plan = _load(output / "decisive_question_plan.json")
    policy = _load(output / "insight_policy.json")
    report_text = _report_text(output)
    source_validation = validate_insight_ledger(
        source, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
    ) if source else {"state": "INCOMPLETE", "incomplete_findings": ["insight_ledger_missing"], "invalid_findings": []}
    result: dict[str, Any] = {
        "schema_version": "insight-question-identity-migration.v1",
        "generated_at": _now(),
        "source_insight_fingerprint": insight_fingerprint(source) if source else "",
        "plan_input_fingerprint": str(plan.get("input_fingerprint") or ""),
        "source_validation": source_validation,
        "status": "NOT_ELIGIBLE",
        "candidate_validation": {},
        "selected_question_id": "",
        "canonical_unchanged": True,
    }
    eligible_gap = (
        not source_validation.get("invalid_findings")
        and source_validation.get("incomplete_findings") == ["question_basis:question_id_missing"]
        and bool((source.get("freeze") or {}).get("frozen"))
    )
    selected = [
        item for item in plan.get("selected_questions") or []
        if isinstance(item, dict) and item.get("question_id") and item.get("question")
    ]
    if not eligible_gap or not selected:
        if persist:
            (output / "insight_question_identity_migration.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return result
    old_text = " ".join((
        str(source.get("decisive_question") or ""),
        _text(source.get("question_basis") or {}),
    ))
    scored: list[tuple[int, str, dict[str, Any]]] = []
    for question in selected:
        family = str(question.get("topic_family") or "")
        terms = _QUESTION_IDENTITY_TERMS.get(family, ())
        score = sum(1 for term in terms if term in old_text)
        scored.append((score, str(question["question_id"]), question))
    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score, _, best_question = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0
    result["match_scores"] = [
        {"question_id": question_id, "score": score}
        for score, question_id, _ in scored
    ]
    if best_score < 3 or best_score - runner_up < 2:
        result["status"] = "AMBIGUOUS_REQUIRES_RESEARCH"
        if persist:
            (output / "insight_question_identity_migration.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        return result
    candidate = deepcopy(source)
    candidate["decisive_question"] = str(best_question["question"])
    candidate.setdefault("question_basis", {})["question_id"] = str(best_question["question_id"])
    candidate["change_reason"] = (
        str(candidate.get("change_reason") or "").strip()
        + "; deterministic selected-question identity migration"
    ).strip("; ")
    candidate["updated_at"] = _now()
    candidate["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    candidate["freeze"]["fingerprint"] = insight_fingerprint(candidate)
    candidate_validation = validate_insight_ledger(
        candidate, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
    )
    result.update({
        "status": "READY_TO_PROMOTE" if candidate_validation.get("state") == "DECISION_READY" else "CANDIDATE_INVALID",
        "candidate_validation": candidate_validation,
        "selected_question_id": str(best_question["question_id"]),
        "candidate_fingerprint": insight_fingerprint(candidate),
    })
    if persist:
        (output / "insight_question_identity_candidate.json").write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "insight_question_identity_migration.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return result


def promote_insight_question_identity_migration(output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    migration = _load(output / "insight_question_identity_migration.json")
    candidate = _load(output / "insight_question_identity_candidate.json")
    source = _load(output / "insight_ledger.json")
    plan = _load(output / "decisive_question_plan.json")
    decisive_validation = _load(output / "decisive_question_validation.json")
    candidate_fingerprint = insight_fingerprint(candidate) if candidate else ""
    source_fingerprint = insight_fingerprint(source) if source else ""

    def _record_promoted() -> dict[str, Any]:
        updated = {
            **migration,
            "status": "PROMOTED",
            "canonical_unchanged": False,
            "canonical_fingerprint": source_fingerprint or candidate_fingerprint,
            "promoted_at": str(migration.get("promoted_at") or _now()),
        }
        (output / "insight_question_identity_migration.json").write_text(
            json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return updated

    # Recover idempotently when canonical persistence succeeded but the
    # lifecycle marker was not written (for example process interruption
    # between those two writes).  The exact candidate fingerprint is the
    # authority; mere semantic similarity is insufficient.
    if (
        migration.get("status") in {"READY_TO_PROMOTE", "PROMOTED"}
        and candidate
        and source_fingerprint == candidate_fingerprint
        and candidate_fingerprint == migration.get("candidate_fingerprint")
    ):
        updated = _record_promoted()
        return {"promoted": False, "already_promoted": True, "migration": updated}
    if migration.get("status") != "READY_TO_PROMOTE" or not candidate:
        return {"promoted": False, "error": "ready_identity_candidate_missing"}
    if decisive_validation.get("state") not in READY_STATES:
        return {"promoted": False, "error": "decisive_questions_not_ready"}
    if insight_fingerprint(source) != migration.get("source_insight_fingerprint"):
        return {"promoted": False, "error": "source_insight_changed"}
    if str(plan.get("input_fingerprint") or "") != str(migration.get("plan_input_fingerprint") or ""):
        return {"promoted": False, "error": "decisive_plan_changed"}
    result = persist_insight_ledger(
        output, candidate, report_text=_report_text(output), allow_frozen_update=True
    )
    if result.get("written"):
        source = _load(output / "insight_ledger.json")
        source_fingerprint = insight_fingerprint(source)
        updated = _record_promoted()
        return {"promoted": True, "result": result, "migration": updated}
    return {"promoted": False, "result": result}


def bind_insight_references(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir); chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    additions: dict[int, list[str]] = {}
    for item in payload.get("insights") or []:
        if not isinstance(item, dict): continue
        insight_id = str(item.get("insight_id") or "").strip()
        if not insight_id: continue
        for chapter in item.get("chapters") or []:
            if not isinstance(chapter, int): continue
            path = chapter_dir / f"_ch{chapter:02d}.md"
            if not path.is_file(): continue
            text = path.read_text(encoding="utf-8")
            if insight_id in _ANCHOR.findall(text): continue
            additions.setdefault(chapter, []).append(f"- 洞见引用：[insight: {insight_id}]")
    changed: list[int] = []
    for chapter, rows in additions.items():
        path = chapter_dir / f"_ch{chapter:02d}.md"; text = path.read_text(encoding="utf-8")
        block = "\n\n### Canonical insight bindings\n\n" + "\n".join(rows) + "\n"
        path.write_text(text.rstrip() + block, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": sorted(changed), "anchors_inserted": sum(map(len, additions.values()))}


def promote_reviewable_insight(output_dir: str | Path, *, report_text: str) -> dict[str, Any]:
    output = Path(output_dir); payload = _load(output / "insight_ledger.json")
    if not payload: return {"promoted": False, "error": "insight_ledger_missing"}
    policy = _load(output / "insight_policy.json")
    validation = validate_insight_ledger(
        payload, output_dir=output, report_text=report_text, enforced=bool(policy.get("enforced"))
    )
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "validation": validation}
    promoted = deepcopy(payload); promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = insight_fingerprint(promoted)
    result = persist_insight_ledger(output, promoted, report_text=report_text, allow_frozen_update=True)
    result["promoted"] = bool(result.get("written")); return result


def initialize_insight_policy(
    output_dir: str | Path, *, run_id: str, enforced: bool,
    analysis_purpose: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir)
    payload = {
        "schema_version": POLICY_VERSION, "run_id": str(run_id),
        "enforced": bool(enforced),
        "analysis_purpose": _analysis_purpose({"analysis_purpose": analysis_purpose}, output),
        "created_at": _now(),
    }
    path = output / "insight_policy.json"; path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_insight_ledger(
    output_dir: str | Path,
    archetype: str,
    decisive_question: str,
    question_basis: dict[str, Any],
    insights: list[dict[str, Any]],
    reverse_expectations: dict[str, Any],
    value_realization: dict[str, Any],
    adversarial_review: dict[str, Any],
    memo: dict[str, Any],
    *, change_reason: str, freeze: bool = True,
    analysis_purpose: str | None = None,
) -> dict[str, Any]:
    output = Path(output_dir); contract = _load(output / "analysis_contract.json")
    purpose = str(analysis_purpose or contract.get("analysis_purpose") or "INVESTMENT_DECISION")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(contract.get("ts_code") or contract.get("code") or output.name),
        "revision": 1, "lifecycle": "decision_ready" if freeze else "reviewable",
        "analysis_purpose": purpose,
        "archetype": str(archetype), "decisive_question": str(decisive_question).strip(),
        "question_basis": deepcopy(question_basis), "insights": deepcopy(insights),
        "adversarial_review": deepcopy(adversarial_review), "memo": deepcopy(memo),
        "change_reason": str(change_reason or "").strip(), "generated_at": _now(),
    }
    if purpose == "INVESTMENT_DECISION":
        payload["reverse_expectations"] = deepcopy(reverse_expectations)
        payload["value_realization"] = deepcopy(value_realization)
    payload["freeze"] = {"frozen": bool(freeze), "fingerprint": insight_fingerprint(payload) if freeze else "", "frozen_at": _now() if freeze else None}
    return payload


def _ids(items: Any, key: str) -> set[str]:
    return {str(item.get(key)) for item in (items or []) if isinstance(item, dict) and item.get(key)}


def _text(value: Any) -> str:
    if isinstance(value, dict): return " ".join(_text(item) for item in value.values())
    if isinstance(value, list): return " ".join(_text(item) for item in value)
    return str(value or "")


def _inline(value: Any) -> str:
    """Render ledger prose without introducing punctuation collisions."""
    text = re.sub(r"\s+", " ", _text(value)).strip()
    text = re.sub(r"[。；;，,]+$", "", text)
    return re.sub(r"。{2,}", "。", text)


def _normalised_content(value: Any) -> str:
    return re.sub(r"\s+|[，。；：、,.!?！？（）()\[\]【】`*_>#|\-]", "", _text(value)).lower()


def _memo_private_identities(value: Any, *, key: str = "") -> set[str]:
    identity_keys = {
        "insight_id", "claim_id", "evidence_id", "decision_entry_id",
        "model_id", "entry_id",
    }
    identity_list_keys = {
        "insight_ids", "claim_ids", "evidence_ids", "decision_entry_ids",
        "valuation_model_ids", "model_ids", "entry_ids", "forward_judgment_ids",
    }
    result: set[str] = set()
    if isinstance(value, dict):
        for child_key, child in value.items():
            child_key = str(child_key)
            if child_key in identity_keys and isinstance(child, str) and child.strip():
                result.add(child.strip())
            elif child_key in identity_list_keys and isinstance(child, list):
                result.update(str(item).strip() for item in child if str(item).strip())
            result.update(_memo_private_identities(child, key=child_key))
    elif isinstance(value, list):
        for child in value:
            result.update(_memo_private_identities(child, key=key))
    return result


def _reader_safe_memo_text(value: Any, payload: dict[str, Any]) -> str:
    """Remove exact control identities from a copied economic sentence."""
    text = value if isinstance(value, str) else _text(value)
    for identity in sorted(_memo_private_identities(payload), key=len, reverse=True):
        text = text.replace(identity, "")
    text = re.sub(
        r"\[(?:insight|decision|valuation|claim|threshold|thesis-test|probability)\s*:[^\]]+\]",
        "",
        text,
        flags=re.I,
    )
    text = re.sub(r"\s+([，。；：,.!?！？])", r"\1", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return text.strip()


def validate_rendered_memo(
    payload: dict[str, Any],
    memo_text: str,
    technical_filename: str,
    reader_filename: str = "",
) -> dict[str, Any]:
    """Prove that formatting a compact memo did not discard decision content.

    The compact layer may rearrange prose, but every decision-bearing ledger field,
    economic judgment and monitoring item must remain visible. Machine IDs and
    binding lists are intentionally excluded; the technical report retains them.
    """
    analysis_purpose = _analysis_purpose(payload)
    required: list[tuple[str, Any]] = [
        ("decisive_question", payload.get("decisive_question")),
    ]
    for idx, insight in enumerate(payload.get("insights") or []):
        keys = (
            "title", "anomaly", "mechanism", "strongest_alternative",
            "discriminating_observation", "falsification",
        )
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
            keys += (
                "operating_impact", "monitoring_or_forward_judgment",
            )
        else:
            keys += ("valuation_impact", "action_impact")
        for key in keys:
            required.append((f"insights[{idx}].{key}", insight.get(key)))
    sections = {
        "adversarial_review": (
            "strongest_case_against", "why_it_may_be_right", "unresolved",
            "judgment_if_true" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "decision_if_true",
        ),
        "memo": (
            "executive_judgment" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "executive_decision",
            "monitoring",
        ),
    }
    if analysis_purpose != "COMPANY_JUDGMENT_ONLY":
        sections.update({
            "reverse_expectations": (
                "as_of", "current_price", "method", "implied_operating_path",
                "assumptions", "conclusion", "flip_condition",
            ),
            "value_realization": (
                "latent_value", "controller", "access_mechanism", "no_catalyst_value",
                "failure_mode",
            ),
        })
        sections["memo"] += ("valuation_action",)
    for section, keys in sections.items():
        value = payload.get(section) or {}
        for key in keys:
            required.append((f"{section}.{key}", value.get(key)))

    haystack = _normalised_content(memo_text)
    missing: list[str] = []
    checked = 0
    for path, value in required:
        parts = value if isinstance(value, list) else [value]
        for idx, part in enumerate(parts):
            needle = _normalised_content(_reader_safe_memo_text(part, payload))
            if not needle:
                continue
            checked += 1
            if needle not in haystack:
                missing.append(f"{path}[{idx}]" if isinstance(value, list) else path)
    checked += 1
    if f"]({technical_filename})" not in memo_text:
        missing.append("technical_report_link")
    if reader_filename:
        checked += 1
        if f"]({reader_filename})" not in memo_text:
            missing.append("reader_report_link")
    try:
        from scripts.reader_coverage import reader_boundary_findings
    except ModuleNotFoundError:
        from reader_coverage import reader_boundary_findings
    leaks = list(reader_boundary_findings(memo_text))
    leaks.extend(
        "memo_private_identity:" + identity
        for identity in sorted(_memo_private_identities(payload))
        if identity and identity in memo_text
    )
    leaks = list(dict.fromkeys(leaks))
    missing = list(dict.fromkeys(missing))
    return {
        "schema_version": "memo-preservation.v1",
        "status": "FAIL" if missing or leaks else "PASS",
        "checked_content_units": checked,
        "preserved_content_units": checked - len(missing),
        "missing_fields": missing,
        "control_plane_leaks": leaks,
        "memo_chars": len(memo_text),
    }


def validate_insight_ledger(payload: dict[str, Any], *, output_dir: str | Path | None = None, report_text: str = "", enforced: bool = False) -> dict[str, Any]:
    invalid: list[str] = []; incomplete: list[str] = []; warnings: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION: invalid.append("schema_version_invalid")
    analysis_purpose = _analysis_purpose(payload, output_dir)
    if analysis_purpose not in ANALYSIS_PURPOSES: invalid.append("analysis_purpose_invalid")
    if not str(payload.get("report_id") or "").strip(): invalid.append("report_id_missing")
    if payload.get("archetype") not in ARCHETYPES: invalid.append("archetype_invalid")
    question = str(payload.get("decisive_question") or "").strip()
    if len(question) < 15 or not question.endswith(("?", "？")): incomplete.append("decisive_question_not_decisive")
    if not str(payload.get("change_reason") or "").strip(): incomplete.append("change_reason_missing")
    output = Path(output_dir) if output_dir is not None else None
    claims = _load(output / "claim_evidence.json") if output is not None else {}
    decisions = _load(output / "decision_ledger.json") if output is not None else {}
    valuations = _load(output / "valuation_model.json") if output is not None else {}
    thesis = _load(output / "thesis_test.json") if output is not None else {}
    contract = _load(output / "analysis_contract.json") if output is not None else {}
    policy = _load(output / "insight_policy.json") if output is not None else {}
    contract_purpose = str(contract.get("analysis_purpose") or "").strip()
    if contract_purpose in ANALYSIS_PURPOSES and analysis_purpose != contract_purpose:
        invalid.append("analysis_purpose_contract_mismatch")
    policy_purpose = str(policy.get("analysis_purpose") or "").strip()
    if policy_purpose in ANALYSIS_PURPOSES and analysis_purpose != policy_purpose:
        invalid.append("analysis_purpose_policy_mismatch")
    claim_purpose = str(claims.get("analysis_purpose") or "").strip()
    if claim_purpose in ANALYSIS_PURPOSES and analysis_purpose != claim_purpose:
        invalid.append("analysis_purpose_claim_evidence_mismatch")
    claim_ids = _ids(claims.get("claims"), "claim_id")
    evidence_ids = {str(raw.get("evidence_id")) for claim in claims.get("claims") or [] if isinstance(claim, dict) for raw in claim.get("raw_facts") or [] if isinstance(raw, dict) and raw.get("evidence_id")}
    decision_ids = _ids([item for item in decisions.get("entries") or [] if isinstance(item, dict) and item.get("status", "active") == "active"], "entry_id")
    model_ids = _ids(valuations.get("models"), "model_id")
    forward_judgment_ids = _ids(thesis.get("forward_judgments"), "judgment_id")

    basis = payload.get("question_basis")
    if not isinstance(basis, dict): invalid.append("question_basis_not_object"); basis = {}
    basis_reason = "why_it_changes_the_judgment" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "why_it_changes_the_decision"
    for key in ("anomaly", basis_reason):
        if not str(basis.get(key) or "").strip(): incomplete.append(f"question_basis:{key}_missing")
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and "why_it_changes_the_decision" in basis:
        invalid.append("question_basis:company_judgment_cannot_carry_decision_reason")
    for eid in basis.get("evidence_ids") or []:
        if output is not None and str(eid) not in evidence_ids: invalid.append(f"question_basis:unknown_evidence:{eid}")
    decisive_policy = _load(output / "decisive_question_policy.json") if output is not None else {}
    decisive_plan = _load(output / "decisive_question_plan.json") if output is not None else {}
    selected_questions = {
        str(item.get("question_id")): str(item.get("question") or "").strip()
        for item in decisive_plan.get("selected_questions") or []
        if isinstance(item, dict) and item.get("question_id")
    }
    question_id = str(basis.get("question_id") or "").strip()
    if decisive_policy.get("enforced"):
        if not question_id:
            incomplete.append("question_basis:question_id_missing")
        elif question_id not in selected_questions:
            invalid.append("question_basis:question_not_selected:" + question_id)
        elif question != selected_questions[question_id]:
            invalid.append("decisive_question_drift:" + question_id)

    insights = payload.get("insights")
    if not isinstance(insights, list): invalid.append("insights_not_array"); insights = []
    if enforced and not 1 <= len(insights) <= 3: incomplete.append("insight_count_must_be_1_to_3")
    insight_ids = _ids(insights, "insight_id")
    if len(insight_ids) != len(insights): invalid.append("insight_id_missing_or_duplicate")
    for idx, insight in enumerate(insights):
        if not isinstance(insight, dict): invalid.append(f"insights[{idx}]:not_object"); continue
        iid = str(insight.get("insight_id") or f"insights[{idx}]")
        required_fields = ("title", "anomaly", "mechanism", "strongest_alternative", "discriminating_observation", "falsification")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
            required_fields += ("operating_impact", "monitoring_or_forward_judgment")
        else:
            required_fields += ("valuation_impact", "action_impact")
        for key in required_fields:
            value = insight.get(key)
            if not _text(value).strip(): incomplete.append(f"{iid}:{key}_missing")
        mechanism = insight.get("mechanism")
        if not isinstance(mechanism, list) or len([x for x in mechanism if str(x).strip()]) < 2: incomplete.append(f"{iid}:mechanism_chain_too_short")
        cid = str(insight.get("claim_id") or "")
        if output is not None and cid not in claim_ids: invalid.append(f"{iid}:unknown_claim:{cid}")
        refs = insight.get("evidence_ids") or []
        if not refs: incomplete.append(f"{iid}:evidence_ids_missing")
        for eid in refs:
            if output is not None and str(eid) not in evidence_ids: invalid.append(f"{iid}:unknown_evidence:{eid}")
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
            for forbidden in ("valuation_impact", "action_impact", "decision_entry_ids"):
                if forbidden in insight:
                    invalid.append(f"{iid}:company_judgment_cannot_carry_{forbidden}")
            frefs = insight.get("forward_judgment_ids")
            if not isinstance(frefs, list):
                invalid.append(f"{iid}:forward_judgment_ids_invalid")
                frefs = []
            elif not frefs:
                incomplete.append(f"{iid}:forward_judgment_ids_missing")
            for fjid in frefs:
                if output is not None and str(fjid) not in forward_judgment_ids:
                    invalid.append(f"{iid}:unknown_forward_judgment:{fjid}")
        else:
            drefs = insight.get("decision_entry_ids") or []
            if not drefs: incomplete.append(f"{iid}:decision_entry_ids_missing")
            for did in drefs:
                if output is not None and str(did) not in decision_ids: invalid.append(f"{iid}:unknown_decision_entry:{did}")
        terms = [str(x).strip() for x in insight.get("company_specific_terms") or [] if str(x).strip()]
        combined = _text(insight)
        if len(terms) < 2 or sum(term in combined for term in terms) < 2: incomplete.append(f"{iid}:company_specificity_missing")
        chapters = insight.get("chapters") or []
        if not chapters or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters): invalid.append(f"{iid}:chapters_invalid")
        elif enforced and not any(iid in _ANCHOR.findall(report_text) for _ in chapters):
            incomplete.append(f"{iid}:report_anchor_missing")

    reverse = payload.get("reverse_expectations") if analysis_purpose != "COMPANY_JUDGMENT_ONLY" else {}
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        for forbidden in ("reverse_expectations", "value_realization"):
            if forbidden in payload:
                invalid.append(f"company_judgment_cannot_carry_{forbidden}")
    else:
        if not isinstance(reverse, dict): invalid.append("reverse_expectations_not_object"); reverse = {}
        for key in ("as_of", "current_price", "method", "implied_operating_path", "assumptions", "conclusion", "flip_condition"):
            if not _text(reverse.get(key)).strip(): incomplete.append(f"reverse_expectations:{key}_missing")
        if str(reverse.get("method") or "").strip().lower() in {"pe", "pb", "low_pe", "low_pb"}: invalid.append("reverse_expectations:multiple_not_reverse_model")
        for mid in reverse.get("valuation_model_ids") or []:
            if output is not None and str(mid) not in model_ids: invalid.append(f"reverse_expectations:unknown_valuation_model:{mid}")
        if not reverse.get("valuation_model_ids"): incomplete.append("reverse_expectations:valuation_model_ids_missing")

        realization = payload.get("value_realization")
        if not isinstance(realization, dict): invalid.append("value_realization_not_object"); realization = {}
        for key in ("latent_value", "controller", "access_mechanism", "no_catalyst_value", "failure_mode"):
            if not _text(realization.get(key)).strip(): incomplete.append(f"value_realization:{key}_missing")
        if "catalyst_required" not in realization or not isinstance(realization.get("catalyst_required"), bool):
            invalid.append("value_realization:catalyst_required_invalid")
        for did in realization.get("decision_entry_ids") or []:
            if output is not None and str(did) not in decision_ids: invalid.append(f"value_realization:unknown_decision_entry:{did}")

    adversarial = payload.get("adversarial_review")
    if not isinstance(adversarial, dict): invalid.append("adversarial_review_not_object"); adversarial = {}
    adverse_consequence = "judgment_if_true" if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "decision_if_true"
    for key in ("strongest_case_against", "why_it_may_be_right", "unresolved", adverse_consequence):
        if not _text(adversarial.get(key)).strip(): incomplete.append(f"adversarial_review:{key}_missing")
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY" and "decision_if_true" in adversarial:
        invalid.append("adversarial_review:company_judgment_cannot_carry_decision_if_true")
    for eid in adversarial.get("evidence_ids") or []:
        if output is not None and str(eid) not in evidence_ids: invalid.append(f"adversarial_review:unknown_evidence:{eid}")

    memo = payload.get("memo")
    if not isinstance(memo, dict): invalid.append("memo_not_object"); memo = {}
    memo_required = ("executive_judgment", "monitoring") if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else ("executive_decision", "valuation_action", "monitoring")
    for key in memo_required:
        if not _text(memo.get(key)).strip(): incomplete.append(f"memo:{key}_missing")
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        for forbidden in ("executive_decision", "valuation_action", "price_rule_exception_basis"):
            if forbidden in memo:
                invalid.append(f"memo:company_judgment_cannot_carry_{forbidden}")
    all_text = _text(payload)
    if _PRICE_STOP.search(all_text) and not str(memo.get("price_rule_exception_basis") or "").strip(): invalid.append("price_only_stop_rule")
    if _FULLY_PRICED.search(all_text) and (not _text(reverse.get("implied_operating_path")).strip() or not _text(reverse.get("assumptions")).strip()): invalid.append("priced_risk_without_reverse_expectations")
    rendered_memo = render_investment_memo(payload, "公司", "CODE", "technical.md")
    if len(rendered_memo) > 32000: invalid.append("investment_memo_over_32000_chars")
    preservation = validate_rendered_memo(payload, rendered_memo, "technical.md")
    invalid.extend(f"memo_content_lost:{item}" for item in preservation["missing_fields"])
    invalid.extend(
        f"memo_control_plane_leak:{item}"
        for item in preservation.get("control_plane_leaks") or []
    )
    known_refs = set(_ANCHOR.findall(report_text))
    for ref in sorted(known_refs - insight_ids): invalid.append(f"unknown_insight_reference:{ref}")
    freeze = payload.get("freeze") or {}
    if freeze.get("frozen") and freeze.get("fingerprint") != insight_fingerprint(payload): invalid.append("freeze_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid)); incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "MONITORING" if payload.get("lifecycle") == "monitoring" else "DECISION_READY" if freeze.get("frozen") else "REVIEWABLE"
    return {"schema_version": "insight-validation.v1", "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS", "invalid_findings": invalid, "incomplete_findings": incomplete, "warnings": warnings, "insight_count": len(insights), "analysis_purpose": analysis_purpose}


def evaluate_output_insight(output_dir: str | Path, *, report_text: str = "", persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir); policy = _load(output / "insight_policy.json")
    if not policy.get("enforced") and not (output / "insight_ledger.json").exists():
        return {"schema_version": "insight-validation.v1", "state": "SKIP", "status": "SKIP", "invalid_findings": [], "incomplete_findings": [], "warnings": []}
    if policy.get("enforced") and not (output / "insight_ledger.json").exists():
        result = {"schema_version": "insight-validation.v1", "state": "INCOMPLETE", "status": "FAIL", "invalid_findings": [], "incomplete_findings": ["insight_ledger_missing"], "warnings": []}
        if persist: (output / "insight_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        return result
    payload = _load(output / "insight_ledger.json")
    result = validate_insight_ledger(payload, output_dir=output, report_text=report_text, enforced=bool(policy.get("enforced")))
    if (
        persist
        and result.get("invalid_findings") == []
        and result.get("incomplete_findings") == ["question_basis:question_id_missing"]
    ):
        migration = build_insight_question_identity_migration(output, persist=True)
        if migration.get("status") == "READY_TO_PROMOTE":
            promotion = promote_insight_question_identity_migration(output)
            if promotion.get("promoted"):
                payload = _load(output / "insight_ledger.json")
                result = validate_insight_ledger(
                    payload, output_dir=output, report_text=report_text,
                    enforced=bool(policy.get("enforced")),
                )
    if persist: (output / "insight_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def persist_insight_ledger(output_dir: str | Path, payload: dict[str, Any], *, report_text: str = "", allow_frozen_update: bool = False) -> dict[str, Any]:
    output = Path(output_dir); path = output / "insight_ledger.json"; existing = _load(path)
    policy = _load(output / "insight_policy.json")
    validation = validate_insight_ledger(
        payload, output_dir=output, report_text=report_text,
        enforced=bool(policy.get("enforced")),
    )
    if validation["state"] == "INVALID" or (
        validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen"))
    ):
        (output / "insight_last_rejected_validation.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {
            "written": False, "path": str(path), "validation": validation,
            "error": "invalid or incomplete insight ledger cannot be frozen",
        }
    if existing.get("freeze", {}).get("frozen") and not allow_frozen_update and insight_fingerprint(existing) != insight_fingerprint(payload):
        return {"written": False, "error": "frozen_insight_ledger_rejected_update", "state": "INVALID"}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "insight_validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path), **validation}


def render_investment_memo(
    payload: dict[str, Any], company_name: str, ts_code: str,
    technical_filename: str, reader_filename: str = "",
) -> str:
    if _analysis_purpose(payload) == "COMPANY_JUDGMENT_ONLY":
        return render_company_judgment_memo(
            payload, company_name, ts_code, technical_filename, reader_filename,
        )
    insights = payload.get("insights") or []
    reverse = payload.get("reverse_expectations") or {}
    realization = payload.get("value_realization") or {}
    adversarial = payload.get("adversarial_review") or {}
    memo = payload.get("memo") or {}
    lines = [
        f"# {company_name} ({ts_code}) 投资备忘录", "",
        "> 执行摘要；完整公司叙事见正式报告，模型推导与证据索引见技术附录。", "",
        "## 结论", "", _inline(memo.get("executive_decision")) + "。", "",
        "### 估值与动作", "", _inline(memo.get("valuation_action")) + "。", "",
        "## 首要决定性问题", "", _inline(payload.get("decisive_question")), "",
        "## 关键洞见", "",
    ]
    for item in insights:
        lines += [
            f"### {_inline(item.get('title')) or '关键洞见'}", "",
            f"- **观察**：{_inline(item.get('anomaly'))}",
            "- **机制**：" + " → ".join(_inline(x) for x in item.get("mechanism") or []),
            f"- **竞争解释**：{_inline(item.get('strongest_alternative'))}",
            f"- **判别观察**：{_inline(item.get('discriminating_observation'))}",
            f"- **证伪条件**：{_inline(item.get('falsification'))}",
            f"- **估值影响**：{_inline(item.get('valuation_impact'))}",
            f"- **动作影响**：{_inline(item.get('action_impact'))}",
            "",
        ]
    lines += [
        "## 市场隐含预期", "",
        f"- **输入**：截至{_inline(reverse.get('as_of'))}，股价{_inline(reverse.get('current_price'))}",
        f"- **方法**：{_inline(reverse.get('method'))}",
        f"- **市场定价路径**：{_inline(reverse.get('implied_operating_path'))}",
        f"- **关键假设**：{'；'.join(_inline(x) for x in reverse.get('assumptions') or [])}",
        f"- **裁决**：{_inline(reverse.get('conclusion'))}",
        f"- **翻转条件**：{_inline(reverse.get('flip_condition'))}", "",
        "## 价值如何兑现", "",
        f"- **潜在价值**：{_inline(realization.get('latent_value'))}",
        f"- **控制人**：{_inline(realization.get('controller'))}",
        f"- **可达路径**：{_inline(realization.get('access_mechanism'))}",
        f"- **无催化剂价值**：{_inline(realization.get('no_catalyst_value'))}",
        f"- **失败方式**：{_inline(realization.get('failure_mode'))}",
        "",
        "## 最强反方", "",
        f"- **反方论点**：{_inline(adversarial.get('strongest_case_against'))}",
        f"- **为何可能成立**：{_inline(adversarial.get('why_it_may_be_right'))}",
        f"- **尚未解决**：{_inline(adversarial.get('unresolved'))}",
        f"- **若成立的动作**：{_inline(adversarial.get('decision_if_true'))}",
        "",
        "## 监控清单", "",
    ]
    lines += [f"- {_inline(item)}" for item in (memo.get("monitoring") if isinstance(memo.get("monitoring"), list) else [memo.get("monitoring")]) if _inline(item)]
    if reader_filename:
        lines += ["", "## 完整报告", "", f"[{reader_filename}]({reader_filename})", ""]
    lines += ["", "## 技术附录", "", f"[{technical_filename}]({technical_filename})", ""]
    return _reader_safe_memo_text("\n".join(lines), payload) + "\n"


def render_company_judgment_memo(
    payload: dict[str, Any], company_name: str, ts_code: str,
    technical_filename: str, reader_filename: str = "",
) -> str:
    """Render the company-learning layer without smuggling in an investment conclusion."""
    insights = payload.get("insights") or []
    adversarial = payload.get("adversarial_review") or {}
    memo = payload.get("memo") or {}
    lines = [
        f"# {company_name} ({ts_code}) 公司判断备忘录", "",
        "> 仅冻结事实、机制、经营传导和后续可结算判断；不包含价格、估值、回报、仓位或交易动作。", "",
        "## 当前公司判断", "", _inline(memo.get("executive_judgment")) + "。", "",
        "## 首要判断问题", "", _inline(payload.get("decisive_question")), "",
        "## 关键机制洞见", "",
    ]
    for item in insights:
        lines += [
            f"### {_inline(item.get('title')) or '关键机制洞见'}", "",
            f"- **观察**：{_inline(item.get('anomaly'))}",
            "- **机制**：" + " → ".join(_inline(x) for x in item.get("mechanism") or []),
            f"- **竞争解释**：{_inline(item.get('strongest_alternative'))}",
            f"- **判别观察**：{_inline(item.get('discriminating_observation'))}",
            f"- **经营传导**：{_inline(item.get('operating_impact'))}",
            f"- **监控 / 前瞻判断**：{_inline(item.get('monitoring_or_forward_judgment'))}",
            f"- **证伪条件**：{_inline(item.get('falsification'))}",
            "",
        ]
    lines += [
        "## 最强反方", "",
        f"- **反方论点**：{_inline(adversarial.get('strongest_case_against'))}",
        f"- **为何可能成立**：{_inline(adversarial.get('why_it_may_be_right'))}",
        f"- **尚未解决**：{_inline(adversarial.get('unresolved'))}",
        f"- **若成立的公司判断**：{_inline(adversarial.get('judgment_if_true'))}",
        "",
        "## 监控清单", "",
    ]
    monitoring = memo.get("monitoring")
    lines += [
        f"- {_inline(item)}"
        for item in (monitoring if isinstance(monitoring, list) else [monitoring])
        if _inline(item)
    ]
    if reader_filename:
        lines += ["", "## 完整报告", "", f"[{reader_filename}]({reader_filename})", ""]
    lines += ["", "## 技术附录", "", f"[{technical_filename}]({technical_filename})", ""]
    return _reader_safe_memo_text("\n".join(lines), payload) + "\n"
