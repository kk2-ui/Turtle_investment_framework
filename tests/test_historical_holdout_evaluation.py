from copy import deepcopy

from scripts.historical_holdout_evaluation import (
    EVALUATION_SCHEMA_VERSION,
    SETTLEMENT_SCHEMA_VERSION,
    build_treatment_pair,
    compile_holdout_utility_verdict,
    validate_holdout_evaluation,
    validate_treatment_pair,
)
from tests.test_historical_judgment_first_draft import _draft
from tests.test_historical_role_isolation import _method_pack


def _packet() -> dict:
    return {
        "schema_version": "historical-holdout-pair-packet.v1",
        "episode_id": "HIST:CN000001:20240501:FY2024",
        "company_id": "CN:000001",
        "cutoff_at": "2024-05-01T00:00:00+08:00",
        "method_pack_id": "METHOD_PACK:JUDGMENT_FIRST:BLIND_FEEDBACK:V1",
        "method_version": "judgment-first-blind-feedback.v1",
        "shared_source_budget": [
            {
                "source_id": "OFFICIAL:FY2023",
                "packet_name": "FY2023.pdf",
                "available_at": "2024-04-01T00:00:00+08:00",
                "time_role": "PRE_CUTOFF",
            }
        ],
        "arms": {
            "baseline": {
                "forecaster_id": "AGENT:BASELINE",
                "method_input": {"state": "NONE"},
            },
            "enhanced": {
                "forecaster_id": "AGENT:ENHANCED",
                "method_input": {
                    "state": "FROZEN_GENERALIZED_METHOD_SUPPLIED",
                    "method_pack_id": "METHOD_PACK:JUDGMENT_FIRST:BLIND_FEEDBACK:V1",
                    "method_version": "judgment-first-blind-feedback.v1",
                },
            },
        },
        "outcome_state": "SEALED_NOT_IN_PACKET",
        "authority": "NONE",
    }


def _pair(*, change: bool = True):
    baseline = _draft()
    enhanced = deepcopy(baseline)
    if change:
        enhanced["material_treatment_snapshot"]["normal_earnings"] = {
            "treatment_code": "UNCHANGED",
            "rationale": "转换三联征出现时先暂停进一步上修。",
        }
        baseline["material_treatment_snapshot"]["normal_earnings"] = {
            "treatment_code": "RAISE",
            "rationale": "当前经济吸收足以小幅上修。",
        }
    pair = build_treatment_pair(
        pair_id="PAIR:HIST:1",
        frozen_at="2024-05-01T01:00:00+08:00",
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        holdout_pair_packet=_packet(),
        method_pack=_method_pack(),
    )
    return baseline, enhanced, pair


def _settlement(pair, status="OBSERVED") -> dict:
    return {
        "schema_version": SETTLEMENT_SCHEMA_VERSION,
        "settlement_id": "SETTLEMENT:HIST:1",
        "pair_id": pair["pair_id"],
        "episode_id": pair["episode_id"],
        "company_id": pair["company_id"],
        "custodian_id": "AGENT:CUSTODIAN",
        "settled_at": "2025-05-01T00:00:00+08:00",
        "cells": [
            {
                "cell_id": cell_id,
                "status": status,
                "classification": "OBSERVED_CLASS" if status == "OBSERVED" else status,
                "evidence_ref": "OFFICIAL:FY2024",
                "observed_facts": ["同责任边界结果已经结算。"],
            }
            for cell_id in pair["shared_outcome_cell_ids"]
        ],
        "outcome_access": "AFTER_PAIR_FREEZE",
        "artifact_status": "SETTLED",
        "authority": "NONE",
    }


def _evaluation(pair, supported_arm="ENHANCED") -> dict:
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "evaluation_id": "EVAL:HIST:1",
        "pair_id": pair["pair_id"],
        "reviewer_id": "AGENT:REVIEWER",
        "evaluated_at": "2025-05-02T00:00:00+08:00",
        "axis_assessments": [
            {
                "axis": axis,
                "settlement_cell_ids": [pair["shared_outcome_cell_ids"][0]],
                "result_supported_arm": supported_arm,
                "rationale": "结果支持该臂冻结的材料处理。",
                "economic_impact": "改变正常盈利与内在价值方向的承保范围。",
            }
            for axis in pair["material_preoutcome_differences"]
        ],
        "overall_utility_verdict": compile_holdout_utility_verdict(
            pair=pair,
            axis_assessments=[
                {"result_supported_arm": supported_arm}
                for _ in pair["material_preoutcome_differences"]
            ],
        ),
        "artifact_status": "EVALUATED",
        "authority": "NONE",
    }


def test_fair_pair_binds_exact_preoutcome_treatments_and_method_difference() -> None:
    baseline, enhanced, pair = _pair()
    assert validate_treatment_pair(
        pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        holdout_pair_packet=_packet(),
        method_pack=_method_pack(),
    ) == []
    pair["enhanced_treatment_snapshot"]["normal_earnings"]["treatment_code"] = "LOWER"
    assert "holdout_pair.enhanced_snapshot_must_match_frozen_draft" in validate_treatment_pair(
        pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        holdout_pair_packet=_packet(),
        method_pack=_method_pack(),
    )


def test_same_material_treatment_is_no_utility_even_if_wording_differs() -> None:
    baseline, enhanced, pair = _pair(change=False)
    enhanced["material_treatment_snapshot"]["normal_earnings"]["rationale"] = "写得更清楚。"
    pair = build_treatment_pair(
        pair_id="PAIR:HIST:1",
        frozen_at="2024-05-01T01:00:00+08:00",
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        holdout_pair_packet=_packet(),
        method_pack=_method_pack(),
    )
    evaluation = _evaluation(pair)
    result = validate_holdout_evaluation(
        evaluation,
        pair=pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        settlement=_settlement(pair),
    )
    assert result["valid"]
    assert result["overall_utility_verdict"] == "NO_MATERIAL_UTILITY"
    assert result["learning_authorization"] == "NONE"


def test_observed_relevant_result_can_create_only_bounded_candidate() -> None:
    baseline, enhanced, pair = _pair()
    result = validate_holdout_evaluation(
        _evaluation(pair, "ENHANCED"),
        pair=pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        settlement=_settlement(pair),
    )
    assert result == {
        "valid": True,
        "findings": [],
        "overall_utility_verdict": "MATERIAL_UTILITY_CANDIDATE",
        "learning_authorization": "CANDIDATE_ONLY",
        "transfer_validated": False,
    }


def test_local_unknown_cannot_be_promoted_by_positive_reviewer_label() -> None:
    baseline, enhanced, pair = _pair()
    evaluation = _evaluation(pair, "ENHANCED")
    result = validate_holdout_evaluation(
        evaluation,
        pair=pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        settlement=_settlement(pair, "LOCAL_UNKNOWN"),
    )
    assert not result["valid"]
    assert result["learning_authorization"] == "NONE"
    assert any("material_assessment_requires_observed_cells" in item for item in result["findings"])


def test_baseline_supported_is_harmful_and_mixed_axes_are_not_validated() -> None:
    baseline, enhanced, pair = _pair()
    harmful = validate_holdout_evaluation(
        _evaluation(pair, "BASELINE"),
        pair=pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        settlement=_settlement(pair),
    )
    assert harmful["overall_utility_verdict"] == "HARMFUL"
    assert harmful["learning_authorization"] == "NONE"


def test_irrelevant_cell_and_nonindependent_reviewer_are_rejected() -> None:
    baseline, enhanced, pair = _pair()
    evaluation = _evaluation(pair)
    evaluation["reviewer_id"] = pair["enhanced_forecaster_id"]
    baseline["outcome_cells"][0]["direct_axes"].remove("normal_earnings")
    baseline["outcome_cells"][0]["preserved_axes"].append("normal_earnings")
    enhanced["outcome_cells"][0]["direct_axes"].remove("normal_earnings")
    enhanced["outcome_cells"][0]["preserved_axes"].append("normal_earnings")
    result = validate_holdout_evaluation(
        evaluation,
        pair=pair,
        baseline_draft=baseline,
        enhanced_draft=enhanced,
        settlement=_settlement(pair),
    )
    assert not result["valid"]
    assert "holdout_evaluation.reviewer_must_be_independent" in result["findings"]
    assert any("settlement_cell_not_bound_to_axis" in item for item in result["findings"])
