from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from scripts.valuation_model_gate import (
    bind_valuation_references,
    build_valuation_model_ledger,
    initialize_valuation_model_policy,
)
from scripts.valuation_value_bridges import compile_valuation_value_bridges
from tests.test_stage13_valuation_model_gate import (
    _as_epv,
    _ddm,
    _payload,
    _validate,
)
from tests.test_valuation_value_bridges import _bridge_input
from tests.test_valuation_value_bridges import _ordinary_distribution_input


def _replacement_route_model() -> dict:
    model = deepcopy(_ddm())
    model.update(
        {
            "model_id": "replacement.going_concern",
            "model_type": "ASSET_VALUE",
            "role": "corroborative",
            "chapters": [12],
            "route_model_id": "REPLACEMENT_VALUE",
            "independence_group_id": "asset_rebuild",
            "shared_assumption_ids": ["customer.rebuild"],
            "basis": {
                "value_scope": "equity",
                "cash_flow_scope": "replacement_cost",
                "currency": "RMB",
                "as_of": "2025-12-31",
                "tax_basis": "not_applicable",
            },
            "assumptions": {},
            "result": {
                "value_per_share": 8.0,
                "range_low": 8.0,
                "range_high": 10.0,
            },
            "sensitivity_tests": [],
            "source_ids": ["compute_bundle.json"],
            "decision_entry_ids": [],
        }
    )
    model.pop("terminal_value", None)
    return model


def _integrated_ledger(
    output: Path,
    *,
    missing_bridge: str | None = None,
    epv_comparable: bool = True,
    replacement_scope_complete: bool = True,
) -> dict:
    seed = _payload(output, freeze=False)
    epv = _as_epv(seed)
    epv["basis"].update({"as_of": "2025-12-31", "value_scope": "enterprise"})
    epv["result"].update(
        {
            "value_per_share": 49.3,
            "range_low": 49.3,
            "range_high": 50.7,
            "endpoint_policy": "CONSERVATIVE_LOW",
        }
    )
    epv["assumptions"]["discount_rate"]["kind"] = "WACC"
    # The canonical cash model adopts the evidenced lower bound.  The
    # historical midpoint remains visible only in the conditional range.
    epv["assumptions"]["retained_value_realization"] = 0.2
    epv["normalization_bridge"].update(
        {
            "working_capital_model_id": "WCM:BRIDGE-TEST",
            "working_capital_reference_period_id": "FY2025",
        }
    )
    seed["models"].append(_replacement_route_model())
    seed["synthesis"]["divergence_explanation"] = (
        "Replacement value is a separate lower-bound cross-check, not a model vote."
    )

    bridge_inputs = _bridge_input(
        cash=True,
        replacement=True,
        working_capital=True,
    )
    cash_context = bridge_inputs["cash_accessibility"]["valuation_context"]
    cash_context.update(
        {
            "valuation_currency": "RMB",
            "fx_source_per_valuation_currency": 1,
        }
    )
    epv["equity_bridge"].update(
        {
            "currency": "RMB",
            "ordinary_share_claim_scope": "Listed ordinary common shares",
            "non_operating_assets": 93.0,
            "equity_value": 493.0,
            "per_share_value": 49.3,
            "cash_component_per_share": 2.7,
            "cash_component_claim_ids": [
                "cash.existing_excess_cash_per_share",
                "cash.related_party_receivable_per_share",
            ],
            "non_operating_asset_components": [
                {
                    "component_id": "recognized-accessible-cash",
                    "kind": "cash",
                    "amount": 27.0,
                    "claim_ids": [
                        "cash.existing_excess_cash_per_share",
                        "cash.related_party_receivable_per_share",
                    ],
                },
                {
                    "component_id": "other-non-operating-assets",
                    "kind": "other",
                    "amount": 66.0,
                    "claim_ids": [],
                },
            ],
            "endpoint_policy": "CONSERVATIVE_LOW",
        }
    )
    seed["synthesis"]["cash_component_contract"] = {
        "cash_model_id": "CASH:BRIDGE-TEST",
        "company_id": "TEST.HK",
        "operating_model_id": epv["model_id"],
        "position_as_of": "2025-12-31",
        "ordinary_share_claim_scope": "Listed ordinary common shares",
        "valuation_currency": "RMB",
        "fx_source_per_valuation_currency": 1,
        "shares": 10,
        "component_claim_ids": [
            "cash.existing_excess_cash_per_share",
            "cash.related_party_receivable_per_share",
        ],
        "inclusion_location": "PRIMARY_MODEL_EQUITY_BRIDGE",
        "canonical_adopted_per_share": 2.7,
        "primary_equity_bridge_cash_component_per_share": 2.7,
        "separate_component_per_share": 0,
    }
    working_input = bridge_inputs["working_capital"]["model_input"]
    working_input["periods"][0]["owner_cash_input"]["base_metric_amount"] = 60
    canonical_epv_input = bridge_inputs["epv"]["model_input"]
    canonical_epv_input["model_id"] = epv["model_id"]
    canonical_epv_input["period_facts"] = [canonical_epv_input["period_facts"][1]]
    canonical_epv_input["period_facts"][0]["amount_range"] = {
        "range_low": 50.0,
        "range_high": 50.0,
    }
    canonical_epv_input["claims_bridge"]["debt"].update({
        "range_low": 80.0,
        "range_high": 80.0,
    })
    canonical_epv_input["claims_bridge"]["minority_interest"].update({
        "range_low": 10.0,
        "range_high": 10.0,
    })
    canonical_epv_input["claims_bridge"]["other_adjustments"].update({
        "range_low": -10.0,
        "range_high": -10.0,
    })
    canonical_epv_input["claims_bridge"]["shares"]["value"] = 10.0
    canonical_epv_input["claims_bridge"]["non_operating_components"] = [
        {
            "component_id": "recognized-accessible-cash",
            "kind": "NON_OPERATING_CASH",
            "range_low": 27.0,
            "range_high": 41.0,
            "claim_ids": [
                "cash.existing_excess_cash_per_share",
                "cash.related_party_receivable_per_share",
            ],
            "source_fact_ids": ["CALC:CASH:BRIDGE-TEST:RECOGNIZED"],
        },
        {
            "component_id": "other-non-operating-assets",
            "kind": "OTHER_NON_OPERATING_ASSET",
            "range_low": 66.0,
            "range_high": 66.0,
            "source_fact_ids": ["OBS:OTHER-NON-OPERATING-ASSETS"],
        }
    ]
    bridge_inputs["replacement_value"]["epv_model_id"] = epv["model_id"]
    replacement_input = bridge_inputs["replacement_value"]["model_input"]
    replacement_input["claims_bridge"]["shares_outstanding"] = 10.0
    epv["cross_check_context"] = {
        key: canonical_epv_input["basis"][key]
        for key in (
            "economic_entity",
            "operating_perimeter",
            "ordinary_share_claim_scope",
        )
    }
    if not replacement_scope_complete:
        regional = next(
            item for item in replacement_input["components"]
            if item["component_type"] == "REGIONAL_OPERATING_ORGANIZATION"
        )
        regional.update({
            "component_id": "regional-organization-unbounded",
            "economic_function": "Rebuild the regional delivery organization.",
            "estimate_status": "UNKNOWN",
            "calculation": {
                "method": "UNAVAILABLE",
                "output_unit": "RMB_m",
                "inputs": [],
            },
            "recognition": {
                "status": "UNKNOWN",
                "method": "NOT_APPLICABLE",
                "reason": "Role-level hiring and ramp evidence is unavailable.",
            },
            "uncertainty_treatment": {
                "boundary": "No replacement cost is recognized until company evidence exists.",
                "investor_consequence": "The joint protection ceiling remains unresolved.",
                "promotion_evidence": "Verified regional hiring and ramp-cost records.",
            },
        })
        replacement_route = next(
            model for model in seed["models"]
            if model.get("route_model_id") == "REPLACEMENT_VALUE"
        )
        replacement_route["result"] = {
            "value_per_share": None,
            "range_low": None,
            "range_high": None,
        }
    if epv_comparable and replacement_scope_complete:
        seed["synthesis"]["joint_protection_price_ceiling"] = 8.0
    elif not epv_comparable:
        for period in canonical_epv_input["period_facts"]:
            period["basis_kind"] = "REPORTED_OCF_AFTER_TAX"
            period["working_capital_application"] = "CURRENT_MOVEMENT_REFLECTED"
            period["observed_working_capital_charge"] = 1.0
            period["amount"] = period.pop("amount_range")["range_low"]
        canonical_epv_input["maintenance_capex"] = {
            "status": "BOUNDED",
            "range_low": 1.0,
            "range_high": 2.0,
            "tax_basis": "AFTER_TAX",
            "source_fact_ids": ["OBS:EPV:MAINTENANCE-CAPEX"],
        }
        canonical_epv_input["maintenance_working_capital"] = {
            "status": "UNKNOWN",
            "reason": "Steady working-capital absorption is unresolved.",
        }
        seed["synthesis"].pop("joint_protection_price_ceiling", None)
    else:
        seed["synthesis"].pop("joint_protection_price_ceiling", None)
    seed["synthesis"]["chosen_value_per_share"] = 49.3
    decision = json.loads((output / "decision_ledger.json").read_text())
    decision["entries"][0]["value"] = 49.3
    (output / "decision_ledger.json").write_text(json.dumps(decision))
    if missing_bridge is not None:
        bridge_inputs.pop(missing_bridge)
        if missing_bridge == "epv":
            replacement_input["epv_cross_check"] = {
                "status": "NOT_COMPARABLE",
                "reason": "No canonical EPV owner is available.",
                "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
            }
            bridge_inputs["replacement_value"].pop("epv_model_id", None)
            seed["synthesis"].pop("joint_protection_price_ceiling", None)

    ledger = build_valuation_model_ledger(
        output,
        seed["company_profile"],
        seed["models"],
        seed["synthesis"],
        change_reason="integrated deterministic value-bridge regression",
        freeze=False,
        value_bridge_inputs=bridge_inputs,
    )
    initialize_valuation_model_policy(
        output,
        run_id="integrated-value-bridge",
        enforced=False,
        require_value_bridge_models=True,
    )
    return ledger


@pytest.mark.parametrize(
    "missing_bridge",
    ["cash_accessibility", "epv", "working_capital", "replacement_value"],
)
def test_value_bridge_policy_requires_each_economically_consumed_model(
    tmp_path: Path,
    missing_bridge: str,
) -> None:
    ledger = _integrated_ledger(tmp_path, missing_bridge=missing_bridge)

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INCOMPLETE"
    assert validation["invalid_findings"] == []
    assert validation["incomplete_findings"] == [
        "value_bridge_models_missing:" + missing_bridge
    ]


def test_enforced_value_bridge_policy_requires_current_fact_bindings(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    initialize_valuation_model_policy(
        tmp_path,
        run_id="integrated-value-bridge-fact-binding",
        enforced=False,
        require_value_bridge_models=True,
        require_value_bridge_fact_bindings=True,
    )

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INCOMPLETE"
    assert validation["invalid_findings"] == []
    assert validation["incomplete_findings"] == [
        "value_bridge_fact_bindings_verified_registry_empty"
    ]


def test_canonical_epv_owner_projects_and_protects_the_route_model_normalization(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    assert ledger["models"][0]["normalization_bridge"] == ledger[
        "value_bridge_models"
    ]["result"]["epv"]["normalization_bridge"]
    ledger["models"][0].pop("normalization_bridge", None)
    initialize_valuation_model_policy(
        tmp_path,
        run_id="canonical-epv-owner",
        enforced=False,
        require_value_bridge_models=True,
        require_normalization_bridge=True,
        require_owner_earnings_normalization=True,
    )

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert (
        "dcf.fcff.base:canonical_epv_normalization_not_projection"
        in validation["invalid_findings"]
    )


def test_arbitrary_half_cash_and_half_single_year_working_capital_are_rejected(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    epv = ledger["models"][0]
    epv["assumptions"]["retained_value_realization"] = 0.5

    cash_validation = _validate(tmp_path, ledger, enforced=False)

    assert "dcf.fcff.base:retained_value_realization_not_cash_model_derived" in (
        cash_validation["invalid_findings"]
    )

    ledger = _integrated_ledger(tmp_path / "working-capital")
    ledger["value_bridge_models"]["model_input"]["epv"]["model_input"][
        "maintenance_working_capital"
    ] = {
        "status": "BOUNDED",
        "range_low": 5.0,
        "range_high": 5.0,
        "tax_basis": "AFTER_TAX",
        "source_fact_ids": ["OBS:ARBITRARY-HALF-WC"],
    }

    validation = _validate(tmp_path / "working-capital", ledger, enforced=False)

    assert any(
        "maintenance_working_capital:canonical_basis_requires_already_reflected"
        in finding
        for finding in validation["invalid_findings"]
    )
    assert validation["state"] == "INVALID"


def test_epv_cash_range_must_preserve_the_canonical_cash_range(tmp_path: Path) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    cash_component = inputs["epv"]["model_input"]["claims_bridge"][
        "non_operating_components"
    ][0]
    cash_component["range_low"] = 34.0
    cash_component["range_high"] = 34.0
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)

    validation = _validate(tmp_path, ledger, enforced=False)

    assert "canonical_epv_cash_component_not_cash_model_derived" in (
        validation["invalid_findings"]
    )


def test_epv_owner_cash_range_must_equal_the_working_capital_model_output(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    reference_period = next(
        period
        for period in inputs["epv"]["model_input"]["period_facts"]
        if period["period_id"] == "FY2025"
    )
    reference_period["amount_range"]["range_high"] = 60.0
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)

    validation = _validate(tmp_path, ledger, enforced=False)

    assert "canonical_epv_owner_cash_range_not_working_capital_model_derived" in (
        validation["invalid_findings"]
    )


def test_every_canonical_epv_period_must_exist_in_the_working_capital_model(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    prior_period = deepcopy(inputs["epv"]["model_input"]["period_facts"][0])
    prior_period.update(
        {
            "period_id": "FY2024",
            "period_start": "2024-01-01",
            "period_end": "2024-12-31",
        }
    )
    inputs["epv"]["model_input"]["period_facts"].insert(0, prior_period)
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)

    validation = _validate(tmp_path, ledger, enforced=False)

    assert "canonical_epv_owner_cash_period_missing_from_working_capital_model" in (
        validation["invalid_findings"]
    )


@pytest.mark.parametrize("method", ["weighted_average", "additive"])
def test_replacement_value_and_epv_cannot_be_weighted_or_added(
    tmp_path: Path,
    method: str,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    ledger["synthesis"]["value_realization_bridge"] = {
        "method": method,
        "output_value_per_share": ledger["synthesis"]["chosen_value_per_share"],
        "inputs": [
            {"model_id": "dcf.fcff.base", "weight": 0.5},
            {"model_id": "replacement.going_concern", "weight": 0.5},
        ],
    }

    validation = _validate(tmp_path, ledger, enforced=False)

    assert "replacement_value_epv_cannot_be_weighted_or_added" in (
        validation["invalid_findings"]
    )


def test_ch12_deterministic_conclusions_are_protected_idempotent_and_rebound(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    chapter_12 = chapters / "_ch12.md"
    chapter_13 = chapters / "_ch13.md"
    chapter_12.write_text("## Ch12 估值\n原有投资分析正文。", encoding="utf-8")
    chapter_13.write_text("## Ch13 交叉验证\n原有投资分析正文。", encoding="utf-8")

    first = bind_valuation_references(tmp_path, ledger)
    first_text = chapter_12.read_text(encoding="utf-8")
    second = bind_valuation_references(tmp_path, ledger)
    second_text = chapter_12.read_text(encoding="utf-8")

    assert first["value_bridge_conclusions_bound"] is True
    assert first["changed_chapters"] == [12, 13]
    assert second["changed_chapters"] == []
    assert first_text == second_text
    assert first_text.count("<!-- TURTLE:VALUE_BRIDGE_BLOCK:BEGIN -->") == 1
    assert first_text.count("<!-- TURTLE:VALUE_BRIDGE_BLOCK:END -->") == 1
    assert "原有投资分析正文。" in first_text
    for slot in ledger["value_bridge_models"]["reader_slots"]:
        assert first_text.count("- " + slot["sentence"]) == 1

    first_conclusion = ledger["value_bridge_models"]["reader_slots"][0]["sentence"]
    chapter_12.write_text(
        first_text.replace("- " + first_conclusion, "- 任意改写为50%现金。"),
        encoding="utf-8",
    )
    rebound = bind_valuation_references(tmp_path, ledger)

    assert rebound["changed_chapters"] == [12]
    assert chapter_12.read_text(encoding="utf-8") == first_text


def test_reader_slot_is_bound_once_and_rebound_from_the_canonical_claim(
    tmp_path: Path,
) -> None:
    compiled = compile_valuation_value_bridges({
        "schema_version": "valuation-value-bridges-input.v1",
        "ordinary_distribution": {"model_input": _ordinary_distribution_input()},
    })
    ledger = {"models": [], "value_bridge_models": compiled}
    chapters = tmp_path / "chapters"
    chapters.mkdir()
    chapter_12 = chapters / "_ch12.md"
    chapter_12.write_text("## Ch12 估值\n原有投资分析正文。", encoding="utf-8")

    first = bind_valuation_references(tmp_path, ledger)
    canonical = chapter_12.read_text(encoding="utf-8")
    sentence = compiled["reader_slots"][0]["sentence"]

    assert first["reader_slots_bound"] == 1
    assert canonical.count(sentence) == 1
    assert "RMB3.758亿元" not in canonical

    chapter_12.write_text(
        canonical.replace("RMB278.417百万元", "RMB375.800百万元"),
        encoding="utf-8",
    )
    rebound = bind_valuation_references(tmp_path, ledger)

    assert rebound["changed_chapters"] == [12]
    assert chapter_12.read_text(encoding="utf-8") == canonical


def test_reader_slot_binding_fails_if_its_target_chapter_is_missing(
    tmp_path: Path,
) -> None:
    compiled = compile_valuation_value_bridges({
        "schema_version": "valuation-value-bridges-input.v1",
        "ordinary_distribution": {"model_input": _ordinary_distribution_input()},
    })

    with pytest.raises(
        ValueError,
        match="value_bridge_reader_binding_invalid:target_chapter_missing:12",
    ):
        bind_valuation_references(
            tmp_path,
            {"models": [], "value_bridge_models": compiled},
        )


def test_ch12_binder_refuses_internal_control_plane_reader_text(tmp_path: Path) -> None:
    ledger = _integrated_ledger(tmp_path)
    chapters = tmp_path / "chapters"
    chapters.mkdir(exist_ok=True)
    chapter_12 = chapters / "_ch12.md"
    chapter_12.write_text("## Ch12 估值\n原有投资分析正文。", encoding="utf-8")
    ledger["value_bridge_models"]["reader_slots"][0]["sentence"] = (
        "PRIMARY_ROUTE_UNKNOWN / DATA_COVERAGE / P_LONG"
    )

    with pytest.raises(ValueError, match="value_bridge_reader_binding_invalid"):
        bind_valuation_references(tmp_path, ledger)

    assert "PRIMARY_ROUTE_UNKNOWN" not in chapter_12.read_text(encoding="utf-8")


def test_joint_protection_ceiling_is_bound_when_comparable_and_null_when_unresolved(
    tmp_path: Path,
) -> None:
    comparable = _integrated_ledger(tmp_path / "comparable")
    comparable_projection = comparable["value_bridge_models"][
        "valuation_projection"
    ]["replacement_value"]["joint_protection_price_ceiling"]
    comparable_validation = _validate(
        tmp_path / "comparable",
        comparable,
        enforced=False,
    )

    assert comparable_projection["value"] == pytest.approx(8.0)
    assert comparable_projection["reason"] == ""
    assert comparable["synthesis"]["joint_protection_price_ceiling"] == pytest.approx(
        8.0
    )
    assert comparable_validation["state"] == "REVIEWABLE"
    assert not any(
        "joint_protection" in finding
        for finding in comparable_validation["invalid_findings"]
        + comparable_validation["incomplete_findings"]
        + comparable_validation["warnings"]
    )

    unresolved = _integrated_ledger(
        tmp_path / "unresolved",
        epv_comparable=False,
    )
    unresolved_projection = unresolved["value_bridge_models"][
        "valuation_projection"
    ]["replacement_value"]["joint_protection_price_ceiling"]
    unresolved_validation = _validate(
        tmp_path / "unresolved",
        unresolved,
        enforced=False,
    )

    assert unresolved_projection["value"] is None
    assert unresolved_projection["reason"] == "EPV_NOT_COMPARABLE"
    assert "joint_protection_price_ceiling" not in unresolved["synthesis"]
    assert unresolved_validation["state"] == "INVALID"
    assert unresolved_validation["incomplete_findings"] == [
        "canonical_epv_primary_not_comparable"
    ]
    assert unresolved_validation["warnings"] == [
        "replacement_value_joint_protection_price_unresolved"
    ]

    incomplete_scope = _integrated_ledger(
        tmp_path / "incomplete-scope",
        replacement_scope_complete=False,
    )
    incomplete_projection = incomplete_scope["value_bridge_models"][
        "valuation_projection"
    ]["replacement_value"]["joint_protection_price_ceiling"]
    incomplete_validation = _validate(
        tmp_path / "incomplete-scope",
        incomplete_scope,
        enforced=False,
    )

    assert incomplete_scope["value_bridge_models"]["result"]["replacement_value"][
        "epv_cross_check"
    ]["status"] == "COMPARABLE"
    assert incomplete_projection["value"] is None
    assert incomplete_projection["reason"] == "REPLACEMENT_SCOPE_INCOMPLETE"
    assert "joint_protection_price_ceiling" not in incomplete_scope["synthesis"]
    assert incomplete_validation["state"] == "REVIEWABLE"
    assert incomplete_validation["invalid_findings"] == []
    assert incomplete_validation["incomplete_findings"] == []
    assert incomplete_validation["warnings"] == [
        "replacement_value_joint_protection_price_unresolved"
    ]


def test_compiled_replacement_cannot_survive_without_active_routed_model(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    ledger["models"] = [
        model for model in ledger["models"]
        if model.get("route_model_id") != "REPLACEMENT_VALUE"
    ]

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INCOMPLETE"
    assert "replacement_value_routed_model_missing" in validation["incomplete_findings"]


def test_compiled_replacement_must_resolve_its_versioned_valuation_archetype(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    replacement = ledger["value_bridge_models"]["model_input"][
        "replacement_value"
    ]["model_input"]
    replacement["model_context"]["valuation_archetype_version"] = "v0"

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert any(
        "model_context:valuation_archetype_unavailable" in finding
        for finding in validation["invalid_findings"]
    )


def test_replacement_gate_rejects_a_route_card_mismatch(tmp_path: Path) -> None:
    ledger = _integrated_ledger(tmp_path)
    # The model keeps its valid v1 card.  This represents a route that was
    # changed without rebuilding the company model, so the gate—not a missing
    # card lookup—must reject the cross-surface mismatch.
    (tmp_path / "valuation_route.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "route_model_id": "REPLACEMENT_VALUE",
                        "valuation_archetype_id": "property_service",
                        "valuation_archetype_version": "v0",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert (
        "replacement.going_concern:replacement_value_archetype_mismatch"
        in validation["invalid_findings"]
    )


def test_replacement_epv_cross_check_must_project_the_canonical_epv_result(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    ledger["value_bridge_models"]["result"]["replacement_value"][
        "epv_cross_check"
    ]["epv_per_share_range"]["range_low"] = 0.9

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert (
        "value_bridge_models:result_not_deterministic_projection"
        in validation["invalid_findings"]
    )


def test_incomplete_replacement_projection_schema_requires_null_ranges() -> None:
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "schemas/valuation_value_bridges.schema.json")
        .read_text(encoding="utf-8")
    )
    projection = schema["$defs"]["replacementProjection"]

    assert {option.get("type") for option in projection["properties"]["per_share_range"]["oneOf"]} == {None, "null"}
    conditional = projection["allOf"][0]
    assert conditional["else"]["properties"]["per_share_range"] == {"type": "null"}
    assert conditional["else"]["properties"]["ordinary_common_equity_range"] == {"type": "null"}


def test_cash_currency_must_match_the_operating_model_that_consumes_it(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    context = inputs["cash_accessibility"]["valuation_context"]
    context.update(
        {
            "valuation_currency": "HKD",
            "fx_source_per_valuation_currency": 2,
        }
    )
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)
    contract = ledger["synthesis"]["cash_component_contract"]
    contract.update(
        {
            "valuation_currency": "HKD",
            "fx_source_per_valuation_currency": 2,
            "canonical_adopted_per_share": 1.7,
            "primary_equity_bridge_cash_component_per_share": 1.7,
        }
    )
    ledger["models"][0]["equity_bridge"]["cash_component_per_share"] = 1.7

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert "cash_component_contract_operating_currency_mismatch" in (
        validation["invalid_findings"]
    )


def test_cash_claim_cannot_be_declared_without_entering_the_equity_bridge_total(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    ledger["models"][0]["equity_bridge"]["non_operating_assets"] = 0

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert "cash_component_contract_non_operating_assets_not_component_reconciled" in (
        validation["invalid_findings"]
    )


def test_cash_component_identity_prevents_primary_and_separate_double_count(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    contract = ledger["synthesis"]["cash_component_contract"]
    contract.update(
        {
            "inclusion_location": "SEPARATE_COMPONENT",
            "primary_equity_bridge_cash_component_per_share": 0,
            "separate_component_per_share": 3.4,
        }
    )
    ledger["synthesis"].update(
        {
            "chosen_value_per_share": 53.4,
            "value_realization_bridge": {
                "method": "separate_value_components",
                "operating_model_id": "dcf.fcff.base",
                "operating_value_per_share": 50,
                "retained_growth_per_share": 0,
                "retained_growth_realization": 0,
                "accessible_cash_per_share": 3.4,
                "cash_inclusion_location": "SEPARATE_COMPONENT",
                "output_value_per_share": 53.4,
            },
        }
    )
    decision = json.loads((tmp_path / "decision_ledger.json").read_text())
    decision["entries"][0]["value"] = 53.4
    (tmp_path / "decision_ledger.json").write_text(json.dumps(decision))

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert "cash_component_contract_separate_inclusion_mismatch" in (
        validation["invalid_findings"]
    )


def test_canonical_and_legacy_cash_bridges_cannot_coexist(tmp_path: Path) -> None:
    ledger = _integrated_ledger(tmp_path)
    ledger["cash_access_bridge"] = {
        "legacy_identity": "must_not_coexist_with_canonical_cash_model"
    }

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert "canonical_and_legacy_cash_bridges_mutually_exclusive" in (
        validation["invalid_findings"]
    )


def test_cash_can_be_included_once_as_a_separate_component(tmp_path: Path) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    inputs["epv"]["model_input"]["claims_bridge"][
        "non_operating_components"
    ] = [
        item
        for item in inputs["epv"]["model_input"]["claims_bridge"][
            "non_operating_components"
        ]
        if item["kind"] != "NON_OPERATING_CASH"
    ]
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)
    epv = ledger["models"][0]
    epv["normalization_bridge"] = deepcopy(
        ledger["value_bridge_models"]["result"]["epv"]["normalization_bridge"]
    )
    epv["result"] = {
        "value_per_share": 46.6,
        "range_low": 46.6,
        "range_high": 46.6,
        "currency": "RMB",
        "status": "COMPARABLE",
        "endpoint_policy": "CONSERVATIVE_LOW",
    }
    epv["equity_bridge"] = {
        "enterprise_value": 500.0,
        "non_operating_assets": 66.0,
        "debt": 80.0,
        "minority_interest": 10.0,
        "other_adjustments": -10.0,
        "equity_value": 466.0,
        "shares": 10.0,
        "per_share_value": 46.6,
        "currency": "RMB",
        "ordinary_share_claim_scope": "Listed ordinary common shares",
        "cash_component_per_share": 0,
        "cash_component_claim_ids": [],
        "non_operating_asset_components": [
            {
                "component_id": "other-non-operating-assets",
                "kind": "other",
                "amount": 66.0,
                "claim_ids": [],
            }
        ],
        "endpoint_policy": "CONSERVATIVE_LOW",
    }
    contract = ledger["synthesis"]["cash_component_contract"]
    contract.update(
        {
            "inclusion_location": "SEPARATE_COMPONENT",
            "primary_equity_bridge_cash_component_per_share": 0,
            "separate_component_per_share": 2.7,
        }
    )
    ledger["synthesis"]["value_realization_bridge"] = {
        "method": "separate_value_components",
        "operating_model_id": "dcf.fcff.base",
        "operating_value_per_share": 46.6,
        "retained_growth_per_share": 0,
        "retained_growth_realization": 0,
        "accessible_cash_per_share": 2.7,
        "cash_component_per_share": 2.7,
        "cash_component_claim_ids": [
            "cash.existing_excess_cash_per_share",
            "cash.related_party_receivable_per_share",
        ],
        "cash_inclusion_location": "SEPARATE_COMPONENT",
        "output_value_per_share": 49.3,
    }
    ledger["synthesis"]["chosen_value_per_share"] = 49.3
    decision = json.loads((tmp_path / "decision_ledger.json").read_text())
    decision["entries"][0]["value"] = 49.3
    (tmp_path / "decision_ledger.json").write_text(json.dumps(decision))

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "REVIEWABLE"
    assert validation["invalid_findings"] == []
