from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import pytest

from scripts import judgment_action_first_control_plane as control
from scripts import judgment_selection_action_first as action_first


def _receipt() -> dict:
    return {
        "schema_version": action_first.SCHEMA_VERSION,
        "receipt_id": "A1:RECEIPT:SYNTHETIC:ONE",
        "receipt_version": 1,
        "candidate_id": "A1:CANDIDATE:SECRET",
        "company_id": "COMPANY:SYNTHETIC:ONE",
        "issuer_id": "ISSUER:SYNTHETIC:ONE",
        "responsibility_unit_id": "RU:SYNTHETIC:OPERATIONS",
        "perimeter_id": "PERIMETER:SYNTHETIC:CONSOLIDATED",
        "cutoff_at": "2020-06-30T23:59:59+08:00",
        "arena_family": "SYNTHETIC_EXPORT_MANUFACTURING",
        "mechanism_topology": "COST_RESTRUCTURING",
        "action": {
            "action_id": "ACTION:SECRET:UPSTREAM_START",
            "implemented_at": "2020-05-01T08:00:00+08:00",
            "implementation_status": action_first.IMPLEMENTED_MATERIAL,
            "implemented_material_action": "A synthetic upstream operating line began production.",
            "responsibility_unit_id": "RU:SYNTHETIC:OPERATIONS",
            "perimeter_id": "PERIMETER:SYNTHETIC:CONSOLIDATED",
            "source_ids": ["SOURCE:SYNTHETIC:ACTION"],
        },
        "hypotheses": {
            "h_a": {
                "hypothesis_id": "H-A:SECRET",
                "mechanism": "Internal supply may reduce an input-cost exposure.",
                "source_ids": ["SOURCE:SYNTHETIC:ACTION"],
            },
            "h_b": {
                "hypothesis_id": "H-B:SECRET",
                "mechanism": "Capacity utilisation may explain the same action without a cost advantage.",
                "source_ids": ["SOURCE:SYNTHETIC:ACTION"],
            },
            "strongest_rival": {
                "hypothesis_id": "H-B:SECRET",
                "explanation": "The operating start can be capacity expansion rather than a lower-cost mechanism.",
                "source_ids": ["SOURCE:SYNTHETIC:ACTION"],
            },
        },
        "static_sources": [{
            "source_id": "SOURCE:SYNTHETIC:ACTION",
            "official_artifact_id": "CNINFO:SYNTHETIC:1200000001",
            "source_url": "https://static.cninfo.com.cn/finalpage/2020-05-01/1200000001.PDF",
            "source_type": action_first.OFFICIAL_STATIC_FINALPAGE_PDF,
            "availability_precision": action_first.TIMESTAMP,
            "published_at": "2020-05-01T12:00:00+08:00",
            "issuer_id": "ISSUER:SYNTHETIC:ONE",
            "responsibility_unit_id": "RU:SYNTHETIC:OPERATIONS",
            "perimeter_id": "PERIMETER:SYNTHETIC:CONSOLIDATED",
            "page": 3,
            "supports": ["IMPLEMENTATION", "MATERIALITY", "HYPOTHESIS", "RIVAL"],
        }],
        "allowed_outputs": [action_first.COMPARATOR_RECRUITMENT_BRIEF],
        "method_transfer_rights": action_first.NO_METHOD_TRANSFER_RIGHTS,
    }


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    control.initialize(conn)
    return conn


def test_valid_receipt_builds_only_an_action_blind_comparator_brief() -> None:
    receipt = _receipt()
    result = action_first.validate_action_first_candidate_receipt(receipt)

    assert result["valid"], result["findings"]
    brief = action_first.build_comparator_recruitment_brief(receipt)
    assert brief == {
        "schema_version": action_first.BRIEF_SCHEMA_VERSION,
        "cutoff_at": "2020-06-30T23:59:59+08:00",
        "arena_family": "SYNTHETIC_EXPORT_MANUFACTURING",
        "mechanism_topology": "COST_RESTRUCTURING",
        "required_carrier_identity": {
            "issuer_id": "ISSUER:SYNTHETIC:ONE",
            "responsibility_unit_id": "RU:SYNTHETIC:OPERATIONS",
            "perimeter_id": "PERIMETER:SYNTHETIC:CONSOLIDATED",
        },
        "static_evidence_conditions": [
            "OFFICIAL_STATIC_FINALPAGE_PDF_ONLY",
            "TIMESTAMPED_SOURCE_STRICTLY_BEFORE_CUTOFF",
            "PAGE_LEVEL_CARRIER_IDENTITY_REQUIRED",
        ],
        "d2_or_cost_conditions": [
            "CUTOFF_BEFORE_COST_DRIVER_HISTORY_REQUIRED",
            "SAME_OR_EXPLICITLY_BRIDGED_RESPONSIBILITY_UNIT_REQUIRED",
        ],
        "d3_d4_conditions": [
            "CUTOFF_BEFORE_RECURRING_D3_FIELD_HISTORY_REQUIRED",
            "CUTOFF_BEFORE_RECURRING_D4_FIELD_HISTORY_REQUIRED",
            "SAME_OR_EXPLICITLY_BRIDGED_PERIMETER_REQUIRED",
        ],
        "control_conditions": [
            "MECHANISM_COMPATIBLE_ARENA_MEMBERSHIP_REQUIRED",
            "NO_POST_CUTOFF_MATERIAL",
            "NO_OUTCOME_PRICE_RETURN_OR_VALUATION_ACCESS",
            "NO_FINAL_PEER_OR_PANEL_SELECTION",
        ],
    }
    rendered = json.dumps(brief, sort_keys=True)
    for forbidden_text in (
        "A1:CANDIDATE:SECRET",
        "ACTION:SECRET:UPSTREAM_START",
        "SOURCE:SYNTHETIC:ACTION",
        "1200000001",
        "H-A:SECRET",
        "H-B:SECRET",
        "Internal supply may reduce",
        "Capacity utilisation may explain",
        "target",
        "peer_panel",
    ):
        assert forbidden_text not in rendered


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (lambda item: item["action"].__setitem__("implementation_status", "PLANNED"), "action.implementation_status_must_be_implemented_material"),
        (lambda item: item["static_sources"][0].__setitem__("source_url", "https://www.cninfo.com.cn/new/disclosure/detail"), "static_sources[0].source_url_must_be_static_cninfo_finalpage_pdf"),
        (lambda item: item["static_sources"][0].__setitem__("published_at", "2020-06-30T23:59:59+08:00"), "static_sources[0].published_at_must_strictly_precede_cutoff"),
        (lambda item: item["static_sources"][0].update({"availability_precision": "DATE_ONLY", "published_at": "2020-05-01"}), "static_sources[0].availability_precision_must_be_timestamp"),
        (lambda item: item["static_sources"][0].__setitem__("issuer_id", "ISSUER:SYNTHETIC:TWO"), "static_sources[0].issuer_id_must_match_receipt"),
        (lambda item: item["action"].__setitem__("responsibility_unit_id", "RU:SYNTHETIC:OTHER"), "action.responsibility_unit_id_must_match_receipt"),
        (lambda item: item["static_sources"][0].__setitem__("page", "3"), "static_sources[0].page_must_be_positive_integer"),
    ],
)
def test_rejects_unimplemented_dynamic_timing_identity_and_type_failures(mutation, finding: str) -> None:
    receipt = _receipt()
    mutation(receipt)

    result = action_first.validate_action_first_candidate_receipt(receipt)

    assert not result["valid"]
    assert finding in result["findings"]


@pytest.mark.parametrize("forbidden_field", ["outcome", "price", "return", "valuation", "peer_panel", "h2", "cjo", "report", "learning", "investment"])
def test_rejects_every_prohibited_downstream_field(forbidden_field: str) -> None:
    receipt = _receipt()
    receipt[forbidden_field] = "not permitted in A1"

    result = action_first.validate_action_first_candidate_receipt(receipt)

    assert not result["valid"]
    assert f"receipt_contains_forbidden_field:{forbidden_field}" in result["findings"]


def test_requires_static_implementation_and_materiality_evidence() -> None:
    receipt = _receipt()
    receipt["static_sources"][0]["supports"] = ["HYPOTHESIS", "RIVAL"]

    result = action_first.validate_action_first_candidate_receipt(receipt)

    assert not result["valid"]
    assert "action.source_ids_must_include_implementation_evidence" in result["findings"]
    assert "action.source_ids_must_include_materiality_evidence" in result["findings"]


def test_requires_hypothesis_and_rival_specific_static_source_support() -> None:
    receipt = _receipt()
    receipt["static_sources"][0]["supports"] = ["IMPLEMENTATION", "MATERIALITY"]

    result = action_first.validate_action_first_candidate_receipt(receipt)

    assert not result["valid"]
    assert "hypotheses.h_a.source_ids_must_include_hypothesis_evidence" in result["findings"]
    assert "hypotheses.h_b.source_ids_must_include_hypothesis_evidence" in result["findings"]
    assert "hypotheses.strongest_rival.source_ids_must_include_rival_evidence" in result["findings"]


def test_control_plane_is_append_only_idempotent_and_replays_exact_receipt() -> None:
    conn = _conn()
    receipt = _receipt()
    registered_at = "2020-07-01T08:00:00+08:00"

    first = control.register_candidate_receipt(conn, receipt, registered_at=registered_at)
    second = control.register_candidate_receipt(conn, deepcopy(receipt), registered_at=registered_at)

    assert first == {
        "registered": True,
        "receipt_id": receipt["receipt_id"],
        "receipt_version": 1,
        "idempotent": False,
    }
    assert second["idempotent"] is True
    assert control.replay_candidate_receipt(
        conn, receipt_id=receipt["receipt_id"], receipt_version=1,
    ) == receipt
    assert control.load_comparator_recruitment_brief(
        conn, receipt_id=receipt["receipt_id"], receipt_version=1,
    ) == action_first.build_comparator_recruitment_brief(receipt)

    conflicting = deepcopy(receipt)
    conflicting["action"]["implemented_material_action"] = "A different action is not a replay."
    with pytest.raises(control.ActionFirstControlPlaneError, match="different content") as error:
        control.register_candidate_receipt(conn, conflicting, registered_at=registered_at)
    assert error.value.code == "candidate_receipt_immutable_conflict"

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute(f"UPDATE {control.RECEIPT_TABLE} SET candidate_id = 'mutated'")


def test_schema_is_closed_and_declares_the_same_single_a1_permission() -> None:
    schema_path = Path("schemas/judgment_selection_action_first_candidate_receipt.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert schema["properties"]["allowed_outputs"]["const"] == [action_first.COMPARATOR_RECRUITMENT_BRIEF]
    assert schema["properties"]["method_transfer_rights"]["const"] == action_first.NO_METHOD_TRANSFER_RIGHTS
    assert schema["$defs"]["static_source"]["additionalProperties"] is False
