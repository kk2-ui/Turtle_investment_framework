from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts import judgment_selection_discovery as discovery


def _evidence(source_id: str, *, published_at: str = "2020-03-30") -> dict:
    return {
        "source_id": source_id,
        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": "ISSUER:CN:SYNTHETIC",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "responsibility_unit_id": "UNIT:SYNTHETIC",
        "unit": "RMB",
        "published_at": published_at,
        "field_ref": f"{source_id}:official-field",
    }


def _cohort_evidence(
    source_id: str, *, issuer_id: str, responsibility_unit_id: str, published_at: str,
    control_group_id: str | None = None,
) -> dict:
    result = {
        "source_id": source_id,
        "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
        "issuer_id": issuer_id,
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "responsibility_unit_id": responsibility_unit_id,
        "unit": "RMB",
        "published_at": published_at,
        "field_ref": f"{source_id}: official field, PDF p12",
    }
    if control_group_id is not None:
        result["observed_control_group_id"] = control_group_id
    return result


def _cohort_record() -> dict:
    members = []
    company_ids = ["CN:SYNTHETIC", *[f"CN:PEER-{index}" for index in range(1, 5)]]
    for company_id in company_ids:
        issuer_id = "ISSUER:" + company_id
        unit_id = "UNIT:" + company_id.removeprefix("CN:")
        control_id = "CONTROL:" + company_id
        boundary = {
            "responsibility_unit_id": unit_id,
            "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
            "unit": "RMB",
        }
        members.append({
            "company_id": company_id,
            "issuer_id": issuer_id,
            "responsibility_unit_id": unit_id,
            "control_group_id": control_id,
            "industry_id": "INDUSTRY:SYNTHETIC",
            "boundary": boundary,
            "industry_business_evidence": [
                _cohort_evidence(f"{company_id}:INDUSTRY", issuer_id=issuer_id, responsibility_unit_id=unit_id, published_at="2020-03-30"),
            ],
            "control_group_evidence": [
                _cohort_evidence(f"{company_id}:CONTROL", issuer_id=issuer_id, responsibility_unit_id=unit_id, published_at="2020-03-30", control_group_id=control_id),
            ],
            "final_peer_panel_disposition": "PENDING_ACTION_WINDOW_REVIEW",
            "final_peer_panel_rationale": "Stage 0 establishes source availability only; action-window comparability is not yet assessed.",
            "d2_field_availability": {
                "field_id": "ANNUAL_UNITS_SOLD",
                "definition": "Annual consolidated units sold.",
                "repetitions": [
                    {"period_end": period_end, "evidence": [
                        _cohort_evidence(f"{company_id}:D2:{period_end}", issuer_id=issuer_id, responsibility_unit_id=unit_id, published_at=published_at),
                    ]}
                    for period_end, published_at in (
                        ("2017-12-31", "2018-03-30"),
                        ("2018-12-31", "2019-03-30"),
                        ("2019-12-31", "2020-03-30"),
                    )
                ],
            },
            "annual_d3_d4_availability": [
                {"period_end": period_end, "evidence": [
                    _cohort_evidence(f"{company_id}:ANNUAL:{period_end}", issuer_id=issuer_id, responsibility_unit_id=unit_id, published_at=published_at),
                ]}
                for period_end, published_at in (
                    ("2015-12-31", "2016-03-30"),
                    ("2016-12-31", "2017-03-30"),
                    ("2017-12-31", "2018-03-30"),
                    ("2018-12-31", "2019-03-30"),
                    ("2019-12-31", "2020-03-30"),
                )
            ],
        })
    return {
        "schema_version": "judgment-selection-cohort-feasibility.v1",
        "cohort_id": "COHORT:SYNTHETIC:20200630",
        "industry_id": "INDUSTRY:SYNTHETIC",
        "selection_as_of": "2020-06-30",
        "universe": {
            "universe_id": "SYNTHETIC:LISTED:INDUSTRY:20200630",
            "membership_rule": "All five listed synthetic issuers with recurring annual official disclosures.",
            "cohort_scope": "PRE_ACTION_DISCLOSURE_FEASIBILITY_SAMPLE",
            "not_final_peer_universe": True,
            "listed_company_ids": company_ids,
        },
        "members": members,
    }


def _stage0_static_package(*, topology: str = "CUSTOMER_RESPONSE") -> dict:
    package = _cohort_record()
    package.update({
        "schema_version": discovery.STAGE0_STATIC_PACKAGE_SCHEMA_VERSION,
        "selection_as_of": "2020-06-30T23:59:59+08:00",
        "cohort_eligibility_as_of": "2020-06-30T23:59:59+08:00",
        "arena_family": "SYNTHETIC_NATIONAL_DURABLE_GOODS",
        "mechanism_topology": topology,
        "entry_kind": discovery.CURATOR_SUPPLIED_STATIC_PDF_PACKAGE,
        "current_admission_assessment": {
            "status": discovery.FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE,
            "reason": "Five independent, continuous-perimeter issuers establish a static pre-action intake cohort.",
        },
        "curator_attestation": {
            "curator_id": "CURATOR:SYNTHETIC:H1-H2",
            "issuer_code_or_name_submitted_to_cninfo_fulltext": False,
            "cninfo_issuer_stock_or_detail_page_opened": False,
            "post_identification_access": discovery.POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY,
            "post_cutoff_metadata_or_body_read": False,
        },
        "competitive_arena": {
            "competitive_arena_id": "ARENA:SYNTHETIC:NATIONAL",
            "market_scope_type": "NATIONAL",
            "product_or_service_scope": "SYNTHETIC_DURABLE_GOODS",
            "geographic_scope": "National customer market; provincial network overlap is not a Stage-0 gate.",
            "customer_end_market_scope": "HOUSEHOLDS",
            "evidence": [],
        },
        "static_pdf_sources": [],
    })
    source_index: dict[str, dict] = {}
    source_periods: dict[str, str] = {}
    for member in package["members"]:
        if topology == "COST_RESTRUCTURING":
            cost = member.pop("d2_field_availability")
            cost["cost_driver_kind"] = "UNIT_OPERATING_COST"
            member["cost_field_availability"] = cost
        member["competitive_arena_id"] = package["competitive_arena"]["competitive_arena_id"]
        member["carrier_identity_source_ids"] = [member["industry_business_evidence"][0]["source_id"]]
        history = member.get("d2_field_availability") or member.get("cost_field_availability")
        for repetition in history["repetitions"]:
            for evidence in repetition["evidence"]:
                source_periods[evidence["source_id"]] = repetition["period_end"]
        for annual in member["annual_d3_d4_availability"]:
            for evidence in annual["evidence"]:
                source_periods[evidence["source_id"]] = annual["period_end"]
        for evidence in discovery._stage0_evidence_records(member):
            source_id = evidence["source_id"]
            source_index.setdefault(source_id, {
                "source_id": source_id,
                "url": f"https://static.cninfo.com.cn/finalpage/2020-03-30/{len(source_index) + 1}.PDF",
                "published_at": evidence["published_at"],
                "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
                "period_end": source_periods.get(source_id, "2019-12-31"),
                "field_refs": [],
                "issuer_id": evidence["issuer_id"],
                "responsibility_unit_id": evidence["responsibility_unit_id"],
                "perimeter_id": evidence["perimeter_id"],
                "unit": evidence["unit"],
            })["field_refs"].append(evidence["field_ref"])
    arena_evidence = discovery._stage0_evidence_records(package["members"][0]["industry_business_evidence"])[0]
    package["competitive_arena"]["evidence"] = [deepcopy(arena_evidence)]
    package["static_pdf_sources"] = list(source_index.values())
    return package


def _manifest() -> dict:
    boundary = {
        "responsibility_unit_id": "UNIT:SYNTHETIC",
        "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
        "unit": "RMB",
    }
    manifest = {
        "schema_version": discovery.MANIFEST_SCHEMA_VERSION,
        "manifest_id": "DISCOVERY:SYNTHETIC:NETWORK-2020",
        "mechanism_topology": "CUSTOMER_RESPONSE_CHAIN",
        "cutoff_at": "2020-12-31T23:59:59+08:00",
        "candidate_identity": {
            "company_id": "CN:SYNTHETIC",
            "issuer_id": "ISSUER:CN:SYNTHETIC",
            "responsibility_unit_id": "UNIT:SYNTHETIC",
            "industry_id": "INDUSTRY:SYNTHETIC",
            "common_boundary": boundary,
        },
        "cohort_feasibility_record": _cohort_record(),
        "action": {
            "action_id": "ACTION:SYNTHETIC:NETWORK",
            "action_statement": "The whole issuer closed its obsolete production network and incurred the stated cash cost.",
            "action_scope": discovery.ACTION_SCOPE,
            "economic_character": discovery.COMMERCIAL_ACTION,
            "economic_action_type": "OPERATING_NETWORK_RESTRUCTURING",
            "action_state": "IMPLEMENTED_OR_IRREVOCABLY_INCURRED",
            "implemented_or_incurred_at": "2020-09-30",
            "boundary": deepcopy(boundary),
            "issuer_scope_bridge": {
                "outcome_scope": "LISTED_CONSOLIDATED_ISSUER",
                "action_scope_relation": "ISSUER_WIDE_OPERATING_DECISION",
                "issuer_level_mechanism_only": True,
                "evidence": [_evidence("ACTION:ISSUER-SCOPE", published_at="2020-10-15")],
            },
            "decision_specificity": {
                "decision_class": "DISCRETIONARY_OPERATING_DECISION",
                "incremental_to_maintenance_or_mandated_baseline": True,
                "evidence": [_evidence("ACTION:INCREMENTAL", published_at="2020-10-15")],
            },
            "explicitly_immaterial": False,
            "implementation_evidence": [_evidence("ACTION:IMPLEMENTED", published_at="2020-10-15")],
            "exposure": {
                "kind": "ACTUAL_CASH_OR_RECOGNIZED_ASSET",
                "actual_basis": "ACTUAL_CASH_PAID",
                "evidence": [_evidence("ACTION:CASH", published_at="2020-10-15")],
            },
        },
        "cutoff_before_facts": [
            {
                "fact_id": "FACT:ACTION",
                "statement": "The actual whole-issuer network action was completed before cutoff.",
                "evidence": [_evidence("FACT:ACTION", published_at="2020-10-15")],
            },
            {
                "fact_id": "FACT:RIVAL",
                "statement": "The issuer's pre-cutoff shipment trend leaves demand deleveraging live.",
                "evidence": [_evidence("FACT:RIVAL", published_at="2020-03-30")],
            },
        ],
        "hypothesis_pair": {
            "decisive_question": "Does whole-issuer network consolidation improve normal economics or does demand deleveraging overwhelm the savings?",
            "primary": {
                "hypothesis_id": "H-A",
                "mechanism": "Network consolidation improves recurring operating contribution and owner cash.",
                "pre_outcome_rationale": "The action is implemented and customer volumes remain independently observable.",
                "supporting_fact_ids": ["FACT:ACTION"],
            },
            "strongest_rival": {
                "hypothesis_id": "H-B",
                "mechanism": "Demand deleveraging and route cost overwhelm the savings.",
                "pre_outcome_rationale": "Volume contraction and route expense leave the rival live at cutoff.",
                "live_before_cutoff": True,
                "supporting_fact_ids": ["FACT:RIVAL"],
            },
            "selection_basis": {
                "directional_preference": "H-A",
                "why_not_common": "The implemented commercial action distinguishes the mechanisms.",
                "why_rival_remains_live": "The disclosed demand and cost facts still support H-B.",
            },
        },
        "d2_observability": {
            "primary_hypothesis_id": "H-A",
            "observation_kind": "UNITS_SOLD",
            "not_mechanically_changed_by_action": True,
            "boundary": deepcopy(boundary),
            "field_id": "ISSUER:SHIPMENTS:ANNUAL",
            "repetitions": [
                {
                    "period_end": period_end,
                    "field_ref": f"{period_end}:shipments",
                    "evidence": [_evidence(f"D2:{period_end}", published_at=published_at)],
                }
                for period_end, published_at in (
                    ("2017-12-31", "2018-03-30"),
                    ("2018-12-31", "2019-03-30"),
                    ("2019-12-31", "2020-03-30"),
                )
            ],
        },
        "source_firewall": {
            "outcome_body_access": "UNREAD_AND_PROHIBITED",
            "outcome_metadata_access": "NONE",
            "post_cutoff_sources_prohibited": True,
            "curator_attestation": "Only cutoff-before official sources were supplied; no result package was accessed.",
            "discovery_entry": {
                "kind": discovery.KNOWN_CUTOFF_BEFORE_STATIC_CNINFO_PDF,
                "issuer_code_or_name_submitted_to_cninfo_fulltext": False,
                "cninfo_issuer_stock_or_detail_page_opened": False,
                "post_identification_access": discovery.POST_IDENTIFICATION_STATIC_PDF_PACKAGE_ONLY,
                "static_pdf_sources": [
                    {
                        "url": "https://static.cninfo.com.cn/finalpage/2020-10-15/SYNTHETIC-ACTION.PDF",
                        "source_id": "ACTION:IMPLEMENTED",
                    },
                    {
                        "url": "https://static.cninfo.com.cn/finalpage/2020-03-30/SYNTHETIC-D2.PDF",
                        "source_id": "D2:2019-12-31",
                    },
                ],
            },
        },
    }
    source_ids = sorted(discovery._manifest_source_ids({
        key: value for key, value in manifest.items() if key != "source_firewall"
    }))
    manifest["source_firewall"]["access_receipt"] = {
        "schema_version": "phase10-pit-runner-attestation.v1",
        "runner": "phase10_pit_runner",
        "assurance_level": "VERIFIED_ARTIFACT_AND_DECLARED_PROCESS",
        "state": "REVIEWABLE",
        "cutoff_at": manifest["cutoff_at"],
        "allowed_source_ids": source_ids,
        "source_allowlist": [
            {"source_id": source_id, "published_at": "2020-10-15"}
            for source_id in source_ids
        ],
    }
    return manifest


def _h2_action_screen_extension() -> tuple[dict, dict]:
    """Make a one-time H2 screen from the legacy synthetic action facts.

    The compatibility manifest remains useful to test its own triage.  H2
    copies only the action-screen facts into a new closed PDF declaration so
    the candidate path cannot submit that manifest directly.
    """
    stage0 = _stage0_static_package()
    manifest = _manifest()
    extension = {
        "schema_version": discovery.ACTION_SCREEN_STATIC_EXTENSION_SCHEMA_VERSION,
        "screen_id": "H2:SYNTHETIC:NETWORK:20201231",
        "stage0_cohort_id": stage0["cohort_id"],
        "stage0_selection_as_of": stage0["selection_as_of"],
        "curator_id": stage0["curator_attestation"]["curator_id"],
        "cutoff_at": manifest["cutoff_at"],
        "mechanism_topology": manifest["mechanism_topology"],
        "candidate_identity": deepcopy(manifest["candidate_identity"]),
        "static_pdf_sources": [],
        "source_firewall_attestation": {
            "outcome_body_access": "UNREAD_AND_PROHIBITED",
            "outcome_metadata_access": "NONE",
            "post_cutoff_sources_prohibited": True,
        },
        "action": deepcopy(manifest["action"]),
        "cutoff_before_facts": deepcopy(manifest["cutoff_before_facts"]),
        "hypothesis_pair": deepcopy(manifest["hypothesis_pair"]),
        "d2_observability": deepcopy(manifest["d2_observability"]),
    }
    sources: dict[str, dict] = {}

    def bind_static_pdf(value: object) -> None:
        if isinstance(value, dict):
            if isinstance(value.get("source_id"), str) and isinstance(value.get("field_ref"), str):
                source_id = value["source_id"]
                page_ref = f"{source_id}: PDF p12"
                value["field_ref"] = page_ref
                sources.setdefault(source_id, {
                    "source_id": source_id,
                    "url": f"https://static.cninfo.com.cn/finalpage/2020-10-15/{len(sources) + 1}.PDF",
                    "published_at": value["published_at"],
                    "source_type": value["source_type"],
                    "field_refs": [],
                    "issuer_id": value["issuer_id"],
                    "responsibility_unit_id": value["responsibility_unit_id"],
                    "perimeter_id": value["perimeter_id"],
                    "unit": value["unit"],
                })["field_refs"].append(page_ref)
            for nested in value.values():
                bind_static_pdf(nested)
        elif isinstance(value, list):
            for nested in value:
                bind_static_pdf(nested)

    for field in ("action", "cutoff_before_facts", "hypothesis_pair", "d2_observability"):
        bind_static_pdf(extension[field])
    extension["static_pdf_sources"] = list(sources.values())
    return stage0, extension


def test_discovery_triage_ready_only_authorizes_next_v4_acquisition() -> None:
    result = discovery.triage_selection_discovery_manifest(_manifest())

    assert result["state"] == discovery.DISCOVERY_READY
    assert result["findings"] == []
    assert result["next_acquisition_package"] == list(discovery.NEXT_V4_ACQUISITION_PACKAGE)
    assert "selection_episode" in result["does_not_grant"]
    assert "outcome_access" in result["does_not_grant"]


def test_stage0_cohort_is_independently_reviewable_before_action_selection() -> None:
    result = discovery.candidate_contract.validate_v4_cohort_feasibility_record(
        _cohort_record(), action_at=None,
    )

    assert result == {"state": "REVIEWABLE", "findings": []}


def test_discovery_rejects_an_explicitly_insufficient_final_panel_cohort_without_breaking_legacy_stage0() -> None:
    manifest = _manifest()
    manifest["cohort_feasibility_record"]["current_admission_assessment"] = {
        "status": "INSUFFICIENT_FOR_V4_FINAL_PANEL",
        "reason": "The retained members cannot form one target plus three comparable peers.",
    }

    result = discovery.triage_selection_discovery_manifest(manifest)

    assert result["state"] == discovery.NO_PRIMARY
    assert result["next_acquisition_package"] == []
    assert result["findings"] == [
        "invalid:cohort_feasibility_record.current_admission_assessment.status:"
        "must_equal_feasible_for_v4_final_panel",
    ]


def test_stage0_cohort_rejects_selection_as_of_on_the_same_action_day() -> None:
    record = _cohort_record()
    record["selection_as_of"] = "2020-09-30"

    result = discovery.candidate_contract.validate_v4_cohort_feasibility_record(
        record, action_at=discovery.candidate_contract._date_or_time("2020-09-30"),
    )

    assert result["state"] == "INVALID"
    assert "cohort_selection_as_of_not_before_action" in result["findings"]


def test_stage0_cohort_rejects_a_pretended_final_peer_universe() -> None:
    record = _cohort_record()
    record["universe"]["not_final_peer_universe"] = False

    result = discovery.candidate_contract.validate_v4_cohort_feasibility_record(
        record, action_at=None,
    )

    assert result["state"] == "INVALID"
    assert "cohort_universe_scope_not_pre_action_feasibility_sample" in result["findings"]


def test_stage0_cohort_requires_an_explicit_final_peer_panel_disposition() -> None:
    record = _cohort_record()
    record["members"][0].pop("final_peer_panel_disposition")

    result = discovery.candidate_contract.validate_v4_cohort_feasibility_record(
        record, action_at=None,
    )

    assert result["state"] == "INVALID"
    assert "cohort_member[0]_final_peer_panel_disposition_invalid" in result["findings"]


def test_stage0_known_scope_break_requires_cutoff_before_evidence() -> None:
    record = _cohort_record()
    record["members"][0]["final_peer_panel_disposition"] = "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    record["members"][0]["final_peer_panel_rationale"] = "A material acquisition changed the consolidated perimeter."

    result = discovery.candidate_contract.validate_v4_cohort_feasibility_record(
        record, action_at=None,
    )

    assert result["state"] == "INVALID"
    assert "cohort_member[0]_comparability_break_evidence_invalid" in result["findings"]


def test_stage0_cohort_cli_validates_without_an_action(tmp_path) -> None:
    cohort_path = tmp_path / "cohort.json"
    cohort_path.write_text(json.dumps(_stage0_static_package()), encoding="utf-8")

    assert discovery.main(["--cohort-only", str(cohort_path)]) == 0


def test_cement_h1_static_package_is_reviewable_via_validator_and_strict_cli(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The curator-supplied cement receipt is H1 intake, not a final panel.

    This guards the audited distinction: known later comparability breaks do
    not retroactively make a cutoff-before static source package invalid.
    """
    root = Path(__file__).resolve().parents[1]
    package_path = root / (
        "docs/development/research/cohorts/"
        "COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json"
    )
    package = json.loads(package_path.read_text(encoding="utf-8"))

    result = discovery.validate_stage0_static_source_package(package)

    assert result == {
        "schema_version": discovery.STAGE0_STATIC_RESULT_SCHEMA_VERSION,
        "state": discovery.STAGE0_FEASIBILITY_REVIEWABLE,
        "findings": [],
        "does_not_grant": list(discovery.DOES_NOT_GRANT),
        "next_permitted_step": "CURATOR_ACTION_SCREEN_STATIC_EXTENSION",
    }
    assert discovery.main(["--cohort-only", str(package_path)]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE


def test_stage0_known_scope_break_is_disclosure_only_and_stays_in_h1() -> None:
    package = _stage0_static_package()
    member = package["members"][1]
    member["final_peer_panel_disposition"] = "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    member["final_peer_panel_rationale"] = "A material acquisition changed the consolidated perimeter."
    member["comparability_break_evidence"] = [
        {
            "source_id": member["industry_business_evidence"][0]["source_id"],
            "source_type": member["industry_business_evidence"][0]["source_type"],
            "issuer_id": member["industry_business_evidence"][0]["issuer_id"],
            "perimeter_id": member["industry_business_evidence"][0]["perimeter_id"],
            "responsibility_unit_id": member["industry_business_evidence"][0]["responsibility_unit_id"],
            "unit": member["industry_business_evidence"][0]["unit"],
            "published_at": member["industry_business_evidence"][0]["published_at"],
            "field_ref": member["industry_business_evidence"][0]["field_ref"],
        }
    ]

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE
    assert result["findings"] == []


def test_discovery_cli_only_exposes_the_strict_h1_intake_mode(tmp_path) -> None:
    manifest_path = tmp_path / "legacy-manifest.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    with pytest.raises(SystemExit) as rejected:
        discovery.main([str(manifest_path)])
    assert rejected.value.code == 2


def test_stage0_static_package_only_freezes_feasibility_and_not_an_episode() -> None:
    result = discovery.validate_stage0_static_source_package(_stage0_static_package())

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE
    assert discovery.FEASIBLE_FOR_H1_STATIC_SOURCE_PACKAGE != discovery.FEASIBLE_FOR_V5_FINAL_PANEL
    assert result["findings"] == []
    assert result["next_permitted_step"] == "CURATOR_ACTION_SCREEN_STATIC_EXTENSION"
    assert "selection_episode" in result["does_not_grant"]
    assert "outcome_access" in result["does_not_grant"]


def test_h1_known_scope_break_is_retained_as_disclosure_only() -> None:
    package = _stage0_static_package()
    member = package["members"][0]
    member["final_peer_panel_disposition"] = "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    member["comparability_break_evidence"] = deepcopy(member["control_group_evidence"])

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE
    assert member["final_peer_panel_disposition"] == "KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK"
    assert "selection_episode" in result["does_not_grant"]


@pytest.mark.parametrize(
    "geographic_scope",
    [
        "Two plants serve one provincial delivered-price market.",
        "Plants in different provinces serve an overlapping delivered-price market.",
    ],
)
def test_h1_regional_arena_does_not_use_province_equality_as_a_hard_gate(geographic_scope: str) -> None:
    package = _stage0_static_package()
    package["arena_family"] = "SYNTHETIC_REGIONAL_DELIVERED_PRICE"
    package["competitive_arena"]["market_scope_type"] = "REGIONAL"
    package["competitive_arena"]["geographic_scope"] = geographic_scope
    package["competitive_arena"]["product_or_service_scope"] = "Bulk cement delivered to construction customers."
    package["competitive_arena"]["customer_end_market_scope"] = "Regional infrastructure and property construction."

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE
    assert not any("geographic" in finding or "province" in finding for finding in result["findings"])


def test_h2_action_screen_is_closed_to_one_h1_member_and_static_pdf_allowlist() -> None:
    stage0, extension = _h2_action_screen_extension()

    result = discovery.validate_action_screen_static_extension(stage0, extension)

    assert result["state"] == discovery.ACTION_SCREEN_REVIEWABLE
    assert result["findings"] == []
    assert result["projected_legacy_manifest"]["cohort_feasibility_record"]["cohort_id"] == stage0["cohort_id"]
    assert "selection_episode" in result["does_not_grant"]
    assert "outcome_access" in result["does_not_grant"]


def test_h2_action_screen_can_cite_an_existing_h1_pdf_without_redeclaring_it() -> None:
    stage0, extension = _h2_action_screen_extension()
    h1_source = stage0["static_pdf_sources"][0]
    evidence = extension["action"]["issuer_scope_bridge"]["evidence"][0]
    original_source_id = evidence["source_id"]
    for field in (
        "source_id", "source_type", "issuer_id", "perimeter_id", "responsibility_unit_id", "unit", "published_at",
    ):
        evidence[field] = h1_source[field]
    evidence["field_ref"] = h1_source["field_refs"][0]
    extension["static_pdf_sources"] = [
        source for source in extension["static_pdf_sources"] if source["source_id"] != original_source_id
    ]

    result = discovery.validate_action_screen_static_extension(stage0, extension)

    assert result["state"] == discovery.ACTION_SCREEN_REVIEWABLE
    assert result["findings"] == []


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("wrong_curator", "invalid:action_screen_extension.curator_id:must_match_h1_curator"),
        ("new_member", "invalid:action_screen_extension:contains_unapproved_information"),
        ("unbound_evidence", "invalid:action_screen_extension.evidence[0].source_id:must_be_declared_action_screen_static_pdf"),
        ("unused_pdf", "invalid:action_screen_extension.static_pdf_sources:must_not_declare_unused_or_post_screen_source:SCREEN:UNUSED"),
        ("same_day_pdf", "invalid:action_screen_extension.static_pdf_sources[0].published_at:must_be_strictly_before_screen_cutoff"),
    ],
)
def test_h2_action_screen_rejects_curator_member_and_source_append_bypasses(
    mutation: str, finding: str,
) -> None:
    stage0, extension = _h2_action_screen_extension()
    if mutation == "wrong_curator":
        extension["curator_id"] = "CURATOR:OTHER"
    elif mutation == "new_member":
        extension["members"] = [{"company_id": "CN:APPENDED"}]
    elif mutation == "unbound_evidence":
        extension["action"]["issuer_scope_bridge"]["evidence"][0]["source_id"] = "SCREEN:APPENDED"
    elif mutation == "unused_pdf":
        extension["static_pdf_sources"].append({
            **deepcopy(extension["static_pdf_sources"][0]),
            "source_id": "SCREEN:UNUSED",
            "field_refs": ["SCREEN:UNUSED: PDF p12"],
        })
    else:
        extension["static_pdf_sources"][0]["published_at"] = "2020-12-31"

    result = discovery.validate_action_screen_static_extension(stage0, extension)

    assert result["state"] == discovery.ACTION_SCREEN_REJECTED
    assert finding in result["findings"]


def test_stage0_static_package_binds_every_annual_field_identity_to_its_pdf_period() -> None:
    package = _stage0_static_package()
    annual = package["members"][0]["annual_d3_d4_availability"][0]
    source_id = annual["evidence"][0]["source_id"]
    source = next(item for item in package["static_pdf_sources"] if item["source_id"] == source_id)
    source["period_end"] = "2019-12-31"

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.INSUFFICIENT_STATIC_SOURCE_PACKAGE
    assert (
        "invalid:members[0].annual_d3_d4_availability[0].evidence[0].period_end:"
        "must_match_declared_static_pdf_period_end"
    ) in result["findings"]


def test_cost_restructuring_stage0_accepts_cost_history_without_customer_d2() -> None:
    result = discovery.validate_stage0_static_source_package(
        _stage0_static_package(topology="COST_RESTRUCTURING"),
    )

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE


def test_cost_restructuring_stage0_can_use_central_customer_d2_history() -> None:
    package = _stage0_static_package(topology="COST_RESTRUCTURING")
    for member in package["members"]:
        member["d2_field_availability"] = member.pop("cost_field_availability")
        member["d2_field_availability"].pop("cost_driver_kind")

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE


def test_cost_restructuring_stage0_accepts_complete_d2_and_cost_histories() -> None:
    package = _stage0_static_package(topology="COST_RESTRUCTURING")
    for member in package["members"]:
        member["d2_field_availability"] = deepcopy(member["cost_field_availability"])
        member["d2_field_availability"].pop("cost_driver_kind")

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_FEASIBILITY_REVIEWABLE


def test_cost_restructuring_stage0_rejects_empty_optional_cost_history() -> None:
    package = _stage0_static_package(topology="COST_RESTRUCTURING")
    for member in package["members"]:
        member["d2_field_availability"] = member.pop("cost_field_availability")
        member["d2_field_availability"].pop("cost_driver_kind")
        member["cost_field_availability"] = {
            "field_id": "ANNUAL_UNIT_OPERATING_COST",
            "cost_driver_kind": "UNIT_OPERATING_COST",
            "definition": "Annual consolidated unit operating cost.",
            "repetitions": [],
        }

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_REJECTED
    assert "invalid:cohort_member[0]_cost_field_availability_not_recurrent" in result["findings"]


def test_cost_restructuring_stage0_rejects_missing_cost_history() -> None:
    package = _stage0_static_package(topology="COST_RESTRUCTURING")
    package["members"][0].pop("cost_field_availability")

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_REJECTED
    assert "invalid:members[0]:must_have_d2_or_cost_field_history_for_cost_restructuring" in result["findings"]


def test_stage0_static_package_rejects_legacy_assessment_and_cannot_false_pass() -> None:
    package = _stage0_static_package()
    package["current_admission_assessment"]["status"] = "INSUFFICIENT_FOR_V4_FINAL_PANEL"

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.STAGE0_REJECTED
    assert "invalid:current_admission_assessment.status:must_equal_feasible_for_h1_static_source_package" in result["findings"]


def test_current_cement_feasibility_record_cannot_false_pass_strict_h1_intake() -> None:
    legacy_path = (
        Path(__file__).resolve().parents[1]
        / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_feasibility.json"
    )
    result = discovery.validate_stage0_static_source_package(
        json.loads(legacy_path.read_text(encoding="utf-8")),
    )

    assert result["state"] == discovery.STAGE0_REJECTED
    assert "invalid:current_admission_assessment.status:must_equal_feasible_for_h1_static_source_package" in result["findings"]


@pytest.mark.parametrize(
    ("mutation", "state", "finding"),
    [
        ("missing_static_source", discovery.INSUFFICIENT_STATIC_SOURCE_PACKAGE, "invalid:static_pdf_sources:must_be_nonempty_list"),
        ("unsafe_static_url", discovery.INSUFFICIENT_STATIC_SOURCE_PACKAGE, "invalid:static_pdf_sources[0].url:must_be_static_cninfo_finalpage_pdf"),
        ("missing_page", discovery.INSUFFICIENT_STATIC_SOURCE_PACKAGE, "invalid:static_pdf_sources[0].field_refs:must_contain_paged_field_references"),
        ("action_leak", discovery.STAGE0_REJECTED, "invalid:package:must_not_contain_action_target_or_outcome_information"),
        ("hypothesis_leak", discovery.STAGE0_REJECTED, "invalid:package:contains_unapproved_information"),
        ("arena_mismatch", discovery.STAGE0_REJECTED, "invalid:members[0].competitive_arena_id:must_match_package_arena"),
    ],
)
def test_stage0_static_package_rejects_source_and_information_boundary_breaks(
    mutation: str, state: str, finding: str,
) -> None:
    package = _stage0_static_package()
    if mutation == "missing_static_source":
        package["static_pdf_sources"] = []
    elif mutation == "unsafe_static_url":
        package["static_pdf_sources"][0]["url"] = "https://www.cninfo.com.cn/new/index"
    elif mutation == "missing_page":
        package["static_pdf_sources"][0]["field_refs"] = ["annual report business section"]
    elif mutation == "action_leak":
        package["action_id"] = "ACTION:LEAK"
    elif mutation == "hypothesis_leak":
        package["hypothesis_pair"] = {"primary": "H-A", "rival": "H-B"}
    else:
        package["members"][0]["competitive_arena_id"] = "ARENA:OTHER"

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == state
    assert finding in result["findings"]


def test_stage0_static_package_rejects_cross_member_pdf_substitution() -> None:
    package = _stage0_static_package()
    target_source = package["members"][0]["industry_business_evidence"][0]
    peer_evidence = package["members"][1]["industry_business_evidence"][0]
    peer_evidence["source_id"] = target_source["source_id"]
    peer_evidence["field_ref"] = target_source["field_ref"]

    result = discovery.validate_stage0_static_source_package(package)

    assert result["state"] == discovery.INSUFFICIENT_STATIC_SOURCE_PACKAGE
    assert "invalid:members[1].evidence[0].issuer_id:must_match_declared_static_pdf_identity" in result["findings"]


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        ("single_product", "invalid:action.action_scope:must_be_candidate_common_boundary"),
        ("subsidiary", "invalid:action.action_scope:must_be_candidate_common_boundary"),
        ("compensation", "invalid:action.economic_character:must_be_commercial_competitive_decision"),
        ("planned", "invalid:action.action_state:must_be_implemented_or_irrevocably_incurred"),
        ("post_cutoff_source", "invalid:action.implementation_evidence[0]_not_cutoff_before"),
        ("d2_revenue", "invalid:d2_observability.observation_kind:must_be_independent_customer_absorption_measure"),
        ("d2_mechanical", "invalid:d2_observability.not_mechanically_changed_by_action:must_be_true"),
        ("illegal_rival", "invalid:hypothesis_pair.strongest_rival.live_before_cutoff:must_be_true"),
        ("firewall", "invalid:source_firewall.outcome_metadata_access:must_be_none"),
        ("missing_cohort", "invalid:cohort_record_not_object"),
        ("cohort_after_action", "invalid:cohort_selection_as_of_not_before_action"),
        ("missing_access_receipt", "missing:source_firewall.access_receipt"),
        ("allowlist_gap", "invalid:source_firewall.access_receipt:supplied_source_not_in_phase10_allowlist"),
        ("missing_discovery_entry", "missing:source_firewall.discovery_entry"),
        ("unsafe_issuer_fulltext", "invalid:source_firewall.discovery_entry.kind:must_be_predeclared_cutoff_before_static_cninfo_pdf_package"),
        ("unsafe_industry_keyword_fulltext", "invalid:source_firewall.discovery_entry.kind:must_be_predeclared_cutoff_before_static_cninfo_pdf_package"),
        ("issuer_lookup_attested", "invalid:source_firewall.discovery_entry.issuer_code_or_name_submitted_to_cninfo_fulltext:must_be_false"),
        ("non_static_post_identification_access", "invalid:source_firewall.discovery_entry.post_identification_access:must_be_predeclared_cutoff_before_static_cninfo_pdf_package_only"),
        ("static_pdf_not_supplied", "invalid:source_firewall.discovery_entry.static_pdf_sources[1].source_id:must_be_a_supplied_cutoff_before_source"),
    ],
)
def test_discovery_triage_rejects_known_pre_candidate_failure_shapes(
    mutation: str, finding: str,
) -> None:
    manifest = _manifest()
    if mutation == "single_product":
        manifest["action"]["action_scope"] = "PRODUCT_ONLY"
    elif mutation == "subsidiary":
        manifest["action"]["action_scope"] = "SUBSIDIARY_ONLY"
    elif mutation == "compensation":
        manifest["action"]["economic_character"] = "GOVERNMENT_COMPENSATION"
    elif mutation == "planned":
        manifest["action"]["action_state"] = "PLANNED"
    elif mutation == "post_cutoff_source":
        manifest["action"]["implementation_evidence"][0]["published_at"] = "2021-01-15"
    elif mutation == "d2_revenue":
        manifest["d2_observability"]["observation_kind"] = "REVENUE_ALONE"
    elif mutation == "d2_mechanical":
        manifest["d2_observability"]["not_mechanically_changed_by_action"] = False
    elif mutation == "illegal_rival":
        manifest["hypothesis_pair"]["strongest_rival"]["live_before_cutoff"] = False
    elif mutation == "firewall":
        manifest["source_firewall"]["outcome_metadata_access"] = "TITLE_ONLY"
    elif mutation == "missing_cohort":
        manifest.pop("cohort_feasibility_record")
    elif mutation == "cohort_after_action":
        manifest["cohort_feasibility_record"]["selection_as_of"] = "2020-10-15"
    elif mutation == "missing_access_receipt":
        manifest["source_firewall"].pop("access_receipt")
    elif mutation == "missing_discovery_entry":
        manifest["source_firewall"].pop("discovery_entry")
    elif mutation == "unsafe_issuer_fulltext":
        manifest["source_firewall"]["discovery_entry"]["kind"] = "CNINFO_FULLTEXT_ISSUER_LOOKUP"
    elif mutation == "unsafe_industry_keyword_fulltext":
        manifest["source_firewall"]["discovery_entry"]["kind"] = "NON_ISSUER_IDENTIFYING_INDUSTRY_KEYWORD"
    elif mutation == "issuer_lookup_attested":
        manifest["source_firewall"]["discovery_entry"]["issuer_code_or_name_submitted_to_cninfo_fulltext"] = True
    elif mutation == "non_static_post_identification_access":
        manifest["source_firewall"]["discovery_entry"]["post_identification_access"] = "CNINFO_STOCK_PAGE"
    elif mutation == "static_pdf_not_supplied":
        manifest["source_firewall"]["discovery_entry"]["static_pdf_sources"][1]["source_id"] = "UNDECLARED:PDF"
    else:
        manifest["source_firewall"]["access_receipt"]["allowed_source_ids"].pop()

    result = discovery.triage_selection_discovery_manifest(manifest)

    assert result["state"] == discovery.NO_PRIMARY
    assert finding in result["findings"]
    assert result["next_acquisition_package"] == []


def test_discovery_triage_returns_precise_missing_source_field() -> None:
    manifest = _manifest()
    del manifest["d2_observability"]["repetitions"][1]["evidence"][0]["field_ref"]

    result = discovery.triage_selection_discovery_manifest(manifest)

    assert result["state"] == discovery.NO_PRIMARY
    assert "invalid:d2_observability.repetitions[1].evidence[0]_invalid" in result["findings"]
