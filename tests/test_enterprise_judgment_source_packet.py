from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_source_packet as packet


def _receipt() -> dict:
    packet_id = "SP:SYNTHETIC:DATE-PRECISE"
    source_id = "SRC:OFFICIAL:ONE"
    field_id = "FIELD:ENTERPRISE_STATE"
    field_ref = packet.build_field_ref(packet_id, source_id, field_id)
    locator_id = "LOC:ENTERPRISE_STATE:P10"
    return {
        "schema_version": packet.SCHEMA_VERSION,
        "packet_id": packet_id,
        "packet_version": 1,
        "company_id": "COMPANY:SYNTHETIC",
        "issuer_id": "ISSUER:SYNTHETIC",
        "cutoff_at": "2025-02-02T00:00:00+08:00",
        "fields": [{
            "field_id": field_id,
            "field_ref": field_ref,
            "source_id": source_id,
            "status": "LOCATED",
            "material_claim_ids": ["CLAIM:ENTERPRISE_STATE"],
            "locator_ids": [locator_id],
        }],
        "sources": [{
            "source_id": source_id,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://official.example/annual-report.pdf",
            "published_on": "2025-01-30",
            "available_on": "2025-02-01",
            "availability_timezone": "Asia/Shanghai",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["UNIT:CONSOLIDATED"],
            "responsibility_perimeter_id": "PERIMETER:LISTED_CONSOLIDATED",
            "unit": "RMB",
            "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": [{
                "locator_id": locator_id,
                "field_id": field_id,
                "field_ref": field_ref,
                "research_question_id": "Q:STATE",
                "locator": "p. 10 business and boundary",
                "page_number": 10,
                "paragraph_ref": "business and boundary",
            }],
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": list(packet.ALLOWED_OUTPUTS),
    }


def _express_receipt() -> dict:
    packet_id = "SP:CN:600233:FY2018"
    source_id = "SRC:CNINFO:600233:FY2018"
    field_id = "FIELD:600233:FY2018:PARCEL_VOLUME"
    locator_id = "LOC:600233:FY2018:PARCEL_VOLUME:P26"
    field_ref = packet.build_field_ref(packet_id, source_id, field_id)
    return {
        "schema_version": packet.SCHEMA_VERSION,
        "packet_id": packet_id,
        "packet_version": 1,
        "company_id": "CN:600233",
        "issuer_id": "ISSUER:CN:600233",
        "cutoff_at": "2019-05-01T00:00:00+08:00",
        "fields": [{
            "field_id": field_id,
            "field_ref": field_ref,
            "source_id": source_id,
            "status": "LOCATED",
            "material_claim_ids": ["CLAIM:PARCEL_VOLUME_BASELINE"],
            "locator_ids": [locator_id],
        }],
        "sources": [{
            "source_id": source_id,
            "source_type": "OFFICIAL_AUDITED_ANNUAL_REPORT",
            "official_url": "https://static.cninfo.com.cn/finalpage/2019-04-18/1206048595.PDF",
            "published_on": "2019-04-18",
            "available_on": "2019-04-18",
            "availability_timezone": "Asia/Shanghai",
            "eligibility": "ELIGIBLE",
            "responsibility_boundary_ids": ["UNIT:CONSOLIDATED_EXPRESS_NETWORK"],
            "responsibility_perimeter_id": "PERIMETER:LISTED_CONSOLIDATED",
            "unit": "PARCELS",
            "access_mode": "REMOTE_OFFICIAL_LOCATOR",
            "locators": [{
                "locator_id": locator_id,
                "field_id": field_id,
                "field_ref": field_ref,
                "research_question_id": "Q:CUSTOMER_COMPETITION_RESPONSE",
                "locator": "PDF p. 26 parcel-volume operating disclosure",
                "page_number": 26,
                "paragraph_ref": "parcel-volume operating disclosure",
            }],
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": list(packet.ALLOWED_OUTPUTS),
    }


def test_date_precise_receipt_projects_locator_map_for_episode_compiler() -> None:
    receipt = _receipt()
    result = packet.compile_core_source_package(receipt)
    assert result["valid"], result["findings"]
    source = result["source_package"]["sources"][0]
    assert source["available_at"] == "2025-02-01T15:59:59+00:00"
    locator = result["locator_map"]["LOC:ENTERPRISE_STATE:P10"]
    assert locator == result["source_packet_read_model"]["locator_map"][locator["locator_id"]]
    assert locator["packet_id"] == receipt["packet_id"]
    assert locator["source_id"] == receipt["sources"][0]["source_id"]
    assert locator["field_id"] == receipt["fields"][0]["field_id"]
    assert locator["field_ref"] == receipt["fields"][0]["field_ref"]
    assert locator["page_number"] == 10
    assert locator["cutoff_eligible"] is True
    assert locator["source_packet_member"] is True
    attestation = result["source_packet_read_model"]["precision_attestations"][0]
    assert attestation["treatment"] == "CONSERVATIVE_END_OF_STATED_DAY"
    assert result["source_packet_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"


def test_source_packet_rejects_date_after_cutoff_and_outcome_payloads() -> None:
    late = _receipt()
    late["sources"][0]["available_on"] = "2025-02-02"
    result = packet.validate_source_packet_receipt(late)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0].available_on_after_cutoff" in result["findings"]

    contaminated = _receipt()
    contaminated["sources"][0]["outcome_value"] = 99
    result = packet.validate_source_packet_receipt(contaminated)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0]_contains_unapproved_field:outcome_value" in result["findings"]

    inverted = _receipt()
    inverted["sources"][0]["published_on"] = "2025-02-02"
    result = packet.validate_source_packet_receipt(inverted)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0].published_on_after_available_on" in result["findings"]


def test_source_packet_rejects_dynamic_pages_even_with_official_access_mode() -> None:
    wrong_mode = _receipt()
    wrong_mode["sources"][0]["access_mode"] = "DYNAMIC_CNINFO_DETAIL_PAGE"
    result = packet.validate_source_packet_receipt(wrong_mode)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0].access_mode_invalid" in result["findings"]

    disguised = _receipt()
    disguised["sources"][0]["official_url"] = (
        "https://www.cninfo.com.cn/new/disclosure/detail?stockCode=600233"
    )
    disguised["sources"][0]["access_mode"] = "REMOTE_OFFICIAL_LOCATOR"
    result = packet.validate_source_packet_receipt(disguised)
    assert not result["valid"]
    assert (
        "source_packet_receipt.sources[0].official_url_dynamic_cninfo_not_allowed"
        in result["findings"]
    )


def test_locator_ids_and_field_bindings_are_closed_within_one_packet() -> None:
    duplicate = _receipt()
    duplicate["sources"][0]["locators"].append(
        deepcopy(duplicate["sources"][0]["locators"][0])
    )
    result = packet.validate_source_packet_receipt(duplicate)
    assert not result["valid"]
    assert (
        "source_packet_receipt.sources[0].locators[1].locator_id_duplicate_in_receipt"
        in result["findings"]
    )

    dangling = _receipt()
    dangling_locator = dangling["sources"][0]["locators"][0]
    dangling_locator["field_id"] = "FIELD:MISSING"
    dangling_locator["field_ref"] = packet.build_field_ref(
        dangling["packet_id"], dangling["sources"][0]["source_id"], "FIELD:MISSING"
    )
    result = packet.validate_source_packet_receipt(dangling)
    assert not result["valid"]
    assert (
        "source_packet_receipt.sources[0].locators[0].field_id_dangling"
        in result["findings"]
    )

    cross_source = _receipt()
    second_source = deepcopy(cross_source["sources"][0])
    second_source["source_id"] = "SRC:OFFICIAL:TWO"
    second_source["official_url"] = "https://official.example/second-annual-report.pdf"
    second_source["locators"] = []
    cross_source["sources"].append(second_source)
    field = cross_source["fields"][0]
    field["source_id"] = second_source["source_id"]
    field["field_ref"] = packet.build_field_ref(
        cross_source["packet_id"], second_source["source_id"], field["field_id"]
    )
    cross_source["sources"][0]["locators"][0]["field_ref"] = field["field_ref"]
    result = packet.validate_source_packet_receipt(cross_source)
    assert not result["valid"]
    assert (
        "source_packet_receipt.sources[0].locators[0].field_cross_source_reference"
        in result["findings"]
    )


def test_nonmaterial_unknown_and_missing_locator_degrade_locally() -> None:
    receipt = _receipt()
    source_id = receipt["sources"][0]["source_id"]
    field_id = "FIELD:CUSTOMER_RESPONSE"
    receipt["fields"].append({
        "field_id": field_id,
        "field_ref": packet.build_field_ref(receipt["packet_id"], source_id, field_id),
        "source_id": source_id,
        "status": "UNKNOWN",
        "material_claim_ids": [],
        "locator_ids": ["LOC:CUSTOMER_RESPONSE:MISSING"],
    })
    result = packet.compile_core_source_package(receipt)
    assert result["valid"], result["findings"]
    assert set(result["locator_map"]) == {"LOC:ENTERPRISE_STATE:P10"}
    assert result["field_map"][field_id]["usable_locator_ids"] == []
    assert any("locator_ids_missing_from_packet" in item for item in result["degradations"])
    assert any("field_status_unknown" in item for item in result["degradations"])


def test_material_claim_dependency_turns_missing_or_incomplete_locator_into_failure() -> None:
    missing = _receipt()
    missing["fields"][0]["locator_ids"] = ["LOC:MISSING"]
    missing["sources"][0]["locators"] = []
    result = packet.validate_source_packet_receipt(missing)
    assert not result["valid"]
    assert any("locator_ids_missing_from_packet" in item for item in result["findings"])
    assert any("material_claim_dependency" in item for item in result["findings"])

    incomplete = _receipt()
    locator = incomplete["sources"][0]["locators"][0]
    locator.pop("page_number")
    locator.pop("paragraph_ref")
    result = packet.validate_source_packet_receipt(incomplete)
    assert not result["valid"]
    assert (
        "source_packet_receipt.sources[0].locators[0].page_or_paragraph_locator_missing_for_material_claim"
        in result["findings"]
    )


def test_nonmaterial_incomplete_locator_does_not_invalidate_other_fields() -> None:
    receipt = _receipt()
    receipt["fields"][0]["material_claim_ids"] = []
    locator = receipt["sources"][0]["locators"][0]
    locator.pop("page_number")
    locator.pop("paragraph_ref")
    result = packet.validate_source_packet_receipt(receipt)
    assert result["valid"], result["findings"]
    assert result["locator_map"] == {}
    assert any("page_or_paragraph_locator_missing" in item for item in result["degradations"])


def test_non_cement_express_fixture_has_no_company_or_year_special_case() -> None:
    receipt = _express_receipt()
    result = packet.compile_core_source_package(receipt)
    assert result["valid"], result["findings"]
    locator_id = receipt["fields"][0]["locator_ids"][0]
    assert result["locator_map"][locator_id]["packet_id"] == "SP:CN:600233:FY2018"
    assert result["locator_map"][locator_id]["field_id"].endswith(":PARCEL_VOLUME")
    assert result["source_package"]["company_id"] == "CN:600233"


def test_source_packet_schema_is_closed_and_exposes_v2_bindings() -> None:
    schema = json.loads(
        Path("schemas/enterprise_judgment_source_packet_receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["additionalProperties"] is False
    assert schema["properties"]["schema_version"]["const"] == packet.SCHEMA_VERSION
    assert schema["properties"]["allowed_outputs"]["const"] == packet.ALLOWED_OUTPUTS
    assert "fields" in schema["required"]
    assert {
        "locator_id", "field_id", "field_ref", "research_question_id", "locator",
    }.issubset(schema["$defs"]["locator"]["required"])
    assert schema["$defs"]["field"]["properties"]["locator_ids"]["uniqueItems"] is True
