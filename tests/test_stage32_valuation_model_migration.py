from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

from scripts.turtle_agent.tools.read_tools import read_structured_ledger_contract
from scripts.turtle_agent.tools.write_tools import write_valuation_model_ledger
from scripts.valuation_model_gate import initialize_valuation_model_policy, persist_valuation_model_ledger
from scripts.valuation_model_migration import (
    migrate_valuation_model,
    promote_valuation_model_migration,
    validate_valuation_semantic_research,
)
from tests.test_stage13_valuation_model_gate import _payload


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _route(*, ddm_role: str = "corroborative") -> dict:
    return {
        "schema_version": "valuation-route.v1",
        "report_id": "TEST",
        "registry_version": "test.v1",
        "archetype_id": "general_operating",
        "route_id": "VR:general:test.v1",
        "legacy_company_profile": {
            "business_type": "general_operating",
            "asset_intensity": "mixed",
        },
        "models": [
            {
                "route_model_id": "DCF_FCFF", "model_type": "DCF", "role": "primary",
                "value_scope": "enterprise", "cash_flow_scope": "FCFF",
                "discount_rate_kind": "WACC", "independence_group": "cashflow",
            },
            {
                "route_model_id": "DDM", "model_type": "DDM", "role": ddm_role,
                "value_scope": "equity", "cash_flow_scope": "dividend",
                "discount_rate_kind": "cost_of_equity", "independence_group": "distribution",
            },
        ],
        "rejected_models": [],
    }


def _setup(output: Path, *, ddm_role: str = "corroborative") -> dict:
    original = _payload(output)
    _write(output / "valuation_model.json", original)
    _write(output / "valuation_route.json", _route(ddm_role=ddm_role))
    _write(output / "valuation_route_policy.json", {"enforced": True})
    initialize_valuation_model_policy(output, run_id="migration-test", enforced=True)
    chapters = output / "chapters"
    chapters.mkdir(exist_ok=True)
    (chapters / "_ch12.md").write_text(
        "## Ch12 估值\n[valuation: dcf.fcff.base]", encoding="utf-8"
    )
    (chapters / "_ch13.md").write_text(
        "## Ch13 DDM\n[valuation: ddm.normalized]", encoding="utf-8"
    )
    return original


def test_identity_only_candidate_promotes_without_changing_valuation_or_decision(tmp_path: Path) -> None:
    original = _setup(tmp_path)
    decision_before = _sha(tmp_path / "decision_ledger.json")
    result = migrate_valuation_model(tmp_path)

    assert result["report"]["semantic_frontier"] == []
    assert result["report"]["candidate_validation"]["state"] == "REVIEWABLE"
    assert result["candidate"]["synthesis"] == original["synthesis"]
    assert (tmp_path / "valuation_model.json").read_text(encoding="utf-8") == json.dumps(
        original, ensure_ascii=False, indent=2
    )

    promoted = promote_valuation_model_migration(tmp_path)
    assert promoted["promoted"] is True
    current = json.loads((tmp_path / "valuation_model.json").read_text(encoding="utf-8"))
    assert current["synthesis"] == original["synthesis"]
    assert [m["result"] for m in current["models"] if m.get("status") == "active"] == [
        m["result"] for m in original["models"] if m.get("status") == "active"
    ]
    assert _sha(tmp_path / "decision_ledger.json") == decision_before


def test_route_migration_is_idempotent_after_promotion(tmp_path: Path) -> None:
    _setup(tmp_path)
    first = migrate_valuation_model(tmp_path)
    assert first["report"]["migration_required"] is True
    assert promote_valuation_model_migration(tmp_path)["promoted"] is True
    canonical = _sha(tmp_path / "valuation_model.json")

    second = migrate_valuation_model(tmp_path)

    assert second["report"]["migration_required"] is False
    assert promote_valuation_model_migration(tmp_path)["already_compatible"] is True
    assert _sha(tmp_path / "valuation_model.json") == canonical


def test_role_change_is_semantic_and_cannot_be_auto_promoted(tmp_path: Path) -> None:
    original = _setup(tmp_path, ddm_role="primary")
    canonical_before = _sha(tmp_path / "valuation_model.json")
    result = migrate_valuation_model(tmp_path)

    assert any(
        item["model_id"] == "ddm.normalized" and item["field"] == "role"
        for item in result["report"]["semantic_frontier"]
    )
    assert promote_valuation_model_migration(tmp_path)["error"] == "semantic_change_requires_valuation_research"
    assert _sha(tmp_path / "valuation_model.json") == canonical_before
    assert json.loads((tmp_path / "valuation_model.json").read_text(encoding="utf-8"))["synthesis"] == original["synthesis"]


def test_cash_flow_scope_cannot_be_renamed_to_owner_earnings(tmp_path: Path) -> None:
    _setup(tmp_path)
    route = json.loads((tmp_path / "valuation_route.json").read_text(encoding="utf-8"))
    route["models"][0]["cash_flow_scope"] = "normalized_owner_earnings"
    _write(tmp_path / "valuation_route.json", route)
    result = migrate_valuation_model(tmp_path)

    issue = next(item for item in result["report"]["semantic_frontier"] if item["model_id"] == "dcf.fcff.base")
    assert issue["field"] == "basis.cash_flow_scope"
    candidate_model = next(item for item in result["candidate"]["models"] if item["model_id"] == "dcf.fcff.base")
    assert candidate_model["basis"]["cash_flow_scope"] == "FCFF"


def test_read_contract_exposes_complete_candidate_and_frontier(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    _write(tmp_path / "fact_observations.json", {
        "observations": [{
            "observation_id": "OBS:dividend", "status": "VERIFIED",
            "fact_name": "dividend_payout_ratio_pct", "domain": "capital_allocation",
            "normalized_value": 50.0, "unit": "pct", "as_of": "2024-12-31",
            "doc_id": "DOC:annual",
        }],
    })
    _write(tmp_path / "calculation_observations.json", {
        "calculations": [{
            "calculation_id": "CALC:gg", "status": "VERIFIED", "tool": "compute_gg",
            "metric_path": "gg_base", "value": 6.2, "unit": "pct_or_pct_point",
        }],
    })
    migrate_valuation_model(tmp_path)
    contract = read_structured_ledger_contract(str(tmp_path), "valuation")

    migration = contract["deterministic_migration"]
    assert migration["canonical_ledger_unchanged"] is True
    assert migration["candidate_models"]
    assert migration["candidate_synthesis"]["chosen_value_per_share"] == 50.0
    assert migration["semantic_frontier"]
    evidence = migration["semantic_research_evidence"]
    assert evidence["verified_observations"][0]["observation_id"] == "OBS:dividend"
    assert evidence["verified_observations"][0]["fact_name"] == "dividend_payout_ratio_pct"
    assert evidence["verified_calculations"][0]["calculation_id"] == "CALC:gg"
    assert evidence["verified_calculations"][0]["metric_path"] == "gg_base"
    assert "value_pct exactly" in migration["discount_rate_completion_rule"]
    assert "Supplying kind alone is invalid" in migration["discount_rate_completion_rule"]


def test_unified_pipeline_runs_candidate_first_migration_hook() -> None:
    source = (Path(__file__).parents[1] / "scripts/turtle_agent/run.py").read_text(encoding="utf-8")
    assert "migrate_valuation_model(output_dir, persist=True)" in source
    assert "semantic_frontier" in source


def _verified_observation(output: Path) -> None:
    _write(output / "fact_observations.json", {
        "observations": [{
            "observation_id": "OBS:route-fit", "status": "VERIFIED",
            "fact_name": "dividend_payout_ratio_pct", "domain": "capital_allocation",
        }]
    })


def _role_resolution() -> list[dict]:
    return [{
        "model_id": "ddm.normalized",
        "field": "role",
        "evidence_ids": ["OBS:route-fit"],
        "research_basis": "已验证公司分红记录及现金分配机制支持该模型承担主要决策锚，而非机械遵循路由名称。",
        "mechanism": "稳定且可归属股东的现金分配直接构成所有者回报，并能够改变模型在决策合成中的权威层级。",
        "valuation_impact": "不改变既有模型结果和估值区间，只改变模型在冲突裁决中的角色。",
        "decision_impact": "保持hold、仓位和触发器不变，但明确主要决策锚的责任。",
    }]


def test_semantic_rename_without_research_cannot_overwrite_canonical(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    proposed = deepcopy(migration["candidate"])
    next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")["role"] = "primary"
    canonical_before = _sha(tmp_path / "valuation_model.json")

    result = write_valuation_model_ledger(
        str(tmp_path),
        company_profile=proposed["company_profile"],
        models=proposed["models"],
        synthesis=proposed["synthesis"],
        semantic_resolutions=[],
        change_reason="rename only",
        freeze=False,
        repair_invalid_frozen=True,
    )

    assert result["written"] is False
    assert any("semantic_resolution_missing" in item for item in result["validation"]["incomplete_findings"])
    assert _sha(tmp_path / "valuation_model.json") == canonical_before


def test_read_contract_resumes_exact_rejected_semantic_draft(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    proposed = deepcopy(migration["candidate"])
    next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")["role"] = "primary"
    weak_resolution = _role_resolution()
    weak_resolution[0]["evidence_ids"] = []

    result = write_valuation_model_ledger(
        str(tmp_path), company_profile=proposed["company_profile"],
        models=proposed["models"], synthesis=proposed["synthesis"],
        semantic_resolutions=weak_resolution, change_reason="bounded draft",
        freeze=False, repair_invalid_frozen=True,
    )
    assert result["written"] is False

    resume = read_structured_ledger_contract(str(tmp_path), "valuation")[
        "deterministic_migration"
    ]["rejected_research_resume"]
    assert resume["candidate"]["models"] == proposed["models"]
    assert resume["resolutions"] == weak_resolution
    assert resume["validation"]["state"] == "INCOMPLETE"
    assert "Repair only" in resume["instruction"]


def test_writer_preserves_better_rejected_draft_across_attempts(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    proposed = deepcopy(migration["candidate"])
    next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")["role"] = "primary"
    exact_but_weak = _role_resolution()
    exact_but_weak[0]["evidence_ids"] = []
    write_valuation_model_ledger(
        str(tmp_path), company_profile=proposed["company_profile"], models=proposed["models"],
        synthesis=proposed["synthesis"], semantic_resolutions=exact_but_weak,
        change_reason="first draft", freeze=False, repair_invalid_frozen=True,
    )
    write_valuation_model_ledger(
        str(tmp_path), company_profile=proposed["company_profile"], models=proposed["models"],
        synthesis=proposed["synthesis"], semantic_resolutions=[],
        change_reason="regressed draft", freeze=False, repair_invalid_frozen=True,
    )

    best = json.loads(
        (tmp_path / "valuation_semantic_resolution_best_rejected.json").read_text(encoding="utf-8")
    )
    assert best["resolutions"] == exact_but_weak
    assert best["candidate"]["models"] == proposed["models"]


def test_writer_can_patch_best_rejected_draft_without_retransmitting_models(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    proposed = deepcopy(migration["candidate"])
    next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")["role"] = "primary"
    weak = _role_resolution()
    weak[0]["evidence_ids"] = []
    write_valuation_model_ledger(
        str(tmp_path), company_profile=proposed["company_profile"], models=proposed["models"],
        synthesis=proposed["synthesis"], semantic_resolutions=weak,
        change_reason="seed best draft", freeze=False, repair_invalid_frozen=True,
    )
    _verified_observation(tmp_path)

    result = write_valuation_model_ledger(
        str(tmp_path), semantic_resolutions=[], resume_best_rejected=True,
        semantic_resolution_patches=_role_resolution(), change_reason="patch only",
        freeze=True, repair_invalid_frozen=True,
    )

    assert result["semantic_validation"]["state"] == "REVIEWABLE"
    assert result["written"] is True
    ledger = json.loads((tmp_path / "valuation_model.json").read_text(encoding="utf-8"))
    semantic = json.loads((tmp_path / "valuation_semantic_resolution.json").read_text(encoding="utf-8"))
    assert ledger["freeze"]["frozen"] is True
    assert semantic["valuation_fingerprint"] == ledger["freeze"]["fingerprint"]


def test_exact_evidence_backed_semantic_resolution_is_reviewable(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    _verified_observation(tmp_path)
    proposed = deepcopy(migration["candidate"])
    next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")["role"] = "primary"

    result = validate_valuation_semantic_research(
        tmp_path, proposed, _role_resolution()
    )

    assert result["state"] == "REVIEWABLE"
    assert result["resolution_count"] == 1


def test_semantic_resolution_cannot_hide_result_change(tmp_path: Path) -> None:
    _setup(tmp_path, ddm_role="primary")
    migration = migrate_valuation_model(tmp_path)
    _verified_observation(tmp_path)
    proposed = deepcopy(migration["candidate"])
    model = next(item for item in proposed["models"] if item["model_id"] == "ddm.normalized")
    model["role"] = "primary"
    model["result"]["value_per_share"] = 999.0

    result = validate_valuation_semantic_research(
        tmp_path, proposed, _role_resolution()
    )

    assert result["state"] == "INVALID"
    assert "semantic_research_model_out_of_scope_change" in result["invalid_findings"]


def test_complete_rejected_valuation_is_not_overwritten_by_empty_attempt(tmp_path: Path) -> None:
    complete = _setup(tmp_path)
    complete = deepcopy(complete)
    complete["synthesis"]["chosen_value_per_share"] = 49.0
    persist_valuation_model_ledger(tmp_path, complete, report_text="")
    persist_valuation_model_ledger(tmp_path, {}, report_text="")

    best = json.loads((tmp_path / "valuation_model_best_rejected.json").read_text())
    assert best["candidate"]["models"] == complete["models"]
    assert best["candidate"]["synthesis"]["chosen_value_per_share"] == 49.0
    assert best["score"][0] == 0


def test_rejected_resume_cannot_drop_models(tmp_path: Path) -> None:
    complete = _setup(tmp_path)
    rejected = deepcopy(complete)
    rejected["synthesis"]["chosen_value_per_share"] = 49.0
    _write(tmp_path / "valuation_model_last_rejected.json", rejected)
    result = write_valuation_model_ledger(
        str(tmp_path), resume_last_rejected=True,
        models=rejected["models"][:1], change_reason="unsafe partial resend",
    )
    assert result["written"] is False
    assert result["error"] == "resume models must preserve the exact complete model_id set"
    assert result["missing_model_ids"]
