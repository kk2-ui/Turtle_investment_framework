from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.judgment_selection_feedback import (
    ACTIVATION_SCHEMA_VERSION,
    AMENDMENT_REVIEW_SCHEMA_VERSION,
    OUTCOME_SCHEMA_VERSION,
    PROHIBITED_OUTPUTS,
    SelectionFeedbackError,
    build_selection_feedback,
    resolve_joint_selection,
    validate_selection_outcome,
    validate_selection_resolution_activation,
    validate_selection_resolution_amendment,
)
from scripts.judgment_selection_peer import (
    PEER_RELATIVE_CONJUNCTION,
    PEER_RELATIVE_METHOD,
    V4_ADMISSION_VERSION,
)
from tests.test_judgment_selection_control import (
    CLAIM_STAGES,
    FIVE_CLAIM_STAGES,
    _candidate,
    _measurement_contract,
    _resolution,
    _source_contract,
    _v4_peer_panel_candidate,
)


STAGE_PREDICATES = {
    stage_id: predicate_id for _, stage_id, predicate_id in CLAIM_STAGES
}
OBSERVED_VALUES = {
    "D3_PRODUCT_VOLUME": (2200.0, "tonnes"),
    "D3_UNIT_ECONOMICS": (11.0, "percent"),
    "D4_WORKING_CAPITAL_AND_CASH": (10_000_000.0, "RMB"),
    "D5_CAPITAL_RETURN": (0.08, "ratio"),
}


def _artifacts(claim_stages: tuple = CLAIM_STAGES) -> tuple[dict, dict, dict, dict]:
    candidate = _candidate(claim_stages)
    return (
        candidate,
        _measurement_contract(claim_stages),
        {
            "episode_id": candidate["case_id"],
            "selection_status": "SELECTION_ADMITTED",
            "learning_eligibility": "SELECTION_METHOD_ELIGIBLE",
            "feedback_items": [
                {"claim_id": claim_id, "stage_id": stage_id}
                for claim_id, stage_id, _ in claim_stages
            ],
        },
        _resolution(claim_stages),
    )


def _outcome(claim_stages: tuple = CLAIM_STAGES) -> dict:
    case, measurement, registration, _ = _artifacts(claim_stages)
    rules = {item["predicate_id"]: item for item in measurement["measurement_rules"]}
    claims = []
    for item in registration["feedback_items"]:
        stage_id = item["stage_id"]
        predicate_id = STAGE_PREDICATES[stage_id]
        rule = rules[predicate_id]
        claim = {
            "claim_id": item["claim_id"],
            "predicate_id": predicate_id,
            "stage_id": stage_id,
            "status": "OBSERVED",
            "source_ids": ["SYNTHETIC:OFFICIAL:" + item["claim_id"]],
            "measurement_scope": rule["required_observation"],
            "prohibited_substitutes": deepcopy(rule["prohibited_substitutes"]),
            "observed_measurement": rule["required_observation"],
            "observation_summary": "Synthetic official observation for validator regression only.",
        }
        if stage_id in OBSERVED_VALUES:
            claim["observed_value"], claim["observed_unit"] = OBSERVED_VALUES[stage_id]
        claims.append(claim)
    return {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "case_id": case["case_id"],
        "freeze_id": case["freeze_id"],
        "settlement_id": "JSELSET:SYNTHETIC:R-102:V1",
        "settlement_as_of": "2026-08-25T23:59:59+08:00",
        "first_outcome_accessed_at": "2026-08-24T09:00:00+08:00",
        "activation_id": "JSELRESACT:SYNTHETIC:R-102:V1",
        "amendment_review_id": "JSELRESREVIEW:SYNTHETIC:R-102:V1",
        "custodian_id": "synthetic-independent-outcome-custodian",
        "selection_status": "SELECTION_ADMITTED",
        "measurement_contract_identity": {
            "schema_version": measurement["schema_version"],
            "case_id": measurement["case_id"],
            "freeze_id": measurement["freeze_id"],
        },
        "registered_claim_ids": [item["claim_id"] for item in registration["feedback_items"]],
        "claims": claims,
        "prohibited_outputs": list(PROHIBITED_OUTPUTS),
    }


def _amendment_review(amendment: dict) -> dict:
    return {
        "schema_version": AMENDMENT_REVIEW_SCHEMA_VERSION,
        "review_id": "JSELRESREVIEW:SYNTHETIC:R-102:V1",
        "case_id": amendment["case_id"],
        "freeze_id": amendment["freeze_id"],
        "amendment_id": amendment["amendment_id"],
        "author_id": amendment["author_id"],
        "selector_id": amendment["selector_id"],
        "reviewer_id": "synthetic-independent-resolution-reviewer",
        "reviewed_at": "2026-08-23T23:45:00+08:00",
        "recorded_at": "2026-08-23T23:46:00+08:00",
        "status": "INDEPENDENTLY_ACCEPTED_PRE_OUTCOME",
        "reviewed_amendment": deepcopy(amendment),
    }


def _activation(amendment: dict, review: dict) -> dict:
    return {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "activation_id": "JSELRESACT:SYNTHETIC:R-102:V1",
        "case_id": amendment["case_id"],
        "freeze_id": amendment["freeze_id"],
        "amendment_id": amendment["amendment_id"],
        "amendment_review_id": review["review_id"],
        "activated_at": "2026-08-23T23:47:00+08:00",
        "recorded_at": "2026-08-23T23:48:00+08:00",
        "activation_source": "CONTROL_DB_RECONSTRUCTED",
        "activation_status": "ACTIVE_FOR_OUTCOME_SETTLEMENT",
        "program_state": "ACTIVE",
        "program_reservation_status": "REGISTERED",
        "feedback_control_registration_status": "REGISTERED",
        "outcome_release_status": "RELEASED_TO_INDEPENDENT_CUSTODIAN",
        "registered_claim_ids": deepcopy(amendment["registered_claim_ids"]),
        "program_id": "JTP:turtle-selection-development-candidate-v1",
        "training_episode_id": "JTE:R-102:huahong-xintai-selection-development-2020",
        "program_reservation_event_id": "JTAE:synthetic-r102-reservation",
        "feedback_control_registration_event_ids": {
            claim_id: "JFCREG:SYNTHETIC:" + claim_id
            for claim_id in amendment["registered_claim_ids"]
        },
        "outcome_release_event_id": "JFCEVT:SYNTHETIC:R102:OUTCOME_RELEASE_AUTHORIZED",
        "custodian_id": "synthetic-independent-outcome-custodian",
    }


def _validate(outcome: dict, claim_stages: tuple = CLAIM_STAGES) -> dict:
    case, measurement, registration, amendment = _artifacts(claim_stages)
    review = _amendment_review(amendment)
    return validate_selection_outcome(
        outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
        resolution_amendment=amendment,
        amendment_review_receipt=review, activation_receipt=_activation(amendment, review),
    )


def _build(outcome: dict, claim_stages: tuple = CLAIM_STAGES) -> dict:
    case, measurement, registration, amendment = _artifacts(claim_stages)
    review = _amendment_review(amendment)
    return build_selection_feedback(
        outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
        resolution_amendment=amendment,
        amendment_review_receipt=review, activation_receipt=_activation(amendment, review),
    )


def _claim(outcome: dict, stage_id: str) -> dict:
    return next(item for item in outcome["claims"] if item["stage_id"] == stage_id)


def _v4_peer_artifacts() -> tuple[dict, dict, dict, dict, dict]:
    """V4 source/measurement contracts bound to the executable candidate fixture."""
    _, measurement, registration, amendment = _artifacts()
    case = _v4_peer_panel_candidate()
    panel = case["peer_panel_observability"]
    order = panel["frozen_panel"]["frozen_order"]
    method = panel["relative_method"]
    d3_formula_id = case["cash_transmission_observability"]["transmission_legs"][0]["official_field_identity"]["field_id"]
    d4_formula_id = case["cash_transmission_observability"]["d4_formula"]["formula_id"]
    anchors = case["cash_transmission_observability"]["materiality_anchors"]
    rules = {rule["predicate_id"]: rule for rule in measurement["measurement_rules"]}
    for stage_id, predicate_id in (
        ("D3_UNIT_ECONOMICS", "SYN-P-D3B"),
        ("D4_WORKING_CAPITAL_AND_CASH", "SYN-P-D4"),
    ):
        anchor = anchors[stage_id]
        formula_id = d3_formula_id if stage_id == "D3_UNIT_ECONOMICS" else d4_formula_id
        rules[predicate_id]["formula_id"] = formula_id
        rules[predicate_id]["primary_test"] = deepcopy(anchor["primary_threshold"])
        rules[predicate_id]["rival_test"] = deepcopy(anchor["rival_threshold"])
        rules[predicate_id]["peer_relative_test"] = {
            "method": PEER_RELATIVE_METHOD,
            "unit": "ratio",
            "conjunction": PEER_RELATIVE_CONJUNCTION,
            "formula_id": formula_id,
            "primary_test": {
                "operator": "GREATER_THAN_OR_EQUAL",
                "value": anchor["relative_peer_threshold"]["relative_ratio_step"], "unit": "ratio",
            },
            "rival_test": {
                "operator": "LESS_THAN_OR_EQUAL",
                "value": -anchor["relative_peer_threshold"]["relative_ratio_step"], "unit": "ratio",
            },
        }
    rules["SYN-P-D3B"].pop("baseline_prediction")
    amendment["simple_baseline_resolution"]["input_claim_ids"] = ["SYN:D3A"]
    amendment["simple_baseline_resolution"]["point_identities"] = [
        identity for identity in amendment["simple_baseline_resolution"]["point_identities"]
        if identity["claim_id"] == "SYN:D3A"
    ]

    def candidate_reference(member: dict) -> dict:
        return next(
            row for row in member["annual_d3_d4_raw_observations"]
            if row["period_end"] == method["reference_period_end"]
        )

    def outcome_snapshot(member: dict) -> dict:
        company_id = member["company_id"]
        issuer_id = member["issuer_id"]
        return {
            "period_end": "2020-12-31",
            "d3_formula_id": d3_formula_id,
            "d4_formula_id": d4_formula_id,
            "fields": {
                field_name: {
                    "allowed_source_types": ["OFFICIAL_AUDITED_ANNUAL_REPORT"],
                    "issuer_id": issuer_id,
                    "perimeter_id": "LISTED_CONSOLIDATED_ISSUER",
                    "field_ref": f"{company_id}:outcome:{field_name}",
                }
                for field_name in (
                    "operating_revenue_rmb", "operating_cost_rmb", "taxes_and_surcharges_rmb",
                    "selling_expense_rmb", "administrative_expense_rmb", "operating_cash_flow_rmb",
                    "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
                    "opening_accounts_receivable_rmb", "opening_prepayments_rmb", "opening_inventory_rmb",
                    "opening_accounts_payable_rmb", "opening_customer_advances_rmb",
                    "ending_accounts_receivable_rmb", "ending_prepayments_rmb", "ending_inventory_rmb",
                    "ending_accounts_payable_rmb", "ending_customer_advances_rmb",
                )
            },
        }

    source_members = []
    measurement_members = []
    candidate_members = [panel["target"], *panel["peers"]]
    for member in candidate_members:
        company_id = member["company_id"]
        reference = candidate_reference(member)
        outcome_contract = outcome_snapshot(member)
        reference_fields = {**reference["d3_raw_fields"], **reference["d4_raw_fields"]}
        reference_contract = {
            "period_end": reference["period_end"],
            "d3_formula_id": reference["d3_formula_id"],
            "d4_formula_id": reference["d4_formula_id"],
            "reference_revenue": reference["d3_raw_fields"]["operating_revenue_rmb"]["value"],
            "fields": reference_fields,
        }
        source_members.append({
            "company_id": company_id,
            "issuer_id": member["issuer_id"],
            "control_group_id": member["control_group_id"],
            "control_group_evidence": deepcopy(member["control_group_evidence"]),
            "responsibility_unit_id": member["responsibility_unit_id"],
            "perimeter_id": member["boundary"]["perimeter_id"],
            "pre_action_history": deepcopy(member["annual_d3_d4_raw_observations"]),
            "reference": deepcopy(reference_contract),
            "outcome": deepcopy(outcome_contract),
        })
        measurement_members.append({
            "company_id": company_id,
            "issuer_id": member["issuer_id"],
            "control_group_id": member["control_group_id"],
            "control_group_evidence": deepcopy(member["control_group_evidence"]),
            "responsibility_unit_id": member["responsibility_unit_id"],
            "perimeter_id": member["boundary"]["perimeter_id"],
            "pre_action_history": deepcopy(member["annual_d3_d4_raw_observations"]),
            "reference": {
                key: deepcopy(value) for key, value in reference_contract.items() if key != "fields"
            },
            "outcome": deepcopy(outcome_contract),
        })
    source = _source_contract()
    source["peer_relative_acquisition"] = {
        "panel_contract_id": panel["panel_contract_id"],
        "frozen_order": deepcopy(order),
        "relative_method": deepcopy(method),
        "outcome_period_end": "2020-12-31",
        "members": source_members,
    }
    measurement["peer_relative_measurement"] = {
        "panel_contract_id": panel["panel_contract_id"],
        "frozen_order": deepcopy(order),
        "relative_method": deepcopy(method),
        "outcome_period_end": "2020-12-31",
        "members": measurement_members,
    }
    return case, source, measurement, registration, amendment


def _v4_peer_outcome() -> tuple[dict, dict, dict, dict, dict, dict]:
    case, source, measurement, registration, amendment = _v4_peer_artifacts()
    outcome = _outcome()
    outcome["measurement_contract_identity"] = {
        "schema_version": measurement["schema_version"],
        "case_id": measurement["case_id"],
        "freeze_id": measurement["freeze_id"],
    }
    panel = case["peer_panel_observability"]
    source_members = source["peer_relative_acquisition"]["members"]
    d3_formula_id = case["cash_transmission_observability"]["transmission_legs"][0]["official_field_identity"]["field_id"]
    d4_formula_id = case["cash_transmission_observability"]["d4_formula"]["formula_id"]

    def scalar(fields: dict, stage_id: str) -> float:
        values = {name: fields[name]["value"] for name in fields}
        if stage_id == "D3_UNIT_ECONOMICS":
            return values["operating_revenue_rmb"] - values["operating_cost_rmb"] - values["taxes_and_surcharges_rmb"] - values["selling_expense_rmb"] - values["administrative_expense_rmb"]
        opening = values["opening_accounts_receivable_rmb"] + values["opening_prepayments_rmb"] + values["opening_inventory_rmb"] - values["opening_accounts_payable_rmb"] - values["opening_customer_advances_rmb"]
        ending = values["ending_accounts_receivable_rmb"] + values["ending_prepayments_rmb"] + values["ending_inventory_rmb"] - values["ending_accounts_payable_rmb"] - values["ending_customer_advances_rmb"]
        return values["operating_cash_flow_rmb"] - values["cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb"] - max(opening - ending, 0.0)

    def raw_snapshot(member: dict, d3: float, d4: float) -> dict:
        company_id = member["company_id"]
        values = {
            "operating_revenue_rmb": 1_000.0,
            "operating_cost_rmb": 900.0 - d3,
            "taxes_and_surcharges_rmb": 20.0,
            "selling_expense_rmb": 30.0,
            "administrative_expense_rmb": 50.0,
            "operating_cash_flow_rmb": d4 + 100.0,
            "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb": 100.0,
            "opening_accounts_receivable_rmb": 10.0,
            "opening_prepayments_rmb": 0.0,
            "opening_inventory_rmb": 0.0,
            "opening_accounts_payable_rmb": 0.0,
            "opening_customer_advances_rmb": 0.0,
            "ending_accounts_receivable_rmb": 10.0,
            "ending_prepayments_rmb": 0.0,
            "ending_inventory_rmb": 0.0,
            "ending_accounts_payable_rmb": 0.0,
            "ending_customer_advances_rmb": 0.0,
        }
        fields = {}
        expected_fields = member["outcome"]["fields"]
        for name, value in values.items():
            expected = expected_fields[name]
            fields[name] = {
                "value": value,
                "unit": "RMB",
                "source_id": f"SYNTHETIC:{company_id}:outcome:{'D3' if name.startswith(('operating_revenue', 'operating_cost', 'taxes', 'selling', 'administrative')) else 'D4'}",
                "source_type": expected["allowed_source_types"][0],
                "issuer_id": expected["issuer_id"],
                "period_end": member["outcome"]["period_end"],
                "perimeter_id": expected["perimeter_id"],
                "published_at": "2021-03-30",
                "field_ref": expected["field_ref"],
            }
        return {
            "d3_formula_id": d3_formula_id,
            "d4_formula_id": d4_formula_id,
            "fields": fields,
        }

    rows = []
    for index, member in enumerate(source_members):
        is_target = index == 0
        reference_fields = member["reference"]["fields"]
        reference_d3 = scalar(reference_fields, "D3_UNIT_ECONOMICS")
        reference_d4 = scalar(reference_fields, "D4_WORKING_CAPITAL_AND_CASH")
        outcome_d3 = 160.0 if is_target else reference_d3 + 50.0
        outcome_d4 = 130.0 if is_target else reference_d4 + 10.0
        rows.append({
            "company_id": member["company_id"],
            "issuer_id": member["issuer_id"],
            "control_group_id": member["control_group_id"],
            "control_group_evidence": deepcopy(member["control_group_evidence"]),
            "responsibility_unit_id": member["responsibility_unit_id"],
            "perimeter_id": member["perimeter_id"],
            "reference_raw": {
                "d3_formula_id": member["reference"]["d3_formula_id"],
                "d4_formula_id": member["reference"]["d4_formula_id"],
                "fields": deepcopy(reference_fields),
            },
            "outcome_raw": raw_snapshot(member, outcome_d3, outcome_d4),
        })
    outcome["peer_relative_measurement"] = {
        "panel_contract_id": panel["panel_contract_id"],
        "frozen_order": deepcopy(panel["frozen_panel"]["frozen_order"]),
        "relative_method": deepcopy(panel["relative_method"]),
        "outcome_period_end": source["peer_relative_acquisition"]["outcome_period_end"],
        "members": rows,
    }
    target_outcome_fields = rows[0]["outcome_raw"]["fields"]
    target_d3 = _claim(outcome, "D3_UNIT_ECONOMICS")
    target_d3.update({
        "observed_value": 160.0,
        "observed_unit": "RMB",
        "source_ids": sorted({
            target_outcome_fields[field_name]["source_id"]
            for field_name in (
                "operating_revenue_rmb", "operating_cost_rmb", "taxes_and_surcharges_rmb",
                "selling_expense_rmb", "administrative_expense_rmb",
            )
        }),
    })
    target_d4 = _claim(outcome, "D4_WORKING_CAPITAL_AND_CASH")
    target_d4.update({
        "observed_value": 130.0,
        "observed_unit": "RMB",
        "source_ids": sorted({
            target_outcome_fields[field_name]["source_id"]
            for field_name in (
                "operating_cash_flow_rmb",
                "cash_paid_to_acquire_fixed_intangible_and_other_long_term_assets_rmb",
                "opening_accounts_receivable_rmb", "opening_prepayments_rmb",
                "opening_inventory_rmb", "opening_accounts_payable_rmb",
                "opening_customer_advances_rmb", "ending_accounts_receivable_rmb",
                "ending_prepayments_rmb", "ending_inventory_rmb",
                "ending_accounts_payable_rmb", "ending_customer_advances_rmb",
            )
        }),
    })
    return outcome, case, source, measurement, registration, amendment


def _validate_v4_peer(outcome: dict) -> dict:
    _, case, source, measurement, registration, amendment = _v4_peer_outcome()
    review = _amendment_review(amendment)
    return validate_selection_outcome(
        outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
        resolution_amendment=amendment, amendment_review_receipt=review,
        activation_receipt=_activation(amendment, review), source_contract=source,
    )


def _build_v4_peer(outcome: dict) -> dict:
    _, case, source, measurement, registration, amendment = _v4_peer_outcome()
    review = _amendment_review(amendment)
    return build_selection_feedback(
        outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
        resolution_amendment=amendment, amendment_review_receipt=review,
        activation_receipt=_activation(amendment, review), source_contract=source,
    )


def test_valid_selection_outcome_builds_explicit_primary_rival_and_baseline_cards() -> None:
    outcome = _outcome()

    assert _validate(outcome) == {
        "schema_version": "judgment-selection-outcome-validation.v1",
        "state": "REVIEWABLE",
        "findings": [],
    }
    feedback = _build(outcome)

    assert feedback["case_id"] == outcome["case_id"]
    assert feedback["freeze_id"] == outcome["freeze_id"]
    assert feedback["settlement_id"] == outcome["settlement_id"]
    assert feedback["settlement_as_of"] == outcome["settlement_as_of"]
    assert feedback["first_outcome_accessed_at"] == outcome["first_outcome_accessed_at"]
    assert feedback["activation_id"] == outcome["activation_id"]
    assert feedback["amendment_review_id"] == outcome["amendment_review_id"]
    assert feedback["custodian_id"] == outcome["custodian_id"]
    assert len(feedback["cards"]) == 6
    by_stage = {item["stage_id"]: item for item in feedback["cards"]}
    assert by_stage["D3_UNIT_ECONOMICS"]["comparison"]["verdict"] == "A_ONLY"
    assert by_stage["D4_WORKING_CAPITAL_AND_CASH"]["comparison"]["verdict"] == "A_ONLY"
    assert by_stage["D2_CUSTOMER_ABSORPTION"]["comparison"]["verdict"] == "NOT_DIAGNOSTIC"
    assert by_stage["D5_CAPITAL_RETURN"]["comparison"]["verdict"] == "NOT_DIAGNOSTIC"
    assert by_stage["D3_UNIT_ECONOMICS"]["comparison"]["simple_baseline"]["result"]["status"] == "MISSED"
    assert feedback["joint_comparison"]["central_discriminator_claim_ids"] == [
        "SYN:D3B", "SYN:D4",
    ]
    assert feedback["joint_comparison"]["mapping_key"] == "A_ONLY|A_ONLY"
    assert feedback["joint_comparison"]["overall_verdict"] == "A_ONLY"
    assert feedback["simple_baseline_resolution"]["state"] == "BASELINE_POINT_LOSS"
    assert feedback["simple_baseline_resolution"]["aggregate_loss"] > 0
    for card in feedback["cards"]:
        comparison = card["comparison"]
        assert comparison["primary_hypothesis"]["hypothesis_id"] == "SYN-H-A"
        assert comparison["strongest_rival"]["hypothesis_id"] == "SYN-H-B"
        assert comparison["simple_baseline"]["baseline_id"] == "SYN-BASELINE"
    assert feedback["control_activation_lineage"]["activation_source"] == "CONTROL_DB_RECONSTRUCTED"
    assert len(feedback["control_activation_lineage"]["feedback_control_registration_event_ids"]) == 6


def test_ordered_five_claim_outcome_uses_the_single_frozen_d3_point_identity() -> None:
    outcome = _outcome(FIVE_CLAIM_STAGES)

    assert _validate(outcome, FIVE_CLAIM_STAGES)["state"] == "REVIEWABLE"
    feedback = _build(outcome, FIVE_CLAIM_STAGES)

    assert [card["stage_id"] for card in feedback["cards"]] == [
        "D1_IMPLEMENTATION",
        "D2_CUSTOMER_ABSORPTION",
        "D3_UNIT_ECONOMICS",
        "D4_WORKING_CAPITAL_AND_CASH",
        "D5_CAPITAL_RETURN",
    ]
    assert feedback["joint_comparison"]["central_discriminator_claim_ids"] == [
        "SYN:D3B", "SYN:D4",
    ]
    assert [
        item["claim_id"]
        for item in feedback["simple_baseline_resolution"]["component_losses"]
    ] == ["SYN:D3B"]


def test_v4_peer_relative_reversal_is_recomputed_and_conjoined_with_absolute_result() -> None:
    outcome, *_ = _v4_peer_outcome()

    assert _validate_v4_peer(outcome) == {
        "schema_version": "judgment-selection-outcome-validation.v1",
        "state": "REVIEWABLE",
        "findings": [],
    }
    feedback = _build_v4_peer(outcome)
    d3 = next(card for card in feedback["cards"] if card["stage_id"] == "D3_UNIT_ECONOMICS")
    d4 = next(card for card in feedback["cards"] if card["stage_id"] == "D4_WORKING_CAPITAL_AND_CASH")

    assert d3["comparison"]["absolute_verdict"] == "A_ONLY"
    assert d3["comparison"]["peer_relative"]["verdict"] == "B_ONLY"
    assert d3["comparison"]["verdict"] == "MIXED"
    assert d4["comparison"]["absolute_verdict"] == "A_ONLY"
    assert d4["comparison"]["peer_relative"]["verdict"] == "A_ONLY"
    assert d4["comparison"]["verdict"] == "A_ONLY"
    assert feedback["joint_comparison"]["overall_verdict"] == "MIXED"


def test_v4_peer_panel_cannot_turn_an_unknown_absolute_target_observation_into_a_winner() -> None:
    outcome, *_ = _v4_peer_outcome()
    d3 = _claim(outcome, "D3_UNIT_ECONOMICS")
    d3["status"] = "UNKNOWN"
    d3["resolution_reason"] = "Target absolute measurement remains unavailable on its frozen scope."
    for field in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        d3.pop(field, None)

    assert _validate_v4_peer(outcome)["state"] == "REVIEWABLE"
    card = next(card for card in _build_v4_peer(outcome)["cards"] if card["stage_id"] == "D3_UNIT_ECONOMICS")

    assert card["comparison"]["absolute_verdict"] == "NOT_DIAGNOSTIC"
    assert card["comparison"]["verdict"] == "NOT_DIAGNOSTIC"


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (
            lambda outcome: outcome["peer_relative_measurement"].__setitem__(
                "outcome_period_end", "2020-09-29",
            ),
            "peer_outcome.outcome_period_before_action",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"].pop(
                "operating_cost_rmb",
            ),
            "peer_outcome.members[CN:SYNTHETIC-PEER-1].outcome:raw_field_set_invalid",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"][
                "operating_cost_rmb"
            ].__setitem__("published_at", "2020-12-31"),
            "published_at_not_strictly_after_candidate_cutoff",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"].__setitem__("peer_verdict", "A_ONLY"),
            "caller_supplied_peer_verdict_or_score",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"].pop(),
            "peer_outcome.member_order_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"].__setitem__(
                1, outcome["peer_relative_measurement"]["members"][2],
            ),
            "peer_outcome.member_order_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"]["operating_cost_rmb"].__setitem__("source_type", "UNFROZEN"),
            "source_type_not_frozen",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"]["operating_cost_rmb"].__setitem__("issuer_id", "ISSUER:WRONG"),
            "issuer_id_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"]["operating_cost_rmb"].__setitem__("period_end", "2021-12-31"),
            "period_end_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"]["operating_cost_rmb"].__setitem__("perimeter_id", "PARENT_ONLY"),
            "perimeter_id_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1]["outcome_raw"]["fields"]["operating_cost_rmb"].__setitem__("field_ref", "wrong-field"),
            "field_ref_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1].__setitem__("issuer_id", "ISSUER:REPLACED"),
            "peer_outcome.member_issuer_id_mismatch:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1].__setitem__(
                "control_group_id",
                outcome["peer_relative_measurement"]["members"][0]["control_group_id"],
            ),
            "peer_outcome.member_control_group_id_mismatch:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][1].__setitem__(
                "control_group_evidence", [],
            ),
            "peer_outcome.member_control_group_evidence_mismatch:CN:SYNTHETIC-PEER-1",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][0]["reference_raw"]["fields"]["operating_revenue_rmb"].__setitem__("value", 999.0),
            "peer_outcome.members[CN:SYNTHETIC].reference.operating_revenue_rmb:value_mismatch",
        ),
        (
            lambda outcome: outcome["peer_relative_measurement"]["members"][0]["outcome_raw"].__setitem__(
                "d4_formula_id", "SYN-OPERATING_CONTRIBUTION",
            ),
            "peer_outcome.members[CN:SYNTHETIC].outcome:formula_identity_mismatch",
        ),
        (
            lambda outcome: _claim(outcome, "D3_UNIT_ECONOMICS").__setitem__("observed_value", 14.0),
            "peer_outcome.target_scalar_mismatch:D3_UNIT_ECONOMICS",
        ),
        (
            lambda outcome: _claim(outcome, "D4_WORKING_CAPITAL_AND_CASH").__setitem__("source_ids", ["wrong-source"]),
            "peer_outcome.target_source_ids_mismatch:D4_WORKING_CAPITAL_AND_CASH",
        ),
    ],
)
def test_v4_peer_outcome_rejects_caller_derivation_panel_and_source_identity_drift(
    mutation, finding: str,
) -> None:
    outcome, *_ = _v4_peer_outcome()
    mutation(outcome)

    result = _validate_v4_peer(outcome)

    assert result["state"] == "INVALID"
    assert any(finding in item for item in result["findings"])


def test_legacy_selection_outcome_is_unchanged_without_a_v4_peer_panel() -> None:
    outcome = _outcome()

    assert _validate(outcome)["state"] == "REVIEWABLE"
    feedback = _build(outcome)
    d3 = next(card for card in feedback["cards"] if card["stage_id"] == "D3_UNIT_ECONOMICS")

    assert d3["comparison"]["verdict"] == "A_ONLY"
    assert d3["comparison"]["peer_relative"] is None


@pytest.mark.parametrize("mutation", ["swap", "drop_required_layer"])
def test_frozen_artifacts_reject_illegal_order_or_missing_five_layer_coverage(
    mutation: str,
) -> None:
    case, measurement, registration, amendment = _artifacts()
    if mutation == "swap":
        registration["feedback_items"][1], registration["feedback_items"][2] = (
            registration["feedback_items"][2], registration["feedback_items"][1]
        )
    else:
        registration["feedback_items"] = [
            item for item in registration["feedback_items"]
            if item["stage_id"] != "D3_UNIT_ECONOMICS"
        ]

    result = validate_selection_resolution_amendment(
        amendment,
        frozen_case=case,
        measurement_contract=measurement,
        registration=registration,
    )

    assert result["state"] == "INVALID"
    assert (
        "registration.stage_ids_must_follow_ordered_five_layer_selection_topology"
        in result["findings"]
    )


@pytest.mark.parametrize(
    ("mutation", "finding"),
    [
        (lambda value: value.__setitem__("case_id", "SELECTIONCASE:WRONG"), "outcome.case_id_mismatch"),
        (lambda value: value.__setitem__("freeze_id", "JFREEZE:WRONG"), "outcome.freeze_id_mismatch"),
        (lambda value: value.__setitem__("settlement_id", ""), "outcome.settlement_id_missing"),
        (
            lambda value: value["measurement_contract_identity"].__setitem__("freeze_id", "JFREEZE:WRONG"),
            "outcome.measurement_contract_identity.freeze_id_mismatch",
        ),
        (
            lambda value: value.__setitem__("settlement_as_of", "2023-04-30T23:59:59+08:00"),
            "outcome.settlement_as_of_before_first_access",
        ),
    ],
)
def test_selection_outcome_rejects_identity_or_clock_drift(mutation, finding: str) -> None:
    outcome = _outcome()
    mutation(outcome)

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert finding in result["findings"]


def test_selection_outcome_rejects_a_missing_registered_claim() -> None:
    outcome = _outcome()
    outcome["claims"].pop(2)

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert "outcome.claims_must_contain_six_registered_claims" in result["findings"]
    assert "outcome.claim_order_or_identity_mismatch" in result["findings"]


def test_selection_outcome_rejects_swapping_the_two_d3_predicate_identities() -> None:
    outcome = _outcome()
    output = _claim(outcome, "D3_PRODUCT_VOLUME")
    output["predicate_id"] = "SYN-P-D3B"

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert "outcome.claims[2]:predicate_does_not_match_resolution_amendment" in result["findings"]


def test_unknown_is_preserved_and_cannot_create_a_directional_selection_verdict() -> None:
    outcome = _outcome()
    cash = _claim(outcome, "D4_WORKING_CAPITAL_AND_CASH")
    cash["status"] = "UNKNOWN"
    cash["resolution_reason"] = "Compatible subsidiary cash bridge was not disclosed."
    for key in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        cash.pop(key, None)

    assert _validate(outcome)["state"] == "REVIEWABLE"
    card = next(item for item in _build(outcome)["cards"] if item["claim_id"] == cash["claim_id"])

    assert card["observation"]["status"] == "UNKNOWN"
    assert card["comparison"]["primary_hypothesis"]["result"]["status"] == "UNKNOWN"
    assert card["comparison"]["strongest_rival"]["result"]["status"] == "UNKNOWN"
    assert card["comparison"]["verdict"] == "NOT_DIAGNOSTIC"
    assert _build(outcome)["joint_comparison"]["overall_verdict"] == "NOT_DIAGNOSTIC"


def test_measurement_mismatch_is_preserved_without_scoring_the_frozen_margin_rule() -> None:
    outcome = _outcome()
    margin = _claim(outcome, "D3_UNIT_ECONOMICS")
    margin["status"] = "MEASUREMENT_MISMATCH"
    margin["resolution_reason"] = "Only a broader magnetic-material margin was disclosed."
    for key in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        margin.pop(key, None)

    assert _validate(outcome)["state"] == "REVIEWABLE"
    card = next(item for item in _build(outcome)["cards"] if item["claim_id"] == margin["claim_id"])

    assert card["observation"]["status"] == "MEASUREMENT_MISMATCH"
    assert card["comparison"]["verdict"] == "NOT_DIAGNOSTIC"
    assert _build(outcome)["joint_comparison"]["overall_verdict"] == "NOT_DIAGNOSTIC"


def test_observed_claim_rejects_a_prohibited_group_proxy() -> None:
    outcome = _outcome()
    cash = _claim(outcome, "D4_WORKING_CAPITAL_AND_CASH")
    cash["observed_measurement"] = "group cash"

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert "outcome.claims[4]:uses_prohibited_substitute" in result["findings"]
    with pytest.raises(SelectionFeedbackError):
        _build(outcome)


def test_d2_volume_cannot_be_supplied_as_a_selection_hit() -> None:
    outcome = _outcome()
    customer = _claim(outcome, "D2_CUSTOMER_ABSORPTION")
    customer["selection_verdict"] = "A_ONLY"

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert any("d2_volume_cannot_be_selection_hit" in item for item in result["findings"])


def test_d5_continuous_read_rejects_binary_hit_miss_or_threshold() -> None:
    outcome = _outcome()
    capital = _claim(outcome, "D5_CAPITAL_RETURN")
    capital["binary_verdict"] = "A_ONLY"
    capital["threshold"] = 0.10

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert any("d5_continuous_read_cannot_be_binary" in item for item in result["findings"])


def test_probability_or_investment_return_cannot_enter_selection_outcome() -> None:
    outcome = _outcome()
    outcome["probability"] = 0.7
    outcome["investment_return"] = 0.2

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert "outcome.probability:caller_supplied_verdict_or_prohibited_output" in result["findings"]
    assert "outcome.investment_return:caller_supplied_verdict_or_prohibited_output" in result["findings"]


def test_append_only_resolution_amendment_binds_joint_mapping_and_frozen_baseline_points() -> None:
    case, measurement, registration, amendment = _artifacts()

    result = validate_selection_resolution_amendment(
        amendment, frozen_case=case, measurement_contract=measurement, registration=registration,
    )

    assert result == {
        "schema_version": "judgment-selection-resolution-amendment-validation.v1",
        "state": "CANDIDATE_REVIEWABLE",
        "findings": [],
    }


def test_baseline_identities_include_only_claims_with_equal_point_forecasts() -> None:
    case, measurement, registration, amendment = _artifacts()
    product_rule = next(
        rule for rule in measurement["measurement_rules"]
        if rule["predicate_id"] == "SYN-P-D3A"
    )
    product_rule.pop("baseline_prediction")
    amendment["simple_baseline_resolution"]["input_claim_ids"] = ["SYN:D3B"]
    amendment["simple_baseline_resolution"]["point_identities"] = [
        amendment["simple_baseline_resolution"]["point_identities"][1]
    ]

    result = validate_selection_resolution_amendment(
        amendment,
        frozen_case=case,
        measurement_contract=measurement,
        registration=registration,
    )

    assert result == {
        "schema_version": "judgment-selection-resolution-amendment-validation.v1",
        "state": "CANDIDATE_REVIEWABLE",
        "findings": [],
    }


def test_baseline_can_cover_frozen_d3_and_d4_scalar_point_identities() -> None:
    case, measurement, registration, amendment = _artifacts()
    rules = {
        rule["predicate_id"]: rule for rule in measurement["measurement_rules"]
    }
    rules["SYN-P-D3A"].pop("baseline_prediction")
    rules["SYN-P-D4"]["baseline_prediction"] = {
        "operator": "EQUAL_POINT_FORECAST",
        "value": 9_000_000.0,
        "unit": "RMB",
    }
    amendment["simple_baseline_resolution"]["input_claim_ids"] = [
        "SYN:D3B", "SYN:D4",
    ]
    amendment["simple_baseline_resolution"]["point_identities"] = [
        {
            "claim_id": "SYN:D3B",
            "predicate_id": "SYN-P-D3B",
            "point_value": 12.0,
            "unit": "percent",
        },
        {
            "claim_id": "SYN:D4",
            "predicate_id": "SYN-P-D4",
            "point_value": 9_000_000.0,
            "unit": "RMB",
        },
    ]
    outcome = _outcome()
    review = _amendment_review(amendment)
    activation = _activation(amendment, review)

    validation = validate_selection_outcome(
        outcome,
        frozen_case=case,
        measurement_contract=measurement,
        registration=registration,
        resolution_amendment=amendment,
        amendment_review_receipt=review,
        activation_receipt=activation,
    )
    feedback = build_selection_feedback(
        outcome,
        frozen_case=case,
        measurement_contract=measurement,
        registration=registration,
        resolution_amendment=amendment,
        amendment_review_receipt=review,
        activation_receipt=activation,
    )

    assert validation["state"] == "REVIEWABLE"
    assert [
        item["claim_id"]
        for item in feedback["simple_baseline_resolution"]["component_losses"]
    ] == ["SYN:D3B", "SYN:D4"]
    assert feedback["simple_baseline_resolution"]["aggregate_loss"] == pytest.approx(
        ((1.0 / 12.0) + (1_000_000.0 / 9_000_000.0)) / 2.0
    )


def test_resolution_amendment_rejects_a_rewritten_joint_row_or_baseline_identity() -> None:
    case, measurement, registration, amendment = _artifacts()
    rewritten = deepcopy(amendment)
    rewritten["joint_selection_resolution"]["mapping"]["A_ONLY|B_ONLY"] = "A_ONLY"
    rewritten["simple_baseline_resolution"]["point_identities"][0]["point_value"] = 2100.0
    rewritten["simple_baseline_resolution"]["loss_function"]["aggregate"]["weights"] = "VOLUME_DOMINATES"
    rewritten["simple_baseline_resolution"]["resolution_rule"]["zero_loss"]["value"] = 0.1

    result = validate_selection_resolution_amendment(
        rewritten, frozen_case=case, measurement_contract=measurement, registration=registration,
    )

    assert result["state"] == "INVALID"
    assert "resolution_amendment.joint_mapping_rule_invalid:A_ONLY|B_ONLY" in result["findings"]
    assert "resolution_amendment.baseline_point_identities[0]:point_identity_mismatch" in result["findings"]
    assert "resolution_amendment.baseline_loss_function_invalid" in result["findings"]
    assert "resolution_amendment.baseline_resolution_rule_invalid" in result["findings"]


def test_overall_verdict_is_derived_from_amendment_mapping_not_a_vote() -> None:
    outcome = _outcome()
    cash = _claim(outcome, "D4_WORKING_CAPITAL_AND_CASH")
    cash["observed_value"] = -1.0

    feedback = _build(outcome)

    assert feedback["joint_comparison"]["per_item_verdicts"]["SYN:D3B"] == "A_ONLY"
    assert feedback["joint_comparison"]["per_item_verdicts"]["SYN:D4"] == "B_ONLY"
    assert feedback["joint_comparison"]["mapping_key"] == "A_ONLY|B_ONLY"
    assert feedback["joint_comparison"]["overall_verdict"] == "MIXED"


def test_simple_baseline_zero_loss_uses_both_frozen_point_identities_without_claiming_method_tie() -> None:
    outcome = _outcome()
    output = _claim(outcome, "D3_PRODUCT_VOLUME")
    margin = _claim(outcome, "D3_UNIT_ECONOMICS")
    output["observed_value"] = 100.0
    margin["observed_value"] = 12.0

    feedback = _build(outcome)

    baseline = feedback["simple_baseline_resolution"]
    assert baseline["state"] == "ZERO_BASELINE_POINT_LOSS"
    assert baseline["aggregate_loss"] == 0
    assert [item["point_value"] for item in baseline["component_losses"]] == [100.0, 12.0]
    assert feedback["joint_comparison"]["overall_verdict"] == "A_ONLY"


def test_d3a_unknown_only_blocks_baseline_not_joint_selection() -> None:
    outcome = _outcome()
    output = _claim(outcome, "D3_PRODUCT_VOLUME")
    output["status"] = "UNKNOWN"
    output["resolution_reason"] = "Same-unit oxide output was not disclosed."
    for key in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        output.pop(key, None)

    feedback = _build(outcome)

    assert feedback["simple_baseline_resolution"]["state"] == "NOT_DIAGNOSTIC"
    assert feedback["joint_comparison"]["overall_verdict"] == "A_ONLY"


def test_candidate_amendment_cannot_execute_without_independent_review_and_activation() -> None:
    case, measurement, registration, amendment = _artifacts()
    outcome = _outcome()

    result = validate_selection_outcome(
        outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
        resolution_amendment=amendment, amendment_review_receipt={}, activation_receipt={},
    )

    assert result["state"] == "INVALID"
    assert any("status_not_accepted" in item for item in result["findings"])
    assert any("status_not_active" in item for item in result["findings"])
    with pytest.raises(SelectionFeedbackError):
        build_selection_feedback(
            outcome, frozen_case=case, measurement_contract=measurement, registration=registration,
            resolution_amendment=amendment, amendment_review_receipt={}, activation_receipt={},
        )


def test_amendment_review_requires_exact_snapshot_role_separation_and_pre_access_clocks() -> None:
    _, _, _, amendment = _artifacts()
    outcome = _outcome()
    review = _amendment_review(amendment)
    activation = _activation(amendment, review)
    review["reviewed_amendment"]["joint_selection_resolution"]["mapping"]["A_ONLY|A_ONLY"] = "MIXED"
    review["reviewer_id"] = amendment["author_id"]
    activation["activated_at"] = "2026-08-24T10:00:00+08:00"

    result = validate_selection_resolution_activation(
        amendment, review, activation, outcome=outcome,
    )

    assert result["state"] == "INVALID"
    assert "amendment_review_receipt.snapshot_mismatch" in result["findings"]
    assert "amendment_review_receipt.reviewer_not_independent" in result["findings"]
    assert "amendment_review_activation_outcome_clock_order_invalid" in result["findings"]


def test_activation_requires_canonical_program_claim_and_release_lineage() -> None:
    _, _, _, amendment = _artifacts()
    outcome = _outcome()
    review = _amendment_review(amendment)
    activation = _activation(amendment, review)
    activation["activation_source"] = "CALLER_DECLARED"
    activation["program_reservation_event_id"] = ""
    activation["feedback_control_registration_event_ids"].pop("SYN:D4")
    activation["outcome_release_event_id"] = ""

    result = validate_selection_resolution_activation(
        amendment, review, activation, outcome=outcome,
    )

    assert result["state"] == "INVALID"
    assert "activation_receipt.source_not_canonical_control_db" in result["findings"]
    assert "activation_receipt.program_reservation_event_id_invalid" in result["findings"]
    assert "activation_receipt.feedback_control_registration_event_ids_mismatch" in result["findings"]
    assert "activation_receipt.outcome_release_event_id_missing" in result["findings"]


@pytest.mark.parametrize("field", ["activation_id", "amendment_review_id", "custodian_id"])
def test_outcome_must_bind_activation_review_and_actual_custodian(field: str) -> None:
    outcome = _outcome()
    outcome[field] = "WRONG:IDENTITY"

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert any(f"outcome.{field}_mismatch" in item for item in result["findings"])


def test_activation_recorded_after_first_outcome_access_is_rejected() -> None:
    _, _, _, amendment = _artifacts()
    outcome = _outcome()
    review = _amendment_review(amendment)
    activation = _activation(amendment, review)
    activation["recorded_at"] = "2026-08-24T10:00:00+08:00"

    result = validate_selection_resolution_activation(
        amendment, review, activation, outcome=outcome,
    )

    assert result["state"] == "INVALID"
    assert "amendment_review_activation_outcome_clock_order_invalid" in result["findings"]


@pytest.mark.parametrize("left", ["A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"])
@pytest.mark.parametrize("right", ["A_ONLY", "B_ONLY", "MIXED", "NOT_DIAGNOSTIC"])
def test_all_sixteen_joint_results_are_read_from_the_amendment_mapping(left: str, right: str) -> None:
    _, _, _, amendment = _artifacts()
    claim_ids = amendment["joint_selection_resolution"]["mapping_key_order"]

    result = resolve_joint_selection(amendment, {claim_ids[0]: left, claim_ids[1]: right})

    key = f"{left}|{right}"
    assert result == {
        "mapping_key": key,
        "overall_verdict": amendment["joint_selection_resolution"]["mapping"][key],
    }


@pytest.mark.parametrize(
    "stage_id",
    ["D1_IMPLEMENTATION", "D2_CUSTOMER_ABSORPTION", "D3_PRODUCT_VOLUME", "D5_CAPITAL_RETURN"],
)
def test_diagnostic_only_claim_status_cannot_change_overall_selection(stage_id: str) -> None:
    outcome = _outcome()
    diagnostic = _claim(outcome, stage_id)
    diagnostic["status"] = "UNKNOWN"
    diagnostic["resolution_reason"] = "Synthetic missing disclosure on a diagnostic-only claim."
    for key in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        diagnostic.pop(key, None)

    feedback = _build(outcome)

    assert feedback["joint_comparison"]["overall_verdict"] == "A_ONLY"


@pytest.mark.parametrize(
    ("stage_id", "status"),
    [
        ("D3_UNIT_ECONOMICS", "UNKNOWN"),
        ("D3_UNIT_ECONOMICS", "MEASUREMENT_MISMATCH"),
        ("D4_WORKING_CAPITAL_AND_CASH", "UNKNOWN"),
        ("D4_WORKING_CAPITAL_AND_CASH", "MEASUREMENT_MISMATCH"),
    ],
)
def test_any_unresolved_central_discriminator_forces_joint_not_diagnostic(stage_id: str, status: str) -> None:
    outcome = _outcome()
    central = _claim(outcome, stage_id)
    central["status"] = status
    central["resolution_reason"] = "Synthetic unresolved central observation."
    for key in ("observed_measurement", "observation_summary", "observed_value", "observed_unit"):
        central.pop(key, None)

    feedback = _build(outcome)

    card = next(item for item in feedback["cards"] if item["claim_id"] == central["claim_id"])
    assert card["observation"]["status"] == status
    assert card["comparison"]["verdict"] == "NOT_DIAGNOSTIC"
    assert feedback["joint_comparison"]["overall_verdict"] == "NOT_DIAGNOSTIC"


def test_amendment_rejects_adding_diagnostic_claims_to_the_central_mapping() -> None:
    case, measurement, registration, amendment = _artifacts()
    invalid = deepcopy(amendment)
    invalid["joint_selection_resolution"]["input_claim_ids"].append("SYN:D5")
    invalid["joint_selection_resolution"]["input_predicate_ids"].append("SYN-P-D5")
    invalid["joint_selection_resolution"]["mapping_key_order"].append("SYN:D5")

    result = validate_selection_resolution_amendment(
        invalid, frozen_case=case, measurement_contract=measurement, registration=registration,
    )

    assert result["state"] == "INVALID"
    assert "resolution_amendment.central_claim_ids_mismatch" in result["findings"]
    assert "resolution_amendment.central_predicate_ids_mismatch" in result["findings"]


@pytest.mark.parametrize(("field", "value"), [("observed_value", "not-a-number"), ("observed_unit", "RMB")])
def test_baseline_input_rejects_non_numeric_value_or_wrong_unit(field: str, value) -> None:
    outcome = _outcome()
    output = _claim(outcome, "D3_PRODUCT_VOLUME")
    output[field] = value

    result = _validate(outcome)

    assert result["state"] == "INVALID"
    assert any(
        marker in item
        for item in result["findings"]
        for marker in ("numeric_value_required_for_frozen_comparison", "observed_unit_does_not_match_frozen_comparison")
    )
