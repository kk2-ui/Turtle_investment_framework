from copy import deepcopy

from scripts.multi_agent_consistency import (
    FREEZE_SCHEMA,
    MANIFEST_SCHEMA,
    PROPOSAL_SCHEMA,
    freeze_canonical_ledger,
    validate_consistency_manifest,
    validate_freeze_record,
    validate_proposal,
    THREE_LAYER_ACCEPTANCE_SCHEMA,
    validate_three_layer_acceptance,
)
from tests.test_staged_judgment_ledger import _contract, _ledger, _source_index


def _proposal(*, role="company_economist", target="components.CORE.normal_earnings_use"):
    return {
        "schema_version": PROPOSAL_SCHEMA,
        "proposal_id": "P:CORE:NORMAL",
        "role": role,
        "target": target,
        "proposed_value": "BASE_RANGE",
        "evidence_ids": ["E1"],
        "reason": "连续经营证据支持，但由 owner 统一裁决。",
    }


def _decision(disposition="CONDITIONAL"):
    return {
        "proposal_id": "P:CORE:NORMAL",
        "disposition": disposition,
        "final_value": "CONDITIONAL_RANGE" if disposition != "REJECT" else None,
        "rationale": "证据支持条件性处理，保留责任边界。",
        "economic_impact": "正常盈利只能进入条件范围。",
        "prohibited_assumption": "不得把未知资本责任当作零。",
        "remediation": "取得维护资本和现金转换桥。",
        "acceptance_criterion": "同责任边界证据支持条件范围。",
    }


def test_narrow_proposal_is_role_and_source_bound_without_mutation():
    contract = _contract(_ledger())
    proposal = _proposal()
    validation = validate_proposal(proposal, contract=contract, source_index=_source_index())
    assert validation["state"] == "REVIEWABLE"
    assert validate_proposal(
        _proposal(role="industry_analyst", target="components.CORE.normal_earnings_use"),
        contract=contract,
        source_index=_source_index(),
    )["state"] == "INVALID"
    assert validate_proposal(
        _proposal(target="components.CORE.price"),
        contract=contract,
        source_index=_source_index(),
    )["state"] == "INVALID"
    assert validate_proposal(
        _proposal(target="components.CORE.component_id"),
        contract=contract,
        source_index=_source_index(),
    )["state"] == "INVALID"

    malformed = _proposal()
    bad_contract = deepcopy(contract)
    bad_contract["cutoff_at"] = "not-a-time"
    assert validate_proposal(malformed, contract=bad_contract, source_index=_source_index())["state"] == "INVALID"
    bad_index = _source_index()
    bad_index["E1"]["available_at"] = "not-a-time"
    assert validate_proposal(malformed, contract=contract, source_index=bad_index)["state"] == "INVALID"


def test_canonical_owner_freezes_one_decision_and_preserves_rejected_sidecar():
    ledger = _ledger()
    contract = _contract(ledger)
    proposal = _proposal()
    result = freeze_canonical_ledger(
        ledger,
        [proposal],
        [_decision()],
        owner_id="owner:primary",
        contract=contract,
        source_index=_source_index(),
    )
    assert result["state"] == "FROZEN"
    assert result["ledger"]["status"] == "FROZEN"
    assert result["ledger"]["components"][0]["normal_earnings_use"] == "CONDITIONAL_RANGE"
    assert result["freeze_record"]["schema_version"] == FREEZE_SCHEMA
    assert validate_freeze_record(result["freeze_record"], ledger=result["ledger"])["state"] == "REVIEWABLE"

    rejected = freeze_canonical_ledger(
        ledger,
        [proposal],
        [_decision("REJECT")],
        owner_id="owner:primary",
        contract=contract,
        source_index=_source_index(),
    )
    assert rejected["state"] == "FROZEN"
    assert rejected["ledger"]["components"][0]["normal_earnings_use"] == "CONDITIONAL_RANGE"
    assert rejected["freeze_record"]["rejected_proposal_ids"] == [proposal["proposal_id"]]


def test_manifest_distinguishes_production_and_four_arm_without_opening_outcome():
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "manifest_id": "M:TEST",
        "mode": "FOUR_ARM_INDEPENDENT",
        "company_id": "CN:TEST",
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "sample_identity": "BLIND_REPLAY",
        "common_source_refs": ["SRC:TEST"],
        "component_vocabulary": ["CORE"],
        "arms": [{"arm_id": f"A{i}", "j0_task": f"A{i}/J0", "j1_task": f"A{i}/J1", "j2_task": f"A{i}/J2"} for i in range(4)],
        "compiler": {"name": "staged_judgment_ledger", "version": "v1"},
        "budget": {"policy": "same cutoff and one attempt per stage"},
        "outcome_access": "SEALED",
    }
    assert validate_consistency_manifest(manifest)["state"] == "REVIEWABLE"
    opened = deepcopy(manifest)
    opened["outcome_access"] = "OPEN"
    assert validate_consistency_manifest(opened)["state"] == "INVALID"
    nested = deepcopy(manifest)
    nested["common_source_refs"] = [{"outcome": "OPEN"}]
    assert validate_consistency_manifest(nested)["state"] == "INVALID"


def test_freeze_record_rejects_tampering_and_acceptance_gate_is_explicit():
    ledger = _ledger(); contract = _contract(ledger); proposal = _proposal()
    result = freeze_canonical_ledger(ledger, [proposal], [_decision()], owner_id="owner:primary", contract=contract, source_index=_source_index())
    assert validate_freeze_record(result["freeze_record"], ledger=result["ledger"], contract=contract, source_index=_source_index())["state"] == "REVIEWABLE"
    tampered = deepcopy(result["freeze_record"]); tampered["decisions"] = []
    assert validate_freeze_record(tampered, ledger=result["ledger"], contract=contract, source_index=_source_index())["state"] == "INVALID"
    tampered_ledger = deepcopy(result["ledger"]); tampered_ledger["company_name"] = "篡改"
    assert validate_freeze_record(result["freeze_record"], ledger=tampered_ledger, contract=contract, source_index=_source_index())["state"] == "INVALID"

    base = {"schema_version": THREE_LAYER_ACCEPTANCE_SCHEMA, "layer1": "PASS", "layer2": "PASS", "layer3": "PASS", "holdout": "PASS", "outcome_settled": True, "release_state": "LIMITED_METHOD_RELEASE"}
    assert validate_three_layer_acceptance(base)["state"] == "REVIEWABLE"
    blocked = deepcopy(base); blocked["outcome_settled"] = False
    assert validate_three_layer_acceptance(blocked)["state"] == "INVALID"
    pre = deepcopy(base); pre.update({"layer3": "PENDING", "holdout": "PENDING", "outcome_settled": False, "release_state": "NO_RELEASE"})
    assert validate_three_layer_acceptance(pre)["state"] == "REVIEWABLE"
