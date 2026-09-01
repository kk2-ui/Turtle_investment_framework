from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import enterprise_judgment_appliance_four_stage_round2 as round2


ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_DIR = ROOT / "docs" / "development" / "research" / "industry_learning_blocks" / "CN_APPLIANCE_FOUR_STAGE_TRAINING_V2"


def _page_text(page: int) -> str:
    return {
        60: "其中：营业收入 7,247,524,855.71 7,314,804,589.33",
        13: "食品加工机系列 3,149,788,827.00 43.46% 3,063,179,010.42 41.88% 2.83%",
        64: "经营活动产生的现金流量净额 48,903,264.69 1,006,736,608.98",
    }.get(page, "")


def test_second_fixed_company_freezes_three_local_fields_and_unknowns():
    episode = round2.build_preoutcome_episode()
    result = round2.validate_preoutcome_episode(episode)
    assert result["valid"], result["findings"]
    assert episode["company_id"] == "CN:002242"
    assert episode["selection_rule"] == "SECOND_FIXED_RESULT_UNSEEN_COMPANY_IN_APPLIANCE_ROSTER"
    assert episode["fair_baseline"]["fact_refs"] == episode["cumulative_enhanced"]["fact_refs"]
    assert [row["measurement_contract"]["metric_id"] for row in episode["minimal_field_chains"]] == [
        "CONSOLIDATED_REVENUE_RMB",
        "PRODUCT_REVENUE_RMB:食品加工机系列",
        "CONSOLIDATED_OPERATING_CASH_FLOW_RMB",
    ]
    assert [row["prediction"]["predicted_direction"] for row in episode["minimal_field_chains"]] == [
        "STABLE", "INCREASE", "STABLE",
    ]
    dimensions = {row["dimension_id"]: row for row in episode["cumulative_enhanced"]["dimensions"]}
    assert dimensions["CUSTOMER_AND_COMPETITIVE_RESPONSE"]["status"] == "UNKNOWN"
    assert dimensions["UNIT_ECONOMICS"]["status"] == "UNKNOWN"
    assert episode["outcome_access"] == {"authorized": False, "content_read": False, "custodian_started": False}
    assert episode["rights"] == round2.RIGHTS


def test_resolution_contract_applies_all_three_prior_iteration_lessons():
    contract = round2.build_resolution_contract()
    result = round2.validate_resolution_contract(contract)
    assert result["valid"], result["findings"]
    assert contract["signed_deviation_rules"]["STABLE_EXPECTATION_UPWARD_MISS"].startswith("FAVORABLE")
    assert contract["product_relative_rule"]["outperformance_threshold_percentage_points"] == 5.0
    assert contract["prior_period_bridge_rule"]["absolute_rmb_tolerance"] == 0.01
    assert contract["prior_period_bridge_rule"]["mechanical_field_settlement_preserved"] is True
    assert contract["rights"] == round2.RIGHTS


def test_committed_resolution_and_freeze_receipts_bind_canonical_episode():
    episode = round2.build_preoutcome_episode()
    resolution = json.loads((ARTIFACT_DIR / "02_e2_resolution_contract.json").read_text(encoding="utf-8"))
    freeze = json.loads((ARTIFACT_DIR / "01_cn002242_preoutcome_freeze_receipt.json").read_text(encoding="utf-8"))
    controller = json.loads((ARTIFACT_DIR / "03_controller_preoutcome_freeze_receipt.json").read_text(encoding="utf-8"))
    assert resolution == round2.build_resolution_contract()
    assert freeze["episode_id"] == episode["episode_id"]
    assert freeze["predictions"] == [
        {
            "measurement_contract_id": chain["measurement_contract"]["measurement_contract_id"],
            "metric_id": chain["measurement_contract"]["metric_id"],
            "predicted_direction": chain["prediction"]["predicted_direction"],
            "settlement_tolerance_rmb": chain["measurement_contract"]["settlement_tolerance"],
        }
        for chain in episode["minimal_field_chains"]
    ]
    assert controller["episode_id"] == episode["episode_id"]
    assert controller["controller_counts"]["outcome_access"] == 0
    assert controller["controller_counts"]["observations"] == 0
    assert controller["controller_counts"]["settlements"] == 0
    assert controller["rights"] == round2.RIGHTS


def test_canonical_validator_rejects_posthoc_direction_or_route_mutation():
    episode = round2.build_preoutcome_episode()
    changed = deepcopy(episode)
    changed["minimal_field_chains"][0]["prediction"]["predicted_direction"] = "DECREASE"
    assert not round2.validate_preoutcome_episode(changed)["valid"]

    changed = deepcopy(episode)
    changed["minimal_field_chains"][0]["technical_route_identity"]["organization_id"] = "caller-chosen"
    assert not round2.validate_preoutcome_episode(changed)["valid"]


def test_existing_minimal_runner_freezes_real_preoutcome_batch(tmp_path, monkeypatch):
    fake_pdf = tmp_path / "CN002242_FY2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    opened_pages = []

    def fake_pdftotext(command, **kwargs):
        assert command[:2] == ["pdftotext", "-f"]
        assert command[3:5] == ["-l", command[2]]
        assert command[5:] == ["-layout", str(fake_pdf), "-"]
        page = int(command[2])
        opened_pages.append(page)
        return SimpleNamespace(stdout=_page_text(page))

    monkeypatch.setattr(round2.subprocess, "run", fake_pdftotext)
    receipt = round2.freeze_preoutcome(tmp_path / "controller.sqlite", local_pdf_path=fake_pdf)
    assert receipt["stage"] == "PRE_OUTCOME_BATCH_FROZEN"
    assert opened_pages == [60, 13, 64]
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
    assert all(row["stage"] == "PRE_OUTCOME_FROZEN" for row in receipt["field_receipts"])
    assert receipt["rights"] == round2.RIGHTS


@pytest.mark.parametrize(
    ("mutation", "error"),
    [
        ("page", "source_field_ref_mismatch"),
        ("metric", "source_responsibility_boundary_mismatch"),
        ("boundary", "source_responsibility_boundary_mismatch"),
        ("unit", "source_unit_mismatch"),
        ("value", "source_numeric_value_mismatch"),
    ],
)
def test_preoutcome_verifier_rejects_material_source_drift(tmp_path, monkeypatch, mutation, error):
    chain = round2.build_minimal_chains()[0]
    source = deepcopy(chain["static_evidence"]["source"])
    verification = deepcopy(chain["source_verification_input"])
    fake_pdf = tmp_path / "CN002242_FY2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    monkeypatch.setattr(round2.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=_page_text(60)))
    if mutation == "page":
        source["field_ref"] = source["field_ref"].replace("p.60", "p.61")
    elif mutation == "metric":
        source["metric_id"] = "PRODUCT_REVENUE_RMB:食品加工机系列"
    elif mutation == "boundary":
        source["responsibility_boundary"] = "LISTED_ISSUER_PARENT_ONLY:CN002242"
    elif mutation == "unit":
        source["unit"] = verification["unit"] = "RMB_THOUSANDS"
    elif mutation == "value":
        source["numeric_value"] = verification["numeric_value"] = 1.0
    with pytest.raises(round2.ApplianceRound2Error, match=error):
        round2.build_local_pdf_source_verifier(fake_pdf)(source, verification)


def test_quote_on_wrong_physical_page_does_not_freeze(tmp_path, monkeypatch):
    chain = round2.build_minimal_chains()[0]
    fake_pdf = tmp_path / "CN002242_FY2017.pdf"
    fake_pdf.write_bytes(b"%PDF-local-fixture")
    monkeypatch.setattr(round2.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=_page_text(64)))
    with pytest.raises(round2.ApplianceRound2Error, match="registered_pdf_exact_quote_not_found_on_declared_page"):
        round2.build_local_pdf_source_verifier(fake_pdf)(chain["static_evidence"]["source"], chain["source_verification_input"])
