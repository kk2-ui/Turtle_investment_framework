from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import judgment_historical_training as history
from tests.test_judgment_selection_discovery import _stage0_static_package


ROOT = Path(__file__).resolve().parents[1]
H1_RECEIPT_REF = {
    "receipt_id": "H1:SYNTHETIC:COHORT:V1",
    "receipt_version": 1,
}


def _cutoff_visible_lifecycle_event(
    *, subject_id: str, event_id: str, event_type: str, observation_status: str,
    effective_at: str, source_available_at: str, absorbing_for: list[str],
    information_role: str = "CUTOFF_VISIBLE",
) -> dict:
    return {
        "schema_version": history.LIFECYCLE_SCHEMA_VERSION,
        "lifecycle_event_id": event_id,
        "subject_id": subject_id,
        "event_type": event_type,
        "effective_at": effective_at,
        "known_at": effective_at,
        "source_available_at": source_available_at,
        "source": {
            "source_id": f"STATIC:SYNTHETIC:{event_id}",
            "source_type": "OFFICIAL_COMPANY_DISCLOSURE",
            "url": "https://static.cninfo.com.cn/finalpage/2021-03-02/123456.PDF",
            "published_at": source_available_at,
            "field_ref": "Synthetic lifecycle disclosure PDF p12.",
            "source_subject_id": subject_id,
        },
        "information_role": information_role,
        "observation_status": observation_status,
        "absorbing_for": absorbing_for,
        "successor_subject_id": None,
        "identity_mappings": [
            {"identity_kind": "ECONOMIC_ENTITY", "identity_id": subject_id, "effective_from": "2013-01-01T00:00:00+08:00", "effective_through": "2020-01-01T00:00:00+08:00"},
            {"identity_kind": "LEGAL_ENTITY", "identity_id": f"LEGAL:{subject_id}", "effective_from": "2013-01-01T00:00:00+08:00", "effective_through": "2020-01-01T00:00:00+08:00"},
            {"identity_kind": "LISTED_SECURITY", "identity_id": f"SECURITY:{subject_id}", "effective_from": "2013-01-01T00:00:00+08:00", "effective_through": "2020-01-01T00:00:00+08:00"},
            {"identity_kind": "REPORTING_PERIMETER", "identity_id": f"PERIMETER:{subject_id}", "effective_from": "2013-01-01T00:00:00+08:00", "effective_through": "2020-01-01T00:00:00+08:00"},
        ],
        "time_origin": "2013-01-01T00:00:00+08:00",
        "observation_entry_at": "2014-01-01T00:00:00+08:00",
        "risk_start_at": "2014-01-01T00:00:00+08:00",
        "interval_start": "2014-01-01T00:00:00+08:00",
        "interval_stop": "2020-01-01T00:00:00+08:00",
        "covariate_as_of": "2013-12-31T00:00:00+08:00",
        "object_class": "LIFECYCLE_CASE",
        "claim_class": "LIFECYCLE_TRANSITION",
        "allowed_outputs": ["LIFECYCLE_ONLY", "RESEARCH_AGENDA"],
    }


def _projected_synthetic_seed() -> dict:
    result = history.project_stage0_h1_to_universe_and_carrier_seed(
        _stage0_static_package(), h1_receipt_ref=H1_RECEIPT_REF,
    )
    assert result["valid"], result["findings"]
    return result


def _predicate(registry: dict) -> dict:
    return {
        "predicate_id": "PREDICATE:SYNTHETIC:NETWORK:V1",
        "frozen_at": "2020-10-31T23:59:59+08:00",
        "action_screen_receipt_ref": {
            "receipt_id": "H2:SYNTHETIC:NETWORK:V1",
            "receipt_version": 1,
        },
        "mechanism_topology": registry["mechanism_topology"],
        "competitive_arena_id": registry["competitive_arena_id"],
        "source_cutoff_at": "2020-12-31T23:59:59+08:00",
        "selection_rule": "ALL_MATCHING_PREDECLARED_ROSTER",
        "requires_independent_control": True,
        "excludes_break_dispositions": ["KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"],
        "outcome_access_prohibited": True,
        "peer_recruitment_population": [{
            "company_id": "CN:SYNTHETIC:PEER-EXTRA",
            "issuer_id": "ISSUER:CN:SYNTHETIC:PEER-EXTRA",
            "control_group_id": "CONTROL:SYNTHETIC:PEER-EXTRA",
            "responsibility_unit_id": "UNIT:SYNTHETIC:PEER-EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "eligibility_decision": "ELIGIBLE",
            "exclusion_reason": None,
        }],
    }


def _recruitment_batch(registry: dict) -> dict:
    predicate = registry["peer_recruitment_predicate"]
    reference = {
        "receipt_id": "STATIC-PEER-BATCH:SYNTHETIC:V1",
        "receipt_version": 1,
    }
    return {
        "schema_version": history.CARRIER_REGISTRY_SCHEMA_VERSION,
        "batch_id": "BATCH:SYNTHETIC:PEER-RECRUITMENT:V1",
        "source_packet_ref": reference,
        "eligibility_predicate_id": predicate["predicate_id"],
        "received_at": "2020-11-01T10:00:00+08:00",
        "curator_id": "CURATOR:SYNTHETIC:H1-H2",
        "static_sources": [{
            "source_id": "STATIC:SYNTHETIC:PEER-EXTRA:ANNUAL",
            "url": "https://static.cninfo.com.cn/finalpage/2020-03-30/123456.PDF",
            "published_at": "2020-03-30T00:00:00+08:00",
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "issuer_id": "ISSUER:CN:SYNTHETIC:PEER-EXTRA",
            "responsibility_unit_id": "UNIT:SYNTHETIC:PEER-EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "period_end": "2019-12-31",
            "field_refs": ["Synthetic official annual report PDF p12."],
        }],
        "carrier_static_coverage": [{
            "carrier_id": "CARRIER:SYNTHETIC:PEER-EXTRA",
            "period_end": "2019-12-31",
            "field_id": "owner_cash_input",
            "source_id": "STATIC:SYNTHETIC:PEER-EXTRA:ANNUAL",
            "field_ref": "Synthetic official annual report PDF p12.",
        }],
        "eligibility_population": [{
            "company_id": "CN:SYNTHETIC:PEER-EXTRA",
            "issuer_id": "ISSUER:CN:SYNTHETIC:PEER-EXTRA",
            "control_group_id": "CONTROL:SYNTHETIC:PEER-EXTRA",
            "responsibility_unit_id": "UNIT:SYNTHETIC:PEER-EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "eligibility_decision": "ELIGIBLE",
            "exclusion_reason": None,
        }],
        "carriers": [{
            "carrier_id": "CARRIER:SYNTHETIC:PEER-EXTRA",
            "batch_id": "BATCH:SYNTHETIC:PEER-RECRUITMENT:V1",
            "company_id": "CN:SYNTHETIC:PEER-EXTRA",
            "issuer_id": "ISSUER:CN:SYNTHETIC:PEER-EXTRA",
            "control_group_id": "CONTROL:SYNTHETIC:PEER-EXTRA",
            "responsibility_unit_id": "UNIT:SYNTHETIC:PEER-EXTRA",
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
            "disposition": "ELIGIBLE_FOR_COMPARATIVE",
            "source_packet_ref": reference,
            "static_source_ids": ["STATIC:SYNTHETIC:PEER-EXTRA:ANNUAL"],
            "eligibility_predicate_id": predicate["predicate_id"],
            "seed_disposition": None,
        }],
    }


def _resolve_all_pending(registry: dict) -> dict:
    predicate_id = registry["peer_recruitment_predicate"]["predicate_id"]
    resolutions = [{
        "carrier_id": carrier["carrier_id"],
        "disposition": "ELIGIBLE_FOR_COMPARATIVE",
        "eligibility_predicate_id": predicate_id,
    } for carrier in registry["carriers"] if carrier["disposition"] == "PENDING_ACTION_WINDOW_REVIEW"]
    result = history.resolve_pending_carrier_eligibility(registry, resolutions)
    assert result["valid"], result["findings"]
    return result["carrier_registry"]


def test_real_cement_h1_projects_five_universe_carriers_and_keeps_breaks() -> None:
    package = json.loads((
        ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    ).read_text(encoding="utf-8"))
    result = history.project_stage0_h1_to_universe_and_carrier_seed(
        package,
        h1_receipt_ref={
            "receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1",
            "receipt_version": 1,
        },
    )

    assert result["valid"], result["findings"]
    assert result["universe_snapshot"]["coverage_status"] == "BOUNDED_PARTIAL"
    assert len(result["universe_snapshot"]["members"]) == 5
    carriers = result["carrier_registry"]["carriers"]
    assert {carrier["company_id"] for carrier in carriers} == {
        "CN:600585", "CN:600801", "CN:000401", "CN:600425", "CN:600802",
    }
    assert sum(carrier["disposition"] == "PENDING_ACTION_WINDOW_REVIEW" for carrier in carriers) == 3
    assert sum(carrier["disposition"] == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK" for carrier in carriers) == 2
    assert result["carrier_registry"]["state"] == "OPEN"
    forged = deepcopy(result["carrier_registry"])
    next(carrier for carrier in forged["carriers"] if carrier["company_id"] == "CN:600801")["disposition"] = "ELIGIBLE_FOR_COMPARATIVE"
    forged_result = history.validate_evidence_carrier_registry(forged)
    assert not forged_result["valid"]
    assert "registry.carriers[1].known_material_break_cannot_gain_comparative_eligibility" in forged_result["findings"]


def test_real_cement_h1_builds_multi_cutoff_history_without_retrospective_backfill() -> None:
    package = json.loads((
        ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    ).read_text(encoding="utf-8"))
    receipt = {
        "receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1",
        "receipt_version": 1,
    }
    default_series = history.build_industry_history_series_from_h1(package, h1_receipt_ref=receipt)
    assert default_series["valid"], default_series["findings"]
    series = default_series["industry_history_series"]
    assert series["schema_version"] == history.HISTORY_SERIES_SCHEMA_VERSION
    assert len(series["snapshots"]) == 6
    assert [snapshot["cutoff_at"] for snapshot in series["snapshots"]] == series["cutoffs"]
    assert all(len(snapshot["members"]) == 5 for snapshot in series["snapshots"])
    assert history.validate_industry_history_series(series)["valid"]

    early_and_late = history.build_industry_history_series_from_h1(
        package,
        h1_receipt_ref=receipt,
        cutoffs=["2014-04-01T00:00:00+08:00", "2014-05-01T00:00:00+08:00"],
    )
    assert early_and_late["valid"], early_and_late["findings"]
    snapshots = early_and_late["industry_history_series"]["snapshots"]
    early = {member["company_id"] for member in snapshots[0]["members"]}
    late = {member["company_id"] for member in snapshots[1]["members"]}
    assert early == {"CN:600585", "CN:600801", "CN:600802"}
    assert late == {"CN:600585", "CN:600801", "CN:000401", "CN:600425", "CN:600802"}
    assert "CN:000401" not in early and "CN:000401" in late


def test_history_series_applies_only_cutoff_visible_lifecycle_facts_to_later_snapshots() -> None:
    package = json.loads((
        ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    ).read_text(encoding="utf-8"))
    events = [
        _cutoff_visible_lifecycle_event(
            subject_id="ECONOMIC_ENTITY:CN:600585",
            event_id="LIFECYCLE:SYNTHETIC:CEMENT:CENSORED",
            event_type="DATA_CENSORED",
            observation_status="CENSORED",
            effective_at="2016-04-01T00:00:00+08:00",
            source_available_at="2016-04-01T00:00:00+08:00",
            absorbing_for=["LISTED_SECURITY"],
        ),
        _cutoff_visible_lifecycle_event(
            subject_id="ECONOMIC_ENTITY:CN:600801",
            event_id="LIFECYCLE:SYNTHETIC:CEMENT:POST_CUTOFF_ONLY",
            event_type="DATA_CENSORED",
            observation_status="CENSORED",
            effective_at="2016-04-01T00:00:00+08:00",
            source_available_at="2016-04-01T00:00:00+08:00",
            absorbing_for=["LISTED_SECURITY"],
            information_role="POST_CUTOFF_CONTEXT",
        ),
    ]
    result = history.build_industry_history_series_from_h1(
        package,
        h1_receipt_ref={
            "receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1",
            "receipt_version": 1,
        },
        cutoffs=["2015-05-01T00:00:00+08:00", "2016-05-01T00:00:00+08:00"],
        lifecycle_events=events,
    )
    assert result["valid"], result["findings"]
    first, second = result["industry_history_series"]["snapshots"]
    first_status = {member["company_id"]: member["risk_status"] for member in first["members"]}
    second_status = {member["company_id"]: member["risk_status"] for member in second["members"]}
    assert first_status["CN:600585"] == "IN_RISK_SET"
    assert second_status["CN:600585"] == "CENSORED"
    assert second_status["CN:600801"] == "IN_RISK_SET"

    invalid = history.build_industry_history_series_from_h1(
        package,
        h1_receipt_ref={
            "receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1",
            "receipt_version": 1,
        },
        cutoffs=["2018-05-01T00:00:00+08:00", "2018-04-01T00:00:00+08:00"],
    )
    assert not invalid["valid"]
    assert "history_series.cutoffs[0]_cannot_follow_h1_selection_as_of" in invalid["findings"]
    assert "history_series.cutoffs_must_be_strictly_increasing" in invalid["findings"]


def test_delayed_entry_and_lifecycle_censoring_do_not_become_losses_or_pit_facts() -> None:
    projection = _projected_synthetic_seed()
    universe = deepcopy(projection["universe_snapshot"])
    universe["members"][0]["risk_start_at"] = "2020-06-29T23:59:59+08:00"
    invalid_universe = history.validate_industry_history_universe_snapshot(universe)
    assert not invalid_universe["valid"]
    assert "universe.members[0].risk_start_at_cannot_precede_observation_entry_at" in invalid_universe["findings"]

    lifecycle = {
        "schema_version": history.LIFECYCLE_SCHEMA_VERSION,
        "lifecycle_event_id": "LIFECYCLE:SYNTHETIC:CENSORED",
        "subject_id": "ECONOMIC_ENTITY:CN:SYNTHETIC",
        "event_type": "DATA_CENSORED",
        "effective_at": "2021-01-01T00:00:00+08:00",
        "known_at": "2021-01-02T00:00:00+08:00",
        "source_available_at": "2021-01-03T00:00:00+08:00",
        "source": {
            "source_id": "STATIC:SYNTHETIC:CENSORED",
            "source_type": "OFFICIAL_COMPANY_DISCLOSURE",
            "url": "https://static.cninfo.com.cn/finalpage/2021-01-03/123456.PDF",
            "published_at": "2021-01-03T00:00:00+08:00",
            "field_ref": "Synthetic lifecycle disclosure PDF p12.",
            "source_subject_id": "ECONOMIC_ENTITY:CN:SYNTHETIC",
        },
        "information_role": "POST_CUTOFF_CONTEXT",
        "observation_status": "CENSORED",
        "absorbing_for": ["LISTED_SECURITY"],
        "successor_subject_id": "ECONOMIC_ENTITY:CN:SYNTHETIC:SUCCESSOR",
        "identity_mappings": [
            {"identity_kind": "ECONOMIC_ENTITY", "identity_id": "ECONOMIC_ENTITY:CN:SYNTHETIC", "effective_from": "2019-01-01T00:00:00+08:00", "effective_through": "2021-01-01T00:00:00+08:00"},
            {"identity_kind": "LEGAL_ENTITY", "identity_id": "LEGAL_ENTITY:CN:SYNTHETIC", "effective_from": "2019-01-01T00:00:00+08:00", "effective_through": "2021-01-01T00:00:00+08:00"},
            {"identity_kind": "LISTED_SECURITY", "identity_id": "LISTED_SECURITY:CN:SYNTHETIC", "effective_from": "2019-01-01T00:00:00+08:00", "effective_through": "2021-01-01T00:00:00+08:00"},
            {"identity_kind": "REPORTING_PERIMETER", "identity_id": "PERIMETER:CN:SYNTHETIC", "effective_from": "2019-01-01T00:00:00+08:00", "effective_through": "2021-01-01T00:00:00+08:00"},
            {"identity_kind": "SUCCESSOR_ENTITY", "identity_id": "ECONOMIC_ENTITY:CN:SYNTHETIC:SUCCESSOR", "effective_from": "2021-01-01T00:00:00+08:00", "effective_through": "2022-01-01T00:00:00+08:00"},
        ],
        "time_origin": "2019-01-01T00:00:00+08:00",
        "observation_entry_at": "2020-01-01T00:00:00+08:00",
        "risk_start_at": "2020-01-01T00:00:00+08:00",
        "interval_start": "2020-01-01T00:00:00+08:00",
        "interval_stop": "2021-01-01T00:00:00+08:00",
        "covariate_as_of": "2019-12-31T00:00:00+08:00",
        "object_class": "LIFECYCLE_CASE",
        "claim_class": "LIFECYCLE_TRANSITION",
        "allowed_outputs": ["LIFECYCLE_ONLY", "RESEARCH_AGENDA"],
    }
    assert history.validate_lifecycle_event(lifecycle, pit_cutoff_at="2020-12-31T23:59:59+08:00")["valid"]
    leaked = deepcopy(lifecycle)
    leaked["information_role"] = "CUTOFF_VISIBLE"
    invalid_lifecycle = history.validate_lifecycle_event(leaked, pit_cutoff_at="2020-12-31T23:59:59+08:00")
    assert not invalid_lifecycle["valid"]
    assert "lifecycle.cutoff_visible_source_cannot_follow_pit_cutoff" in invalid_lifecycle["findings"]
    source_drift = deepcopy(lifecycle)
    source_drift["source"]["published_at"] = "2021-01-04T00:00:00+08:00"
    source_drift["source"]["field_ref"] = "Synthetic lifecycle disclosure PDF appendix."
    invalid_source = history.validate_lifecycle_event(source_drift)
    assert not invalid_source["valid"]
    assert "lifecycle.source.published_at_must_match_source_available_at" in invalid_source["findings"]
    assert "lifecycle.source.field_ref_must_be_paged_pdf_reference" in invalid_source["findings"]


def test_terminal_lifecycle_event_cannot_be_reopened_by_later_survived_event() -> None:
    package = json.loads((
        ROOT / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    ).read_text(encoding="utf-8"))
    subject_id = "ECONOMIC_ENTITY:CN:600585"
    liquidation = _cutoff_visible_lifecycle_event(
        subject_id=subject_id,
        event_id="LIFECYCLE:SYNTHETIC:LIQUIDATION",
        event_type="LIQUIDATED",
        observation_status="COMPETING_EVENT_OBSERVED",
        effective_at="2016-04-01T00:00:00+08:00",
        source_available_at="2016-04-01T00:00:00+08:00",
        absorbing_for=["ECONOMIC_ENTITY"],
    )
    forged_survival = _cutoff_visible_lifecycle_event(
        subject_id=subject_id,
        event_id="LIFECYCLE:SYNTHETIC:FORGED-SURVIVAL",
        event_type="SURVIVED",
        observation_status="OBSERVED",
        effective_at="2016-05-01T00:00:00+08:00",
        source_available_at="2016-05-01T00:00:00+08:00",
        absorbing_for=["LISTED_SECURITY"],
    )
    result = history.build_industry_history_series_from_h1(
        package,
        h1_receipt_ref={
            "receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1",
            "receipt_version": 1,
        },
        cutoffs=["2016-06-01T00:00:00+08:00"],
        lifecycle_events=[liquidation, forged_survival],
    )
    assert result["valid"], result["findings"]
    member = next(item for item in result["industry_history_series"]["snapshots"][0]["members"] if item["subject_id"] == subject_id)
    assert member["risk_status"] == "EXITED"


def test_lifecycle_teaching_case_allows_known_history_without_comparative_permissions() -> None:
    lifecycle = _cutoff_visible_lifecycle_event(
        subject_id="ECONOMIC_ENTITY:CN:SYNTHETIC:ACQUIRED",
        event_id="LIFECYCLE:SYNTHETIC:ACQUIRED",
        event_type="ACQUIRED",
        observation_status="COMPETING_EVENT_OBSERVED",
        effective_at="2021-03-01T00:00:00+08:00",
        source_available_at="2021-03-02T00:00:00+08:00",
        absorbing_for=["INDEPENDENT_CONTROL"],
    )
    case = {
        "schema_version": history.TEACHING_CASE_SCHEMA_VERSION,
        "teaching_case_id": "TEACHING:SYNTHETIC:ACQUISITION:V1",
        "subject_id": lifecycle["subject_id"],
        "lifecycle_event": lifecycle,
        "source_packet_refs": [{"receipt_id": "TEACHING:SYNTHETIC:SOURCE:V1", "receipt_version": 1}],
        "teaching_question": "Does an acquisition end independent-control observation without proving operating failure?",
        "mechanism_hypothesis": "Control transfer is a competing lifecycle event, not a zero-return or business-liquidation proxy.",
        "prohibited_substitutes": ["Treating delisting as a business failure", "Treating missing terminal return as zero"],
        "outcome_knowledge_role": "HISTORICAL_OUTCOME_KNOWN",
        "object_class": "TEACHING_CASE",
        "claim_class": "WITHIN_CASE_MECHANISM",
        "allowed_outputs": ["TEACHING_ONLY", "BOUNDARY_ASSET", "RESEARCH_AGENDA"],
    }
    admitted = history.admit_lifecycle_teaching_case(case)
    assert admitted["valid"], admitted["findings"]
    assert admitted["teaching_case"]["outcome_knowledge_role"] == "HISTORICAL_OUTCOME_KNOWN"

    forged = deepcopy(case)
    forged["allowed_outputs"] = ["TEACHING_ONLY", "SELECTION_METHOD_ELIGIBLE"]
    rejected = history.admit_lifecycle_teaching_case(forged)
    assert not rejected["valid"]
    assert "teaching_case.allowed_outputs_not_permitted_for_claim" in rejected["findings"]
    assert "teaching_case.allowed_outputs_cannot_grant_method_or_report_authority" in rejected["findings"]

    wrong_subject = deepcopy(case)
    wrong_subject["subject_id"] = "ECONOMIC_ENTITY:CN:SYNTHETIC:OTHER"
    rejected_subject = history.admit_lifecycle_teaching_case(wrong_subject)
    assert not rejected_subject["valid"]
    assert "teaching_case.lifecycle_event.subject_id_must_match_case" in rejected_subject["findings"]


def test_real_cement_perimeter_break_is_admitted_only_as_lifecycle_teaching() -> None:
    artifact = json.loads((
        ROOT / "docs/development/research/cohorts/TEACHING_LIFECYCLE_CN_600801_PERIMETER_BREAK_20170324.json"
    ).read_text(encoding="utf-8"))
    admitted = history.admit_lifecycle_teaching_case(artifact)
    assert admitted["valid"], admitted["findings"]
    lifecycle = admitted["teaching_case"]["lifecycle_event"]
    assert lifecycle["event_type"] == "PERIMETER_CONTINUITY_UNRESOLVED"
    assert lifecycle["source"]["url"] == "https://static.cninfo.com.cn/finalpage/2017-03-24/1203190337.PDF"
    assert "SELECTION_METHOD_ELIGIBLE" not in admitted["teaching_case"]["allowed_outputs"]


def test_r104_mixed_settlement_projects_only_to_boundary_teaching_case() -> None:
    directory = ROOT / "docs/development/research/experiments/R-104_chongqing_beer_network_pruning_unit_economics_20160430"
    frozen_case = json.loads((directory / "01_case_freeze.json").read_text(encoding="utf-8"))
    post_review = json.loads((directory / "11_independent_post_outcome_review.json").read_text(encoding="utf-8"))
    boundary_note = json.loads((directory / "judgment_learning_notes/LNOTE_R-104_D4-CASH_MIXED-MECHANISM-BOUNDARY_20260824.json").read_text(encoding="utf-8"))
    result = history.project_mixed_boundary_episode_to_teaching_case(
        frozen_case,
        post_review,
        boundary_note,
        teaching_case_id="TEACHING:R-104:MIXED-D3-D4-BOUNDARY:V1",
        source_artifact_refs=[
            {"role": "FROZEN_CASE", "artifact_ref": "01_case_freeze.json"},
            {"role": "INDEPENDENT_POST_OUTCOME_REVIEW", "artifact_ref": "11_independent_post_outcome_review.json"},
            {"role": "BOUNDARY_NOTE", "artifact_ref": "judgment_learning_notes/LNOTE_R-104_D4-CASH_MIXED-MECHANISM-BOUNDARY_20260824.json"},
        ],
    )
    assert result["valid"], result["findings"]
    artifact = result["teaching_case"]
    assert artifact["boundary_disposition"] == "MIXED_MECHANISM_BOUNDARY"
    assert artifact["allowed_outputs"] == ["TEACHING_ONLY", "BOUNDARY_ASSET", "RESEARCH_AGENDA"]
    assert "Do not let D3 operating-contribution improvement override the contrary D4 owner-cash result." in artifact["prohibited_substitutes"]

    forged = deepcopy(post_review)
    forged["learning_authorization"] = "DIRECTIONAL"
    rejected = history.project_mixed_boundary_episode_to_teaching_case(
        frozen_case, forged, boundary_note,
        teaching_case_id="TEACHING:R-104:MIXED-D3-D4-BOUNDARY:V1",
        source_artifact_refs=[
            {"role": "FROZEN_CASE", "artifact_ref": "01_case_freeze.json"},
            {"role": "INDEPENDENT_POST_OUTCOME_REVIEW", "artifact_ref": "11_independent_post_outcome_review.json"},
            {"role": "BOUNDARY_NOTE", "artifact_ref": "judgment_learning_notes/LNOTE_R-104_D4-CASH_MIXED-MECHANISM-BOUNDARY_20260824.json"},
        ],
    )
    assert not rejected["valid"]
    assert "boundary_review.learning_authorization_must_be_none" in rejected["findings"]


def test_teaching_and_lifecycle_permissions_cannot_upgrade_to_selection_or_report_use() -> None:
    teaching = {
        "schema_version": history.ADMISSION_SCHEMA_VERSION,
        "artifact_id": "TEACHING:SYNTHETIC:MECHANISM",
        "object_class": "TEACHING_CASE",
        "claim_class": "WITHIN_CASE_MECHANISM",
        "allowed_outputs": ["TEACHING_ONLY", "BOUNDARY_ASSET"],
    }
    assert history.validate_claim_specific_admission(teaching)["valid"]

    prohibited = deepcopy(teaching)
    prohibited["allowed_outputs"] = ["TEACHING_ONLY", "SELECTION_METHOD_ELIGIBLE"]
    result = history.validate_claim_specific_admission(prohibited)
    assert not result["valid"]
    assert "admission.allowed_outputs_not_permitted_for_claim" in result["findings"]
    assert "admission.allowed_outputs_cannot_grant_method_or_report_authority" in result["findings"]


def test_static_peer_batch_requires_frozen_predicate_and_freeze_closes_that_snapshot() -> None:
    registry = _projected_synthetic_seed()["carrier_registry"]
    missing_predicate = history.append_static_peer_recruitment_batch(registry, {})
    assert not missing_predicate["valid"]
    assert missing_predicate["findings"] == ["peer_recruitment_eligibility_predicate_not_frozen"]

    predicate_result = history.freeze_peer_recruitment_eligibility_predicate(registry, _predicate(registry))
    assert predicate_result["valid"], predicate_result["findings"]
    registry = predicate_result["carrier_registry"]
    appended = history.append_static_peer_recruitment_batch(registry, _recruitment_batch(registry))
    assert appended["valid"], appended["findings"]
    registry = _resolve_all_pending(appended["carrier_registry"])
    frozen = history.freeze_evidence_carrier_registry(registry, frozen_at="2020-11-02T10:00:00+08:00")
    assert frozen["valid"], frozen["findings"]
    assert frozen["freeze_receipt"]["state"] == "FROZEN"

    rejected_append = history.append_static_peer_recruitment_batch(
        frozen["carrier_registry"], _recruitment_batch(frozen["carrier_registry"]),
    )
    assert not rejected_append["valid"]
    assert rejected_append["findings"] == ["carrier_registry_frozen"]


def test_recruited_static_source_must_be_cutoff_before_and_identity_bound() -> None:
    registry = _projected_synthetic_seed()["carrier_registry"]
    registry = history.freeze_peer_recruitment_eligibility_predicate(
        registry, _predicate(registry),
    )["carrier_registry"]
    batch = _recruitment_batch(registry)
    batch["static_sources"][0]["url"] = "https://www.cninfo.com.cn/new/disclosure/detail"
    batch["static_sources"][0]["published_at"] = "2021-01-01T00:00:00+08:00"
    batch["static_sources"][0]["issuer_id"] = "ISSUER:CN:OTHER"
    batch["static_sources"][0]["period_end"] = "not-a-date"

    result = history.append_static_peer_recruitment_batch(registry, batch)
    assert not result["valid"]
    assert "peer_recruitment_batch.static_sources[0].url_must_be_static_cninfo_finalpage_pdf" in result["findings"]
    assert "peer_recruitment_batch.static_sources[0].published_at_must_be_strictly_before_predicate_cutoff" in result["findings"]
    assert "peer_recruitment_batch.static_sources[0].period_end_must_be_iso_date" in result["findings"]
    assert "peer_recruitment_batch.carriers[0].static_source_identity_must_match_carrier" in result["findings"]


def test_recruited_static_coverage_must_bind_exact_pdf_page_period_and_field() -> None:
    registry = _projected_synthetic_seed()["carrier_registry"]
    registry = history.freeze_peer_recruitment_eligibility_predicate(
        registry, _predicate(registry),
    )["carrier_registry"]
    batch = _recruitment_batch(registry)
    coverage = batch["carrier_static_coverage"][0]
    coverage["field_ref"] = "Synthetic official annual report PDF p13."
    coverage["period_end"] = "2018-12-31"
    coverage["field_id"] = "uncovered_owner_cash_input"

    result = history.append_static_peer_recruitment_batch(registry, batch)

    assert not result["valid"]
    assert "peer_recruitment_batch.carrier_static_coverage[0].field_ref_must_match_declared_static_pdf_page" in result["findings"]
    assert "peer_recruitment_batch.carrier_static_coverage[0].period_end_must_match_declared_static_pdf" in result["findings"]


def test_comparative_claim_needs_frozen_registry_and_uses_only_eligible_carriers() -> None:
    registry = _projected_synthetic_seed()["carrier_registry"]
    predicate_result = history.freeze_peer_recruitment_eligibility_predicate(registry, _predicate(registry))
    registry = _resolve_all_pending(predicate_result["carrier_registry"])
    admission = {
        "schema_version": history.ADMISSION_SCHEMA_VERSION,
        "artifact_id": "COMPARATIVE:SYNTHETIC:NETWORK",
        "object_class": "COMPARATIVE_EPISODE",
        "claim_class": "RELATIVE_CAUSAL",
        "allowed_outputs": ["COMPARATIVE_SETTLEMENT_CANDIDATE"],
        "registry_id": registry["registry_id"],
        "target_company_id": registry["carriers"][0]["company_id"],
        "comparator_company_ids": [carrier["company_id"] for carrier in registry["carriers"][1:4]],
    }
    before_freeze = history.validate_claim_specific_admission(admission, registry=registry)
    assert not before_freeze["valid"]
    assert "admission.comparative_episode_requires_frozen_carrier_registry" in before_freeze["findings"]

    frozen = history.freeze_evidence_carrier_registry(registry, frozen_at="2020-11-02T10:00:00+08:00")
    admitted = history.validate_claim_specific_admission(admission, registry=frozen["carrier_registry"])
    assert not admitted["valid"]
    assert admitted["findings"] == ["admission.comparative_requires_registered_registry_control_plane"]

    break_carrier = deepcopy(frozen["carrier_registry"])
    break_carrier["carriers"][1]["disposition"] = "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    rejected = history.validate_claim_specific_admission(admission, registry=break_carrier)
    assert not rejected["valid"]
    assert "admission.comparative_panel_must_use_frozen_eligible_carriers" in rejected["findings"]


def test_schema_is_valid_json_and_declares_a_closed_registry_shape() -> None:
    schema = json.loads((ROOT / "schemas/historical_training_control.schema.json").read_text(encoding="utf-8"))
    registry = schema["$defs"]["carrier_registry"]
    assert registry["additionalProperties"] is False
    assert registry["properties"]["peer_recruitment_predicate"]
    history_series = schema["$defs"]["history_series"]
    assert history_series["additionalProperties"] is False
    assert history_series["properties"]["snapshots"]["items"]["$ref"] == "#/$defs/universe"
    teaching_case = schema["$defs"]["teaching_case"]
    assert teaching_case["additionalProperties"] is False
    assert teaching_case["properties"]["lifecycle_event"]["$ref"] == "#/$defs/lifecycle"
    boundary_case = schema["$defs"]["boundary_teaching_case"]
    assert boundary_case["additionalProperties"] is False
    assert boundary_case["properties"]["boundary_disposition"]["const"] == "MIXED_MECHANISM_BOUNDARY"
