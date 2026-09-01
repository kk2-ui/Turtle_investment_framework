from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.valuation_value_bridges import (
    compile_valuation_value_bridges,
    validate_valuation_value_bridge_input,
    validate_valuation_value_bridges,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests/fixtures/02669_value_bridge_regression.json"


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _compiled() -> tuple[dict, dict]:
    fixture = _fixture()
    model_input = fixture["value_bridge_input"]
    assert validate_valuation_value_bridge_input(model_input)["state"] == "VALID"
    compiled = compile_valuation_value_bridges(model_input)
    assert validate_valuation_value_bridges(compiled)["state"] == "VALID"
    return fixture, compiled


def test_02669_fixture_preserves_the_accepted_observations_needed_by_all_three_models() -> None:
    observations = _fixture()["accepted_observations"]

    assert observations["cash_and_bank_balances"] == pytest.approx(6270.725)
    assert observations["restricted_bank_deposits"] == pytest.approx(12.827)
    assert observations["one_year_operating_cash_floor"] == pytest.approx(1153.458)
    assert observations["related_party_receivables"] == pytest.approx(805.644)
    assert observations["shares_outstanding_million"] == pytest.approx(3283.960460)
    assert observations["working_capital_cash_changes"] == {
        "FY2022": pytest.approx(154.516),
        "FY2023": pytest.approx(-38.978),
        "FY2024": pytest.approx(305.708),
        "FY2025": pytest.approx(275.426),
    }


def test_02669_cash_is_evidence_bounded_without_an_arbitrary_half_haircut() -> None:
    fixture, compiled = _compiled()
    cash = compiled["result"]["cash_accessibility"]
    existing = cash["existing_excess_cash_realization"]

    assert fixture["case_identity"]["cash_temporal_evidence_status"] == (
        "NO_REALIZATION_PERIOD_OR_POST_POSITION_EVENT_EVIDENCE_ADMITTED"
    )
    assert existing["history"] == []
    assert cash["related_party_receivable_realization"][
        "post_position_collections"
    ] == pytest.approx(0.0)
    assert cash["legal_cash_accessibility"]["adopted_value"] == pytest.approx(0.0)
    assert cash["legal_cash_accessibility"]["additive_leaf_total"] == 0
    assert cash["legal_cash_accessibility"][
        "diagnostic_total_ceiling"
    ] == pytest.approx(5104.440)
    assert cash["legal_cash_accessibility"]["amount_range"] == {
        "low": pytest.approx(0.0),
        "base": pytest.approx(0.0),
        "high": pytest.approx(5104.440),
    }
    assert existing["amount_range"] == {
        "low": pytest.approx(0.0),
        "base": pytest.approx(0.0),
        "high": pytest.approx(0.0),
    }
    assert existing["legal_upper_bound"] == pytest.approx(0.0)
    assert existing["historical_observed_rate_range"] is None
    assert existing["realization_rate_range"] is None
    assert existing["adopted_realization_rate"] is None
    assert existing["adopted_value"] == pytest.approx(0.0)
    assert existing["evidenced_lower_bound"] == pytest.approx(0.0)
    assert existing["conditional_amount_range"] is None
    assert existing["unrecognized_remainder"] == pytest.approx(5104.440)
    assert existing["adoption_policy"] == (
        "zero_recognized_until_history_and_continuity_are_evidence_backed"
    )
    receivable = cash["related_party_receivable_realization"]
    assert receivable["gross_receivables"] == pytest.approx(805.644)
    assert receivable["amount_range"] == {
        "low": pytest.approx(0.0),
        "base": pytest.approx(0.0),
        "high": pytest.approx(0.0),
    }
    assert receivable["adopted_value"] == pytest.approx(0.0)
    assert receivable["unrecognized_net_exposure"] == pytest.approx(805.644)
    assert receivable["rows"][0]["uncollected_recovery_rate_range"] is None
    legal_projection = compiled["valuation_projection"]["cash_accessibility"][
        "legal_cash_accessibility"
    ]
    assert legal_projection["adopted_per_share"] == pytest.approx(0.0)
    assert legal_projection[
        "diagnostic_unrecognized_ceiling_per_share"
    ] == pytest.approx(1.5544, abs=1e-4)


def test_02669_after_tax_distribution_has_a_deterministic_reader_slot() -> None:
    _, compiled = _compiled()

    assert compiled["result"]["ordinary_distribution"][
        "after_tax_common_distribution"
    ] == 278.41697737781914
    claim = next(
        claim
        for claim in compiled["numeric_claims"]
        if claim["claim_id"] == "distribution.after_tax_common"
    )
    assert claim["selected_value"] == 278.41697737781914
    slot = next(
        item for item in compiled["reader_slots"]
        if item["slot_id"] == "after_tax_common_distribution"
    )
    assert slot == {
        "slot_id": "after_tax_common_distribution",
        "claim_id": "distribution.after_tax_common",
        "metric": "AFTER_TAX_COMMON_DISTRIBUTION",
        "target_chapter": 12,
        "display_variants": {
            "million_3dp": "RMB278.417百万元",
            "hundred_million_3dp_approx": "约RMB2.784亿元",
        },
        "sentence": (
            "税费和收取摩擦后的普通股分配为RMB278.417百万元，"
            "即约RMB2.784亿元。"
        ),
    }
    assert "3.758" not in str(compiled)


def test_02669_working_capital_history_stays_observed_while_persistence_stays_unknown() -> None:
    _, compiled = _compiled()
    working_capital = compiled["result"]["working_capital"]
    periods = working_capital["period_results"]

    assert {
        period["period_id"]: period["stock_flow_reconciliation"][
            "actual_cash_capital_charge"
        ]
        for period in periods
    } == {
        "FY2022": pytest.approx(154.516),
        "FY2023": pytest.approx(-38.978),
        "FY2024": pytest.approx(305.708),
        "FY2025": pytest.approx(275.426),
    }
    for period in periods:
        assert period["disclosure_mode"] == "NET_MOVEMENT_ONLY"
        assert period["cohort_results"] == []
        assert period["stock_flow_reconciliation"][
            "cash_capital_attribution_status"
        ] == "UNKNOWN"
        assert all(
            value is None
            for value in period["stock_flow_reconciliation"][
                "charge_by_cohort_role"
            ].values()
        )
        assert period["normalization_status"] == "UNKNOWN"
        assert period["recurring_steady_state_charge_range"] is None
        assert period["adopted_recurring_charge"] is None
        assert period["normalized_owner_cash_range"] is None
        assert period["adopted_normalized_owner_cash"] is None

    assert not any(
        claim["metric"]
        in {
            "recurring_working_capital_owner_earnings_charge",
            "normalized_owner_cash_for_valuation",
        }
        for claim in compiled["numeric_claims"]
    )
    observed_claims = {
        claim["claim_id"]: claim
        for claim in compiled["numeric_claims"]
        if claim["metric"] == "observed_working_capital_cash_capital_charge"
    }
    assert observed_claims[
        "working_capital.observed_cash_capital_charge.FY2025"
    ]["selected_value"] == pytest.approx(275.426)
    slot = next(
        item
        for item in compiled["reader_slots"]
        if item["slot_id"] == "working_capital_normalization_summary"
    )
    assert "净占用RMB275.43百万元" in slot["sentence"]
    assert "本期利润的可变现性低于报表利润所示" in slot["sentence"]
    assert "EPV不能作为买入依据" in slot["sentence"]


def test_02669_replacement_anchors_do_not_masquerade_as_a_complete_company_range() -> None:
    _, compiled = _compiled()
    replacement = compiled["result"]["replacement_value"]
    components = {item["component_id"]: item for item in replacement["component_results"]}

    assert replacement["unknown_component_ids"] == [
        "customer-relationships",
        "regional-operating-organization",
        "fulfillment-and-project-track-record",
    ]
    assert replacement["scenario_only_component_ids"] == [
        "customer-acquisition-channel-platform-anchor",
        "project-startup-working-capital-anchor",
        "other-functional-assets-cost-anchor",
    ]
    assert components["customer-acquisition-channel-platform-anchor"]["estimated_range"] == {
        "range_low": pytest.approx(309.731794),
        "range_high": pytest.approx(309.731794),
    }
    assert components["project-startup-working-capital-anchor"]["estimated_range"] == {
        "range_low": pytest.approx(0.0),
        "range_high": pytest.approx(413.387),
    }
    assert components["other-functional-assets-cost-anchor"]["estimated_range"] == {
        "range_low": pytest.approx(428.486),
        "range_high": pytest.approx(735.906),
    }
    assert replacement["ordinary_common_equity_range"] is None
    assert replacement["per_share_range"] is None
    assert replacement["economic_conclusion"]["replacement_range_status"] == "INCOMPLETE"
    assert replacement["economic_conclusion"]["claims_bridge_status"] == (
        "NOT_APPLIED_TO_INCOMPLETE_REPLACEMENT_SCOPE"
    )
    assert replacement["epv_cross_check"]["status"] == "NOT_COMPARABLE"
    assert not any(
        claim["metric"] == "going_concern_replacement_value_per_share"
        for claim in compiled["numeric_claims"]
    )


def test_02669_has_no_joint_protection_price_until_replacement_and_epv_are_comparable() -> None:
    _, compiled = _compiled()
    epv = compiled["result"]["epv"]
    ceiling = compiled["valuation_projection"]["replacement_value"][
        "joint_protection_price_ceiling"
    ]

    assert epv["status"] == "NOT_COMPARABLE"
    assert epv["critical_unknowns"] == [
        "maintenance_capex",
        "maintenance_working_capital",
        "capitalization_rate",
        "claims_bridge",
    ]
    assert epv["sustainable_owner_earnings_range"] is None
    assert epv["ordinary_common_equity_range"] is None
    assert epv["per_share_range"] is None
    assert compiled["result"]["replacement_value"]["epv_cross_check"][
        "status"
    ] == "NOT_COMPARABLE"
    assert ceiling["value"] is None
    assert ceiling["reason"] == "REPLACEMENT_SCOPE_INCOMPLETE"
    assert not any(
        claim["metric"] == "joint_protection_price_ceiling"
        for claim in compiled["numeric_claims"]
    )


def test_02669_reader_conclusion_states_the_open_boundary_in_investor_language() -> None:
    _, compiled = _compiled()
    text = "\n".join(slot["sentence"] for slot in compiled["reader_slots"])

    assert "持续经营重置价值还没有覆盖全部关键能力和启动资本" in text
    assert "不能声称资产与盈利共同提供价格底" in text
    assert "EPV不能作为买入依据" in text
    assert "不能相加抬高价值" in text
    assert "普通股现金已证可达金额为每股RMB0" in text
    assert "合并诊断条件上限为每股RMB1.5544，仍未认可" in text
    assert "存量超额现金已证下限为每股RMB0" in text
    assert "未认可余量为每股RMB1.5544" in text
    assert "关联方应收已证下限仅为已收回金额" in text
    assert "未认可余量为每股RMB0.2453" in text
    assert "未来留存现金不预设实现率，已证下限为RMB0百万元" in text
    assert "未形成条件区间，未认可余量为RMB0百万元" in text
    assert "保持空值" not in text
    for internal_term in (
        "CUSTOMER_ACQUISITION_CHANNEL",
        "PROJECT_STARTUP_WORKING_CAPITAL",
        "OTHER_FUNCTIONAL_ASSET",
        "P_LONG",
        "PRIMARY_ROUTE_UNKNOWN",
        "DATA_COVERAGE",
        "SCENARIO_ONLY",
        "RECOGNIZED",
        "CROSS_CHECK_ONLY",
    ):
        assert internal_term not in text
