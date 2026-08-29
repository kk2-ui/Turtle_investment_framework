from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.report_completion import evaluate_report_completion
from scripts.enterprise_underwriting_episode import project_price_free_underwriting_thesis
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.read_tools import read_valuation_route
from scripts.valuation_model_gate import validate_valuation_model_ledger
from scripts.valuation_routing import (
    build_company_archetype,
    build_valuation_route,
    evaluate_output_valuation_route,
    initialize_valuation_route_policy,
    load_registry,
    validate_company_archetype,
    validate_valuation_route,
)
from scripts import enterprise_judgment_core as enterprise_core
from tests.test_enterprise_judgment_core import (
    _judgment_input, _ledger, _model, _review, _source_package,
    _underwriting_episode,
)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _fixture(output: Path, industry: str = "物业服务", include_gg: bool = True) -> None:
    _write(output / "analysis_contract.json", {
        "ts_code": "09999.HK", "industry_classification": {"l1": "一般企业", "l2": industry, "peer_group": industry},
        "cyclicality_profile": {"label": "弱周期"},
    })
    _write(output / "industry_context.json", {"meta": {"industry_l1": "一般企业", "industry_l2": industry, "industry_group": industry}})
    bundle = {"factor3": {"gg": {"base": 6.0}}, "factor4": {"II_adjusted": 5.5}}
    if not include_gg:
        bundle["factor3"] = {}
    _write(output / "compute_bundle.json", bundle)
    _write(output / "report_context.json", {"meta": {"report_id": "09999.HK"}, "domains": {}, "unresolved_gaps": []})


def _valuation_reference_root() -> Path:
    """Find the shared reference pack from both primary and linked worktrees."""
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "130家估值模型"
        if candidate.is_dir():
            return candidate
    raise AssertionError("缺少共享资料目录：130家估值模型")


def test_registry_is_internally_closed_and_prohibits_model_vote() -> None:
    registry = load_registry()
    models = set(registry["models"])
    assert len(registry["archetypes"]) >= 8
    assert registry["model_policy"]["no_unjustified_weighted_average"] is True
    for spec in registry["archetypes"].values():
        routed = set(spec["primary_models"] + spec["corroborative_models"] + spec["stress_models"])
        rejected = set(spec["rejected_models"])
        assert routed <= models and rejected <= models and not routed & rejected


def test_reference_index_covers_every_local_file_without_granting_fact_status() -> None:
    root = _valuation_reference_root()
    index = json.loads((Path(__file__).parents[1] / "config/valuation_reference_index.json").read_text(encoding="utf-8"))
    actual = [path for path in root.rglob("*") if path.is_file()]
    assert index["summary"]["file_count"] == len(actual) == 364
    assert len(index["files"]) == len(actual)
    assert all(len(item["sha256"]) == 64 and item["company_fact_eligible"] is False for item in index["files"])
    assert index["policy"]["parameter_copying_forbidden"] is True


def test_property_service_classification_is_deterministic_and_evidence_bound(tmp_path: Path) -> None:
    _fixture(tmp_path)
    first = build_company_archetype(tmp_path, persist=False)
    second = build_company_archetype(tmp_path, persist=False)
    assert first["primary_archetype"]["archetype_id"] == "property_service"
    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert first["validation"]["state"] == "REVIEWABLE"
    assert any(item["matched_rule"] == "物业服务" for item in first["matching_evidence"])


def test_routing_identity_ignores_context_timestamp_and_downstream_decisive_plan(tmp_path: Path) -> None:
    _fixture(tmp_path)
    context = json.loads((tmp_path / "report_context.json").read_text(encoding="utf-8"))
    context["meta"].update({"generated_at": "2026-08-03T10:00:00+00:00", "context_fingerprint": "stable-evidence"})
    _write(tmp_path / "report_context.json", context)
    _write(tmp_path / "decisive_question_plan.json", {"input_fingerprint": "old-plan"})
    first = build_company_archetype(tmp_path, persist=False)

    context["meta"]["generated_at"] = "2026-08-03T11:00:00+00:00"
    _write(tmp_path / "report_context.json", context)
    _write(tmp_path / "decisive_question_plan.json", {"input_fingerprint": "new-plan"})
    second = build_company_archetype(tmp_path, persist=False)

    assert first["input_fingerprint"] == second["input_fingerprint"]
    assert "decisive_question_plan.json" not in first["input_sources"]
    assert first["input_sources"]["report_context.json"] == "stable-evidence"


def test_four_high_coverage_industry_routes_are_distinct(tmp_path: Path) -> None:
    cases = {
        "物业服务": "property_service", "家用电器": "mature_consumer_manufacturing",
        "广告包装": "asset_light_media_platform", "银行": "regulated_financial",
        "钢铁": "heavy_asset_cyclical", "电力": "utility_infrastructure",
    }
    for idx, (industry, expected) in enumerate(cases.items()):
        output = tmp_path / str(idx); output.mkdir(); _fixture(output, industry)
        assert build_company_archetype(output, persist=False)["primary_archetype"]["archetype_id"] == expected


def test_missing_archetype_input_is_incomplete_not_invented(tmp_path: Path) -> None:
    _fixture(tmp_path, include_gg=False)
    payload = build_company_archetype(tmp_path, persist=False)
    assert payload["validation"]["state"] == "INCOMPLETE"
    assert "compute_bundle.factor3.gg.base" in payload["missing_required_inputs"]


def test_new_input_after_routing_warns_without_identity_drift(tmp_path: Path) -> None:
    _fixture(tmp_path); payload = build_company_archetype(tmp_path, persist=False)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract["tracking"] = {"new": True}; _write(tmp_path / "analysis_contract.json", contract)
    result = validate_company_archetype(payload, load_registry(), output_dir=tmp_path)
    assert result["state"] == "REVIEWABLE"
    assert "input_source_changed_after_routing:analysis_contract.json" in result["warnings"]


def test_route_has_role_based_models_rejections_and_exact_basis(tmp_path: Path) -> None:
    _fixture(tmp_path); archetype = build_company_archetype(tmp_path, persist=False)
    route = build_valuation_route(tmp_path, archetype, persist=False)
    assert route["validation"]["state"] == "REVIEWABLE"
    assert {item["route_model_id"] for item in route["models"] if item["role"] == "primary"} == {"RETURN_DECOMPOSITION", "EPV"}
    assert {item["route_model_id"] for item in route["rejected_models"]} == {"DCF_FCFF"}
    assert route["synthesis_policy"]["method"] == "role_based_decision_not_weighted_average"


def test_underwriting_thesis_overrides_archetype_default_route_without_adding_value(tmp_path: Path) -> None:
    _fixture(tmp_path, industry="水泥")
    archetype = build_company_archetype(tmp_path, persist=False)
    episode = json.loads((Path(__file__).parents[1] / "docs/development/research/enterprise_underwriting_episodes/CN600585_20240501_WORKED_CASE_V1.json").read_text(encoding="utf-8"))
    projection = project_price_free_underwriting_thesis(episode)
    projection["company_id"] = archetype["report_id"]

    route = build_valuation_route(
        tmp_path, archetype, underwriting_thesis_projection=projection, persist=False,
    )

    assert route["validation"]["state"] == "REVIEWABLE"
    assert {item["route_model_id"] for item in route["models"] if item["role"] == "primary"} == {
        "ASSET_VALUE", "EPV",
    }
    assert route["underwriting_thesis_ref"]["underwriting_thesis_id"] == projection["underwriting_thesis_id"]
    assert "DOMESTIC_INCREMENTAL_ASSET_RETURN" in route["underwriting_input_treatments"]["excluded_component_ids"]
    assert "price" not in route["underwriting_input_treatments"]


def test_underwriting_route_honors_intentionally_empty_auxiliary_roles(tmp_path: Path) -> None:
    _fixture(tmp_path, industry="水泥")
    archetype = build_company_archetype(tmp_path, persist=False)
    episode = _underwriting_episode()
    projection = project_price_free_underwriting_thesis(episode)
    projection["company_id"] = archetype["report_id"]
    projection["value_route"]["valuation_model_roles"] = {"primary": ["EPV"]}

    route = build_valuation_route(
        tmp_path,
        archetype,
        underwriting_thesis_projection=projection,
        persist=False,
    )

    assert route["validation"]["state"] == "REVIEWABLE"
    assert {(item["role"], item["route_model_id"]) for item in route["models"]} == {
        ("primary", "EPV")
    }


def test_underwriting_route_rejects_company_or_model_identity_mismatch(tmp_path: Path) -> None:
    _fixture(tmp_path, industry="水泥")
    archetype = build_company_archetype(tmp_path, persist=False)
    episode = json.loads((Path(__file__).parents[1] / "docs/development/research/enterprise_underwriting_episodes/CN600585_20240501_WORKED_CASE_V1.json").read_text(encoding="utf-8"))
    projection = project_price_free_underwriting_thesis(episode)
    try:
        build_valuation_route(tmp_path, archetype, underwriting_thesis_projection=projection, persist=False)
    except ValueError as exc:
        assert "company" in str(exc)
    else:
        raise AssertionError("company mismatch must not route")

    projection["company_id"] = archetype["report_id"]
    projection["value_route"]["valuation_model_roles"]["primary"] = ["NOT_A_MODEL"]
    try:
        build_valuation_route(tmp_path, archetype, underwriting_thesis_projection=projection, persist=False)
    except ValueError as exc:
        assert "unknown model" in str(exc)
    else:
        raise AssertionError("unknown underwriting model binding must not route")


def test_runtime_route_automatically_consumes_episode_bound_in_frozen_cjo(
    tmp_path: Path,
) -> None:
    _fixture(tmp_path, industry="水泥")
    package = _source_package()
    episode = _underwriting_episode()
    candidate = enterprise_core.compile_cjo_candidate(
        model=_model(source_package=package),
        ledger=_ledger(),
        source_package=package,
        judgment_input=_judgment_input(),
        underwriting_episode=episode,
    )
    frozen = enterprise_core.freeze_cjo(
        candidate=candidate,
        independent_review=_review(candidate),
    )
    frozen_path = tmp_path / "frozen_cjo.json"
    _write(frozen_path, frozen)
    contract = json.loads((tmp_path / "analysis_contract.json").read_text(encoding="utf-8"))
    contract.update({
        "company_id": frozen["company_id"],
        "canonical_judgment_refs": {"frozen_cjo_ref": "frozen_cjo.json"},
    })
    _write(tmp_path / "analysis_contract.json", contract)

    archetype = build_company_archetype(tmp_path, persist=False)
    route = build_valuation_route(tmp_path, archetype, persist=False)

    assert route["validation"]["state"] == "REVIEWABLE"
    assert route["underwriting_thesis_ref"]["episode_id"] == episode["episode_id"]
    assert {item["route_model_id"] for item in route["models"] if item["role"] == "primary"} == {
        "EPV",
    }


def test_route_rejects_basis_role_and_synthesis_tampering(tmp_path: Path) -> None:
    _fixture(tmp_path); archetype = build_company_archetype(tmp_path, persist=False)
    route = build_valuation_route(tmp_path, archetype, persist=False)
    bad = deepcopy(route)
    bad["models"][0]["value_scope"] = "enterprise"
    bad["models"][0]["role"] = "stress"
    bad["synthesis_policy"]["method"] = "weighted_average"
    result = validate_valuation_route(bad, archetype, load_registry())
    assert result["state"] == "INVALID"
    assert any("basis_drift:value_scope" in item for item in result["invalid_findings"])
    assert "primary_model_set_mismatch" in result["invalid_findings"]
    assert "unjustified_weighted_average_not_prohibited" in result["invalid_findings"]


def test_policy_is_backward_compatible_but_enforced_run_requires_route(tmp_path: Path) -> None:
    assert evaluate_output_valuation_route(tmp_path, persist=False)["state"] == "SKIP"
    initialize_valuation_route_policy(tmp_path, run_id="run-25", enforced=True)
    result = evaluate_output_valuation_route(tmp_path, persist=False)
    assert result["state"] == "INCOMPLETE"
    assert result["incomplete_findings"] == ["company_archetype_missing"]


def test_valuation_ledger_cannot_bypass_canonical_route(tmp_path: Path) -> None:
    _fixture(tmp_path)
    archetype = build_company_archetype(tmp_path, persist=True)
    build_valuation_route(tmp_path, archetype, persist=True)
    initialize_valuation_route_policy(tmp_path, run_id="run-route", enforced=True)
    payload = {
        "schema_version": "valuation-model-ledger.v1", "report_id": "09999.HK", "change_reason": "test",
        "company_profile": {"business_type": "bank", "asset_intensity": "asset_heavy", "valuation_route": "free", "route_reasoning": "ignore canonical route"},
        "models": [{"model_id": "bad", "route_model_id": "DCF_FCFE", "model_type": "DCF", "role": "primary", "status": "active", "independence_group_id": "invented"}],
        "synthesis": {"action": "avoid", "range_low": 1, "range_high": 2, "chosen_value_per_share": 1.5, "decision_rule": "test", "divergence_explanation": "test"},
    }
    result = validate_valuation_model_ledger(payload, output_dir=tmp_path, enforced=False)
    assert result["state"] == "INVALID"
    assert "company_profile_business_type_route_mismatch" in result["invalid_findings"]
    assert "bad:model_role_route_mismatch" in result["invalid_findings"]
    assert "bad:independence_group_route_mismatch" in result["invalid_findings"]
    assert "bad:discount_rate_kind_route_mismatch" in result["invalid_findings"]


def test_route_read_tool_and_registry_are_auto_discoverable(tmp_path: Path) -> None:
    _fixture(tmp_path); archetype = build_company_archetype(tmp_path, persist=True); build_valuation_route(tmp_path, archetype, persist=True)
    assert read_valuation_route(str(tmp_path))["ok"] is True
    registry = ToolRegistry(); registry.auto_discover("turtle_agent.tools.read_tools")
    assert "read_valuation_route" in registry.list_tools()


def test_completion_exposes_route_as_independent_hard_gate(tmp_path: Path) -> None:
    output = tmp_path / "out"; output.mkdir()
    initialize_valuation_route_policy(output, run_id="run-completion", enforced=True)
    result = evaluate_report_completion("draft", str(output))
    assert result.validators["valuation_route"]["state"] == "INCOMPLETE"
    assert any(item.startswith("Valuation route: INCOMPLETE") for item in result.blocking_findings)


def test_phase03_schemas_and_pipeline_hook_exist() -> None:
    root = Path(__file__).parents[1]
    for name in ("company_archetype.schema.json", "valuation_route.schema.json", "archetype_valuation_registry.schema.json", "valuation_reference_index.schema.json"):
        assert json.loads((root / "schemas" / name).read_text(encoding="utf-8"))["$schema"].endswith("2020-12/schema")
    source = (root / "scripts/turtle_agent/run.py").read_text(encoding="utf-8")
    assert "[Phase 3.85] 行业原型与估值路由" in source
