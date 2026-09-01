from __future__ import annotations

import json
from pathlib import Path


_RESULT = Path("docs/development/research/cohorts/CACT003_A1_CANONICALIZATION_CURATOR_RESULT_V1.json")


def test_cact003_canonicalization_stops_without_inventing_a_dushan_boundary() -> None:
    """Timestamped metadata cannot promote issuer context into a Dushan A1 receipt."""
    result = json.loads(_RESULT.read_text(encoding="utf-8"))

    assert result["status"] == "EVIDENCE_INELIGIBLE_NO_A1_RECEIPT"
    assert result["allowed_outputs"] == ["EVIDENCE_INELIGIBLE_STOP_RECEIPT_ONLY"]
    assert result["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"
    assert result["canonicalization_result"]["timestamp_requirement"] == "SATISFIED"
    assert result["canonicalization_result"]["same_boundary_bridge_requirement"] == "NOT_SATISFIED"
    assert all(item["availability_precision"] == "TIMESTAMP" for item in result["official_metadata_availability"])
    assert all(item["cutoff_check"] == "STRICTLY_BEFORE_CUTOFF" for item in result["official_metadata_availability"])

    direct_action = result["static_source_boundary_reading"][0]
    issuer_context = result["static_source_boundary_reading"][2:]
    assert direct_action["declared_responsibility_unit_id"] == result["candidate_binding"]["proposed_action_responsibility_unit_id"]
    assert all(item["declared_responsibility_unit_id"] is None for item in issuer_context)
    assert "H2" in result["information_boundary"]["prohibited_inputs"]
    assert "OUTCOME_DOCUMENTS" in result["information_boundary"]["prohibited_inputs"]
