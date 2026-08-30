from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.industry_experience_pack import main, validate_industry_experience_pack


ROOT = Path(__file__).resolve().parents[1]
PILOT_ROOT = (
    ROOT
    / "docs/development/research/industry_learning_blocks"
    / "CN_CEMENT_2014_2018"
)
PACK_PATH = PILOT_ROOT / "56_industry_experience_pack_replay_v1.json"
CONTEXT_PATH = PILOT_ROOT / "55_industry_underwriting_context_replay_v1.json"


def _pack() -> dict:
    return json.loads(PACK_PATH.read_text(encoding="utf-8"))


def test_cement_replay_is_reviewable_draft_and_names_real_readiness_gaps() -> None:
    result = validate_industry_experience_pack(_pack())

    assert result["state"] == "REVIEWABLE"
    assert result["declared_state"] == result["derived_state"] == "DRAFT"
    assert set(result["training_readiness_gaps"]) == {
        "industry_context_is_bounded",
        "official_industry_observation_missing",
        "company_roles_missing:SHARED_SHOCK_DIVERGENCE",
        "shared_shock_comparison_missing",
    }


def test_manifest_cannot_claim_training_ready_from_company_boundary_work_alone() -> None:
    pack = _pack()
    pack["state"] = "TRAINING_READY"

    result = validate_industry_experience_pack(pack)

    assert result["state"] == "INVALID"
    assert "pack.declared_state_exceeds_evidence:DRAFT" in result["findings"]


def _training_ready_pack(tmp_path: Path) -> dict:
    pack = _pack()
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    context["context_status"] = "READY"
    context_path = tmp_path / "industry_context_ready.json"
    context_path.write_text(json.dumps(context, ensure_ascii=False), encoding="utf-8")
    context_source = next(
        item
        for item in pack["source_objects"]
        if item["kind"] == "INDUSTRY_UNDERWRITING_CONTEXT"
    )
    old_context_ref = context_source["ref"]
    context_source["ref"] = str(context_path)
    pack["current_synthesis"]["source_refs"] = [
        str(context_path) if item == old_context_ref else item
        for item in pack["current_synthesis"]["source_refs"]
    ]
    pack["source_objects"].append({
        "kind": "OFFICIAL_INDUSTRY_OBSERVATION",
        "object_id": "OBS:CN:CEMENT:OFFICIAL:PRE_CUTOFF:V1",
        "ref": "docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md",
        "available_at": "2018-04-30T23:59:59+08:00",
        "knowledge_role": "CUTOFF_SAFE_EVIDENCE",
        "use_status": "INCLUDED",
    })
    pack["role_coverage"]["company_paths"][1]["roles"].append(
        "SHARED_SHOCK_DIVERGENCE"
    )
    pack["role_coverage"]["company_paths"][2]["roles"].append(
        "SHARED_SHOCK_DIVERGENCE"
    )
    pack["role_coverage"]["shared_shock_comparisons"] = [{
        "shock": "Synthetic common cutoff shock for validator regression.",
        "company_ids": ["CN:600425", "CN:600802"],
        "discriminator": "Like-for-like operating and cash response.",
        "source_refs": [
            "docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/04_industry_learning_block.json"
        ],
    }]
    pack["state"] = "TRAINING_READY"
    return pack


def test_training_ready_is_derived_from_industry_context_roles_and_settlement(
    tmp_path: Path,
) -> None:
    pack = _training_ready_pack(tmp_path)

    result = validate_industry_experience_pack(pack)

    assert result["state"] == "REVIEWABLE"
    assert result["derived_state"] == "TRAINING_READY"
    assert result["training_readiness_gaps"] == []


def test_transfer_and_release_require_independent_company_and_time_utility(
    tmp_path: Path,
) -> None:
    pack = _training_ready_pack(tmp_path)
    company_review = {
        "review_id": "REVIEW:COMPANY:HOLDOUT:V1",
        "axis": "COMPANY_HOLDOUT",
        "verdict": "MATERIAL_UTILITY",
        "independent": True,
        "ref": "AGENTS.md",
    }
    pack["transfer_reviews"] = [company_review]
    pack["state"] = "TRANSFER_CANDIDATE"
    candidate = validate_industry_experience_pack(pack)
    assert candidate["state"] == "REVIEWABLE"
    assert candidate["derived_state"] == "TRANSFER_CANDIDATE"

    released = deepcopy(pack)
    released["transfer_reviews"].append({
        "review_id": "REVIEW:TIME:HOLDOUT:V1",
        "axis": "TIME_HOLDOUT",
        "verdict": "MATERIAL_UTILITY",
        "independent": True,
        "ref": "GOALS.md",
    })
    released["state"] = "RELEASED"
    result = validate_industry_experience_pack(released)
    assert result["state"] == "REVIEWABLE"
    assert result["derived_state"] == "RELEASED"


def test_pack_cannot_become_a_fact_store_or_investment_authority() -> None:
    pack = _pack()
    pack["boundary"]["creates_fact_store"] = True
    pack["boundary"]["grants_valuation_or_investment_authority"] = True

    result = validate_industry_experience_pack(pack)

    assert result["state"] == "INVALID"
    assert "pack.boundary_must_preserve_non_authoritative_manifest_role" in result["findings"]


def test_result_known_replay_cannot_masquerade_as_cutoff_safe_pack_evidence() -> None:
    pack = _pack()
    worked = next(
        item for item in pack["source_objects"] if item["kind"] == "WORKED_CASE"
    )
    worked["knowledge_role"] = "CUTOFF_SAFE_EVIDENCE"
    worked["use_status"] = "INCLUDED"

    result = validate_industry_experience_pack(pack)

    assert result["state"] == "INVALID"
    assert any(
        "cutoff_safe_source_available_after_pack_cutoff" in item
        for item in result["findings"]
    )


def test_company_role_cannot_mature_pack_without_bound_source_object() -> None:
    pack = _pack()
    pack["role_coverage"]["company_paths"][0]["source_refs"] = [
        "docs/development/research/NOT_A_BOUND_PACK_SOURCE.json"
    ]

    result = validate_industry_experience_pack(pack)

    assert result["state"] == "INVALID"
    assert any("source_ref_not_bound" in item for item in result["findings"])


def test_cli_returns_reviewable_for_checked_in_replay(capsys) -> None:
    assert main([str(PACK_PATH), "--root", str(ROOT)]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["state"] == "REVIEWABLE"
    assert payload["derived_state"] == "DRAFT"
