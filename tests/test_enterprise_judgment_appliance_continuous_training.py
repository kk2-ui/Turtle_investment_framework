from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import enterprise_judgment_appliance_continuous_training as training


ROOT = Path(__file__).resolve().parents[1]
ROUND10 = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_ROUND10_V2_POSTOUTCOME"
ARTIFACT = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_CONTINUOUS_TRAINING_V1" / "CN002032_20180930_PREOUTCOME_FREEZE_RECEIPT.json"
CONTROLLER_RECEIPT = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_CONTINUOUS_TRAINING_V1" / "CN002032_20180930_CONTROLLER_PREOUTCOME_FREEZE_RECEIPT.json"


def _round10_inputs():
    return (
        json.loads((ROUND10 / "02_external_method_review.json").read_text()),
        json.loads((ROUND10 / "03_batch_completion_receipt.json").read_text()),
    )


def _objects():
    review, completion = _round10_inputs()
    candidate = training.build_curriculum_candidate(review, completion)
    roster = training.build_roster()
    episode = training.build_preoutcome_episode(candidate, roster)
    return candidate, roster, episode


def test_round10_negative_result_compiles_one_future_only_curriculum_candidate():
    candidate, _, _ = _objects()
    result = training.validate_curriculum_candidate(candidate)
    assert result["valid"], result["findings"]
    assert candidate["round10_conclusion_preserved"] == "NO_MATERIAL_UTILITY"
    assert candidate["automatic_method_advantage_count"] == 0
    assert candidate["rights"] == training.RIGHTS


def test_roster_uses_role_company_cutoff_exposure_not_company_blacklist():
    _, roster, _ = _objects()
    result = training.validate_roster(roster)
    assert result["valid"], result["findings"]
    first = roster["candidate_order"][0]
    assert roster["selection_basis"] == "ROLE_X_COMPANY_X_CUTOFF_ACTUAL_INPUT_EXPOSURE"
    assert roster["company_level_blacklist_policy"].startswith("PROHIBITED")
    assert first["company_id"] == "CN:002032"
    assert first["cutoff_at"] == training.CUTOFF_AT
    assert first["actual_input_exposure"] == "CUTOFF_BEFORE_SOURCE_ONLY"
    assert first["preoutcome_role_ids"] == [training.CURATOR_ID, training.FORECASTER_ID]
    assert first["role_independence"] == "SEQUENTIAL_FUNCTIONAL_PARTITION_NOT_HOLDOUT"


def test_supor_episode_freezes_product_boundary_and_existing_minimal_contracts():
    candidate, roster, episode = _objects()
    result = training.validate_preoutcome_episode(episode, curriculum_candidate=candidate, roster=roster)
    assert result["valid"], result["findings"]
    assert episode["fair_baseline"]["fact_refs"] == episode["cumulative_enhanced"]["fact_refs"]
    assert episode["fair_baseline"]["treatment"] == "CONTINUE_OPERATING_UNDERWRITING"
    assert episode["cumulative_enhanced"]["treatment"] == "CONDITIONAL_PRODUCT_QUALITY_UNDERWRITING"
    metrics = [row["measurement_contract"]["metric_id"] for row in episode["minimal_field_chains"]]
    assert metrics == [
        "CONSOLIDATED_REVENUE_RMB",
        "PRODUCT_REVENUE_RMB:电锅类",
        "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
    ]
    assert episode["outcome_access"] == {"authorized": False, "content_read": False, "custodian_started": False}
    assert episode["rights"] == training.RIGHTS


def test_product_boundary_or_outcome_contamination_rejects_without_widening_other_fields():
    candidate, roster, episode = _objects()
    drift = deepcopy(episode)
    drift["minimal_field_chains"][1]["measurement_contract"]["responsibility_boundary"] = "LISTED_ISSUER_CONSOLIDATED:CN002032"
    result = training.validate_preoutcome_episode(drift, curriculum_candidate=candidate, roster=roster)
    assert not result["valid"]
    assert any("responsibility_boundary" in finding for finding in result["findings"])

    contaminated = deepcopy(episode)
    contaminated["outcome_label"] = "INCREASE"
    result = training.validate_preoutcome_episode(contaminated, curriculum_candidate=candidate, roster=roster)
    assert not result["valid"]
    assert any("outcome_label_forbidden_preoutcome" in finding for finding in result["findings"])


def test_committed_freeze_receipt_matches_canonical_episode_identity():
    candidate, roster, episode = _objects()
    receipt = json.loads(ARTIFACT.read_text())
    assert receipt["episode_id"] == episode["episode_id"]
    assert receipt["curriculum_candidate_id"] == candidate["curriculum_candidate_id"]
    assert receipt["roster_id"] == roster["roster_id"]
    assert receipt["company_id"] == episode["company_id"]
    assert receipt["cutoff_at"] == episode["cutoff_at"]
    assert receipt["source_id"] == episode["source_packet"]["source"]["source_id"]
    assert receipt["field_contract_ids"] == [
        row["measurement_contract"]["measurement_contract_id"]
        for row in episode["minimal_field_chains"]
    ]
    assert receipt["predicted_directions"] == {
        row["measurement_contract"]["metric_id"]: row["prediction"]["predicted_direction"]
        for row in episode["minimal_field_chains"]
    }
    assert receipt["outcome_access"] == episode["outcome_access"]
    assert receipt["rights"] == training.RIGHTS


def _pdf_page_text(page: int) -> str:
    if page == 12:
        return """
        营业收入合计 14,187,347,425.77 100% 11,947,123,201.12 100% 18.75%
        电锅类 3,809,138,321.20 26.85% 3,462,194,790.53 28.98% 10.02%
        """
    if page == 16:
        return "经营活动产生的现金流量净额 1,081,469,057.39 1,388,911,912.47 -22.14%"
    return ""


def test_existing_runner_freezes_all_three_fields_with_controller_owned_chronology(tmp_path, monkeypatch):
    review, completion = _round10_inputs()
    fake_pdf = tmp_path / "registered-cn002032-fy2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    opened_pages = []

    def fake_pdftotext(command, **kwargs):
        assert command[:2] == ["pdftotext", "-f"]
        assert command[3:5] == ["-l", command[2]]
        assert command[5:] == ["-layout", str(fake_pdf), "-"]
        page = int(command[2])
        opened_pages.append(page)
        return SimpleNamespace(stdout=_pdf_page_text(page))

    monkeypatch.setattr(training.subprocess, "run", fake_pdftotext)
    database = tmp_path / "preoutcome.sqlite"
    source_receipts = tmp_path / "source-receipts"
    result = training.freeze_supor_preoutcome(
        database,
        local_pdf_path=fake_pdf,
        round10_review=review,
        round10_completion=completion,
        source_receipt_directory=source_receipts,
    )

    assert result["stage"] == "PRE_OUTCOME_BATCH_FROZEN"
    assert opened_pages == [12, 12, 16]
    assert result["controller_counts"] == {
        "decision_contracts": 3,
        "technical_route_identities": 3,
        "measurement_contracts": 3,
        "static_evidence": 3,
        "predictions": 3,
        "outcome_access": 0,
        "source_inventories": 0,
        "observations": 0,
        "settlements": 0,
    }
    assert len(result["field_receipts"]) == 3
    assert all(row["stage"] == "PRE_OUTCOME_FROZEN" for row in result["field_receipts"])
    for row in result["field_receipts"]:
        chronology = list(row["recorded_chronology"].values())
        assert chronology == sorted(chronology)
        assert row["allowed_outputs"] == ["MECHANICAL_SETTLEMENT_ONLY"]
        assert row["method_transfer_rights"] == "NO_METHOD_TRANSFER_RIGHTS"
    assert len(list(source_receipts.glob("*.json"))) == 3
    assert result["outcome_access"] == {
        "authorized": False,
        "content_read": False,
        "custodian_started": False,
    }
    assert result["rights"] == training.RIGHTS


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("page", "source_field_ref_mismatch"),
        ("metric", "source_responsibility_boundary_mismatch"),
        ("boundary", "source_responsibility_boundary_mismatch"),
        ("unit", "source_unit_mismatch"),
        ("value", "source_numeric_value_mismatch"),
    ],
)
def test_local_pdf_verifier_rejects_field_identity_drift(tmp_path, monkeypatch, mutation, expected_code):
    _, _, episode = _objects()
    chain = episode["minimal_field_chains"][0]
    source = deepcopy(chain["static_evidence"]["source"])
    verification = deepcopy(chain["source_verification_input"])
    fake_pdf = tmp_path / "registered-cn002032-fy2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    monkeypatch.setattr(
        training.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=_pdf_page_text(12)),
    )
    if mutation == "page":
        source["field_ref"] = source["field_ref"].replace("p.12", "p.13")
    elif mutation == "metric":
        source["metric_id"] = "PRODUCT_REVENUE_RMB:电锅类"
    elif mutation == "boundary":
        source["responsibility_boundary"] = "LISTED_ISSUER_PARENT_ONLY:CN002032"
    elif mutation == "unit":
        source["unit"] = "CNY_THOUSANDS"
        verification["unit"] = "CNY_THOUSANDS"
    elif mutation == "value":
        source["numeric_value"] = 1.0
        verification["numeric_value"] = 1.0

    verifier = training.build_local_pdf_source_verifier(fake_pdf)
    with pytest.raises(training.ApplianceContinuousTrainingError, match=expected_code):
        verifier(source, verification)


def test_local_pdf_verifier_rejects_quote_found_only_on_another_page(tmp_path, monkeypatch):
    _, _, episode = _objects()
    chain = episode["minimal_field_chains"][0]
    fake_pdf = tmp_path / "registered-cn002032-fy2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    monkeypatch.setattr(
        training.subprocess,
        "run",
        lambda *args, **kwargs: SimpleNamespace(stdout=_pdf_page_text(16)),
    )
    verifier = training.build_local_pdf_source_verifier(fake_pdf)
    with pytest.raises(
        training.ApplianceContinuousTrainingError,
        match="registered_pdf_exact_quote_not_found_on_declared_page",
    ):
        verifier(chain["static_evidence"]["source"], chain["source_verification_input"])


def test_committed_controller_receipt_records_real_preoutcome_boundary_only():
    receipt = json.loads(CONTROLLER_RECEIPT.read_text(encoding="utf-8"))
    assert receipt["episode_id"] == training.EPISODE_ID
    assert receipt["status"] == "CONTROLLER_PREOUTCOME_FREEZE_READY_FOR_REVIEW"
    assert receipt["field_stages"] == ["PRE_OUTCOME_FROZEN"] * 3
    assert receipt["controller_counts"] == {
        "decision_contracts": 3,
        "technical_route_identities": 3,
        "measurement_contracts": 3,
        "static_evidence": 3,
        "predictions": 3,
        "outcome_access": 0,
        "source_inventories": 0,
        "observations": 0,
        "settlements": 0,
    }
    assert receipt["registered_source"]["outcome_period_source_opened"] is False
    assert receipt["outcome_access"] == {
        "authorized": False,
        "content_read": False,
        "custodian_started": False,
    }
    assert receipt["rights"] == training.RIGHTS
