from __future__ import annotations

import json
from pathlib import Path

from scripts import enterprise_judgment_episode as episode
from scripts import enterprise_judgment_reconstruction as reconstruction
from scripts import enterprise_judgment_source_packet as source_packet
from scripts import judgment_training_decision_contract as contract


_EPISODE_DIR = Path("docs/development/research/episodes/EJE_CN002083_20190501")


def _load(name: str) -> dict:
    return json.loads((_EPISODE_DIR / name).read_text(encoding="utf-8"))


def test_cn002083_is_a_cutoff_safe_e1_enterprise_judgment_episode() -> None:
    receipt = _load("01_source_packet_receipt.json")
    decision_contract = _load("02_decision_contract.json")
    model = _load("03_enterprise_system_model.json")
    ledger = _load("04_management_decision_ledger.json")
    spec = _load("05_j1_reconstruction_spec.json")
    manifest = _load("06_episode_manifest.json")

    projected = source_packet.compile_core_source_package(receipt)
    assert projected["valid"], projected["findings"]
    assert contract.validate_training_decision_contract(decision_contract)["valid"]
    compiled = reconstruction.compile_enterprise_reconstruction(
        spec,
        source_packet_receipt=receipt,
        source_package=projected["source_package"],
        enterprise_model=model,
        decision_ledger=ledger,
        decision_contract=decision_contract,
    )
    assert compiled["valid"], compiled["findings"]
    assert compiled["reconstruction"]["management_decision_ledger_slice"]["decisions"] == []
    assert (
        compiled["reconstruction"]["management_decision_ledger_slice"]["decision_observation"]["status"]
        == "INSUFFICIENT_EVIDENCE"
    )

    result = episode.compile_episode_read_model(
        manifest,
        decision_contract=decision_contract,
        reconstruction_binding={
            "reconstruction": compiled["reconstruction"],
            "spec": spec,
            "source_packet_receipt": receipt,
            "source_package": projected["source_package"],
            "enterprise_model": model,
            "decision_ledger": ledger,
        },
    )
    assert result["valid"], result["findings"]
    rows = {row["claim_id"]: row for row in result["episode_read_model"]["claim_output_matrix"]}
    assert len(rows["CLAIM:CN002083:OPERATING_SYSTEM"]["allowed_outputs"]) > 1
    assert len(rows["CLAIM:CN002083:EXPORT_EARNINGS"]["allowed_outputs"]) > 1
    assert len(rows["CLAIM:CN002083:CASH"]["allowed_outputs"]) > 1
    assert rows["CLAIM:CN002083:MANAGEMENT"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert rows["CLAIM:CN002083:PERMANENT_LOSS"]["allowed_outputs"] == ["RESEARCH_AGENDA"]
    assert result["episode_read_model"]["eligible_admission_levels"]["E1_RECONSTRUCTION"] is True
    assert result["episode_read_model"]["eligible_admission_levels"]["E2_MECHANISM_PROBE"] is False
    assert result["episode_read_model"]["investment_authorization"] == "NOT_AUTHORIZED"
