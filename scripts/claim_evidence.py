#!/usr/bin/env python3
"""V3 major-claim evidence ledger and claim-to-source publication gate."""

from __future__ import annotations

import hashlib
import json
import math
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from scripts.evidence_citation import EvidenceRegistry
except ModuleNotFoundError:
    from evidence_citation import EvidenceRegistry


SCHEMA_VERSION = "claim-evidence-ledger.v1"
POLICY_VERSION = "claim-evidence-policy.v1"
REQUIRED_CLAIM_CHAPTERS = frozenset({0, 3, 4, 8, 9, 12, 13, 14})
AUTHORITIES = {
    "audited_filing": 1.0,
    "company_filing": 0.9,
    "official_statistics": 0.9,
    "industry_data": 0.75,
    "media": 0.5,
    "other": 0.3,
    "verified_calculation": 0.85,
}
DISTANCES = {
    "raw_data": 1.0,
    "direct_statement": 0.9,
    "secondary_summary": 0.65,
    "analysis": 0.4,
    "rumor": 0.1,
}
SUPPORT_TYPES = {"supports", "contradicts", "context"}
BASIS_MATCHES = {"exact", "compatible", "uncertain", "mismatch"}
CONFIDENCE_KINDS = {"frequency", "base_rate", "analyst_subjective", "scenario_weight"}
INTERNAL_SOURCES = {"report_internal", "report_derivation", "framework_method"}
SELF_REFERENTIAL_FILES = {
    "claim_evidence.json", "claim_evidence_validation.json", "claim_evidence_diff.json",
    "decision_ledger.json", "decision_ledger_validation.json", "completion_report.json",
    "absolute_quality_scorecard.json",
}
MIN_DIRECT_SUPPORT_QUALITY = 0.45
_CLAIM_REF_RE = re.compile(r"\[claim:\s*([A-Za-z0-9_.:@/-]+)\s*\]", re.IGNORECASE)
_CHAPTER_RE = re.compile(r"^##\s+Ch(\d+)\b", re.MULTILINE)
_DATE_RE = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")
_FACT_NUMBER_RE = re.compile(
    r"(?<![A-Za-z0-9_])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
)


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _observation_covers_fact_numbers(
    fact: str, observation: dict[str, Any]
) -> bool:
    """Require one direct evidence row to be numerically atomic.

    Every substantive number asserted by ``fact`` must occur in the verified
    quote/value. Years are metadata and are ignored. Compound facts therefore
    need one evidence row per observation instead of borrowing an unrelated
    VERIFIED identity from the same document.
    """
    def numbers(value: Any) -> list[float]:
        result: list[float] = []
        for token in _FACT_NUMBER_RE.findall(str(value or "")):
            try:
                number = float(token.replace(",", ""))
            except ValueError:
                continue
            if number.is_integer() and 1900 <= number <= 2100:
                continue
            result.append(number)
        return result

    asserted = numbers(fact)
    if not asserted:
        return True
    observed = numbers(observation.get("raw_text"))
    observed += numbers(observation.get("raw_value"))
    observed += numbers(observation.get("normalized_value"))
    # Filing tables conventionally express negative values in parentheses.
    for source in (observation.get("raw_text"), observation.get("raw_value")):
        for token in re.findall(r"\(((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)\)", str(source or "")):
            try:
                observed.append(-float(token.replace(",", "")))
            except ValueError:
                pass
    return bool(observed) and all(
        any(
            math.isclose(value, candidate, rel_tol=1e-6, abs_tol=1e-6)
            for candidate in observed
        )
        for value in asserted
    )


def _canonical_payload(payload: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(payload)
    value.pop("freeze", None)
    value.pop("generated_at", None)
    value.pop("updated_at", None)
    return value


def claim_ledger_fingerprint(payload: dict[str, Any]) -> str:
    raw = json.dumps(_canonical_payload(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def initialize_claim_evidence_policy(
    output_dir: str | Path,
    *,
    run_id: str,
    enforced: bool,
    required_chapters: set[int] | frozenset[int] = REQUIRED_CLAIM_CHAPTERS,
) -> dict[str, Any]:
    payload = {
        "schema_version": POLICY_VERSION,
        "run_id": str(run_id),
        "enforced": bool(enforced),
        "required_chapters": sorted(required_chapters),
        "created_at": _now(),
    }
    path = Path(output_dir) / "claim_evidence_policy.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def build_claim_evidence_ledger(
    output_dir: str | Path,
    claims: list[dict[str, Any]],
    *,
    change_reason: str,
    freeze: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    contract = _read_json(output / "analysis_contract.json")
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "report_id": str(contract.get("ts_code") or contract.get("code") or output.name),
        "revision": 1,
        "lifecycle": "decision_ready" if freeze else "reviewable",
        "change_reason": str(change_reason or "").strip(),
        "claims": deepcopy(claims),
        "generated_at": _now(),
    }
    payload["freeze"] = {
        "frozen": bool(freeze),
        "fingerprint": claim_ledger_fingerprint(payload) if freeze else "",
        "frozen_at": _now() if freeze else None,
    }
    return payload


def _chapter_texts(report_text: str) -> dict[int, str]:
    matches = list(_CHAPTER_RE.finditer(report_text))
    result: dict[int, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(report_text)
        result[int(match.group(1))] = report_text[match.start():end]
    return result


def _normalized_prose(text: str) -> str:
    return re.sub(r"\s+|[`*_#>|]", "", str(text or ""))


def bind_claim_references(output_dir: str | Path, payload: dict[str, Any]) -> dict[str, Any]:
    """Append a compact canonical registry for declared claim/chapter links."""
    output = Path(output_dir); chapter_dir = output / "chapters"
    if not chapter_dir.is_dir(): chapter_dir = output
    additions: dict[int, list[str]] = {}
    for claim in payload.get("claims") or []:
        if not isinstance(claim, dict) or not claim.get("claim_id"): continue
        claim_id = str(claim["claim_id"]); chapters = claim.get("chapters") or []
        for offset, chapter in enumerate(chapters):
            if not isinstance(chapter, int): continue
            path = chapter_dir / f"_ch{chapter:02d}.md"
            if not path.is_file(): continue
            text = path.read_text(encoding="utf-8")
            if claim_id in _CLAIM_REF_RE.findall(text) and (
                offset != 0 or _normalized_prose(claim.get("claim")) in _normalized_prose(text)
            ): continue
            if offset == 0:
                row = f"- {claim.get('claim')} [claim: {claim_id}]"
            else:
                row = f"- 重大主张交叉引用：[claim: {claim_id}]"
            additions.setdefault(chapter, []).append(row)
    changed: list[int] = []
    for chapter, rows in additions.items():
        path = chapter_dir / f"_ch{chapter:02d}.md"; text = path.read_text(encoding="utf-8")
        block = "\n\n### Canonical claim bindings\n\n" + "\n".join(rows) + "\n"
        path.write_text(text.rstrip() + block, encoding="utf-8"); changed.append(chapter)
    return {"changed_chapters": sorted(changed), "anchors_inserted": sum(map(len, additions.values()))}


def promote_reviewable_claim_evidence(output_dir: str | Path, *, report_text: str) -> dict[str, Any]:
    output = Path(output_dir); payload = _read_json(output / "claim_evidence.json")
    if not payload: return {"promoted": False, "error": "claim_evidence_missing"}
    policy = _read_json(output / "claim_evidence_policy.json")
    validation = validate_claim_evidence_ledger(
        payload, report_text=report_text, output_dir=output,
        enforced=bool(policy.get("enforced")),
        required_chapters=set(policy.get("required_chapters") or REQUIRED_CLAIM_CHAPTERS),
    )
    if validation.get("state") != "REVIEWABLE":
        return {"promoted": False, "validation": validation}
    promoted = deepcopy(payload); promoted["lifecycle"] = "decision_ready"
    promoted["freeze"] = {"frozen": True, "fingerprint": "", "frozen_at": _now()}
    promoted["freeze"]["fingerprint"] = claim_ledger_fingerprint(promoted)
    result = persist_claim_evidence_ledger(output, promoted, report_text=report_text)
    result["promoted"] = bool(result.get("written")); return result


def validate_claim_evidence_ledger(
    payload: dict[str, Any],
    *,
    report_text: str = "",
    output_dir: str | Path | None = None,
    enforced: bool = False,
    required_chapters: set[int] | frozenset[int] = REQUIRED_CLAIM_CHAPTERS,
) -> dict[str, Any]:
    invalid: list[str] = []
    incomplete: list[str] = []
    warnings: list[str] = []
    quality_rows: list[dict[str, Any]] = []
    registry = EvidenceRegistry()
    if output_dir is not None and Path(output_dir).is_dir():
        registry.register_from_output_dir(str(output_dir))
    decision_entries = {
        str(item.get("entry_id"))
        for item in (_read_json(Path(output_dir) / "decision_ledger.json").get("entries") or [])
        if isinstance(item, dict) and item.get("entry_id")
    } if output_dir is not None else set()
    official_policy = _read_json(Path(output_dir) / "official_evidence_policy.json") if output_dir is not None else {}
    official_evidence_enforced = bool(official_policy.get("enforced"))
    official_observations = {
        str(item.get("observation_id")): item
        for item in (_read_json(Path(output_dir) / "fact_observations.json").get("observations") or [])
        if isinstance(item, dict) and item.get("observation_id")
    } if output_dir is not None else {}
    calculation_payload = _read_json(Path(output_dir) / "calculation_observations.json") if output_dir is not None else {}
    calculation_observations = {
        str(item.get("calculation_id")): item
        for item in calculation_payload.get("calculations") or []
        if isinstance(item, dict) and item.get("calculation_id")
    }
    calculation_validation: dict[str, Any] = {}
    if calculation_payload and output_dir is not None:
        try:
            from scripts.computation_evidence import validate_calculation_observations
        except ModuleNotFoundError:
            from computation_evidence import validate_calculation_observations
        calculation_validation = validate_calculation_observations(
            calculation_payload, Path(output_dir), rebuild=True
        )

    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(payload.get("report_id") or "").strip():
        invalid.append("report_id_missing")
    if not str(payload.get("change_reason") or "").strip():
        incomplete.append("change_reason_missing")
    claims = payload.get("claims") if isinstance(payload, dict) else None
    if not isinstance(claims, list):
        invalid.append("claims_not_array")
        claims = []
    if enforced and not claims:
        incomplete.append("major_claims_missing")

    seen_claims: set[str] = set()
    seen_evidence: set[str] = set()
    covered_chapters: set[int] = set()
    claim_map: dict[str, dict[str, Any]] = {}
    for cidx, claim in enumerate(claims):
        prefix = f"claims[{cidx}]"
        if not isinstance(claim, dict):
            invalid.append(prefix + ":not_object")
            continue
        claim_id = str(claim.get("claim_id") or "").strip()
        if not claim_id:
            invalid.append(prefix + ":claim_id_missing")
        elif claim_id in seen_claims:
            invalid.append("duplicate_claim_id:" + claim_id)
        seen_claims.add(claim_id)
        claim_map[claim_id] = claim
        if not str(claim.get("claim") or "").strip():
            invalid.append(f"{claim_id or prefix}:claim_missing")
        chapters = claim.get("chapters")
        if not isinstance(chapters, list) or any(not isinstance(ch, int) or ch < 0 or ch > 14 for ch in chapters):
            invalid.append(f"{claim_id or prefix}:chapters_invalid")
            chapters = []
        covered_chapters.update(chapters)
        for field in ("reasoning_steps", "applicability_conditions"):
            values = claim.get(field)
            if not isinstance(values, list) or not any(str(item).strip() for item in values):
                incomplete.append(f"{claim_id or prefix}:{field}_missing")
        alternatives = claim.get("alternative_explanations")
        if not isinstance(alternatives, list) or not any(str(item).strip() for item in alternatives):
            incomplete.append(f"{claim_id or prefix}:alternative_explanations_missing")
        confidence = claim.get("confidence")
        if not isinstance(confidence, dict):
            invalid.append(f"{claim_id or prefix}:confidence_invalid")
        else:
            if confidence.get("kind") not in CONFIDENCE_KINDS:
                invalid.append(f"{claim_id or prefix}:confidence_kind_invalid")
            try:
                value = float(confidence.get("value"))
                if not 0 <= value <= 1:
                    raise ValueError
            except (TypeError, ValueError):
                invalid.append(f"{claim_id or prefix}:confidence_value_invalid")
            if not str(confidence.get("basis") or "").strip():
                incomplete.append(f"{claim_id or prefix}:confidence_basis_missing")
        impact = claim.get("decision_impact")
        if not isinstance(impact, dict) or any(not str(impact.get(key) or "").strip() for key in ("valuation", "position", "action")):
            incomplete.append(f"{claim_id or prefix}:decision_impact_missing")
        refs = claim.get("decision_entry_ids")
        if not isinstance(refs, list):
            invalid.append(f"{claim_id or prefix}:decision_entry_ids_invalid")
            refs = []
        if enforced and not refs:
            incomplete.append(f"{claim_id or prefix}:decision_entry_ids_missing")
        for ref in refs:
            if output_dir is not None and str(ref) not in decision_entries:
                invalid.append(f"{claim_id or prefix}:unknown_decision_entry:{ref}")

        facts = claim.get("raw_facts")
        if not isinstance(facts, list):
            invalid.append(f"{claim_id or prefix}:raw_facts_invalid")
            facts = []
        direct_support = 0
        qualified_support = 0
        source_groups: set[str] = set()
        for eidx, evidence in enumerate(facts):
            eprefix = f"{claim_id or prefix}.raw_facts[{eidx}]"
            if not isinstance(evidence, dict):
                invalid.append(eprefix + ":not_object")
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if not evidence_id:
                invalid.append(eprefix + ":evidence_id_missing")
            elif evidence_id in seen_evidence:
                invalid.append("duplicate_evidence_id:" + evidence_id)
            seen_evidence.add(evidence_id)
            source_id = str(evidence.get("source_id") or "").strip()
            canonical, unresolved = registry.canonicalize_anchor(source_id)
            if not source_id or unresolved or not canonical:
                invalid.append(f"{evidence_id or eprefix}:source_unresolved:{'|'.join(unresolved) or source_id}")
            authority = str(evidence.get("authority") or "")
            distance = str(evidence.get("claim_distance") or "")
            if authority not in AUTHORITIES:
                invalid.append(f"{evidence_id or eprefix}:authority_invalid")
            if distance not in DISTANCES:
                invalid.append(f"{evidence_id or eprefix}:claim_distance_invalid")
            support_type = str(evidence.get("support_type") or "")
            basis_match = str(evidence.get("basis_match") or "")
            if support_type not in SUPPORT_TYPES:
                invalid.append(f"{evidence_id or eprefix}:support_type_invalid")
            if basis_match not in BASIS_MATCHES:
                invalid.append(f"{evidence_id or eprefix}:basis_match_invalid")
            if basis_match == "mismatch" and evidence.get("direct_support"):
                invalid.append(f"{evidence_id or eprefix}:direct_support_basis_mismatch")
            elif basis_match == "uncertain":
                warnings.append(f"{evidence_id or eprefix}:basis_match_uncertain")
            if not str(evidence.get("fact") or "").strip():
                invalid.append(f"{evidence_id or eprefix}:fact_missing")
            for field in ("published_at", "data_as_of"):
                date = str(evidence.get(field) or "").strip()
                if not date or not _DATE_RE.match(date):
                    incomplete.append(f"{evidence_id or eprefix}:{field}_missing_or_invalid")
            if not str(evidence.get("conflict_of_interest") or "").strip():
                incomplete.append(f"{evidence_id or eprefix}:conflict_of_interest_missing")
            group = str(evidence.get("source_group_id") or "").strip()
            if not group:
                incomplete.append(f"{evidence_id or eprefix}:source_group_id_missing")
            else:
                source_groups.add(group)
            is_direct = bool(evidence.get("direct_support")) and support_type == "supports"
            if is_direct:
                direct_support += 1
                observation_id = str(evidence.get("observation_id") or "").strip()
                calculation_id = str(evidence.get("calculation_id") or "").strip()
                if observation_id and calculation_id:
                    invalid.append(f"{evidence_id or eprefix}:multiple_direct_evidence_identities")
                if official_evidence_enforced and not observation_id and not calculation_id:
                    invalid.append(f"{evidence_id or eprefix}:verified_evidence_identity_required")
                if observation_id:
                    observation = official_observations.get(observation_id)
                    if observation is None:
                        invalid.append(f"{evidence_id or eprefix}:unknown_observation_id:{observation_id}")
                    elif observation.get("status") != "VERIFIED":
                        invalid.append(f"{evidence_id or eprefix}:observation_not_verified:{observation_id}")
                    elif source_id != str(observation.get("doc_id") or ""):
                        invalid.append(f"{evidence_id or eprefix}:observation_source_mismatch:{observation_id}")
                    elif not _observation_covers_fact_numbers(
                        str(evidence.get("fact") or ""), observation
                    ):
                        invalid.append(
                            f"{evidence_id or eprefix}:observation_numeric_support_mismatch:{observation_id}"
                        )
                elif calculation_id:
                    calculation = calculation_observations.get(calculation_id)
                    if calculation_validation.get("state") != "VERIFIED":
                        invalid.append(f"{evidence_id or eprefix}:calculation_evidence_invalid")
                    elif calculation is None:
                        invalid.append(f"{evidence_id or eprefix}:unknown_calculation_id:{calculation_id}")
                    elif calculation.get("status") != "VERIFIED":
                        invalid.append(f"{evidence_id or eprefix}:calculation_not_verified:{calculation_id}")
                    elif source_id != str(calculation.get("tool") or ""):
                        invalid.append(f"{evidence_id or eprefix}:calculation_source_mismatch:{calculation_id}")
                    elif not _observation_covers_fact_numbers(
                        str(evidence.get("fact") or ""),
                        {"raw_text": calculation.get("value"), "raw_value": calculation.get("value"), "normalized_value": calculation.get("value")},
                    ):
                        invalid.append(f"{evidence_id or eprefix}:calculation_numeric_support_mismatch:{calculation_id}")
                    if authority != "verified_calculation":
                        invalid.append(f"{evidence_id or eprefix}:calculation_authority_mismatch")
                if set(canonical).issubset(INTERNAL_SOURCES | SELF_REFERENTIAL_FILES):
                    invalid.append(f"{evidence_id or eprefix}:circular_internal_support")
                quality = AUTHORITIES.get(authority, 0) * DISTANCES.get(distance, 0)
                if basis_match in {"exact", "compatible"} and quality >= MIN_DIRECT_SUPPORT_QUALITY:
                    qualified_support += 1
            quality_rows.append({
                "claim_id": claim_id,
                "evidence_id": evidence_id,
                "authority": authority,
                "claim_distance": distance,
                "quality": round(AUTHORITIES.get(authority, 0) * DISTANCES.get(distance, 0), 3),
                "source_group_id": group,
            })
        if not direct_support:
            incomplete.append(f"{claim_id or prefix}:direct_support_missing")
        elif not qualified_support:
            incomplete.append(f"{claim_id or prefix}:qualified_direct_support_missing")
        if len(facts) > 1 and len(source_groups) == 1:
            warnings.append(f"{claim_id or prefix}:same_origin_not_independent")

    if enforced:
        for chapter in sorted(set(required_chapters) - covered_chapters):
            incomplete.append(f"required_claim_chapter_missing:Ch{chapter}")

    chapters = _chapter_texts(report_text)
    report_refs = set(_CLAIM_REF_RE.findall(report_text))
    for ref in sorted(report_refs - seen_claims):
        invalid.append("unknown_claim_reference:" + ref)
    for claim_id, claim in claim_map.items():
        claim_chapters = claim.get("chapters") or []
        for chapter in claim_chapters:
            if not _CLAIM_REF_RE.search(chapters.get(chapter, "")) or claim_id not in _CLAIM_REF_RE.findall(chapters.get(chapter, "")):
                incomplete.append(f"claim_reference_missing:Ch{chapter}:{claim_id}")
        if claim_chapters:
            home = int(claim_chapters[0])
            if _normalized_prose(claim.get("claim")) not in _normalized_prose(chapters.get(home, "")):
                incomplete.append(f"canonical_claim_text_missing:Ch{home}:{claim_id}")

    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    warnings = list(dict.fromkeys(warnings))
    frozen = bool((payload.get("freeze") or {}).get("frozen"))
    fingerprint = str((payload.get("freeze") or {}).get("fingerprint") or "")
    if frozen and fingerprint != claim_ledger_fingerprint(payload):
        invalid.append("freeze_fingerprint_mismatch")
    if invalid:
        state = "INVALID"
    elif incomplete:
        state = "INCOMPLETE"
    elif payload.get("lifecycle") == "monitoring":
        state = "MONITORING"
    elif frozen:
        state = "DECISION_READY"
    else:
        state = "REVIEWABLE"
    independent_groups = len({row["source_group_id"] for row in quality_rows if row["source_group_id"]})
    return {
        "schema_version": "claim-evidence-validation.v1",
        "state": state,
        "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid,
        "incomplete_findings": incomplete,
        "warnings": warnings,
        "evidence_quality": quality_rows,
        "independent_source_groups": independent_groups,
        "claim_ids": sorted(seen_claims),
        "covered_chapters": sorted(covered_chapters),
        "required_chapters": sorted(required_chapters) if enforced else [],
        "enforced": bool(enforced),
    }


def claim_evidence_diff(old: dict[str, Any], new: dict[str, Any], *, change_reason: str) -> dict[str, Any]:
    old_claims = {str(item.get("claim_id")): item for item in old.get("claims") or [] if isinstance(item, dict)}
    new_claims = {str(item.get("claim_id")): item for item in new.get("claims") or [] if isinstance(item, dict)}
    changes = [
        {"claim_id": claim_id, "before": old_claims.get(claim_id), "after": new_claims.get(claim_id)}
        for claim_id in sorted(set(old_claims) | set(new_claims))
        if old_claims.get(claim_id) != new_claims.get(claim_id)
    ]
    return {
        "schema_version": "claim-evidence-diff.v1",
        "generated_at": _now(),
        "change_reason": str(change_reason or "").strip(),
        "old_fingerprint": claim_ledger_fingerprint(old) if old else None,
        "new_fingerprint": claim_ledger_fingerprint(new) if new else None,
        "changes": changes,
    }


def persist_claim_evidence_ledger(
    output_dir: str | Path,
    payload: dict[str, Any],
    *,
    report_text: str = "",
    allow_frozen_update: bool = False,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / "claim_evidence.json"
    diff_path = output / "claim_evidence_diff.json"
    old = _read_json(path)
    policy = _read_json(output / "claim_evidence_policy.json")
    required = set(policy.get("required_chapters") or REQUIRED_CLAIM_CHAPTERS)
    validation = validate_claim_evidence_ledger(
        payload,
        report_text=report_text,
        output_dir=output,
        enforced=bool(policy.get("enforced")),
        required_chapters=required,
    )
    if validation["state"] == "INVALID":
        (output / "claim_evidence_last_rejected.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "claim_evidence_last_rejected_validation.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"written": False, "path": str(path), "validation": validation, "error": "claim evidence validation failed"}
    if validation["state"] == "INCOMPLETE" and bool((payload.get("freeze") or {}).get("frozen")):
        (output / "claim_evidence_last_rejected.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (output / "claim_evidence_last_rejected_validation.json").write_text(
            json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return {"written": False, "path": str(path), "validation": validation, "error": "incomplete claim evidence cannot be frozen"}
    diff = claim_evidence_diff(old, payload, change_reason=str(payload.get("change_reason") or ""))
    changed = bool(old) and claim_ledger_fingerprint(old) != claim_ledger_fingerprint(payload)
    if old and bool((old.get("freeze") or {}).get("frozen")) and changed and not allow_frozen_update:
        diff["status"] = "REJECTED_FROZEN"
        diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"written": False, "path": str(path), "diff_path": str(diff_path), "claim_evidence_frozen": True, "validation": validation, "error": "frozen claim evidence rejected an update"}
    metadata_changed = bool(old) and (
        old.get("lifecycle") != payload.get("lifecycle")
        or (old.get("freeze") or {}) != (payload.get("freeze") or {})
    )
    if old and not changed:
        # Fingerprints intentionally exclude lifecycle/freeze metadata.  A
        # promotion must nevertheless persist those fields; otherwise a
        # REVIEWABLE claim ledger can report a successful promotion while
        # remaining unfrozen forever.
        diff["status"] = "METADATA_REPAIRED" if metadata_changed else "NO_CHANGE"
        ledger = payload if metadata_changed else old
    else:
        diff["status"] = "APPLIED" if old else "INITIALIZED"
        if old:
            payload["revision"] = max(int(old.get("revision") or 1) + 1, int(payload.get("revision") or 1))
            payload["freeze"]["fingerprint"] = claim_ledger_fingerprint(payload)
        ledger = payload
    path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    diff_path.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "path": str(path), "diff_path": str(diff_path), "ledger": ledger, "validation": validation, "diff": diff}


def evaluate_output_claim_evidence(
    output_dir: str | Path,
    *,
    report_text: str = "",
    persist: bool = True,
) -> dict[str, Any]:
    output = Path(output_dir)
    policy = _read_json(output / "claim_evidence_policy.json")
    ledger = _read_json(output / "claim_evidence.json")
    enforced = bool(policy.get("enforced"))
    required = set(policy.get("required_chapters") or REQUIRED_CLAIM_CHAPTERS)
    if not ledger:
        state = "INCOMPLETE" if enforced else "SKIP"
        result = {
            "schema_version": "claim-evidence-validation.v1",
            "state": state,
            "status": "FAIL" if enforced else "SKIP",
            "invalid_findings": [],
            "incomplete_findings": ["claim_evidence_missing"] if enforced else [],
            "warnings": [],
            "enforced": enforced,
            "policy": policy,
        }
    else:
        result = validate_claim_evidence_ledger(
            ledger, report_text=report_text, output_dir=output, enforced=enforced, required_chapters=required
        )
        result["policy"] = policy
    if persist:
        (output / "claim_evidence_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result
