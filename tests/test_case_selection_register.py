from __future__ import annotations

import json
from pathlib import Path

from scripts.base_rate_case_library import build_candidate_cases_from_output
from scripts.case_selection_register import (
    case_selection_register_fingerprint,
    persist_case_selection_register,
    prepare_case_selection_register,
    validate_case_selection_register,
    validate_output_case_selection,
)
from scripts.claim_evidence import validate_claim_evidence_ledger
from scripts.thesis_test_gate import validate_thesis_test_ledger


FLYWHEEL_STATE_VECTOR_FIELDS = (
    "mechanism_domain", "current_state", "competitive_fork", "observable_symptom",
    "cycle_phase", "business_boundary", "result_metric", "upstream_mediator",
    "boundary_condition",
)


def _entry(
    entry_id: str,
    *,
    isolation: str = "PIT_PRE_OUTCOME",
    exclusion_status: str = "INCLUDED",
) -> dict:
    return {
        "entry_id": entry_id,
        "company_id": "COMPANY:001",
        "period_id": "2024Q4",
        "information_cutoff": "2025-03-31",
        "state_vector_as_of": "2025-03-31",
        "state_vector": {
            "channel_mix": "dealer-heavy",
            "capacity_utilization": "below prior peak",
        },
        "selection_mode": "MOST_SIMILAR",
        "case_role": "LITERAL_REPLICATION",
        "mechanism_arrow": {
            "arrow_id": "ARROW:channel-to-owner-cash",
            "from": "channel incentive change",
            "to": "cash conversion",
            "expected_difference": "inventory and retail sell-out lead the terminal cash outcome",
        },
        "exclusion": {
            "status": exclusion_status,
            "reason": "pre-cutoff state vector matches the pre-registered comparison rule",
        },
        "cluster": {
            "company_id": "COMPANY:001",
            "period_cluster_id": "2024Q4",
            "mechanism_cluster_id": "channel-incentive",
        },
        "outcome_isolation": isolation,
    }


def _register(*, outcome_selected: bool = False) -> dict:
    isolation = "OUTCOME_SELECTED_RESEARCH_ONLY" if outcome_selected else "PIT_PRE_OUTCOME"
    exclusion_status = "EXCLUDED" if outcome_selected else "INCLUDED"
    return {
        "schema_version": "case-selection-register.v1",
        "register_id": "CSR:home-appliance-channel.v1",
        "common_mechanism_question": "渠道激励变化是否先于终端需求和现金转换恶化？",
        "selection_information_cutoff": "2025-03-31",
        "universe": {
            "universe_id": "UNIV:domestic-appliance-listed",
            "definition": "截至 cutoff 可取得年度披露的国内家电公司",
            "as_of": "2025-03-31",
            "candidate_company_ids": ["COMPANY:001", "COMPANY:002"],
            "state_vector_fields": ["channel_mix", "capacity_utilization"],
            "source_ids": ["DOC:annual-2024", "DOC:exchange-2025-03"],
        },
        "entries": [_entry("CSRSEL:home-appliance:001", isolation=isolation, exclusion_status=exclusion_status)],
    }


def _bind_output(
    output: Path, register: dict, *, entry_id: str = "CSRSEL:home-appliance:001",
) -> None:
    output.mkdir(exist_ok=True)
    (output / "analysis_contract.json").write_text(json.dumps({
        "case_selection": {
            "register_id": register["register_id"],
            "register_fingerprint": register["freeze"]["fingerprint"],
            "entry_id": entry_id,
        },
    }), encoding="utf-8")


def _flywheel_entry(
    entry_id: str, company_id: str, *, upstream_mediator: str, boundary_condition: str,
) -> dict:
    entry = _entry(entry_id)
    entry["company_id"] = company_id
    entry["cluster"]["company_id"] = company_id
    entry["state_vector"] = {
        "mechanism_domain": "room-air-conditioner channel economics",
        "current_state": "channel inventory rising against retail sell-out",
        "competitive_fork": "demand weakness versus channel incentive pull-forward",
        "observable_symptom": "sell-in and sell-out divergence",
        "cycle_phase": "late replacement-cycle slowdown",
        "business_boundary": "domestic room-air-conditioner retail",
        "result_metric": "same-definition retailer sell-out volume",
        "upstream_mediator": upstream_mediator,
        "boundary_condition": boundary_condition,
    }
    return entry


def _flywheel_register() -> dict:
    register = _register()
    focal = _flywheel_entry(
        "CSRSEL:flywheel:focal", "COMPANY:001",
        upstream_mediator="channel incentive-driven sell-in", boundary_condition="multi-brand dealer channel",
    )
    near_miss = _flywheel_entry(
        "CSRSEL:flywheel:near", "COMPANY:002",
        upstream_mediator="retailer pull-through demand", boundary_condition="multi-brand dealer channel",
    )
    boundary = _flywheel_entry(
        "CSRSEL:flywheel:boundary", "COMPANY:003",
        upstream_mediator="channel incentive-driven sell-in", boundary_condition="project-based procurement channel",
    )
    register["universe"]["candidate_company_ids"] = ["COMPANY:001", "COMPANY:002", "COMPANY:003"]
    register["universe"]["state_vector_fields"] = list(FLYWHEEL_STATE_VECTOR_FIELDS)
    register["entries"] = [focal, near_miss, boundary]
    register["judgment_flywheel_sampling"] = {
        "enabled": True,
        "batches": [{
            "batch_id": "CSRFWB:room-ac-channel.v1",
            "members": [
                {"entry_id": focal["entry_id"], "role": "FOCAL"},
                {
                    "entry_id": near_miss["entry_id"], "role": "NEAR_MISS",
                    "focal_entry_id": focal["entry_id"], "upstream_mediator_relation": "OPPOSITE",
                },
                {
                    "entry_id": boundary["entry_id"], "role": "BOUNDARY_REPLICATION",
                    "focal_entry_id": focal["entry_id"],
                },
            ],
        }],
    }
    return register


def _write_flywheel_possibility_evidence(output: Path, register: dict) -> list[dict]:
    """Materialize only the canonical ledgers that a frozen mapping indexes."""
    output.mkdir(parents=True, exist_ok=True)
    raw_facts: list[dict] = []
    observations: list[dict] = []
    documents: list[dict] = []
    mappings: list[dict] = []

    conditions = [
        ("PCOND:shared-mechanism-domain", "COMMON", "mechanism_domain"),
    ]
    for entry in register["entries"]:
        if entry["entry_id"] == "CSRSEL:flywheel:near":
            conditions.append(("PCOND:near-upstream-mediator", "MEDIATOR_EXCEPTION", "upstream_mediator"))
        for condition_id, role, field in conditions:
            suffix = f"{entry['entry_id'].rsplit(':', 1)[-1]}:{condition_id.rsplit(':', 1)[-1]}"
            evidence_id = "EVD:condition:" + suffix
            observation_id = "OBS:condition:" + suffix
            source_id = "DOC:condition:" + suffix
            raw_facts.append({
                "evidence_id": evidence_id,
                "observation_id": observation_id,
                "source_id": source_id,
                "source_group_id": "LINEAGE:condition:" + suffix,
                "fact": f"{entry['company_id']} 的 {field} 截至 cutoff 已被官方披露。",
                "authority": "company_filing",
                "claim_distance": "raw_data",
                "published_at": "2025-03-20",
                "data_as_of": "2025-03-15",
                "direct_support": True,
                "support_type": "supports",
                "basis_match": "exact",
                "conflict_of_interest": "公司披露；仅用于验证可比条件的存在。",
            })
            observations.append({
                "observation_id": observation_id,
                "doc_id": source_id,
                "status": "VERIFIED",
                "as_of": "2025-03-15",
            })
            documents.append({
                "doc_id": source_id,
                "authority": "company_filing",
                "published_at": "2025-03-20",
            })
            mappings.append({
                "entry_id": entry["entry_id"],
                "condition_id": condition_id,
                "role": role,
                "state_vector_field": field,
                "evidence_refs": [{
                    "evidence_id": evidence_id,
                    "observation_id": observation_id,
                    "source_id": source_id,
                    "cutoff_at": entry["information_cutoff"],
                    "as_of": "2025-03-15",
                }],
            })
        conditions = [("PCOND:shared-mechanism-domain", "COMMON", "mechanism_domain")]
    (output / "claim_evidence.json").write_text(json.dumps({
        "claims": [{"claim_id": "claim.possibility-conditions", "raw_facts": raw_facts}],
    }), encoding="utf-8")
    (output / "fact_observations.json").write_text(json.dumps({"observations": observations}), encoding="utf-8")
    (output / "document_manifest.json").write_text(json.dumps({"documents": documents}), encoding="utf-8")
    register["possibility_condition_evidence"] = {"mappings": mappings}
    return mappings


def test_register_freezes_pre_cutoff_universe_state_vector_and_selection_roles(tmp_path: Path) -> None:
    prepared = prepare_case_selection_register(_register())
    validation = validate_case_selection_register(prepared)
    assert validation["state"] == "REVIEWABLE"
    assert validation["admissible_entry_ids"] == ["CSRSEL:home-appliance:001"]
    saved = persist_case_selection_register(tmp_path, _register())
    assert saved["written"] is True
    assert case_selection_register_fingerprint(saved["register"]) == saved["register"]["freeze"]["fingerprint"]
    changed = _register()
    changed["entries"][0]["selection_mode"] = "DIVERSE"
    assert persist_case_selection_register(tmp_path, changed)["error"] == "frozen_case_selection_register_conflict"


def test_register_allows_cutoff_state_names_and_requires_outcome_selected_exclusion() -> None:
    register = _register()
    register["entries"][0]["state_vector"]["actual_channel_mix_at_cutoff"] = "dealer-heavy"
    assert validate_case_selection_register(prepare_case_selection_register(register))["state"] == "REVIEWABLE"
    selected = _register(outcome_selected=True)
    selected["entries"][0]["exclusion"]["status"] = "INCLUDED"
    result = validate_case_selection_register(prepare_case_selection_register(selected))
    assert "entries[0]:outcome_selected_must_be_excluded" in result["invalid_findings"]


def test_explicit_judgment_flywheel_batch_requires_a_comparable_three_company_pairing() -> None:
    result = validate_case_selection_register(prepare_case_selection_register(_flywheel_register()))

    assert result["state"] == "REVIEWABLE"
    assert result["judgment_flywheel_batch_ids"] == ["CSRFWB:room-ac-channel.v1"]


def test_judgment_flywheel_universe_must_preserve_every_screened_company() -> None:
    hidden_candidate = _flywheel_register()
    hidden_candidate["universe"]["candidate_company_ids"].append("COMPANY:004")
    hidden_result = validate_case_selection_register(prepare_case_selection_register(hidden_candidate))

    assert hidden_result["state"] == "INVALID"
    assert (
        "judgment_flywheel_sampling:universe_candidate_without_screen_entry:COMPANY:004"
        in hidden_result["invalid_findings"]
    )

    outside_candidate = _flywheel_register()
    outside_candidate["universe"]["candidate_company_ids"].remove("COMPANY:003")
    outside_result = validate_case_selection_register(prepare_case_selection_register(outside_candidate))

    assert outside_result["state"] == "INVALID"
    assert (
        "judgment_flywheel_sampling:screen_entry_company_outside_universe:COMPANY:003"
        in outside_result["invalid_findings"]
    )


def test_judgment_flywheel_near_miss_must_isolate_only_the_upstream_mediator() -> None:
    register = _flywheel_register()
    register["entries"][1]["state_vector"]["observable_symptom"] = "promotion-driven sell-out spike"

    result = validate_case_selection_register(prepare_case_selection_register(register))

    assert result["state"] == "INVALID"
    assert "judgment_flywheel_sampling.batches[0]:near_miss_observable_symptom_must_match_focal" in result["invalid_findings"]


def test_judgment_flywheel_near_miss_cannot_vary_a_shared_extra_state_vector_field() -> None:
    register = _flywheel_register()
    register["entries"][0]["state_vector"]["channel_structure"] = "dealer-led"
    register["entries"][1]["state_vector"]["channel_structure"] = "direct-led"
    register["entries"][2]["state_vector"]["channel_structure"] = "project-led"
    register["universe"]["state_vector_fields"].append("channel_structure")

    result = validate_case_selection_register(prepare_case_selection_register(register))

    assert result["state"] == "INVALID"
    assert "judgment_flywheel_sampling.batches[0]:near_miss_channel_structure_must_match_focal" in result["invalid_findings"]


def test_judgment_flywheel_boundary_replication_must_isolate_only_the_boundary_condition() -> None:
    register = _flywheel_register()
    register["entries"][2]["state_vector"]["current_state"] = "channel inventory falling against retail sell-out"

    result = validate_case_selection_register(prepare_case_selection_register(register))

    assert result["state"] == "INVALID"
    assert "judgment_flywheel_sampling.batches[0]:boundary_replication_current_state_must_match_focal" in result["invalid_findings"]


def test_judgment_flywheel_rejects_unpaired_or_result_selected_comparisons() -> None:
    register = _flywheel_register()
    register["entries"][1]["state_vector"]["upstream_mediator"] = register["entries"][0]["state_vector"]["upstream_mediator"]
    register["entries"][2]["state_vector"]["boundary_condition"] = register["entries"][0]["state_vector"]["boundary_condition"]
    register["entries"][2]["outcome_isolation"] = "OUTCOME_SELECTED_RESEARCH_ONLY"
    register["entries"][2]["exclusion"]["status"] = "EXCLUDED"
    register["entries"][2]["company_id"] = "COMPANY:001"
    register["entries"][2]["cluster"]["company_id"] = "COMPANY:001"
    register["entries"][0]["state_vector"]["data_availability_score"] = 99
    register["judgment_flywheel_sampling"]["batches"][0]["members"][1]["data_availability_score"] = 99
    register["judgment_flywheel_sampling"]["batches"][0]["members"][2]["focal_entry_id"] = "CSRSEL:flywheel:near"

    result = validate_case_selection_register(prepare_case_selection_register(register))

    assert result["state"] == "INVALID"
    assert "judgment_flywheel_sampling.batches[0].members[1]:unsupported_field:data_availability_score" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0].members[0]:state_vector_field_prohibited:data_availability_score" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0].members[2]:entry_must_be_pit_pre_outcome_and_included" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0]:members_must_use_three_distinct_companies" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0]:boundary_replication_must_link_focal" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0]:near_miss_upstream_mediator_must_differ_from_focal" in result["invalid_findings"]
    assert "judgment_flywheel_sampling.batches[0]:boundary_replication_boundary_condition_must_differ_from_focal" in result["invalid_findings"]


def test_judgment_flywheel_cannot_omit_any_comparable_state_vector_dimension() -> None:
    register = _flywheel_register()
    for entry in register["entries"]:
        entry["state_vector"].pop("result_metric")

    result = validate_case_selection_register(prepare_case_selection_register(register))

    assert result["state"] == "INCOMPLETE"
    assert "judgment_flywheel_sampling.batches[0].members[0]:state_vector_field_missing:result_metric" in result["incomplete_findings"]


def test_enabled_flywheel_persistence_and_output_admission_require_frozen_possibility_condition_evidence(tmp_path: Path) -> None:
    output = tmp_path / "output"
    missing = persist_case_selection_register(output, _flywheel_register())

    assert missing["written"] is False
    assert "judgment_flywheel_sampling:possibility_condition_evidence_missing" in missing["validation"]["incomplete_findings"]

    register = _flywheel_register()
    _write_flywheel_possibility_evidence(output, register)
    saved = persist_case_selection_register(output, register)

    assert saved["written"] is True
    _bind_output(output, saved["register"], entry_id="CSRSEL:flywheel:focal")
    assert validate_output_case_selection(output)["state"] == "REVIEWABLE"
    claim_ledger = json.loads((output / "claim_evidence.json").read_text(encoding="utf-8"))
    claim_ledger["claims"][0]["raw_facts"][0]["published_at"] = "2025-04-01"
    (output / "claim_evidence.json").write_text(json.dumps(claim_ledger), encoding="utf-8")

    stale_evidence = validate_output_case_selection(output)

    assert stale_evidence["state"] == "INVALID"
    assert any(item.endswith(":evidence_published_after_cutoff") for item in stale_evidence["invalid_findings"])


def test_flywheel_condition_mapping_rejects_unresolved_post_cutoff_and_outcome_injection(tmp_path: Path) -> None:
    output = tmp_path / "output"
    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    mappings[0]["evidence_refs"][0]["evidence_id"] = "EVD:unresolved-placeholder"

    unresolved = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert unresolved["state"] == "INVALID"
    assert any(item.endswith(":evidence_unknown") for item in unresolved["invalid_findings"])

    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    evidence_id = mappings[0]["evidence_refs"][0]["evidence_id"]
    claim_ledger = json.loads((output / "claim_evidence.json").read_text(encoding="utf-8"))
    next(fact for fact in claim_ledger["claims"][0]["raw_facts"] if fact["evidence_id"] == evidence_id)["published_at"] = "2025-04-01"
    (output / "claim_evidence.json").write_text(json.dumps(claim_ledger), encoding="utf-8")

    post_cutoff = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert post_cutoff["state"] == "INVALID"
    assert any(item.endswith(":evidence_published_after_cutoff") for item in post_cutoff["invalid_findings"])

    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    mappings[0]["evidence_refs"][0]["outcome_event_id"] = "CASEEV:post-outcome-result"

    outcome_injection = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert outcome_injection["state"] == "INVALID"
    assert any(item.endswith(":unsupported_field:outcome_event_id") for item in outcome_injection["invalid_findings"])


def test_flywheel_common_conditions_need_three_precise_entry_bindings_but_can_share_an_industry_source(tmp_path: Path) -> None:
    output = tmp_path / "output"
    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    register["possibility_condition_evidence"]["mappings"] = [
        row for row in mappings
        if not (row["entry_id"] == "CSRSEL:flywheel:near" and row["role"] == "COMMON")
    ]

    one_side_missing = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert one_side_missing["state"] == "INCOMPLETE"
    assert "judgment_flywheel_sampling.batches[0]:condition_entry_mapping_missing:PCOND:shared-mechanism-domain:CSRSEL:flywheel:near" in one_side_missing["incomplete_findings"]

    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    for row in mappings:
        if row["role"] == "COMMON":
            row["state_vector_field"] = "boundary_condition"

    not_common = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert not_common["state"] == "INVALID"
    assert "judgment_flywheel_sampling.batches[0]:common_condition_state_vector_must_match:PCOND:shared-mechanism-domain" in not_common["invalid_findings"]

    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    claim_ledger = json.loads((output / "claim_evidence.json").read_text(encoding="utf-8"))
    common_rows = [row for row in mappings if row["role"] == "COMMON"]
    shared_source_id = common_rows[0]["evidence_refs"][0]["source_id"]
    for row in common_rows:
        reference = row["evidence_refs"][0]
        fact = next(
            item for item in claim_ledger["claims"][0]["raw_facts"]
            if item["evidence_id"] == reference["evidence_id"]
        )
        fact.update({
            "source_id": shared_source_id,
            "source_group_id": "LINEAGE:industry-cycle",
        })
        reference["source_id"] = shared_source_id
    (output / "claim_evidence.json").write_text(json.dumps(claim_ledger), encoding="utf-8")
    observations = json.loads((output / "fact_observations.json").read_text(encoding="utf-8"))
    for row in common_rows:
        reference = row["evidence_refs"][0]
        next(
            item for item in observations["observations"]
            if item["observation_id"] == reference["observation_id"]
        )["doc_id"] = shared_source_id
    (output / "fact_observations.json").write_text(json.dumps(observations), encoding="utf-8")

    shared_industry_source = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert shared_industry_source["state"] == "REVIEWABLE"

    focal_ref, near_ref = (row["evidence_refs"][0] for row in common_rows[:2])
    near_ref.update({
        "evidence_id": focal_ref["evidence_id"],
        "observation_id": focal_ref["observation_id"],
        "source_id": focal_ref["source_id"],
    })
    reused_binding = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert reused_binding["state"] == "INVALID"
    assert any(
        item.startswith("judgment_flywheel_sampling.batches[0]:condition_evidence_reused_between_entries:PCOND:shared-mechanism-domain")
        for item in reused_binding["invalid_findings"]
    )
    assert any(
        item.startswith("judgment_flywheel_sampling.batches[0]:condition_observation_reused_between_entries:PCOND:shared-mechanism-domain")
        for item in reused_binding["invalid_findings"]
    )


def test_flywheel_near_miss_mediator_exception_requires_its_own_mapping(tmp_path: Path) -> None:
    output = tmp_path / "output"
    register = _flywheel_register()
    mappings = _write_flywheel_possibility_evidence(output, register)
    register["possibility_condition_evidence"]["mappings"] = [
        row for row in mappings if row["role"] != "MEDIATOR_EXCEPTION"
    ]

    result = validate_case_selection_register(prepare_case_selection_register(register), output_dir=output)

    assert result["state"] == "INCOMPLETE"
    assert "judgment_flywheel_sampling.batches[0]:mediator_exception_condition_missing" in result["incomplete_findings"]


def test_outcome_selected_entry_is_blocked_from_pit_evidence_central_path_and_fj_calibration(tmp_path: Path) -> None:
    output = tmp_path / "output"
    saved = persist_case_selection_register(output, _register(outcome_selected=True))
    assert saved["written"] is True
    _bind_output(output, saved["register"])

    admission = validate_output_case_selection(output)
    assert admission["state"] == "INVALID"
    assert admission["admission"] == {
        "pit_evidence": False, "central_path": False, "forward_judgment_calibration": False,
    }
    finding = "outcome_selected_research_only_cannot_enter_pit_evidence_or_central_path_or_forward_judgment_calibration"
    assert finding in admission["invalid_findings"]
    assert build_candidate_cases_from_output(output, library_dir=tmp_path / "library")["error"] == "case_selection_not_admissible_for_forward_judgment_calibration"
    claim = validate_claim_evidence_ledger({}, output_dir=output)
    assert "case_selection:" + finding in claim["invalid_findings"]
    thesis = validate_thesis_test_ledger({}, output_dir=output)
    assert "case_selection:" + finding in thesis["invalid_findings"]


def test_cohort_contract_cannot_omit_its_selection_reference(tmp_path: Path) -> None:
    (tmp_path / "analysis_contract.json").write_text(
        json.dumps({"case_selection_required": True}), encoding="utf-8"
    )
    result = validate_output_case_selection(tmp_path)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["case_selection_reference_required_for_this_cohort"]
