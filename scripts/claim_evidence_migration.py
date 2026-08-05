#!/usr/bin/env python3
"""Conservatively migrate legacy claim rows onto VERIFIED observations.

The migration never overwrites ``claim_evidence.json``.  It atomizes compound
legacy evidence where exact numbers can be found in page-located official
observations, demotes unsupported direct rows to context, and emits a candidate
plus a machine-readable unresolved frontier for review or a bounded writer run.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.claim_evidence import (
        claim_ledger_fingerprint, persist_claim_evidence_ledger, validate_claim_evidence_ledger,
    )
except ModuleNotFoundError:
    from claim_evidence import (
        claim_ledger_fingerprint, persist_claim_evidence_ledger, validate_claim_evidence_ledger,
    )


SCHEMA_VERSION = "claim-evidence-migration.v1"
_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?")
_PAREN_NUMBER_RE = re.compile(r"\(((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\)")


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _report_text(output: Path) -> str:
    chapters = sorted((output / "chapters").glob("_ch*.md"))
    if chapters:
        return "\n\n".join(path.read_text(encoding="utf-8") for path in chapters)
    preferred = output / "reports" / "最新_分析报告_v13.md"
    return preferred.read_text(encoding="utf-8") if preferred.is_file() else ""


def _numbers(value: Any, *, accounting_parentheses: bool = False) -> list[float]:
    text = str(value or "")
    result: list[float] = []
    for token in _NUMBER_RE.findall(text):
        try:
            number = float(token.replace(",", ""))
        except ValueError:
            continue
        if number.is_integer() and 1900 <= number <= 2100:
            continue
        result.append(number)
    if accounting_parentheses:
        for token in _PAREN_NUMBER_RE.findall(text):
            number = float(token.replace(",", ""))
            result.append(-number)
    return result


def _close(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1e-6, abs_tol=1e-6)


def _observation_numbers(observation: dict[str, Any]) -> list[float]:
    values = _numbers(observation.get("raw_text"), accounting_parentheses=True)
    values += _numbers(observation.get("raw_value"), accounting_parentheses=True)
    values += _numbers(observation.get("normalized_value"), accounting_parentheses=True)
    return values


def _matching_observations(
    evidence: dict[str, Any], observations: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[float]]:
    asserted = _numbers(evidence.get("fact"))
    if not asserted:
        return [], []
    matches: list[dict[str, Any]] = []
    covered: list[float] = []
    seen_identity: set[tuple[Any, ...]] = set()
    for observation in observations:
        observed = _observation_numbers(observation)
        overlap = [value for value in asserted if any(_close(value, item) for item in observed)]
        if not overlap:
            continue
        identity = (
            observation.get("doc_id"), observation.get("as_of"),
            observation.get("fact_name"), observation.get("normalized_value"),
        )
        if identity in seen_identity:
            continue
        seen_identity.add(identity)
        matches.append(observation)
        covered.extend(overlap)
    unresolved = [
        value for value in asserted
        if not any(_close(value, item) for item in covered)
    ]
    return matches, unresolved


def _matching_calculations(
    evidence: dict[str, Any], calculations: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[float]]:
    asserted = _numbers(evidence.get("fact"))
    source = str(evidence.get("source_id") or "")
    eligible = sorted(
        (item for item in calculations if item.get("status") == "VERIFIED" and item.get("tool") == source),
        key=lambda item: (len(str(item.get("metric_path") or "")), str(item.get("metric_path") or "")),
    )
    matches: list[dict[str, Any]] = []
    unresolved: list[float] = []
    used_ids: set[str] = set()
    for value in asserted:
        match = next((
            item for item in eligible
            if item.get("calculation_id") not in used_ids and _close(value, float(item.get("value")))
        ), None)
        if match is None:
            if not any(_close(value, item) for item in unresolved):
                unresolved.append(value)
            continue
        used_ids.add(str(match.get("calculation_id")))
        matches.append(match)
    return matches, unresolved


def _eligible_observations(
    evidence: dict[str, Any], observations: list[dict[str, Any]],
    documents: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Limit numeric matching to documents/domains implied by provenance."""
    source = Path(str(evidence.get("source_id") or "")).name
    lowered = source.lower()
    if lowered.startswith("compute_") or lowered in {"get_peer_comparison", "tool_output"}:
        return []
    doc_ids = {
        doc_id for doc_id, document in documents.items()
        if source in {
            Path(str(document.get("local_path") or "")).name,
            Path(str(document.get("derived_text_path") or "")).name,
        }
    }
    if doc_ids:
        # A compound comparative fact may be supported by each year's own
        # filing; never expand beyond years explicitly named in that fact.
        named_years = set(re.findall(r"(?:FY)?(20\d{2})", str(evidence.get("fact") or "")))
        if named_years:
            doc_ids.update(
                doc_id for doc_id, document in documents.items()
                if str(document.get("period_end") or "")[:4] in named_years
                and document.get("doc_type") == "annual_report"
            )
        return [item for item in observations if item.get("doc_id") in doc_ids]
    domain = None
    if lowered == "governance.json":
        domain = "governance"
    elif lowered == "segments.json":
        domain = "operations"
    return [item for item in observations if item.get("domain") == domain] if domain else []


def _atomic_evidence(
    old: dict[str, Any], observation: dict[str, Any], *, index: int,
    documents: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    doc_id = str(observation.get("doc_id") or "")
    document = documents.get(doc_id, {})
    value = observation.get("normalized_value")
    unit = str(observation.get("unit") or "").strip()
    year = str(observation.get("as_of") or "")[:4]
    fact = (
        f"{observation.get('fact_name')}(FY{year}, "
        f"basis={observation.get('basis')})={value} {unit}".rstrip()
    )
    old_id = str(old.get("evidence_id") or "evidence")
    return {
        "evidence_id": f"{old_id}.obs{index}",
        "source_id": doc_id,
        "source_group_id": doc_id,
        "observation_id": observation.get("observation_id"),
        "fact": fact,
        "authority": "audited_filing",
        "claim_distance": "raw_data",
        "published_at": str(document.get("published_at") or observation.get("as_of") or ""),
        "data_as_of": str(observation.get("as_of") or ""),
        "direct_support": True,
        "support_type": "supports",
        "basis_match": "exact",
        "conflict_of_interest": "issuer disclosure; page-located in an official filing",
        "migrated_from_evidence_id": old_id,
    }


def _atomic_calculation_evidence(
    old: dict[str, Any], calculation: dict[str, Any], *, index: int,
    data_as_of: str, generated_at: str,
) -> dict[str, Any]:
    old_id = str(old.get("evidence_id") or "evidence")
    tool = str(calculation.get("tool") or "")
    return {
        "evidence_id": f"{old_id}.calc{index}",
        "source_id": tool,
        "source_group_id": f"derived:{tool}:{calculation.get('input_fingerprint')}",
        "calculation_id": calculation.get("calculation_id"),
        "fact": f"{calculation.get('metric_path')}={calculation.get('value')} {calculation.get('unit')}",
        "authority": "verified_calculation",
        "claim_distance": "direct_statement",
        "published_at": generated_at[:10],
        "data_as_of": data_as_of,
        "direct_support": True,
        "support_type": "supports",
        "basis_match": "exact",
        "conflict_of_interest": "deterministic framework calculation; inspect input fingerprint",
        "migrated_from_evidence_id": old_id,
    }


def migrate_claim_evidence(output_dir: str | Path, *, persist: bool = True) -> dict[str, Any]:
    output = Path(output_dir)
    original = _read_json(output / "claim_evidence.json")
    facts = _read_json(output / "fact_observations.json")
    manifest = _read_json(output / "document_manifest.json")
    policy = _read_json(output / "claim_evidence_policy.json")
    calculation_payload = _read_json(output / "calculation_observations.json")
    if not original:
        raise ValueError("claim_evidence.json is missing or invalid")
    verified = [
        item for item in facts.get("observations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    ]
    documents = {
        str(item.get("doc_id")): item for item in manifest.get("documents") or []
        if isinstance(item, dict) and item.get("doc_id")
    }
    calculations = [
        item for item in calculation_payload.get("calculations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    ]
    contract = _read_json(output / "analysis_contract.json")
    data_as_of = str(contract.get("period_end") or contract.get("analysis_end_date") or "")
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", data_as_of):
        data_as_of = max((str(item.get("as_of") or "") for item in verified), default="")
    candidate = deepcopy(original)
    candidate.pop("freeze", None)
    candidate["lifecycle"] = "reviewable"
    candidate["change_reason"] = (
        "Deterministic migration candidate: bind legacy direct evidence to exact "
        "VERIFIED observations; unsupported rows demoted to context"
    )
    candidate["generated_at"] = _now()
    migrations: list[dict[str, Any]] = []
    unresolved: list[dict[str, Any]] = []
    for claim in candidate.get("claims") or []:
        migrated_rows: list[dict[str, Any]] = []
        for evidence in claim.get("raw_facts") or []:
            if not isinstance(evidence, dict):
                continue
            is_direct = bool(evidence.get("direct_support")) and evidence.get("support_type") == "supports"
            if not is_direct or evidence.get("observation_id"):
                migrated_rows.append(evidence)
                continue
            eligible = _eligible_observations(evidence, verified, documents)
            matches, missing_numbers = _matching_observations(evidence, eligible)
            calculation_matches: list[dict[str, Any]] = []
            if str(evidence.get("source_id") or "") in {"compute_aa", "compute_gg"}:
                calculation_matches, missing_numbers = _matching_calculations(evidence, calculations)
            for index, observation in enumerate(matches, start=1):
                migrated_rows.append(_atomic_evidence(evidence, observation, index=index, documents=documents))
            for index, calculation in enumerate(calculation_matches, start=1):
                migrated_rows.append(_atomic_calculation_evidence(
                    evidence, calculation, index=index, data_as_of=data_as_of,
                    generated_at=str(calculation_payload.get("generated_at") or _now()),
                ))
            demoted = deepcopy(evidence)
            demoted["direct_support"] = False
            demoted["support_type"] = "context"
            demoted["migration_note"] = "not direct until every material input has a verified observation or computation identity"
            migrated_rows.append(demoted)
            row = {
                "claim_id": claim.get("claim_id"),
                "evidence_id": evidence.get("evidence_id"),
                "matched_observation_ids": [item.get("observation_id") for item in matches],
                "matched_calculation_ids": [item.get("calculation_id") for item in calculation_matches],
                "unresolved_numbers": missing_numbers,
                "status": "PARTIAL" if (matches or calculation_matches) and missing_numbers else ("MIGRATED" if (matches or calculation_matches) else "UNRESOLVED"),
            }
            migrations.append(row)
            if row["status"] != "MIGRATED":
                unresolved.append(row)
        claim["raw_facts"] = migrated_rows
    candidate["freeze"] = {"frozen": False, "fingerprint": "", "frozen_at": None}
    validation = validate_claim_evidence_ledger(
        candidate,
        report_text=_report_text(output),
        output_dir=output,
        enforced=bool(policy.get("enforced")),
        required_chapters=set(policy.get("required_chapters") or []),
    )
    report = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _now(),
        "source_ledger_fingerprint": claim_ledger_fingerprint(original),
        "candidate_fingerprint": claim_ledger_fingerprint(candidate),
        "canonical_ledger_unchanged": True,
        "verified_observation_count": len(verified),
        "migration_rows": migrations,
        "unresolved_frontier": unresolved,
        "candidate_validation": validation,
    }
    if persist:
        (output / "claim_evidence_migration_candidate.json").write_text(
            json.dumps(candidate, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "claim_evidence_migration_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return {"candidate": candidate, "report": report}


def _semantic_claims(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for claim in payload.get("claims") or []:
        item = deepcopy(claim)
        item.pop("raw_facts", None)
        result.append(item)
    return result


def promote_migration_candidate(output_dir: str | Path) -> dict[str, Any]:
    """Promote only an evidence-only, fully reviewable deterministic migration."""
    output = Path(output_dir)
    original = _read_json(output / "claim_evidence.json")
    candidate = _read_json(output / "claim_evidence_migration_candidate.json")
    report = _read_json(output / "claim_evidence_migration_report.json")
    if not original or not candidate or not report:
        return {"promoted": False, "error": "migration_artifacts_missing"}
    if report.get("source_ledger_fingerprint") != claim_ledger_fingerprint(original):
        return {"promoted": False, "error": "canonical_changed_since_migration"}
    validation = report.get("candidate_validation") or {}
    if validation.get("state") != "REVIEWABLE" or validation.get("invalid_findings") or validation.get("incomplete_findings"):
        return {"promoted": False, "error": "candidate_not_reviewable", "validation": validation}
    if _semantic_claims(original) != _semantic_claims(candidate):
        return {"promoted": False, "error": "semantic_claim_change_detected"}
    for claim in candidate.get("claims") or []:
        for evidence in claim.get("raw_facts") or []:
            if evidence.get("direct_support") and evidence.get("support_type") == "supports":
                identities = bool(evidence.get("observation_id")) + bool(evidence.get("calculation_id"))
                if identities != 1:
                    return {"promoted": False, "error": "direct_identity_invariant_failed"}
    promoted = deepcopy(candidate)
    promoted["lifecycle"] = "decision_ready"
    promoted["change_reason"] = (
        "Deterministic evidence-only migration: atomic VERIFIED official/calculation identities; "
        "claim semantics and decisions unchanged"
    )
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = claim_ledger_fingerprint(promoted)
    result = persist_claim_evidence_ledger(
        output, promoted, report_text=_report_text(output), allow_frozen_update=True
    )
    promoted_ok = bool(result.get("written")) and result.get("validation", {}).get("state") == "DECISION_READY"
    report["canonical_ledger_unchanged"] = not promoted_ok
    report["promotion"] = {
        "promoted": promoted_ok,
        "promoted_at": _now() if promoted_ok else None,
        "validation": result.get("validation"),
        "error": result.get("error"),
    }
    (output / "claim_evidence_migration_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return {"promoted": promoted_ok, **result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--no-persist", action="store_true")
    parser.add_argument("--promote-if-reviewable", action="store_true")
    args = parser.parse_args()
    result = migrate_claim_evidence(args.output_dir, persist=not args.no_persist)
    report = result["report"]
    print(json.dumps({
        "candidate_state": report["candidate_validation"]["state"],
        "migration_rows": len(report["migration_rows"]),
        "unresolved_rows": len(report["unresolved_frontier"]),
        "canonical_ledger_unchanged": report["canonical_ledger_unchanged"],
    }, ensure_ascii=False, indent=2))
    if args.promote_if_reviewable and not args.no_persist:
        promoted = promote_migration_candidate(args.output_dir)
        print(json.dumps({"promotion": promoted.get("promoted"), "error": promoted.get("error")}, ensure_ascii=False, indent=2))
        return 0 if promoted.get("promoted") else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
