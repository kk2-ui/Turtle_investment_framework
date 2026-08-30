from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.turtle_agent.tools.read_tools import read_valuation_route
from scripts.valuation_archetypes import resolve_valuation_archetype
from scripts.valuation_evidence_plan import (
    build_valuation_evidence_plan,
    compile_valuation_evidence_plan,
)
from scripts.valuation_routing import build_company_archetype, build_valuation_route


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = (
    ROOT
    / "tests"
    / "fixtures"
    / "valuation_evidence_plan"
    / "property_service_current_evidence.json"
)
PLAN_SCHEMA = ROOT / "schemas" / "valuation_evidence_plan.schema.json"
ATTEMPT_SCHEMA = (
    ROOT / "schemas" / "valuation_evidence_attempt_receipts.schema.json"
)


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _route_fixture(output: Path, industry: str = "物业服务") -> tuple[dict, dict]:
    _write(
        output / "analysis_contract.json",
        {
            "ts_code": "09999.HK",
            "industry_classification": {
                "l1": "一般企业",
                "l2": industry,
                "peer_group": industry,
            },
            "cyclicality_profile": {"label": "弱周期"},
        },
    )
    _write(
        output / "industry_context.json",
        {
            "meta": {
                "industry_l1": "一般企业",
                "industry_l2": industry,
                "industry_group": industry,
            }
        },
    )
    _write(
        output / "compute_bundle.json",
        {"factor3": {"gg": {"base": 6.0}}, "factor4": {"II_adjusted": 5.5}},
    )
    _write(
        output / "report_context.json",
        {"meta": {"report_id": "09999.HK"}, "domains": {}, "unresolved_gaps": []},
    )
    archetype = build_company_archetype(output, persist=True)
    route = build_valuation_route(output, archetype, persist=True)
    return archetype, route


def _role(plan: dict, component_type: str, evidence_role: str) -> dict:
    component = next(
        item for item in plan["components"]
        if item["component_type"] == component_type
    )
    return next(
        item for item in component["evidence_roles"]
        if item["evidence_role"] == evidence_role
    )


def test_route_and_active_card_compile_role_level_evidence_work(tmp_path: Path) -> None:
    _, route = _route_fixture(tmp_path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _write(tmp_path / "fact_observations.json", fixture["fact_observations"])
    _write(
        tmp_path / "valuation_evidence_attempt_receipts.json",
        fixture["attempt_receipts"],
    )

    plan = build_valuation_evidence_plan(tmp_path, persist=True)

    assert plan["state"] == "PLAN_READY"
    assert plan["route_id"] == route["route_id"]
    assert plan["applicability"]["state"] == "ROUTE_BOUND"
    assert plan["model_readiness"] == "EVIDENCE_INCOMPLETE"
    assert plan["policy"] == {
        "company_values_exposed": False,
        "default_haircuts_allowed": False,
        "attempt_receipt_grants_evidence": False,
    }
    available = _role(
        plan,
        "CUSTOMER_RELATIONSHIP",
        "CONTRACT_POPULATION_OR_CUSTOMER_BOOK",
    )
    assert available["evidence_state"] == "AVAILABLE"
    assert available["eligible_observation_ids"] == ["OBS:VEP:CONTRACT-BOOK"]
    assert available["attempt_receipt"]["state"] == "NOT_REQUIRED"

    ineligible = _role(
        plan,
        "CUSTOMER_RELATIONSHIP",
        "RETENTION_OR_CHURN_COHORT_EVIDENCE",
    )
    assert ineligible["evidence_state"] == "INELIGIBLE"
    assert ineligible["unknown_treatment"] == "PRESERVE_LOCAL_UNKNOWN"
    assert ineligible["attempt_receipt"]["state"] == "RECORDED"

    missing = _role(
        plan,
        "CUSTOMER_RELATIONSHIP",
        "WIN_OR_REBUILD_COST_EVIDENCE",
    )
    assert missing["evidence_state"] == "MISSING"
    assert missing["attempt_receipt"]["receipt"]["outcome"] == "PUBLIC_INFO_UNAVAILABLE"
    assert missing["likely_official_sources"]
    assert missing["likely_acquisition_modules"]
    assert missing["query_hints"]
    assert missing["bounded_stopping_rule"]
    assert "COMPANY_LEVEL_REPLACEMENT_RANGE" in missing["affected_valuation_claims"]
    assert "COMPANY_LEVEL_REPLACEMENT_RANGE" in plan["blocked_valuation_claims"]

    serialized = json.dumps(plan, ensure_ascii=False, sort_keys=True)
    assert "314.159" not in serialized
    assert "271.828" not in serialized
    assert "normalized_value" not in serialized
    assert json.loads(
        (tmp_path / "valuation_evidence_plan.json").read_text(encoding="utf-8")
    ) == plan


def test_schema_accepts_plan_and_attempt_fixture(tmp_path: Path) -> None:
    jsonschema = pytest.importorskip("jsonschema")
    _route_fixture(tmp_path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    _write(tmp_path / "fact_observations.json", fixture["fact_observations"])
    _write(
        tmp_path / "valuation_evidence_attempt_receipts.json",
        fixture["attempt_receipts"],
    )
    plan = build_valuation_evidence_plan(tmp_path, persist=False)

    jsonschema.Draft202012Validator(
        json.loads(PLAN_SCHEMA.read_text(encoding="utf-8"))
    ).validate(plan)
    jsonschema.Draft202012Validator(
        json.loads(ATTEMPT_SCHEMA.read_text(encoding="utf-8"))
    ).validate(fixture["attempt_receipts"])


def test_attempt_receipt_never_promotes_missing_role(tmp_path: Path) -> None:
    archetype, route = _route_fixture(tmp_path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    attempts = deepcopy(fixture["attempt_receipts"])
    attempts["receipts"][1]["outcome"] = "EVIDENCE_FOUND"
    attempts["receipts"][1]["evidence_ids"] = ["OBS:VEP:RETENTION-CANDIDATE"]

    plan = compile_valuation_evidence_plan(
        route=route,
        company_archetype=archetype,
        fact_observations=fixture["fact_observations"],
        attempt_receipts=attempts,
    )

    role = _role(
        plan,
        "CUSTOMER_RELATIONSHIP",
        "WIN_OR_REBUILD_COST_EVIDENCE",
    )
    assert role["evidence_state"] == "MISSING"
    assert role["attempt_receipt"]["state"] == "RECORDED"
    assert plan["model_readiness"] == "EVIDENCE_INCOMPLETE"


def test_attempt_receipt_with_company_value_is_rejected_from_plan(tmp_path: Path) -> None:
    archetype, route = _route_fixture(tmp_path)
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    attempts = deepcopy(fixture["attempt_receipts"])
    attempts["receipts"][1]["query_hints_used"] = ["rebuild cost RMB314 million"]

    plan = compile_valuation_evidence_plan(
        route=route,
        company_archetype=archetype,
        fact_observations=fixture["fact_observations"],
        attempt_receipts=attempts,
    )

    role = _role(
        plan,
        "CUSTOMER_RELATIONSHIP",
        "WIN_OR_REBUILD_COST_EVIDENCE",
    )
    assert role["attempt_receipt"]["state"] == "RECEIPT_REGISTRY_INVALID"
    assert role["attempt_receipt"]["receipt"] is None
    assert "RMB314" not in json.dumps(plan, ensure_ascii=False)
    assert any("contains_value_or_parameter" in item for item in plan["findings"])


def test_all_exact_verified_roles_make_evidence_ready(tmp_path: Path) -> None:
    archetype, route = _route_fixture(tmp_path)
    card = resolve_valuation_archetype("property_service", "v2")
    roles = sorted({
        role
        for component in card["required_component_specs"]
        for role in component["required_evidence_roles"]
    })
    observations = {
        "observations": [
            {
                "observation_id": "OBS:VEP:" + role,
                "status": "VERIFIED",
                "valuation_evidence_roles": [role],
            }
            for role in roles
        ]
    }

    plan = compile_valuation_evidence_plan(
        route=route,
        company_archetype=archetype,
        fact_observations=observations,
    )

    assert plan["state"] == "PLAN_READY"
    assert plan["model_readiness"] == "EVIDENCE_READY"
    assert plan["evidence_summary"]["MISSING"] == 0
    assert plan["evidence_summary"]["INELIGIBLE"] == 0
    assert plan["blocked_valuation_claims"] == []


def test_incomplete_route_applicability_cannot_become_usable(tmp_path: Path) -> None:
    archetype, route = _route_fixture(tmp_path)
    incomplete = deepcopy(route)
    replacement = next(
        item for item in incomplete["models"]
        if item["route_model_id"] == "REPLACEMENT_VALUE"
    )
    replacement["required_conditions"] = []
    card = resolve_valuation_archetype("property_service", "v2")
    observations = {
        "observations": [
            {
                "observation_id": "OBS:VEP:" + role,
                "status": "VERIFIED",
                "valuation_evidence_roles": [role],
            }
            for role in sorted({
                role
                for component in card["required_component_specs"]
                for role in component["required_evidence_roles"]
            })
        ]
    }

    plan = compile_valuation_evidence_plan(
        route=incomplete,
        company_archetype=archetype,
        fact_observations=observations,
    )

    assert plan["state"] == "INCOMPLETE"
    assert plan["applicability"]["state"] == "INCOMPLETE"
    assert plan["model_readiness"] == "BLOCKED"
    assert "REPLACEMENT_VALUE:fragility_or_conditions_missing" in plan["findings"]
    assert "COMPANY_LEVEL_REPLACEMENT_RANGE" in plan["blocked_valuation_claims"]


def test_historical_card_without_acquisition_guidance_is_explicitly_blocked(
    tmp_path: Path,
) -> None:
    archetype, route = _route_fixture(tmp_path)
    historical_route = deepcopy(route)
    replacement = next(
        item for item in historical_route["models"]
        if item["route_model_id"] == "REPLACEMENT_VALUE"
    )
    replacement["valuation_archetype_version"] = "v1"

    plan = compile_valuation_evidence_plan(
        route=historical_route,
        company_archetype=archetype,
        fact_observations={},
    )

    assert plan["state"] == "INVALID"
    assert plan["model_readiness"] == "BLOCKED"
    assert plan["valuation_archetype"]["version"] == "v1"
    assert plan["findings"] == [
        "valuation_archetype_evidence_role_guidance_missing:"
        "VALUATION_ARCHETYPE:property_service:v1"
    ]


def test_route_without_versioned_replacement_card_is_not_required(tmp_path: Path) -> None:
    archetype, route = _route_fixture(tmp_path, industry="家用电器")

    plan = compile_valuation_evidence_plan(
        route=route,
        company_archetype=archetype,
        fact_observations={},
    )

    assert plan["state"] == "NOT_REQUIRED"
    assert plan["model_readiness"] == "NOT_REQUIRED"
    assert plan["components"] == []


def test_read_valuation_route_exposes_plan_before_valuation(tmp_path: Path) -> None:
    _route_fixture(tmp_path)

    result = read_valuation_route(str(tmp_path))

    assert result["ok"] is True
    assert result["valuation_evidence_plan"]["state"] == "PLAN_READY"
    assert result["valuation_evidence_plan"]["model_readiness"] == "EVIDENCE_INCOMPLETE"
    assert "检索收据" in result["instruction"]
