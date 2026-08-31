#!/usr/bin/env python3
"""Compile accepted expert corrections into bounded training memory.

The existing enterprise-underwriting runtime owns the actual training Episode,
and the existing judgment-feedback control plane owns cutoff settlement.  This
module fills the smaller gap between them: it turns an accepted human/report
correction trace into portable questions and conditional principles that may be
supplied as ``TRAINING_MEMORY`` on a later, unseen company or cutoff.

The compiler deliberately drops company facts, prices and source evidence.
Those remain in the teacher package for provenance only and can never become
target-company evidence.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any


PACKAGE_SCHEMA = "expert-correction-teacher-package.v1"
VALIDATION_SCHEMA = "expert-correction-teacher-package-validation.v1"
MEMORY_SCHEMA = "expert-correction-training-memory.v1"

TEACHING_IDENTITIES = {
    "RESULT_KNOWN_EXPERT_CORRECTED",
    "RESULT_KNOWN_REVIEW_CORRECTED",
}
ROOT_CAUSES = {
    "DATA_COVERAGE",
    "ACQUISITION_MODULE",
    "REASONING",
    "MODEL",
    "WRITING",
}
DECISION_SURFACES = {
    "INDUSTRY_FUTURE",
    "CENTRAL_THESIS",
    "BUSINESS_ENGINE",
    "MANAGEMENT_AND_CAPITAL_ALLOCATION",
    "NORMAL_EARNINGS",
    "OWNER_CASH",
    "PERMANENT_LOSS",
    "VALUE_ROUTE",
    "PRICE_IDENTITY",
    "STRONGEST_RIVAL",
    "REVERSAL_EVIDENCE",
    "SOURCE_BINDING",
}
REQUIRED_ACCEPTANCE_SURFACES = {
    "CENTRAL_THESIS",
    "BUSINESS_ENGINE",
    "OWNER_CASH",
    "PERMANENT_LOSS",
    "VALUE_ROUTE",
    "PRICE_IDENTITY",
    "STRONGEST_RIVAL",
    "REVERSAL_EVIDENCE",
    "SOURCE_BINDING",
}
SOURCE_ROLES = {
    "TARGET_REPORT",
    "MATERIAL_REVIEW",
    "CORRECTION_HANDOFF",
    "PRINCIPLE_SOURCE",
}
SOURCE_STATES = {
    "ACCEPTED_TEACHING_PROVENANCE",
    "ACCEPT_WITH_DATA_LIMITED_TEACHING_PROVENANCE",
}
AUTHORITY = "TRAINING_MEMORY_ONLY_NOT_CURRENT_INVESTMENT_EVIDENCE"
CUTOFF_STATUS = "PREREGISTERED_NO_OUTCOME_VALUES"

_ROOT = Path(__file__).resolve().parents[1]
_CURRENCY_OR_PRICE = re.compile(
    r"(?:\b(?:HKD|RMB|USD|CNY|EUR|GBP)(?=\s|\d|[:])|[$¥€£]|\b\d+\.\d+\b|\b\d+(?:\.\d+)?%|\b\d+(?:\.\d+)?\s*(?:港元|元/股|每股))",
    re.I,
)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _items(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(value: Any, *, allow_empty: bool = False) -> bool:
    items = _items(value)
    return (
        (allow_empty or bool(items))
        and all(_text(item) for item in items)
        and len(set(items)) == len(items)
    )


def _instant(value: Any) -> datetime | None:
    if not _text(value):
        return None
    candidate = str(value).strip()
    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def _canonical_ref(value: Any) -> str:
    return str(value or "").split("#", 1)[0].strip()


def _source_ref_resolvable(value: Any) -> bool:
    reference = _canonical_ref(value)
    if not reference or "://" in reference:
        return False
    path = Path(reference).expanduser()
    if not path.is_absolute():
        path = _ROOT / path
    return path.is_file()


def _expected_fields(
    value: dict[str, Any], expected: set[str], path: str, findings: list[str]
) -> None:
    if set(value) != expected:
        findings.append(path + ".fields_invalid")


def _required_text(
    value: dict[str, Any], field: str, path: str, findings: list[str]
) -> None:
    if not _text(value.get(field)):
        findings.append(f"{path}.{field}_missing")


def _required_texts(
    value: dict[str, Any], field: str, path: str, findings: list[str]
) -> None:
    if not _texts(value.get(field)):
        findings.append(f"{path}.{field}_missing_or_invalid")


def _portable_text_findings(
    value: Any,
    *,
    path: str,
    company_id: str,
    company_name: str,
) -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            findings.extend(
                _portable_text_findings(
                    child,
                    path=f"{path}.{key}",
                    company_id=company_id,
                    company_name=company_name,
                )
            )
    elif isinstance(value, list):
        for index, child in enumerate(value):
            findings.extend(
                _portable_text_findings(
                    child,
                    path=f"{path}[{index}]",
                    company_id=company_id,
                    company_name=company_name,
                )
            )
    elif isinstance(value, str):
        if company_id and company_id.lower() in value.lower():
            findings.append(path + ".contains_teacher_company_id")
        company_tokens = {
            token.lower()
            for token in re.split(r"[^A-Za-z0-9]+", company_id)
            if len(token) >= 4
        }
        if any(token in value.lower() for token in company_tokens):
            findings.append(path + ".contains_teacher_company_id_token")
        if company_name and company_name.lower() in value.lower():
            findings.append(path + ".contains_teacher_company_name")
        if _CURRENCY_OR_PRICE.search(value):
            findings.append(path + ".contains_currency_or_price")
    return findings


def _validate_sources(value: Any, findings: list[str]) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    raw_sources = _items(value)
    if not raw_sources:
        findings.append("source_artifacts_missing")
        return sources
    for index, raw in enumerate(raw_sources):
        item = _mapping(raw)
        path = f"source_artifacts[{index}]"
        _expected_fields(
            item,
            {"artifact_id", "ref", "role", "review_state", "teaching_use"},
            path,
            findings,
        )
        for field in ("artifact_id", "ref", "teaching_use"):
            _required_text(item, field, path, findings)
        artifact_id = str(item.get("artifact_id") or "")
        if artifact_id in sources:
            findings.append(path + ".artifact_id_duplicate")
        elif artifact_id:
            sources[artifact_id] = item
        if item.get("role") not in SOURCE_ROLES:
            findings.append(path + ".role_invalid")
        if item.get("review_state") not in SOURCE_STATES:
            findings.append(path + ".review_state_invalid")
        if _text(item.get("ref")) and not _source_ref_resolvable(item.get("ref")):
            findings.append(path + ".ref_not_resolvable")
    return sources


def _validate_corrections(
    value: Any,
    *,
    sources: dict[str, dict[str, Any]],
    company_id: str,
    company_name: str,
    findings: list[str],
) -> dict[str, dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    raw_events = _items(value)
    if not raw_events:
        findings.append("correction_events_missing")
        return events
    for index, raw in enumerate(raw_events):
        item = _mapping(raw)
        path = f"correction_events[{index}]"
        _expected_fields(
            item,
            {
                "event_id",
                "accepted_source_artifact_ids",
                "before_error_pattern",
                "root_cause_classes",
                "economic_object",
                "responsibility_boundary",
                "error_mechanism",
                "economic_impact",
                "prohibited_assumptions",
                "correction",
                "transfer",
                "decision_surfaces",
            },
            path,
            findings,
        )
        for field in (
            "event_id",
            "before_error_pattern",
            "economic_object",
            "responsibility_boundary",
            "error_mechanism",
            "economic_impact",
        ):
            _required_text(item, field, path, findings)
        event_id = str(item.get("event_id") or "")
        if event_id in events:
            findings.append(path + ".event_id_duplicate")
        elif event_id:
            events[event_id] = item

        source_ids = _items(item.get("accepted_source_artifact_ids"))
        if not _texts(source_ids):
            findings.append(path + ".accepted_source_artifact_ids_invalid")
        else:
            missing = sorted(set(source_ids) - set(sources))
            if missing:
                findings.append(path + ".source_artifact_unknown:" + ",".join(missing))
            roles = {
                sources[source_id].get("role")
                for source_id in source_ids
                if source_id in sources
            }
            if not roles.intersection({"MATERIAL_REVIEW", "CORRECTION_HANDOFF"}):
                findings.append(path + ".accepted_review_or_handoff_required")

        causes = _items(item.get("root_cause_classes"))
        if not _texts(causes) or not set(causes).issubset(ROOT_CAUSES):
            findings.append(path + ".root_cause_classes_invalid")
        _required_texts(item, "prohibited_assumptions", path, findings)
        surfaces = _items(item.get("decision_surfaces"))
        if not _texts(surfaces) or not set(surfaces).issubset(DECISION_SURFACES):
            findings.append(path + ".decision_surfaces_invalid")

        correction = _mapping(item.get("correction"))
        _expected_fields(
            correction,
            {
                "best_current_judgment",
                "required_company_evidence",
                "investor_consequence",
                "uncertainty_treatment",
                "countercondition",
                "reversal_observation",
            },
            path + ".correction",
            findings,
        )
        for field in (
            "best_current_judgment",
            "investor_consequence",
            "uncertainty_treatment",
            "countercondition",
            "reversal_observation",
        ):
            _required_text(correction, field, path + ".correction", findings)
        _required_texts(
            correction, "required_company_evidence", path + ".correction", findings
        )

        transfer = _mapping(item.get("transfer"))
        _expected_fields(
            transfer,
            {
                "portable_rule",
                "applicable_when",
                "not_applicable_when",
                "next_case_probe",
            },
            path + ".transfer",
            findings,
        )
        for field in transfer:
            _required_text(transfer, field, path + ".transfer", findings)
        findings.extend(
            _portable_text_findings(
                {"event_id": event_id, "transfer": transfer},
                path=path + ".transfer",
                company_id=company_id,
                company_name=company_name,
            )
        )
    return events


def _validate_principles(
    value: Any,
    *,
    sources: dict[str, dict[str, Any]],
    events: dict[str, dict[str, Any]],
    company_id: str,
    company_name: str,
    findings: list[str],
) -> None:
    raw_principles = _items(value)
    if not raw_principles:
        findings.append("conditional_principles_missing")
        return
    seen: set[str] = set()
    for index, raw in enumerate(raw_principles):
        item = _mapping(raw)
        path = f"conditional_principles[{index}]"
        _expected_fields(
            item,
            {
                "principle_id",
                "title",
                "source_artifact_id",
                "principle_statement",
                "economic_object",
                "applicable_when",
                "mechanism",
                "target_company_evidence",
                "common_misuse",
                "counterconditions",
                "downstream_use",
                "disconfirming_observation",
                "derived_from_event_ids",
            },
            path,
            findings,
        )
        for field in (
            "principle_id",
            "title",
            "principle_statement",
            "economic_object",
            "applicable_when",
            "mechanism",
            "common_misuse",
            "downstream_use",
            "disconfirming_observation",
        ):
            _required_text(item, field, path, findings)
        principle_id = str(item.get("principle_id") or "")
        if principle_id in seen:
            findings.append(path + ".principle_id_duplicate")
        seen.add(principle_id)
        source_id = str(item.get("source_artifact_id") or "")
        if source_id not in sources:
            findings.append(path + ".source_artifact_unknown")
        elif sources[source_id].get("role") != "PRINCIPLE_SOURCE":
            findings.append(path + ".source_artifact_must_be_principle_source")
        for field in ("target_company_evidence", "counterconditions"):
            _required_texts(item, field, path, findings)
        event_ids = _items(item.get("derived_from_event_ids"))
        if not _texts(event_ids):
            findings.append(path + ".derived_from_event_ids_invalid")
        else:
            missing = sorted(set(event_ids) - set(events))
            if missing:
                findings.append(path + ".derived_event_unknown:" + ",".join(missing))
        findings.extend(
            _portable_text_findings(
                {
                    key: item.get(key)
                    for key in (
                        "principle_id",
                        "title",
                        "principle_statement",
                        "economic_object",
                        "applicable_when",
                        "mechanism",
                        "target_company_evidence",
                        "common_misuse",
                        "counterconditions",
                        "downstream_use",
                        "disconfirming_observation",
                    )
                },
                path=path,
                company_id=company_id,
                company_name=company_name,
            )
        )


def _validate_cutoff_design(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    path = "cutoff_feedback_design"
    _expected_fields(
        item,
        {
            "status",
            "target_identity_rule",
            "outcome_source_policy",
            "forbidden_outcome_proxies",
            "feedback_clocks",
            "settlement_route",
            "learning_route",
        },
        path,
        findings,
    )
    if item.get("status") != CUTOFF_STATUS:
        findings.append(path + ".status_invalid")
    for field in (
        "target_identity_rule",
        "outcome_source_policy",
        "settlement_route",
        "learning_route",
    ):
        _required_text(item, field, path, findings)
    _required_texts(item, "forbidden_outcome_proxies", path, findings)
    clocks = _items(item.get("feedback_clocks"))
    if not clocks:
        findings.append(path + ".feedback_clocks_missing")
    seen: set[str] = set()
    for index, raw in enumerate(clocks):
        clock = _mapping(raw)
        clock_path = f"{path}.feedback_clocks[{index}]"
        _expected_fields(
            clock,
            {
                "clock_id",
                "horizon",
                "episode_claims",
                "diagnostic_observation",
                "supports_rule",
                "refutes_rule",
                "mixed_rule",
            },
            clock_path,
            findings,
        )
        for field in (
            "clock_id",
            "horizon",
            "diagnostic_observation",
            "supports_rule",
            "refutes_rule",
            "mixed_rule",
        ):
            _required_text(clock, field, clock_path, findings)
        _required_texts(clock, "episode_claims", clock_path, findings)
        clock_id = str(clock.get("clock_id") or "")
        if clock_id in seen:
            findings.append(clock_path + ".clock_id_duplicate")
        seen.add(clock_id)


def _validate_acceptance(value: Any, findings: list[str]) -> None:
    item = _mapping(value)
    path = "transfer_acceptance"
    _expected_fields(
        item,
        {
            "baseline_policy",
            "enhanced_policy",
            "agent_isolation",
            "reviewer_blinding",
            "decisive_surfaces",
            "pass_rule",
            "failure_rule",
            "report_gate",
            "claim_limit",
        },
        path,
        findings,
    )
    for field in (
        "baseline_policy",
        "enhanced_policy",
        "agent_isolation",
        "reviewer_blinding",
        "pass_rule",
        "failure_rule",
        "report_gate",
        "claim_limit",
    ):
        _required_text(item, field, path, findings)
    surfaces = _items(item.get("decisive_surfaces"))
    if not _texts(surfaces) or not set(surfaces).issubset(DECISION_SURFACES):
        findings.append(path + ".decisive_surfaces_invalid")
    missing = sorted(REQUIRED_ACCEPTANCE_SURFACES - set(surfaces))
    if missing:
        findings.append(path + ".required_surfaces_missing:" + ",".join(missing))


def validate_teacher_package(package: Any) -> dict[str, Any]:
    """Validate a teacher package without granting method or investment authority."""

    findings: list[str] = []
    value = _mapping(package)
    if not value:
        return {
            "schema_version": VALIDATION_SCHEMA,
            "state": "INVALID",
            "findings": ["package_must_be_object"],
        }
    _expected_fields(
        value,
        {
            "schema_version",
            "package_id",
            "case_identity",
            "source_artifacts",
            "correction_events",
            "conditional_principles",
            "cutoff_feedback_design",
            "transfer_acceptance",
            "authority",
        },
        "package",
        findings,
    )
    if value.get("schema_version") != PACKAGE_SCHEMA:
        findings.append("schema_version_invalid")
    _required_text(value, "package_id", "package", findings)
    if value.get("authority") != AUTHORITY:
        findings.append("authority_invalid")

    identity = _mapping(value.get("case_identity"))
    _expected_fields(
        identity,
        {
            "company_id",
            "company_name",
            "case_cutoff_at",
            "teaching_identity",
            "outcome_access",
        },
        "case_identity",
        findings,
    )
    for field in ("company_id", "company_name", "case_cutoff_at"):
        _required_text(identity, field, "case_identity", findings)
    if _text(identity.get("case_cutoff_at")) and _instant(identity.get("case_cutoff_at")) is None:
        findings.append("case_identity.case_cutoff_at_invalid")
    if identity.get("teaching_identity") not in TEACHING_IDENTITIES:
        findings.append("case_identity.teaching_identity_invalid")
    if identity.get("outcome_access") != "RESULT_KNOWN":
        findings.append("case_identity.outcome_access_must_be_result_known")

    sources = _validate_sources(value.get("source_artifacts"), findings)
    events = _validate_corrections(
        value.get("correction_events"),
        sources=sources,
        company_id=str(identity.get("company_id") or ""),
        company_name=str(identity.get("company_name") or ""),
        findings=findings,
    )
    _validate_principles(
        value.get("conditional_principles"),
        sources=sources,
        events=events,
        company_id=str(identity.get("company_id") or ""),
        company_name=str(identity.get("company_name") or ""),
        findings=findings,
    )
    _validate_cutoff_design(value.get("cutoff_feedback_design"), findings)
    _validate_acceptance(value.get("transfer_acceptance"), findings)
    unique = list(dict.fromkeys(findings))
    return {
        "schema_version": VALIDATION_SCHEMA,
        "state": "TRAINING_READY" if not unique else "INVALID",
        "findings": unique,
        "authority": AUTHORITY,
    }


def compile_training_memory(package: Any) -> str:
    """Return deterministic, company-free Markdown for TRAINING_MEMORY use."""

    validation = validate_teacher_package(package)
    if validation["state"] != "TRAINING_READY":
        raise ValueError("teacher_package_invalid:" + ",".join(validation["findings"]))
    value = _mapping(package)
    lines = [
        "# Expert-correction training memory",
        "",
        f"> schema: `{MEMORY_SCHEMA}`",
        "> authority: `TRAINING_MEMORY_ONLY_NOT_TARGET_COMPANY_EVIDENCE`",
        "",
        "This memory changes question order, rival checks, conditional treatment and price/route identity only.",
        "It is not evidence about the target company, cannot be cited in the target Episode, and cannot supply a valuation, price or action.",
        "",
        "## Portable correction rules",
        "",
    ]
    for event in _items(value.get("correction_events")):
        item = _mapping(event)
        transfer = _mapping(item.get("transfer"))
        surfaces = ", ".join(str(surface) for surface in _items(item.get("decision_surfaces")))
        lines.extend(
            [
                f"### {item.get('event_id')}",
                "",
                f"- Rule: {transfer.get('portable_rule')}",
                f"- Apply when: {transfer.get('applicable_when')}",
                f"- Do not apply when: {transfer.get('not_applicable_when')}",
                f"- Next-case probe: {transfer.get('next_case_probe')}",
                f"- Decision surfaces: {surfaces}",
                "",
            ]
        )
    lines.extend(["## Conditional investment principles", ""])
    for principle in _items(value.get("conditional_principles")):
        item = _mapping(principle)
        evidence = "; ".join(str(entry) for entry in _items(item.get("target_company_evidence")))
        counterconditions = "; ".join(str(entry) for entry in _items(item.get("counterconditions")))
        lines.extend(
            [
                f"### {item.get('principle_id')} — {item.get('title')}",
                "",
                f"- Principle: {item.get('principle_statement')}",
                f"- Economic object: {item.get('economic_object')}",
                f"- Apply when: {item.get('applicable_when')}",
                f"- Mechanism: {item.get('mechanism')}",
                f"- Required target evidence: {evidence}",
                f"- Common misuse: {item.get('common_misuse')}",
                f"- Counterconditions: {counterconditions}",
                f"- Downstream use: {item.get('downstream_use')}",
                f"- Disconfirming observation: {item.get('disconfirming_observation')}",
                "",
            ]
        )
    lines.extend(
        [
            "## Use boundary",
            "",
            "On a later company, rebuild every fact and every economic link from that company's allowed cutoff sources.",
            "If a rule's applicability evidence is absent, narrow or reject the analogy. Do not reward additional prose, caveats or fields;",
            "the only useful change is a material improvement in the enterprise judgment or investment treatment.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("JSON root must be an object")
    return value


def _write_text(path: str | Path, content: str) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate one teacher package")
    validate.add_argument("package")

    compile_memory = subparsers.add_parser(
        "compile-memory", help="compile bounded Markdown for TRAINING_MEMORY"
    )
    compile_memory.add_argument("package")
    compile_memory.add_argument("--output", required=True)

    arguments = parser.parse_args(argv)
    package = _load_json(arguments.package)
    if arguments.command == "validate":
        result = validate_teacher_package(package)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result["state"] == "TRAINING_READY" else 1
    memory = compile_training_memory(package)
    _write_text(arguments.output, memory)
    print(arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
