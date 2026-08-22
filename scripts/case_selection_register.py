#!/usr/bin/env python3
"""Freeze pre-outcome cohort selection without creating another case library.

The register is deliberately a small output-side planning object.  A selected
company×period only becomes a ``CASE:`` / ``MEP:`` through the existing
append-only base-rate library.  Keeping those identities separate prevents a
selection list from being misrepresented as a realised historical sample.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "case-selection-register.v1"
REGISTER_FILE = "case_selection_register.json"
SELECTION_MODES = {
    "TYPICAL", "DIVERSE", "MOST_SIMILAR", "MOST_DIFFERENT", "DEVIANT",
}
CASE_ROLES = {"LITERAL_REPLICATION", "THEORETICAL_EXTENSION", "DEVIANT_TEST"}
EXCLUSION_STATUSES = {"INCLUDED", "EXCLUDED"}
OUTCOME_ISOLATIONS = {"PIT_PRE_OUTCOME", "OUTCOME_SELECTED_RESEARCH_ONLY"}
JUDGMENT_FLYWHEEL_ROLES = {"FOCAL", "NEAR_MISS", "BOUNDARY_REPLICATION"}
JUDGMENT_FLYWHEEL_REQUIRED_STATE_VECTOR_FIELDS = (
    "mechanism_domain", "current_state", "competitive_fork", "observable_symptom",
    "cycle_phase", "business_boundary", "result_metric", "upstream_mediator",
    "boundary_condition",
)
JUDGMENT_FLYWHEEL_SAMPLING_FIELDS = {"enabled", "batches"}
JUDGMENT_FLYWHEEL_BATCH_FIELDS = {"batch_id", "members"}
JUDGMENT_FLYWHEEL_MEMBER_FIELDS = {
    "entry_id", "role", "focal_entry_id", "upstream_mediator_relation",
}
POSSIBILITY_CONDITION_MAPPING_FIELDS = {"mappings"}
POSSIBILITY_CONDITION_MAPPING_ROW_FIELDS = {
    "entry_id", "condition_id", "role", "state_vector_field", "evidence_refs",
}
POSSIBILITY_CONDITION_EVIDENCE_REF_FIELDS = {
    "evidence_id", "observation_id", "source_id", "cutoff_at", "as_of",
}
POSSIBILITY_CONDITION_ROLES = {"COMMON", "MEDIATOR_EXCEPTION"}
JUDGMENT_FLYWHEEL_PROHIBITED_FIELDS = {
    "data_availability_score", "source_availability_score", "availability_score", "selection_score",
    "price", "share_price", "market_price", "return", "expected_return", "actual_result",
    "realized_result", "outcome",
}


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _read(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _evidence_indexes(output: Path) -> tuple[
    dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]],
]:
    """Read existing canonical evidence ledgers without copying their facts."""
    claim_ledger = _read(output / "claim_evidence.json")
    evidence = {
        str(fact.get("evidence_id")): fact
        for claim in claim_ledger.get("claims") or []
        if isinstance(claim, dict)
        for fact in claim.get("raw_facts") or []
        if isinstance(fact, dict) and str(fact.get("evidence_id") or "").strip()
    }
    observations = {
        str(item.get("observation_id")): item
        for item in _read(output / "fact_observations.json").get("observations") or []
        if isinstance(item, dict) and str(item.get("observation_id") or "").strip()
    }
    documents = {
        str(item.get("doc_id")): item
        for item in _read(output / "document_manifest.json").get("documents") or []
        if isinstance(item, dict) and str(item.get("doc_id") or "").strip()
    }
    return evidence, observations, documents


def _day(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None


def _present(value: Any) -> bool:
    return value not in (None, "", [], {})


def _unsupported_fields(value: dict[str, Any], allowed: set[str]) -> list[str]:
    """Keep opt-in sampling metadata from becoming a hidden scoring model."""
    return sorted(str(field) for field in value if field not in allowed)


def _prohibited_flywheel_fields(value: dict[str, Any]) -> list[str]:
    return sorted(str(field) for field in value if str(field).lower() in JUDGMENT_FLYWHEEL_PROHIBITED_FIELDS)


def _fingerprint_payload(register: dict[str, Any]) -> dict[str, Any]:
    value = deepcopy(register)
    value.pop("generated_at", None)
    value.pop("updated_at", None)
    value.pop("freeze", None)
    return value


def case_selection_register_fingerprint(register: dict[str, Any]) -> str:
    raw = json.dumps(
        _fingerprint_payload(register), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _validate_judgment_flywheel_sampling(
    register: dict[str, Any],
    *,
    entries_by_id: dict[str, dict[str, Any]],
    universe_state_vector_fields: set[str],
    invalid: list[str],
    incomplete: list[str],
) -> list[str]:
    """Validate a deliberately tiny, pre-outcome three-case comparison batch.

    This is a selection constraint, not a new case library or a score.  Its
    only usable inputs are the register's existing pre-cutoff entries and
    state vectors.  A batch is therefore rejected rather than silently
    downgraded when its focal/near-miss/boundary comparison cannot be made.
    """
    sampling = register.get("judgment_flywheel_sampling")
    if sampling is None:
        return []
    if not isinstance(sampling, dict):
        invalid.append("judgment_flywheel_sampling_not_object")
        return []
    for field in _unsupported_fields(sampling, JUDGMENT_FLYWHEEL_SAMPLING_FIELDS):
        invalid.append("judgment_flywheel_sampling:unsupported_field:" + field)
    if sampling.get("enabled") is not True:
        invalid.append("judgment_flywheel_sampling_must_be_explicitly_enabled")
    # A flywheel batch is deliberately selected from a small, declared
    # pre-outcome universe.  If a company can sit in that universe without an
    # INCLUDED or EXCLUDED entry, later reviewers cannot tell whether it was
    # screened out on a cutoff-available reason or simply disappeared after
    # looking less persuasive.  This is intentionally limited to the opt-in
    # sampling mode: ordinary case registers remain planning objects rather
    # than exhaustive screening logs.
    universe = register.get("universe")
    candidate_company_ids = {
        str(company_id).strip()
        for company_id in (universe or {}).get("candidate_company_ids") or []
        if str(company_id).strip()
    } if isinstance(universe, dict) else set()
    entry_company_ids = {
        str(entry.get("company_id") or "").strip()
        for entry in entries_by_id.values()
        if str(entry.get("company_id") or "").strip()
    }
    for company_id in sorted(candidate_company_ids - entry_company_ids):
        invalid.append(
            "judgment_flywheel_sampling:universe_candidate_without_screen_entry:" + company_id
        )
    for company_id in sorted(entry_company_ids - candidate_company_ids):
        invalid.append(
            "judgment_flywheel_sampling:screen_entry_company_outside_universe:" + company_id
        )
    batches = sampling.get("batches")
    if not isinstance(batches, list) or not batches:
        incomplete.append("judgment_flywheel_sampling_batches_missing")
        return []
    missing_universe_fields = sorted(
        set(JUDGMENT_FLYWHEEL_REQUIRED_STATE_VECTOR_FIELDS) - universe_state_vector_fields
    )
    if missing_universe_fields:
        incomplete.extend(
            "judgment_flywheel_sampling:universe_state_vector_field_missing:" + field
            for field in missing_universe_fields
        )
    for field in sorted(field for field in universe_state_vector_fields if field.lower() in JUDGMENT_FLYWHEEL_PROHIBITED_FIELDS):
        invalid.append("judgment_flywheel_sampling:universe_state_vector_field_prohibited:" + field)
    batch_ids: list[str] = []
    for batch_index, batch in enumerate(batches):
        prefix = f"judgment_flywheel_sampling.batches[{batch_index}]"
        if not isinstance(batch, dict):
            invalid.append(prefix + ":not_object")
            continue
        for field in _unsupported_fields(batch, JUDGMENT_FLYWHEEL_BATCH_FIELDS):
            invalid.append(prefix + ":unsupported_field:" + field)
        batch_id = str(batch.get("batch_id") or "").strip()
        if not batch_id.startswith("CSRFWB:"):
            invalid.append(prefix + ":batch_id_invalid")
        elif batch_id in batch_ids:
            invalid.append("judgment_flywheel_batch_id_duplicate:" + batch_id)
        batch_ids.append(batch_id)
        members = batch.get("members")
        if not isinstance(members, list):
            incomplete.append(prefix + ":members_missing")
            continue
        if len(members) != 3:
            invalid.append(prefix + ":must_contain_exactly_three_members")
        members_by_role: dict[str, dict[str, Any]] = {}
        member_entry_ids: set[str] = set()
        member_entries: dict[str, dict[str, Any]] = {}
        for member_index, member in enumerate(members):
            member_prefix = f"{prefix}.members[{member_index}]"
            if not isinstance(member, dict):
                invalid.append(member_prefix + ":not_object")
                continue
            for field in _unsupported_fields(member, JUDGMENT_FLYWHEEL_MEMBER_FIELDS):
                invalid.append(member_prefix + ":unsupported_field:" + field)
            role = str(member.get("role") or "")
            if role not in JUDGMENT_FLYWHEEL_ROLES:
                invalid.append(member_prefix + ":role_invalid")
            elif role in members_by_role:
                invalid.append(prefix + ":role_duplicate:" + role)
            else:
                members_by_role[role] = member
            entry_id = str(member.get("entry_id") or "").strip()
            if not entry_id:
                incomplete.append(member_prefix + ":entry_id_missing")
                continue
            if entry_id in member_entry_ids:
                invalid.append(prefix + ":entry_id_duplicate:" + entry_id)
            member_entry_ids.add(entry_id)
            entry = entries_by_id.get(entry_id)
            if entry is None:
                invalid.append(member_prefix + ":entry_not_found:" + entry_id)
                continue
            member_entries[role] = entry
            if (
                entry.get("outcome_isolation") != "PIT_PRE_OUTCOME"
                or str((entry.get("exclusion") or {}).get("status") or "") != "INCLUDED"
            ):
                invalid.append(member_prefix + ":entry_must_be_pit_pre_outcome_and_included")
            for field in _prohibited_flywheel_fields(entry):
                invalid.append(member_prefix + ":entry_field_prohibited:" + field)
            state_vector = entry.get("state_vector")
            if not isinstance(state_vector, dict):
                incomplete.append(member_prefix + ":state_vector_missing")
                continue
            for field in _prohibited_flywheel_fields(state_vector):
                invalid.append(member_prefix + ":state_vector_field_prohibited:" + field)
            for field in JUDGMENT_FLYWHEEL_REQUIRED_STATE_VECTOR_FIELDS:
                if not _present(state_vector.get(field)):
                    incomplete.append(member_prefix + ":state_vector_field_missing:" + field)

        if set(members_by_role) != JUDGMENT_FLYWHEEL_ROLES:
            invalid.append(prefix + ":must_contain_one_focal_one_near_miss_one_boundary_replication")
            continue
        focal = members_by_role["FOCAL"]
        focal_entry_id = str(focal.get("entry_id") or "").strip()
        focal_entry = member_entries.get("FOCAL")
        near_miss = members_by_role["NEAR_MISS"]
        boundary = members_by_role["BOUNDARY_REPLICATION"]
        for role, member in (("NEAR_MISS", near_miss), ("BOUNDARY_REPLICATION", boundary)):
            if str(member.get("focal_entry_id") or "").strip() != focal_entry_id:
                invalid.append(prefix + f":{role.lower()}_must_link_focal")
        if str(near_miss.get("upstream_mediator_relation") or "") != "OPPOSITE":
            invalid.append(prefix + ":near_miss_upstream_mediator_relation_must_be_opposite")

        company_ids = {
            str(entry.get("company_id") or "").strip()
            for entry in member_entries.values()
            if str(entry.get("company_id") or "").strip()
        }
        if len(company_ids) != 3:
            invalid.append(prefix + ":members_must_use_three_distinct_companies")
        if focal_entry is None:
            continue
        focal_vector = focal_entry.get("state_vector")
        near_entry = member_entries.get("NEAR_MISS")
        boundary_entry = member_entries.get("BOUNDARY_REPLICATION")
        if not isinstance(focal_vector, dict) or not isinstance(near_entry, dict) or not isinstance(boundary_entry, dict):
            continue
        near_vector = near_entry.get("state_vector")
        boundary_vector = boundary_entry.get("state_vector")
        if not isinstance(near_vector, dict) or not isinstance(boundary_vector, dict):
            continue
        # A near miss isolates its upstream mediator, and a boundary
        # replication isolates its boundary condition: each has the exact
        # same comparison dimensions and values as the focal except for its
        # one declared difference.
        for role, vector in (("near_miss", near_vector), ("boundary_replication", boundary_vector)):
            if set(vector) != set(focal_vector):
                invalid.append(prefix + f":{role}_state_vector_dimensions_mismatch")
        for field in sorted(set(focal_vector) - {"upstream_mediator"}):
            if _present(focal_vector.get(field)) and _present(near_vector.get(field)) and focal_vector.get(field) != near_vector.get(field):
                invalid.append(prefix + ":near_miss_" + field + "_must_match_focal")
        if _present(focal_vector.get("upstream_mediator")) and _present(near_vector.get("upstream_mediator")) and focal_vector.get("upstream_mediator") == near_vector.get("upstream_mediator"):
            invalid.append(prefix + ":near_miss_upstream_mediator_must_differ_from_focal")
        for field in sorted(set(focal_vector) - {"boundary_condition"}):
            if _present(focal_vector.get(field)) and _present(boundary_vector.get(field)) and focal_vector.get(field) != boundary_vector.get(field):
                invalid.append(prefix + ":boundary_replication_" + field + "_must_match_focal")
        if _present(focal_vector.get("boundary_condition")) and _present(boundary_vector.get("boundary_condition")) and focal_vector.get("boundary_condition") == boundary_vector.get("boundary_condition"):
            invalid.append(prefix + ":boundary_replication_boundary_condition_must_differ_from_focal")
    return sorted(batch_id for batch_id in batch_ids if batch_id)


def _validate_possibility_condition_evidence(
    register: dict[str, Any],
    *,
    entries_by_id: dict[str, dict[str, Any]],
    output: Path | None,
    invalid: list[str],
    incomplete: list[str],
) -> None:
    """Bind an opt-in three-object batch to pre-outcome canonical facts.

    The mapping is deliberately only an index over claim evidence, verified
    observations and document identities.  It stores no duplicate facts and
    makes no outcome judgment.  Structural-only validation remains usable for
    the legacy/authoring preview path; persistence and output admission pass an
    output directory and therefore must resolve this chain.
    """
    sampling = register.get("judgment_flywheel_sampling")
    if not isinstance(sampling, dict) or sampling.get("enabled") is not True:
        return
    if output is None:
        return

    root = "judgment_flywheel_sampling"
    mapping_payload = register.get("possibility_condition_evidence")
    if not isinstance(mapping_payload, dict):
        incomplete.append(root + ":possibility_condition_evidence_missing")
        return
    for field in _unsupported_fields(mapping_payload, POSSIBILITY_CONDITION_MAPPING_FIELDS):
        invalid.append(root + ".possibility_condition_evidence:unsupported_field:" + field)
    mappings = mapping_payload.get("mappings")
    if not isinstance(mappings, list) or not mappings:
        incomplete.append(root + ":possibility_condition_evidence_mappings_missing")
        return

    evidence_by_id, observations_by_id, documents_by_id = _evidence_indexes(output)
    if not evidence_by_id:
        incomplete.append(root + ":possibility_condition_claim_evidence_missing")
    if not observations_by_id:
        incomplete.append(root + ":possibility_condition_fact_observations_missing")
    if not documents_by_id:
        incomplete.append(root + ":possibility_condition_document_manifest_missing")

    records: list[dict[str, Any]] = []
    seen_entry_condition: set[tuple[str, str]] = set()
    for index, mapping in enumerate(mappings):
        prefix = f"{root}.possibility_condition_evidence.mappings[{index}]"
        if not isinstance(mapping, dict):
            invalid.append(prefix + ":not_object")
            continue
        for field in _unsupported_fields(mapping, POSSIBILITY_CONDITION_MAPPING_ROW_FIELDS):
            invalid.append(prefix + ":unsupported_field:" + field)
        entry_id = str(mapping.get("entry_id") or "").strip()
        condition_id = str(mapping.get("condition_id") or "").strip()
        role = str(mapping.get("role") or "").strip()
        state_vector_field = str(mapping.get("state_vector_field") or "").strip()
        if entry_id not in entries_by_id:
            invalid.append(prefix + ":entry_unknown:" + entry_id)
        if not condition_id.startswith("PCOND:"):
            invalid.append(prefix + ":condition_id_invalid")
        elif (entry_id, condition_id) in seen_entry_condition:
            invalid.append(prefix + ":entry_condition_duplicate")
        else:
            seen_entry_condition.add((entry_id, condition_id))
        if role not in POSSIBILITY_CONDITION_ROLES:
            invalid.append(prefix + ":role_invalid")
        entry = entries_by_id.get(entry_id) or {}
        state_vector = entry.get("state_vector") if isinstance(entry.get("state_vector"), dict) else {}
        if not state_vector_field:
            incomplete.append(prefix + ":state_vector_field_missing")
        elif state_vector_field not in state_vector:
            invalid.append(prefix + ":state_vector_field_unknown")
        elif state_vector_field.lower() in JUDGMENT_FLYWHEEL_PROHIBITED_FIELDS:
            invalid.append(prefix + ":state_vector_field_prohibited")
        refs = mapping.get("evidence_refs")
        if not isinstance(refs, list) or not refs:
            incomplete.append(prefix + ":evidence_refs_missing")
            refs = []

        entry_cutoff = _day(entry.get("information_cutoff"))
        evidence_ids: set[str] = set()
        observation_ids: set[str] = set()
        seen_evidence: set[str] = set()
        for ref_index, reference in enumerate(refs):
            ref_prefix = f"{prefix}.evidence_refs[{ref_index}]"
            if not isinstance(reference, dict):
                invalid.append(ref_prefix + ":not_object")
                continue
            for field in _unsupported_fields(reference, POSSIBILITY_CONDITION_EVIDENCE_REF_FIELDS):
                invalid.append(ref_prefix + ":unsupported_field:" + field)
            evidence_id = str(reference.get("evidence_id") or "").strip()
            observation_id = str(reference.get("observation_id") or "").strip()
            source_id = str(reference.get("source_id") or "").strip()
            if not evidence_id:
                incomplete.append(ref_prefix + ":evidence_id_missing")
            elif evidence_id in seen_evidence:
                invalid.append(ref_prefix + ":evidence_id_duplicate")
            seen_evidence.add(evidence_id)
            if not observation_id:
                incomplete.append(ref_prefix + ":observation_id_missing")
            if not source_id:
                incomplete.append(ref_prefix + ":source_id_missing")
            cutoff_at = _day(reference.get("cutoff_at"))
            as_of = _day(reference.get("as_of"))
            if cutoff_at is None:
                incomplete.append(ref_prefix + ":cutoff_at_missing_or_invalid")
            elif entry_cutoff is not None and cutoff_at != entry_cutoff:
                invalid.append(ref_prefix + ":cutoff_at_does_not_match_entry")
            if as_of is None:
                incomplete.append(ref_prefix + ":as_of_missing_or_invalid")
            elif cutoff_at is not None and as_of > cutoff_at:
                invalid.append(ref_prefix + ":as_of_after_cutoff")

            raw_fact = evidence_by_id.get(evidence_id)
            if raw_fact is None:
                invalid.append(ref_prefix + ":evidence_unknown")
                continue
            if str(raw_fact.get("source_id") or "").strip() != source_id:
                invalid.append(ref_prefix + ":source_id_does_not_match_evidence")
                continue
            if str(raw_fact.get("observation_id") or "").strip() != observation_id:
                invalid.append(ref_prefix + ":observation_id_does_not_match_evidence")
                continue
            if raw_fact.get("direct_support") is not True or raw_fact.get("support_type") != "supports":
                invalid.append(ref_prefix + ":evidence_not_direct_support")
            if raw_fact.get("basis_match") != "exact":
                invalid.append(ref_prefix + ":evidence_basis_not_exact")
            if raw_fact.get("claim_distance") not in {"raw_data", "direct_statement"}:
                invalid.append(ref_prefix + ":evidence_not_first_order")
            raw_published_at = _day(raw_fact.get("published_at"))
            raw_as_of = _day(raw_fact.get("data_as_of"))
            if raw_published_at is None:
                incomplete.append(ref_prefix + ":evidence_published_at_missing_or_invalid")
            elif cutoff_at is not None and raw_published_at > cutoff_at:
                invalid.append(ref_prefix + ":evidence_published_after_cutoff")
            if raw_as_of is None:
                incomplete.append(ref_prefix + ":evidence_as_of_missing_or_invalid")
            elif as_of is not None and raw_as_of != as_of:
                invalid.append(ref_prefix + ":as_of_does_not_match_evidence")

            observation = observations_by_id.get(observation_id)
            if observation is None:
                invalid.append(ref_prefix + ":observation_unknown")
                continue
            if observation.get("status") != "VERIFIED":
                invalid.append(ref_prefix + ":observation_not_verified")
            if str(observation.get("doc_id") or "").strip() != source_id:
                invalid.append(ref_prefix + ":observation_source_mismatch")
            observation_as_of = _day(observation.get("as_of"))
            if observation_as_of is None:
                incomplete.append(ref_prefix + ":observation_as_of_missing_or_invalid")
            elif as_of is not None and observation_as_of != as_of:
                invalid.append(ref_prefix + ":as_of_does_not_match_observation")

            document = documents_by_id.get(source_id)
            if document is None:
                invalid.append(ref_prefix + ":source_document_unknown")
                continue
            if str(raw_fact.get("authority") or "").strip() != str(document.get("authority") or "").strip():
                invalid.append(ref_prefix + ":evidence_authority_does_not_match_document")
            document_published_at = _day(document.get("published_at"))
            if document_published_at is None:
                incomplete.append(ref_prefix + ":document_published_at_missing_or_invalid")
            elif cutoff_at is not None and document_published_at > cutoff_at:
                invalid.append(ref_prefix + ":document_published_after_cutoff")
            # A common cycle/arena condition may legitimately come from one
            # industry or macro document.  The cross-company guard is instead
            # at the precise-fact level: each entry must have its own canonical
            # EVD/OBS binding, even when the document lineage is shared.
            evidence_ids.add(evidence_id)
            observation_ids.add(observation_id)
        records.append({
            "prefix": prefix, "entry_id": entry_id, "condition_id": condition_id,
            "role": role, "state_vector_field": state_vector_field,
            "evidence_ids": evidence_ids, "observation_ids": observation_ids,
        })

    batches = sampling.get("batches") if isinstance(sampling.get("batches"), list) else []
    batch_entry_ids: set[str] = set()
    for batch_index, batch in enumerate(batches):
        if not isinstance(batch, dict):
            continue
        batch_prefix = f"{root}.batches[{batch_index}]"
        members = batch.get("members") if isinstance(batch.get("members"), list) else []
        role_by_entry = {
            str(member.get("entry_id") or "").strip(): str(member.get("role") or "")
            for member in members if isinstance(member, dict) and str(member.get("entry_id") or "").strip()
        }
        if set(role_by_entry.values()) != JUDGMENT_FLYWHEEL_ROLES:
            continue
        expected_entries = set(role_by_entry)
        batch_entry_ids.update(expected_entries)
        batch_records = [record for record in records if record["entry_id"] in expected_entries]
        grouped: dict[str, list[dict[str, Any]]] = {}
        for record in batch_records:
            grouped.setdefault(record["condition_id"], []).append(record)
        common_condition_ids: set[str] = set()
        mediator_condition_ids: set[str] = set()
        near_entry_ids = {
            entry_id for entry_id, role in role_by_entry.items()
            if role == "NEAR_MISS"
        }
        for condition_id, condition_records in grouped.items():
            roles = {record["role"] for record in condition_records}
            if len(roles) != 1:
                invalid.append(batch_prefix + ":condition_role_not_consistent:" + condition_id)
                continue
            role = next(iter(roles))
            mapped_entries = {record["entry_id"] for record in condition_records}
            fields = {record["state_vector_field"] for record in condition_records}
            if len(fields) != 1:
                invalid.append(batch_prefix + ":condition_state_vector_field_not_consistent:" + condition_id)
            field = next(iter(fields)) if fields else ""
            if role == "COMMON":
                common_condition_ids.add(condition_id)
                if field == "upstream_mediator":
                    invalid.append(batch_prefix + ":common_condition_cannot_use_upstream_mediator:" + condition_id)
                for entry_id in sorted(expected_entries - mapped_entries):
                    incomplete.append(
                        batch_prefix + ":condition_entry_mapping_missing:" + condition_id + ":" + entry_id
                    )
                if mapped_entries == expected_entries and field:
                    common_values: set[str] = set()
                    for entry_id in expected_entries:
                        vector = entries_by_id.get(entry_id, {}).get("state_vector")
                        value = vector.get(field) if isinstance(vector, dict) else None
                        common_values.add(json.dumps(value, ensure_ascii=False, sort_keys=True))
                    if len(common_values) != 1:
                        invalid.append(
                            batch_prefix + ":common_condition_state_vector_must_match:"
                            + condition_id
                        )
            elif role == "MEDIATOR_EXCEPTION":
                mediator_condition_ids.add(condition_id)
                if field != "upstream_mediator":
                    invalid.append(batch_prefix + ":mediator_exception_must_use_upstream_mediator:" + condition_id)
                if mapped_entries != near_entry_ids:
                    invalid.append(batch_prefix + ":mediator_exception_must_map_near_miss_only:" + condition_id)
            entry_evidence_ids: dict[str, set[str]] = {}
            entry_observation_ids: dict[str, set[str]] = {}
            for record in condition_records:
                entry_evidence_ids.setdefault(record["entry_id"], set()).update(record["evidence_ids"])
                entry_observation_ids.setdefault(record["entry_id"], set()).update(record["observation_ids"])
            required_entries = expected_entries if role == "COMMON" else near_entry_ids
            for entry_id in sorted(required_entries):
                if not entry_evidence_ids.get(entry_id):
                    incomplete.append(
                        batch_prefix + ":condition_evidence_missing:" + condition_id + ":" + entry_id
                    )
                if not entry_observation_ids.get(entry_id):
                    incomplete.append(
                        batch_prefix + ":condition_observation_missing:" + condition_id + ":" + entry_id
                    )
            for left in sorted(required_entries):
                for right in sorted(required_entries):
                    if left >= right:
                        continue
                    shared_evidence = entry_evidence_ids.get(left, set()) & entry_evidence_ids.get(right, set())
                    if shared_evidence:
                        invalid.append(
                            batch_prefix + ":condition_evidence_reused_between_entries:"
                            + condition_id + ":" + left + ":" + right
                        )
                    shared_observations = entry_observation_ids.get(left, set()) & entry_observation_ids.get(right, set())
                    if shared_observations:
                        invalid.append(
                            batch_prefix + ":condition_observation_reused_between_entries:"
                            + condition_id + ":" + left + ":" + right
                        )
        if not common_condition_ids:
            incomplete.append(batch_prefix + ":common_possibility_condition_missing")
        if not mediator_condition_ids:
            incomplete.append(batch_prefix + ":mediator_exception_condition_missing")
        elif len(mediator_condition_ids) != 1:
            invalid.append(batch_prefix + ":mediator_exception_condition_must_be_unique")
    for record in records:
        if record["entry_id"] not in batch_entry_ids:
            invalid.append(record["prefix"] + ":entry_not_in_enabled_flywheel_batch")


def validate_case_selection_register(
    register: Any, *, output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a frozen cohort plan using only cutoff-available information."""
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(register, dict):
        return {
            "schema_version": "case-selection-register-validation.v1",
            "state": "INVALID", "status": "FAIL",
            "invalid_findings": ["register_not_object"], "incomplete_findings": [],
            "admissible_entry_ids": [], "outcome_selected_entry_ids": [],
            "judgment_flywheel_batch_ids": [],
        }
    if register.get("schema_version") != SCHEMA_VERSION:
        invalid.append("schema_version_invalid")
    if not str(register.get("register_id") or "").startswith("CSR:"):
        invalid.append("register_id_invalid")
    if not str(register.get("common_mechanism_question") or "").strip():
        incomplete.append("common_mechanism_question_missing")
    cutoff = _day(register.get("selection_information_cutoff"))
    if cutoff is None:
        invalid.append("selection_information_cutoff_invalid")
    universe_state_vector_fields: set[str] = set()
    universe = register.get("universe")
    if not isinstance(universe, dict):
        incomplete.append("universe_missing")
    else:
        for field in ("universe_id", "definition"):
            if not str(universe.get(field) or "").strip():
                incomplete.append("universe_" + field + "_missing")
        universe_as_of = _day(universe.get("as_of"))
        if universe_as_of is None:
            incomplete.append("universe_as_of_missing")
        elif cutoff is not None and universe_as_of > cutoff:
            invalid.append("universe_as_of_after_selection_cutoff")
        for field in ("candidate_company_ids", "state_vector_fields", "source_ids"):
            values = universe.get(field)
            if not isinstance(values, list) or not values or any(not str(item).strip() for item in values):
                incomplete.append("universe_" + field + "_missing")
            elif len({str(item) for item in values}) != len(values):
                invalid.append("universe_" + field + "_duplicate")
            elif field == "state_vector_fields":
                universe_state_vector_fields = {str(item) for item in values}

    entries = register.get("entries")
    if not isinstance(entries, list) or not entries:
        incomplete.append("entries_missing")
        entries = []
    entry_ids: set[str] = set()
    entries_by_id: dict[str, dict[str, Any]] = {}
    admissible: list[str] = []
    outcome_selected: list[str] = []
    for index, entry in enumerate(entries):
        prefix = f"entries[{index}]"
        if not isinstance(entry, dict):
            invalid.append(prefix + ":not_object")
            continue
        entry_id = str(entry.get("entry_id") or "")
        if not entry_id.startswith("CSRSEL:"):
            invalid.append(prefix + ":entry_id_invalid")
        elif entry_id in entry_ids:
            invalid.append("entry_id_duplicate:" + entry_id)
        entry_ids.add(entry_id)
        if entry_id and entry_id not in entries_by_id:
            entries_by_id[entry_id] = entry
        for field in ("company_id", "period_id"):
            if not str(entry.get(field) or "").strip():
                incomplete.append(prefix + ":" + field + "_missing")
        entry_cutoff = _day(entry.get("information_cutoff"))
        if entry_cutoff is None:
            invalid.append(prefix + ":information_cutoff_invalid")
        elif cutoff is not None and entry_cutoff > cutoff:
            invalid.append(prefix + ":information_cutoff_after_register_cutoff")
        state_vector_as_of = _day(entry.get("state_vector_as_of"))
        if state_vector_as_of is None:
            incomplete.append(prefix + ":state_vector_as_of_missing")
        elif entry_cutoff is not None and state_vector_as_of > entry_cutoff:
            invalid.append(prefix + ":state_vector_after_entry_cutoff")
        state_vector = entry.get("state_vector")
        if not isinstance(state_vector, dict) or not state_vector:
            incomplete.append(prefix + ":state_vector_missing")
        if entry.get("selection_mode") not in SELECTION_MODES:
            invalid.append(prefix + ":selection_mode_invalid")
        if entry.get("case_role") not in CASE_ROLES:
            invalid.append(prefix + ":case_role_invalid")
        arrow = entry.get("mechanism_arrow")
        if not isinstance(arrow, dict):
            incomplete.append(prefix + ":mechanism_arrow_missing")
        else:
            for field in ("arrow_id", "from", "to", "expected_difference"):
                if not str(arrow.get(field) or "").strip():
                    incomplete.append(prefix + ":mechanism_arrow_" + field + "_missing")
        exclusion = entry.get("exclusion")
        exclusion_status = ""
        if not isinstance(exclusion, dict):
            incomplete.append(prefix + ":exclusion_missing")
        else:
            exclusion_status = str(exclusion.get("status") or "")
            if exclusion_status not in EXCLUSION_STATUSES:
                invalid.append(prefix + ":exclusion_status_invalid")
            if not str(exclusion.get("reason") or "").strip():
                incomplete.append(prefix + ":exclusion_reason_missing")
        cluster = entry.get("cluster")
        if not isinstance(cluster, dict):
            incomplete.append(prefix + ":cluster_missing")
        else:
            for field in ("company_id", "period_cluster_id", "mechanism_cluster_id"):
                if not str(cluster.get(field) or "").strip():
                    incomplete.append(prefix + ":cluster_" + field + "_missing")
            if str(cluster.get("company_id") or "") and str(entry.get("company_id") or "") and cluster.get("company_id") != entry.get("company_id"):
                invalid.append(prefix + ":cluster_company_id_mismatch")
        isolation = str(entry.get("outcome_isolation") or "")
        if isolation not in OUTCOME_ISOLATIONS:
            invalid.append(prefix + ":outcome_isolation_invalid")
        elif isolation == "OUTCOME_SELECTED_RESEARCH_ONLY":
            outcome_selected.append(entry_id)
            if exclusion_status != "EXCLUDED":
                invalid.append(prefix + ":outcome_selected_must_be_excluded")
        elif isolation == "PIT_PRE_OUTCOME" and exclusion_status == "INCLUDED":
            admissible.append(entry_id)

    judgment_flywheel_batch_ids = _validate_judgment_flywheel_sampling(
        register,
        entries_by_id=entries_by_id,
        universe_state_vector_fields=universe_state_vector_fields,
        invalid=invalid,
        incomplete=incomplete,
    )
    _validate_possibility_condition_evidence(
        register,
        entries_by_id=entries_by_id,
        output=Path(output_dir) if output_dir is not None else None,
        invalid=invalid,
        incomplete=incomplete,
    )

    freeze = register.get("freeze")
    if not isinstance(freeze, dict):
        incomplete.append("freeze_missing")
    elif freeze.get("frozen") is not True:
        invalid.append("register_must_be_frozen")
    else:
        if _day(freeze.get("frozen_at")) is None:
            incomplete.append("freeze_frozen_at_missing")
        if freeze.get("fingerprint") != case_selection_register_fingerprint(register):
            invalid.append("freeze_fingerprint_mismatch")
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "schema_version": "case-selection-register-validation.v1",
        "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid, "incomplete_findings": incomplete,
        "admissible_entry_ids": sorted(admissible),
        "outcome_selected_entry_ids": sorted(outcome_selected),
        "judgment_flywheel_batch_ids": judgment_flywheel_batch_ids,
    }


def prepare_case_selection_register(register: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(register)
    payload.setdefault("schema_version", SCHEMA_VERSION)
    payload.setdefault("generated_at", _now())
    payload["freeze"] = {
        "frozen": True, "frozen_at": _now(), "fingerprint": "",
    }
    payload["freeze"]["fingerprint"] = case_selection_register_fingerprint(payload)
    return payload


def persist_case_selection_register(output_dir: str | Path, register: dict[str, Any]) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    path = output / REGISTER_FILE
    payload = prepare_case_selection_register(register)
    validation = validate_case_selection_register(payload, output_dir=output)
    if validation["state"] != "REVIEWABLE":
        return {"written": False, "path": str(path), "validation": validation}
    existing = _read(path)
    if existing:
        if case_selection_register_fingerprint(existing) == case_selection_register_fingerprint(payload):
            return {"written": True, "idempotent": True, "path": str(path), "register": existing, "validation": validate_case_selection_register(existing, output_dir=output)}
        return {"written": False, "path": str(path), "error": "frozen_case_selection_register_conflict", "validation": validation}
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"written": True, "idempotent": False, "path": str(path), "register": payload, "validation": validation}


def validate_output_case_selection(output_dir: str | Path) -> dict[str, Any]:
    """Return an explicit admission decision for a selected PIT output.

    Legacy and ordinary company reports have no selection reference and are
    intentionally ``SKIP``.  Once a contract references a register, it must
    use an entry that was frozen as ``PIT_PRE_OUTCOME``; an outcome-selected
    entry can remain useful for question discovery but cannot supply PIT
    evidence, a central path, or a forward-judgment calibration case.
    """
    output = Path(output_dir)
    contract = _read(output / "analysis_contract.json")
    reference = contract.get("case_selection")
    if reference is None:
        if contract.get("case_selection_required") is True:
            return {
                "state": "INCOMPLETE", "status": "FAIL", "invalid_findings": [],
                "incomplete_findings": ["case_selection_reference_required_for_this_cohort"],
                "admission": {
                    "pit_evidence": False, "central_path": False,
                    "forward_judgment_calibration": False,
                },
            }
        return {
            "state": "SKIP", "status": "SKIP", "invalid_findings": [],
            "incomplete_findings": [], "admission": {
                "pit_evidence": None, "central_path": None, "forward_judgment_calibration": None,
            },
        }
    invalid: list[str] = []
    incomplete: list[str] = []
    if not isinstance(reference, dict):
        invalid.append("case_selection_reference_not_object")
        reference = {}
    register_file = str(reference.get("register_file") or REGISTER_FILE)
    register = _read(output / register_file)
    validation = validate_case_selection_register(register, output_dir=output)
    if validation["state"] != "REVIEWABLE":
        invalid.extend("case_selection_register:" + item for item in validation["invalid_findings"])
        incomplete.extend("case_selection_register:" + item for item in validation["incomplete_findings"])
    register_id = str(reference.get("register_id") or "")
    fingerprint = str(reference.get("register_fingerprint") or "")
    entry_id = str(reference.get("entry_id") or "")
    if register_id != str(register.get("register_id") or ""):
        invalid.append("case_selection_register_id_mismatch")
    if fingerprint != str((register.get("freeze") or {}).get("fingerprint") or ""):
        invalid.append("case_selection_register_fingerprint_mismatch")
    entry = next(
        (item for item in register.get("entries") or [] if isinstance(item, dict) and item.get("entry_id") == entry_id),
        None,
    )
    if entry is None:
        invalid.append("case_selection_entry_missing")
        isolation = ""
    else:
        isolation = str(entry.get("outcome_isolation") or "")
    admission = {
        "pit_evidence": False, "central_path": False, "forward_judgment_calibration": False,
    }
    if isolation == "PIT_PRE_OUTCOME" and str(((entry or {}).get("exclusion") or {}).get("status") or "") == "INCLUDED":
        admission = {key: True for key in admission}
    elif isolation == "OUTCOME_SELECTED_RESEARCH_ONLY":
        invalid.append("outcome_selected_research_only_cannot_enter_pit_evidence_or_central_path_or_forward_judgment_calibration")
    elif entry is not None:
        invalid.append("case_selection_entry_not_admissible")
    invalid = list(dict.fromkeys(invalid))
    incomplete = list(dict.fromkeys(incomplete))
    state = "INVALID" if invalid else "INCOMPLETE" if incomplete else "REVIEWABLE"
    return {
        "state": state, "status": "FAIL" if state in {"INVALID", "INCOMPLETE"} else "PASS",
        "invalid_findings": invalid, "incomplete_findings": incomplete,
        "register_id": register_id, "entry_id": entry_id, "outcome_isolation": isolation,
        "register_fingerprint": str((register.get("freeze") or {}).get("fingerprint") or ""),
        "register_file": register_file,
        "admission": admission,
    }
