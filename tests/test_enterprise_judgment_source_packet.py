from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import enterprise_judgment_source_packet as packet


def _receipt() -> dict:
    return {
        "schema_version": packet.SCHEMA_VERSION,
        "packet_id": "SP:SYNTHETIC:DATE-PRECISE",
        "packet_version": 1,
        "company_id": "COMPANY:SYNTHETIC",
        "issuer_id": "ISSUER:SYNTHETIC",
        "cutoff_at": "2025-02-02T00:00:00+08:00",
        "sources": [{
            "source_id": "SRC:OFFICIAL:ONE",
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
            "locators": [{"research_question_id": "Q:STATE", "locator": "p. 10 business and boundary"}],
        }],
        "object_class": "SOURCE_PACKET_RECEIPT",
        "claim_class": "CUTOFF_ELIGIBLE_SOURCE_RECEIPT",
        "allowed_outputs": list(packet.ALLOWED_OUTPUTS),
    }


def test_date_precise_receipt_projects_a_conservative_core_source_package() -> None:
    receipt = _receipt()
    result = packet.compile_core_source_package(receipt)
    assert result["valid"], result["findings"]
    source = result["source_package"]["sources"][0]
    assert source["available_at"] == "2025-02-01T15:59:59+00:00"
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

    dynamic = _receipt()
    dynamic["sources"][0]["access_mode"] = "DYNAMIC_CNINFO_DETAIL_PAGE"
    result = packet.validate_source_packet_receipt(dynamic)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0].access_mode_invalid" in result["findings"]

    inverted = _receipt()
    inverted["sources"][0]["published_on"] = "2025-02-02"
    result = packet.validate_source_packet_receipt(inverted)
    assert not result["valid"]
    assert "source_packet_receipt.sources[0].published_on_after_available_on" in result["findings"]


def test_source_packet_schema_is_closed() -> None:
    schema = json.loads(Path("schemas/enterprise_judgment_source_packet_receipt.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["allowed_outputs"]["const"] == packet.ALLOWED_OUTPUTS
