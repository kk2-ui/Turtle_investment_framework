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
    epv["basis"]["as_of"] = "2025-12-31"
    epv["assumptions"]["retained_value_realization"] = 0.4
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
            "cash_component_per_share": 3.4,
            "cash_component_claim_ids": [
                "cash.existing_excess_cash_per_share",
                "cash.related_party_receivable_per_share",
            ],
            "non_operating_asset_components": [
                {
                    "component_id": "recognized-accessible-cash",
                    "kind": "cash",
                    "amount": 34.0,
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
        "canonical_adopted_per_share": 3.4,
        "primary_equity_bridge_cash_component_per_share": 3.4,
        "separate_component_per_share": 0,
    }
    working_input = bridge_inputs["working_capital"]["model_input"]
    working_input["periods"][0]["owner_cash_input"]["base_metric_amount"] = 60
    replacement_input = bridge_inputs["replacement_value"]["model_input"]
    replacement_input["claims_bridge"]["shares_outstanding"] = 10.0
    replacement_input["epv_cross_check"].update(
        {
            "model_id": epv["model_id"],
            "equity_value_low": 500.0,
            "equity_value_high": 500.0,
            "per_share_low": 50.0,
            "per_share_high": 50.0,
            "shares_outstanding": 10.0,
        }
    )
    epv["cross_check_context"] = {
        key: replacement_input["epv_cross_check"][key]
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
        replacement_input["epv_cross_check"] = {
            "status": "NOT_COMPARABLE",
            "reason": "The ordinary-share claim scope cannot yet be bounded on the same basis.",
            "synthesis_rule": "CROSS_CHECK_ONLY_NEVER_ADD_OR_AVERAGE",
        }
        seed["synthesis"].pop("joint_protection_price_ceiling", None)
    else:
        seed["synthesis"].pop("joint_protection_price_ceiling", None)
    if missing_bridge is not None:
        bridge_inputs.pop(missing_bridge)

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
    ["cash_accessibility", "working_capital", "replacement_value"],
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
        "value_bridge_fact_bindings_missing"
    ]


def test_arbitrary_half_cash_and_half_single_year_working_capital_are_rejected(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    epv = ledger["models"][0]
    epv["assumptions"]["retained_value_realization"] = 0.5

    working_result = ledger["value_bridge_models"]["result"]["working_capital"]
    reference = working_result["reference_period_result"]
    actual_charge = reference["stock_flow_reconciliation"][
        "actual_cash_capital_charge"
    ]
    arbitrary_half_charge_owner_cash = (
        reference["current_owner_cash"] + actual_charge - actual_charge * 0.5
    )
    epv["normalization_bridge"][
        "normalized_earnings_model_currency"
    ] = arbitrary_half_charge_owner_cash

    validation = _validate(tmp_path, ledger, enforced=False)

    assert "dcf.fcff.base:retained_value_realization_not_cash_model_derived" in (
        validation["invalid_findings"]
    )
    assert "dcf.fcff.base:normalized_earnings_not_working_capital_derived" in (
        validation["invalid_findings"]
    )
    assert validation["state"] == "INVALID"


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
    assert unresolved_validation["state"] == "REVIEWABLE"
    assert unresolved_validation["invalid_findings"] == []
    assert unresolved_validation["incomplete_findings"] == []
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


def test_replacement_epv_cross_check_must_project_the_active_epv_result(
    tmp_path: Path,
) -> None:
    ledger = _integrated_ledger(tmp_path)
    inputs = deepcopy(ledger["value_bridge_models"]["model_input"])
    cross_check = inputs["replacement_value"]["model_input"]["epv_cross_check"]
    cross_check.update(
        {
            "equity_value_low": 9.0,
            "equity_value_high": 11.0,
            "per_share_low": 0.9,
            "per_share_high": 1.1,
        }
    )
    ledger["value_bridge_models"] = compile_valuation_value_bridges(inputs)

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "INVALID"
    assert "replacement_value_epv_cross_check_not_active_epv_per_share_low" in (
        validation["invalid_findings"]
    )
    assert "replacement_value_epv_cross_check_not_active_epv_equity_value_high" in (
        validation["invalid_findings"]
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
    epv = ledger["models"][0]
    epv["equity_bridge"].update(
        {
                "non_operating_assets": 66,
                "enterprise_value": 534,
                "equity_value": 500,
                "per_share_value": 50.0,
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
        }
    )
    contract = ledger["synthesis"]["cash_component_contract"]
    contract.update(
        {
            "inclusion_location": "SEPARATE_COMPONENT",
            "primary_equity_bridge_cash_component_per_share": 0,
            "separate_component_per_share": 3.4,
        }
    )
    ledger["synthesis"]["value_realization_bridge"] = {
        "method": "separate_value_components",
        "operating_model_id": "dcf.fcff.base",
        "operating_value_per_share": 46.6,
        "retained_growth_per_share": 0,
        "retained_growth_realization": 0,
        "accessible_cash_per_share": 3.4,
        "cash_component_per_share": 3.4,
        "cash_component_claim_ids": [
            "cash.existing_excess_cash_per_share",
            "cash.related_party_receivable_per_share",
        ],
        "cash_inclusion_location": "SEPARATE_COMPONENT",
        "output_value_per_share": 50,
    }

    validation = _validate(tmp_path, ledger, enforced=False)

    assert validation["state"] == "REVIEWABLE"
    assert validation["invalid_findings"] == []
