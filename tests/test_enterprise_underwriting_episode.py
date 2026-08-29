from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from scripts.enterprise_underwriting_episode import (
    compile_underwriting_projections,
    render_underwriting_readout,
    validate_enterprise_underwriting_episode,
    validate_underwriting_projection_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
EPISODES = ROOT / "docs/development/research/enterprise_underwriting_episodes"


def _episode(name: str) -> dict:
    return json.loads((EPISODES / name).read_text(encoding="utf-8"))


def test_worked_cases_are_reviewable_and_reuse_only_existing_sources() -> None:
    for name in ("MAGNA_200903_WORKED_CASE_V1.json", "CN600585_20240501_WORKED_CASE_V1.json"):
        episode = _episode(name)
        assert validate_enterprise_underwriting_episode(episode)["state"] == "REVIEWABLE"
        for evidence in episode["evidence_trace"]:
            assert (ROOT / evidence["source_ref"]).is_file()
        for reference in episode["existing_object_refs"]:
            assert (ROOT / reference["ref"]).is_file()


def test_magna_is_a_distressed_cycle_demonstration_and_not_a_conch_conclusion() -> None:
    magna = _episode("MAGNA_200903_WORKED_CASE_V1.json")
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")

    assert magna["underwriting_route"] == "DISTRESSED_CYCLICAL"
    assert "GROWTH_VALUE_AS_PRIMARY" in magna["value_route"]["excluded_routes"]
    assert magna["sample_identity"] == conch["sample_identity"] == "WORKED_CASE"
    assert magna["company_id"] != conch["company_id"]
    assert "不能复制 Magna 的恢复结论" in magna["existing_object_refs"][1]["role"]
    assert "项目级客户" in conch["component_treatments"][2]["reason"]


def test_conch_same_thesis_projects_deterministically_to_cjo_valuation_and_report_consumers() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    bundle = compile_underwriting_projections(conch)
    stored = {
        "cjo_candidate_projection": _episode_projection("CN600585_20240501_CJO_CANDIDATE_PROJECTION.json"),
        "valuation_route_request": _episode_projection("CN600585_20240501_VALUATION_ROUTE_REQUEST.json"),
        "golden_report_underwriting_handoff": _episode_projection("CN600585_20240501_GOLDEN_REPORT_UNDERWRITING_HANDOFF.json"),
    }

    assert bundle == compile_underwriting_projections(deepcopy(conch))
    assert bundle == stored
    assert validate_underwriting_projection_bundle(conch, bundle)["state"] == "REVIEWABLE"
    thesis_id = conch["underwriting_thesis"]["thesis_id"]
    assert {item["underwriting_thesis_id"] for item in bundle.values()} == {thesis_id}
    assert bundle["cjo_candidate_projection"]["central_path"] == bundle["golden_report_underwriting_handoff"]["central_path"]
    assert bundle["valuation_route_request"]["normal_earnings_input_treatment"] == conch["underwriting_thesis"]["normal_earnings_treatment"]


def _episode_projection(name: str) -> dict:
    return json.loads((EPISODES / name).read_text(encoding="utf-8"))


def test_price_facing_treatment_cannot_rewrite_the_underwriting_thesis() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    revised_price_treatment = deepcopy(conch)
    revised_price_treatment["investment_treatment"] = "A future price observation changes research priority only."

    assert compile_underwriting_projections(revised_price_treatment)["cjo_candidate_projection"]["central_path"] == conch["underwriting_thesis"]["central_path"]
    forbidden = deepcopy(conch)
    forbidden["underwriting_thesis"]["price"] = "must not become a business fact"
    findings = validate_enterprise_underwriting_episode(forbidden)["findings"]
    assert any("price_boundary" in finding for finding in findings)


def test_local_owner_cash_limit_does_not_erase_survival_or_value_route() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    treatments = {item["component_id"]: item["treatment"] for item in conch["component_treatments"]}

    assert treatments["ORDINARY_SHARE_OWNER_CASH"] == "CANNOT_BOUND"
    assert treatments["CONSOLIDATED_SURVIVAL_AND_FINANCING"] == "UNDERWRITE"
    assert treatments["DOMESTIC_INCREMENTAL_ASSET_RETURN"] == "EXCLUDE_FROM_BASE"
    assert conch["value_route"]["primary_routes"] == ["ASSET_VALUE", "EARNINGS_POWER_VALUE", "CAPITAL_RETURN_CROSS_CHECK"]


def test_readout_is_investor_facing_and_preserves_the_strongest_rival() -> None:
    conch = _episode("CN600585_20240501_WORKED_CASE_V1.json")
    rendered = render_underwriting_readout(conch)
    reader_file = (EPISODES / "CN600585_20240501_INVESTOR_READOUT.md").read_text(encoding="utf-8")

    assert "即时生存风险低" in rendered
    assert "海外毛利改善" in rendered
    assert "DOMESTIC_INCREMENTAL_ASSET_RETURN：EXCLUDE_FROM_BASE" in rendered
    assert "能穿越周期" in reader_file
    assert "新增国内资产" in reader_file
    assert "schema" not in reader_file.lower()
