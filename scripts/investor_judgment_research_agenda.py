#!/usr/bin/env python3
"""Project accepted learning evidence into a research-agenda-only handoff.

The projection lets later research reuse bounded questions and acquisition
lessons without treating them as company facts, validated methods, CJO inputs,
or investment conclusions.  Invalidated and unreviewed evidence stays outside
the candidate-rule set.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
from pathlib import Path
from typing import Any

try:
    from scripts.investor_judgment_learning_read_model import (
        DOWNSTREAM_RIGHTS,
        READ_MODEL_SCHEMA_VERSION,
        validate_learning_read_model,
    )
except ModuleNotFoundError:  # pragma: no cover - direct script import
    from investor_judgment_learning_read_model import (
        DOWNSTREAM_RIGHTS,
        READ_MODEL_SCHEMA_VERSION,
        validate_learning_read_model,
    )


AGENDA_SCHEMA_VERSION = "investor-judgment-research-agenda.v1"
POLICY_SCHEMA_VERSION = "investor-judgment-research-agenda-policy.v1"
ALLOWED_OUTPUTS = ["RESEARCH_AGENDA_ONLY"]
REUSABLE_METHOD_STATUSES = {"POSITIVE_DEVELOPMENT_UTILITY"}
LOCAL_LESSON_STATUSES = {"ACCEPTED_LOCAL_FINDING"}
NEGATIVE_METHOD_STATUSES = {"NO_ADVANTAGE_PROVED", "NO_MATERIAL_UTILITY"}
POLICY_DISPOSITIONS = {
    "CANDIDATE_RESEARCH_RULE",
    "COMPANY_CONTINUATION_ONLY",
    "INVALIDATION_REMEDIATION_ONLY",
}


class ResearchAgendaError(ValueError):
    """Raised when a learning read model is not safe for agenda projection."""


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _required_text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ResearchAgendaError(field + "_missing")
    return text


def _assert_closed_rights(read_model: dict[str, Any]) -> None:
    rights = _mapping(read_model.get("rights"))
    if set(rights) != set(DOWNSTREAM_RIGHTS):
        raise ResearchAgendaError("read_model_rights_incomplete")
    opened = [right for right, status in rights.items() if status != "NOT_AUTHORIZED"]
    if opened:
        raise ResearchAgendaError("read_model_right_open:" + ",".join(sorted(opened)))


def _company_context(entry: dict[str, Any]) -> dict[str, Any] | None:
    finding = _mapping(entry.get("company_finding"))
    status = str(finding.get("status") or "")
    if not status.startswith("ACCEPTED_"):
        return None
    company_ids = _items(entry.get("company_ids"))
    if len(company_ids) != 1 or entry.get("company_id") != company_ids[0]:
        return None
    return {
        "context_id": "CONTEXT:" + _required_text(entry.get("evidence_id"), "evidence_id"),
        "round_id": _required_text(entry.get("round_id"), "round_id"),
        "company_id": _required_text(entry.get("company_id"), "company_id"),
        "cutoff_at": _required_text(entry.get("cutoff_at"), "cutoff_at"),
        "statement": str(finding.get("statement") or ""),
        "use_permission": "HISTORICAL_COMPANY_CONTEXT_ONLY",
        "prohibited_use": (
            "Do not transfer this company finding to another issuer, infer general management quality, "
            "or use it as valuation, report or investment authority."
        ),
        "source_artifacts": deepcopy(_mapping(entry.get("source_artifacts"))),
    }


def _policy_entries(policy: dict[str, Any], evidence_inventory: list[Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(policy, dict):
        raise ResearchAgendaError("policy_not_object")
    if policy.get("schema_version") != POLICY_SCHEMA_VERSION:
        raise ResearchAgendaError("policy_schema_version_invalid")
    entries: dict[str, dict[str, Any]] = {}
    for raw_entry in _items(policy.get("entries")):
        entry = _mapping(raw_entry)
        round_id = _required_text(entry.get("round_id"), "policy_round_id")
        if round_id in entries:
            raise ResearchAgendaError("duplicate_policy_round_id:" + round_id)
        entries[round_id] = entry
    evidence_rounds = {_required_text(_mapping(item).get("round_id"), "round_id") for item in evidence_inventory}
    if set(entries) != evidence_rounds:
        raise ResearchAgendaError("policy_round_coverage_mismatch")

    for raw_entry in evidence_inventory:
        evidence = _mapping(raw_entry)
        round_id = _required_text(evidence.get("round_id"), "round_id")
        _required_text(entries[round_id].get("rationale"), "policy_rationale")
        expected = set(range(1, len(_items(evidence.get("next_evidence"))) + 1))
        seen: set[int] = set()
        disposition_values: set[str] = set()
        for raw_disposition in _items(entries[round_id].get("dispositions")):
            disposition = _mapping(raw_disposition)
            index = disposition.get("next_evidence_index")
            if not isinstance(index, int) or index < 1:
                raise ResearchAgendaError("policy_index_invalid:" + round_id)
            if index in seen:
                raise ResearchAgendaError("policy_index_duplicate:" + round_id + ":" + str(index))
            seen.add(index)
            if disposition.get("disposition") not in POLICY_DISPOSITIONS:
                raise ResearchAgendaError("policy_disposition_invalid:" + round_id + ":" + str(index))
            disposition_values.add(str(disposition.get("disposition")))
        if seen != expected:
            raise ResearchAgendaError("policy_index_coverage_mismatch:" + round_id)
        invalidated = isinstance(evidence.get("invalidated_evidence"), dict)
        if invalidated and disposition_values != {"INVALIDATION_REMEDIATION_ONLY"}:
            raise ResearchAgendaError("invalidated_policy_disposition_invalid:" + round_id)
        if not invalidated and "INVALIDATION_REMEDIATION_ONLY" in disposition_values:
            raise ResearchAgendaError("noninvalidated_policy_disposition_invalid:" + round_id)
    return entries


def _selected_next_evidence(
    entry: dict[str, Any],
    policy_entry: dict[str, Any],
    disposition: str,
) -> list[tuple[int, str]]:
    next_evidence = _items(entry.get("next_evidence"))
    selected: list[tuple[int, str]] = []
    for raw_item in _items(policy_entry.get("dispositions")):
        item = _mapping(raw_item)
        if item.get("disposition") != disposition:
            continue
        index = int(item["next_evidence_index"])
        statement = str(next_evidence[index - 1] or "").strip()
        if statement:
            selected.append((index, statement))
    return selected


def _candidate_rules(entry: dict[str, Any], policy_entry: dict[str, Any]) -> list[dict[str, Any]]:
    if not bool(entry.get("independent_review_present")):
        return []
    finding_status = str(_mapping(entry.get("company_finding")).get("status") or "")
    method_status = str(_mapping(entry.get("method_utility")).get("status") or "")
    if finding_status in LOCAL_LESSON_STATUSES:
        rule_status = "LOCAL_LESSON_REPLICATION_REQUIRED"
        evidence_class = "LOCAL_COMPANY_JUDGMENT_CHANGE"
    elif method_status in REUSABLE_METHOD_STATUSES:
        rule_status = "DEVELOPMENT_UTILITY_REPLICATION_REQUIRED"
        evidence_class = "POSITIVE_DEVELOPMENT_METHOD_UTILITY"
    elif method_status in NEGATIVE_METHOD_STATUSES:
        rule_status = (
            "NO_MATERIAL_UTILITY_REDESIGN_REQUIRED"
            if method_status == "NO_MATERIAL_UTILITY"
            else "NO_ADVANTAGE_REDESIGN_REQUIRED"
        )
        evidence_class = "VALID_NEGATIVE_METHOD_OR_MEASUREMENT_LESSON"
    else:
        return []

    round_id = _required_text(entry.get("round_id"), "round_id")
    evidence_id = _required_text(entry.get("evidence_id"), "evidence_id")
    rules = []
    for index, text in _selected_next_evidence(entry, policy_entry, "CANDIDATE_RESEARCH_RULE"):
        rules.append({
            "rule_candidate_id": f"RESEARCH-RULE:{round_id}:{index}",
            "source_evidence_id": evidence_id,
            "source_round_id": round_id,
            "evidence_class": evidence_class,
            "status": rule_status,
            "research_change": text,
            "allowed_use": "NEXT_EPISODE_QUESTION_OR_ACQUISITION_DESIGN_ONLY",
            "acceptance_needed": (
                "Apply before outcome access on a different eligible company-cutoff and settle under a declared "
                "same-definition contract with independent review."
            ),
            "prohibited_use": (
                "Not a company fact, validated method, probability, CJO amendment, valuation input, report conclusion, "
                "buy band or investment action."
            ),
        })
    return rules


def _company_continuations(entry: dict[str, Any], policy_entry: dict[str, Any]) -> list[dict[str, Any]]:
    if not bool(entry.get("independent_review_present")):
        return []
    round_id = _required_text(entry.get("round_id"), "round_id")
    evidence_id = _required_text(entry.get("evidence_id"), "evidence_id")
    return [{
        "continuation_id": f"COMPANY-CONTINUATION:{round_id}:{index}",
        "source_evidence_id": evidence_id,
        "source_round_id": round_id,
        "company_id": _required_text(entry.get("company_id"), "company_id"),
        "status": "COMPANY_CONTINUATION_ONLY",
        "research_change": statement,
        "allowed_use": "SAME_ISSUER_FUTURE_CUTOFF_RESEARCH_ONLY",
        "prohibited_use": "Do not transfer this issuer-specific follow-up into a cross-company method rule.",
    } for index, statement in _selected_next_evidence(
        entry, policy_entry, "COMPANY_CONTINUATION_ONLY"
    )]


def _method_caution(entry: dict[str, Any]) -> dict[str, Any] | None:
    method = _mapping(entry.get("method_utility"))
    status = str(method.get("status") or "")
    if status not in NEGATIVE_METHOD_STATUSES:
        return None
    return {
        "caution_id": "METHOD-CAUTION:" + _required_text(entry.get("evidence_id"), "evidence_id"),
        "source_round_id": _required_text(entry.get("round_id"), "round_id"),
        "status": status,
        "statement": str(method.get("statement") or ""),
        "research_effect": (
            "Do not credit the enhanced method with material utility. A new unseen episode needs separate frozen "
            "Baseline and Enhanced resolution rules plus a field that can actually distinguish their treatment."
        ),
    }


def _quarantined_evidence(
    entry: dict[str, Any],
    policy_entry: dict[str, Any],
) -> dict[str, Any] | None:
    invalidation = entry.get("invalidated_evidence")
    if not isinstance(invalidation, dict):
        return None
    return {
        "quarantine_id": "QUARANTINE:" + _required_text(entry.get("evidence_id"), "evidence_id"),
        "source_round_id": _required_text(entry.get("round_id"), "round_id"),
        "status": str(invalidation.get("status") or "INVALIDATED"),
        "root_causes": deepcopy(_items(invalidation.get("root_causes"))),
        "prohibited_claims": deepcopy(_items(invalidation.get("prohibited_claims"))),
        "remediation": str(invalidation.get("remediation") or ""),
        "remediation_actions": [statement for _, statement in _selected_next_evidence(
            entry, policy_entry, "INVALIDATION_REMEDIATION_ONLY"
        )],
        "allowed_use": "FAILURE_MODE_AND_NEW_EPOCH_DESIGN_ONLY",
        "reentry_condition": (
            "Only a different unseen company-cutoff under a pre-outcome frozen corrected epoch may create new method evidence."
        ),
    }


def build_research_agenda(
    read_model: dict[str, Any],
    policy: dict[str, Any],
    *,
    read_model_ref: str = "",
    policy_ref: str = "",
) -> dict[str, Any]:
    """Build a no-authority research agenda from a validated learning read model."""
    if not isinstance(read_model, dict):
        raise ResearchAgendaError("read_model_not_object")
    if read_model.get("schema_version") != READ_MODEL_SCHEMA_VERSION:
        raise ResearchAgendaError("read_model_schema_version_invalid")
    validation = validate_learning_read_model(read_model)
    if not validation["valid"]:
        raise ResearchAgendaError("read_model_invalid:" + ",".join(validation["findings"]))
    _assert_closed_rights(read_model)
    ceiling = _mapping(read_model.get("current_ceiling"))
    if ceiling.get("strict_validation_level") != "L1" or ceiling.get("next_unmet_level") != "L2":
        raise ResearchAgendaError("unsupported_learning_ceiling")
    if policy.get("as_of") != read_model.get("as_of"):
        raise ResearchAgendaError("policy_as_of_mismatch")

    evidence_inventory = _items(read_model.get("evidence_inventory"))
    policy_by_round = _policy_entries(policy, evidence_inventory)
    company_contexts: list[dict[str, Any]] = []
    candidate_rules: list[dict[str, Any]] = []
    company_continuations: list[dict[str, Any]] = []
    method_cautions: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    unreviewed: list[dict[str, Any]] = []

    for raw_entry in evidence_inventory:
        entry = _mapping(raw_entry)
        round_id = _required_text(entry.get("round_id"), "round_id")
        policy_entry = policy_by_round[round_id]
        context = _company_context(entry)
        if context is not None:
            company_contexts.append(context)
        candidate_rules.extend(_candidate_rules(entry, policy_entry))
        company_continuations.extend(_company_continuations(entry, policy_entry))
        caution = _method_caution(entry)
        if caution is not None:
            method_cautions.append(caution)
        quarantine = _quarantined_evidence(entry, policy_entry)
        if quarantine is not None:
            quarantined.append(quarantine)
        if not bool(entry.get("independent_review_present")):
            unreviewed.append({
                "round_id": _required_text(entry.get("round_id"), "round_id"),
                "evidence_id": _required_text(entry.get("evidence_id"), "evidence_id"),
                "status": "EXCLUDED_PENDING_INDEPENDENT_REVIEW",
            })

    candidate_ids = {item["source_evidence_id"] for item in candidate_rules}
    quarantined_ids = {
        item["quarantine_id"].removeprefix("QUARANTINE:") for item in quarantined
    }
    if candidate_ids & quarantined_ids:
        raise ResearchAgendaError("quarantined_evidence_reused_as_candidate_rule")

    return {
        "schema_version": AGENDA_SCHEMA_VERSION,
        "as_of": _required_text(read_model.get("as_of"), "as_of"),
        "read_model_ref": str(read_model_ref or ""),
        "policy_ref": str(policy_ref or ""),
        "readiness": {
            "state": "READY_FOR_L2_RESEARCH_DESIGN",
            "meaning": (
                "Existing receipts may guide the next mechanism-pair design, but none may supply a company conclusion "
                "or validated method claim for that episode."
            ),
        },
        "next_training_contract": {
            "target_level": "L2",
            "objective": str(_mapping(read_model.get("investor_readout")).get("next_decisive_step") or ""),
            "required_evidence": deepcopy(_items(ceiling.get("evidence_needed"))),
            "required_independence": (
                "Different eligible company-cutoff, pre-outcome frozen mechanism pair and resolver, official result source, "
                "and external post-outcome review."
            ),
            "prohibited_shortcuts": [
                "Do not use a candidate research rule as an issuer fact or selected mechanism.",
                "Do not repair a resolver after outcome access and credit the same episode.",
                "Do not remove UNKNOWN, MIXED, NOT_DIAGNOSTIC or MEASUREMENT_MISMATCH from the denominator.",
                "Do not use price, return, CJO, valuation or a final report to choose or settle the mechanism pair.",
            ],
        },
        "historical_company_context": company_contexts,
        "candidate_research_rules": candidate_rules,
        "company_continuation_agenda": company_continuations,
        "method_cautions": method_cautions,
        "quarantined_evidence": quarantined,
        "unreviewed_evidence": unreviewed,
        "preserved_denominator": deepcopy(_mapping(read_model.get("preserved_denominator"))),
        "rights": {right: "NOT_AUTHORIZED" for right in DOWNSTREAM_RIGHTS},
        "allowed_outputs": list(ALLOWED_OUTPUTS),
        "aggregation_policy": "NO_TOTAL_RANKING_NO_METHOD_WIN_RATE",
    }


def validate_research_agenda(agenda: dict[str, Any]) -> dict[str, Any]:
    findings: list[str] = []
    if not isinstance(agenda, dict):
        return {"valid": False, "findings": ["agenda_not_object"]}
    if agenda.get("schema_version") != AGENDA_SCHEMA_VERSION:
        findings.append("schema_version_invalid")
    if agenda.get("allowed_outputs") != ALLOWED_OUTPUTS:
        findings.append("allowed_outputs_invalid")
    if _mapping(agenda.get("readiness")).get("state") != "READY_FOR_L2_RESEARCH_DESIGN":
        findings.append("readiness_invalid")
    if _mapping(agenda.get("next_training_contract")).get("target_level") != "L2":
        findings.append("target_level_invalid")
    rights = _mapping(agenda.get("rights"))
    if set(rights) != set(DOWNSTREAM_RIGHTS) or set(rights.values()) != {"NOT_AUTHORIZED"}:
        findings.append("rights_invalid")
    allowed_rule_statuses = {
        "LOCAL_LESSON_REPLICATION_REQUIRED",
        "DEVELOPMENT_UTILITY_REPLICATION_REQUIRED",
        "NO_ADVANTAGE_REDESIGN_REQUIRED",
        "NO_MATERIAL_UTILITY_REDESIGN_REQUIRED",
    }
    for rule in _items(agenda.get("candidate_research_rules")):
        row = _mapping(rule)
        if row.get("status") not in allowed_rule_statuses:
            findings.append("candidate_rule_status_invalid:" + str(row.get("rule_candidate_id") or "UNKNOWN"))
    if any(_mapping(item).get("status") not in NEGATIVE_METHOD_STATUSES for item in _items(agenda.get("method_cautions"))):
        findings.append("method_caution_status_invalid")
    if any(not str(_mapping(item).get("status") or "").startswith("INVALIDATED")
           for item in _items(agenda.get("quarantined_evidence"))):
        findings.append("quarantine_status_invalid")
    return {"valid": not findings, "findings": findings}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--read-model", required=True, help="Learning read model JSON path.")
    parser.add_argument("--policy", required=True, help="Explicit agenda disposition policy JSON path.")
    parser.add_argument("--output", help="Output JSON path; stdout when omitted.")
    parser.add_argument("--check-only", action="store_true", help="Validate without writing output.")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    read_model_ref = str(Path(args.read_model))
    read_model_path = Path(args.read_model).resolve()
    policy_ref = str(Path(args.policy))
    policy_path = Path(args.policy).resolve()
    read_model = json.loads(read_model_path.read_text(encoding="utf-8"))
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    agenda = build_research_agenda(
        read_model,
        policy,
        read_model_ref=read_model_ref,
        policy_ref=policy_ref,
    )
    validation = validate_research_agenda(agenda)
    if not validation["valid"]:
        raise ResearchAgendaError("agenda_invalid:" + ",".join(validation["findings"]))
    if not args.check_only:
        payload = json.dumps(agenda, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            Path(args.output).write_text(payload, encoding="utf-8")
        else:
            print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
