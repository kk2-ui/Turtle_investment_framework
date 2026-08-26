from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts import judgment_training_cjo_mirror as mirror
from tests.test_judgment_pit_forecast import _forecast, _universe_and_h1
from tests.test_judgment_training_decision_contract import _contract


def _enterprise_bundle(forecast: dict) -> dict:
    cutoff = forecast["cutoff_at"]
    return {
        "schema_version": "enterprise-judgment-v3.v1",
        "enterprise_system_model": {
            "model_id": "ESM:SYNTHETIC:TRAINING:MIRROR",
            "company_id": forecast["issuer_id"],
            "version": "1",
            "as_of": cutoff,
            "responsibility_unit_ids": ["RU:SYNTHETIC:OPERATING"],
            "competitive_arena_ids": ["ARENA:SYNTHETIC:OPERATING"],
            "nodes": [
                {
                    "node_id": "NODE:SYNTHETIC:OPERATING",
                    "observation_state": "OBSERVED",
                    "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
                    "measurement_scope_id": "SCOPE:SYNTHETIC:OPERATING",
                },
                {
                    "node_id": "NODE:SYNTHETIC:CASH",
                    "observation_state": "UNKNOWN",
                    "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
                    "measurement_scope_id": "SCOPE:SYNTHETIC:CASH",
                },
            ],
            "edges": [
                {
                    "edge_id": "EDGE:SYNTHETIC:OPERATING-CASH",
                    "from_node_id": "NODE:SYNTHETIC:OPERATING",
                    "to_node_id": "NODE:SYNTHETIC:CASH",
                    "relationship": "cash conversion",
                    "actor_side": "OPERATING_UNIT",
                    "interface": "operating cash conversion",
                    "cross_side_effect": "working-capital timing remains an explicit unknown",
                    "measurement_scope_id": "SCOPE:SYNTHETIC:CASH",
                    "observation_state": "INFERRED",
                },
            ],
        },
        "responsibility_units": [{
            "unit_id": "RU:SYNTHETIC:OPERATING",
            "accounting_perimeter": forecast["issuer_id"],
            "decision_scope": "issuer operating system",
            "economic_carrier": "cutoff-visible operating and cash system",
            "measurement_surface": "operating margin and cash conversion",
        }],
        "competitive_arenas": [{
            "arena_id": "ARENA:SYNTHETIC:OPERATING",
            "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
            "product_or_service_scope": "synthetic operating scope",
            "customer_task": "synthetic customer task",
            "competition_interface": "synthetic competitive interface",
            "economic_state": "cutoff-visible state",
            "window": "forecast cutoff",
            "required_overlap_dimensions": [{
                "dimension": "CUSTOMER_TASK", "relation": "NOT_REQUIRED",
                "rationale": "teaching mirror does not claim a causal comparator",
            }],
            "members": [{
                "member_id": forecast["issuer_id"],
                "role": "NOT_COMPARABLE",
                "actor_side": "ISSUER",
                "interface": "issuer operating system",
                "overlap_evidence": [],
            }],
        }],
        "scope_bridges": [{
            "scope_bridge_id": "BRIDGE:SYNTHETIC:OPERATING",
            "bridge_type": "IDENTITY",
            "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
            "decision_scope_ref": "issuer operating decision scope",
            "economic_carrier_ref": "issuer operating carrier",
            "measurement_surface_ref": "issuer operating measurement",
            "accounting_perimeter_ref": forecast["issuer_id"],
            "permitted_conclusion_scope": "training-only issuer operating hypothesis",
        }],
        "management_decision_ledger": {
            "ledger_id": "LEDGER:SYNTHETIC:TRAINING:MIRROR",
            "entries": [{
                "decision_id": "DECISION:SYNTHETIC:TRAINING:MIRROR",
                "cutoff_at": cutoff,
                "decision_type": "OPERATING",
                "ex_ante": {
                    "decision_quality": "INDETERMINATE",
                    "objective": "understand the cutoff-visible operating system",
                    "alternatives": ["defer conclusion pending a discriminating source"],
                    "known_unknowns": ["cash conversion durability"],
                    "commitment": "preserve uncertainty as a teaching guardrail",
                },
            }],
        },
        "cjo": {
            "cjo_id": "CJO:SYNTHETIC:TRAINING:MIRROR",
            "model_id": "ESM:SYNTHETIC:TRAINING:MIRROR",
            "state": {
                "lane": "ENTERPRISE_MODEL",
                "lifecycle": "FROZEN",
                "resolution": "SELECTIVE_SUPPORT",
                "permission": "TEACHING_ONLY",
                "frozen_at": "2021-01-03T00:00:00+00:00",
            },
            "scope_bridge_id": "BRIDGE:SYNTHETIC:OPERATING",
            "owner_cash_bridge": {
                "status": "OPEN_FOR_RESEARCH_ONLY",
                "ordinary_share_access_status": "UNKNOWN",
                "permanent_loss_status": "UNKNOWN",
                "scope_bridge_id": "BRIDGE:SYNTHETIC:OPERATING",
                "evidence_ref": "H1:SYNTHETIC:FORECAST:V1",
            },
            "driver_register": [{
                "driver_id": "DRIVER:SYNTHETIC:OPERATING",
                "responsibility_unit_id": "RU:SYNTHETIC:OPERATING",
                "scope_bridge_id": "BRIDGE:SYNTHETIC:OPERATING",
                "normalized_earnings_delta": 0.0,
                "owner_cash_delta": 0.0,
            }],
        },
    }


def _mirror(contract: dict, forecast: dict, bundle: dict) -> dict:
    model = bundle["enterprise_system_model"]
    return {
        "schema_version": mirror.SCHEMA_VERSION,
        "mirror_id": "MIRROR:SYNTHETIC:TRAINING:V1",
        "decision_contract_ref": {
            "contract_id": contract["contract_id"], "contract_version": contract["contract_version"],
        },
        "forecast_ref": {"forecast_id": forecast["forecast_id"]},
        "enterprise_model_ref": {
            "model_id": model["model_id"], "version": model["version"], "as_of": model["as_of"],
        },
        "cjo_ref": {"cjo_id": bundle["cjo"]["cjo_id"]},
        "forecast_dimension_routing": [{
            "dimension_id": dimension["dimension_id"],
            "treatment": "CJO_REVIEW_QUESTION" if dimension["evidence_status"] == "MODEL_UNCERTAIN" else "CJO_UNKNOWN_GUARDRAIL",
            "question_or_guardrail": "Retain this cutoff-visible state as an explicit CJO teaching question, not a valuation input.",
        } for dimension in forecast["dimensions"]],
        "overlay_boundary": {
            "status": "NOT_AUTHORIZED",
            "prohibited_outputs": list(mirror.OVERLAY_PROHIBITED_OUTPUTS),
            "next_step": "RESEARCH_AGENDA_ONLY",
        },
        "roles": {
            "judgment_owner_id": contract["roles"]["judgment_owner_id"],
            "independent_challenger_id": contract["roles"]["independent_challenger_id"],
        },
        "object_class": "HISTORICAL_CJO_TRAINING_MIRROR",
        "claim_class": "CONTRACT_FIRST_CJO_REPLAY",
        "allowed_outputs": list(mirror.ALLOWED_OUTPUTS),
    }


def _bound_fixture() -> tuple[dict, dict, dict, dict, dict, dict]:
    universe, h1 = _universe_and_h1()
    bootstrap = _forecast(universe, h1, universe["members"][0]["company_id"])
    contract = _contract(bootstrap)
    forecast = _forecast(
        universe, h1, bootstrap["company_id"], forecast_id="FORECAST:SYNTHETIC:TRAINING:MIRROR:V2",
        decision_contract_ref={"contract_id": contract["contract_id"], "contract_version": contract["contract_version"]},
    )
    bundle = _enterprise_bundle(forecast)
    return contract, forecast, bundle, _mirror(contract, forecast, bundle), universe, h1


def test_cjo_mirror_binds_contract_first_forecast_to_teaching_cjo_and_blocks_overlay() -> None:
    contract, forecast, bundle, teaching_mirror, universe, h1 = _bound_fixture()
    result = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=forecast, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert result["valid"], result["findings"]
    assert result["cjo_mirror"]["overlay_boundary"]["status"] == "NOT_AUTHORIZED"

    schema = json.loads(Path("schemas/judgment_training_cjo_mirror.schema.json").read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False
    assert schema["properties"]["overlay_boundary"]["properties"]["status"]["const"] == "NOT_AUTHORIZED"


def test_cjo_mirror_preserves_unknowns_and_never_accepts_investment_or_v1_retrofit() -> None:
    contract, forecast, bundle, teaching_mirror, universe, h1 = _bound_fixture()
    forecast["dimensions"][0]["evidence_status"] = "EVIDENCE_INELIGIBLE"
    forecast["dimensions"][0]["forecast_by_window"] = []
    teaching_mirror["forecast_dimension_routing"][0]["treatment"] = "CJO_UNKNOWN_GUARDRAIL"
    result = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=forecast, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert result["valid"], result["findings"]

    wrong_treatment = deepcopy(teaching_mirror)
    wrong_treatment["forecast_dimension_routing"][0]["treatment"] = "CJO_REVIEW_QUESTION"
    result = mirror.validate_training_cjo_mirror(
        wrong_treatment, contract=contract, forecast=forecast, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert not result["valid"]
    assert "cjo_mirror.forecast_dimension_routing[0].treatment_must_preserve_forecast_evidence_status" in result["findings"]

    investment_leak = deepcopy(teaching_mirror)
    investment_leak["overlay_boundary"]["status"] = "AUTHORIZED"
    investment_leak["overlay_boundary"]["prohibited_outputs"] = []
    result = mirror.validate_training_cjo_mirror(
        investment_leak, contract=contract, forecast=forecast, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert not result["valid"]
    assert "cjo_mirror.historical_training_cannot_authorize_investment_overlay" in result["findings"]

    v1 = deepcopy(forecast)
    v1["schema_version"] = "turtle-pit-company-state-forecast.v1"
    v1["forecast_epoch_id"] = "TURTLE_PIT_COMPANY_FORECAST_EPOCH_V1"
    v1.pop("decision_contract_ref")
    result = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=v1, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert not result["valid"]
    assert "cjo_mirror.requires_contract_first_forecast_v2" in result["findings"]

    cjo_investment = deepcopy(bundle)
    cjo_investment["cjo"]["state"]["permission"] = "INVESTMENT_INPUT"
    cjo_investment["cjo"]["owner_cash_bridge"].update({
        "status": "CLOSED", "ordinary_share_access_status": "CLOSED", "permanent_loss_status": "ASSESSED",
    })
    result = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=forecast, enterprise_bundle=cjo_investment,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert not result["valid"]
    assert "cjo_mirror.requires_frozen_teaching_only_cjo" in result["findings"]

    contaminated_forecast = deepcopy(forecast)
    contaminated_forecast["outcome"] = "later realised operating result"
    result = mirror.validate_training_cjo_mirror(
        teaching_mirror, contract=contract, forecast=contaminated_forecast, enterprise_bundle=bundle,
        universe_snapshot=universe, stage0_package=h1,
    )
    assert not result["valid"]
    assert "forecast:forecast_contains_unapproved_field:outcome" in result["findings"]


def test_compiler_projects_real_h1_forecast_v2_into_teaching_only_bundle() -> None:
    root = Path(__file__).resolve().parents[1]
    h1 = json.loads((root / "docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json").read_text(encoding="utf-8"))
    submission = json.loads((root / "docs/development/research/cohorts/PILOT_CN_CEMENT_20180430_ISOLATED_FORECAST_SUBMISSION.json").read_text(encoding="utf-8"))
    from scripts import judgment_historical_training as history
    from scripts import judgment_pit_forecast as pit

    h1_ref = {"receipt_id": "H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1", "receipt_version": 1}
    series = history.build_industry_history_series_from_h1(h1, h1_receipt_ref=h1_ref, cutoffs=[submission["cutoff_at"]])
    universe = series["industry_history_series"]["snapshots"][0]
    refs = {
        member["company_id"]: {"contract_id": f"DC:PILOT:CN:CEMENT:20180430:{member['company_id']}", "contract_version": 1}
        for member in universe["members"]
    }
    compiled = pit.compile_isolated_forecast_submission(
        submission, universe_snapshot=universe, stage0_package=h1, h1_receipt_ref=h1_ref,
        decision_contract_refs=refs,
    )
    assert compiled["valid"], compiled["findings"]
    forecast = next(item for item in compiled["forecasts"] if item["company_id"] == "CN:600801")
    contract = _contract(forecast)
    contract["contract_id"] = forecast["decision_contract_ref"]["contract_id"]
    compiled_mirror = mirror.compile_training_cjo_mirror(
        contract, forecast, universe_snapshot=universe, stage0_package=h1,
        cjo_frozen_at="2026-08-25T09:37:29+00:00",
    )
    assert compiled_mirror["valid"], compiled_mirror["findings"]
    bundle = compiled_mirror["enterprise_bundle"]
    assert bundle["cjo"]["state"]["permission"] == "TEACHING_ONLY"
    assert bundle["cjo"]["state"]["resolution"] == "MIXED"
    assert compiled_mirror["cjo_mirror"]["overlay_boundary"]["status"] == "NOT_AUTHORIZED"
