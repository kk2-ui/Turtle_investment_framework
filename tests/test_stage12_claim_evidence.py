from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from scripts.absolute_quality_scorecard import _claim_evidence_adjacency, score_chapter
from scripts.claim_evidence import (
    _observation_covers_fact_numbers,
    build_claim_evidence_ledger,
    evaluate_output_claim_evidence,
    initialize_claim_evidence_policy,
    persist_claim_evidence_ledger,
    validate_claim_evidence_ledger,
)
from scripts.evidence_citation import EvidenceRegistry, validate_evidence_coverage
from scripts.report_completion import evaluate_report_completion
from scripts.turtle_agent.run import _repair_targets_from_completion
from scripts.turtle_agent.tool_registry import ToolRegistry


REQUIRED = [0, 3, 4, 8, 9, 12, 13, 14]
CLAIM_TEXT = "客户留存支持议价能力，但结论受价格竞争约束。"


def _report(claim_id: str = "claim.moat") -> str:
    return "\n\n".join(
        f"## Ch{idx} 测试\n{CLAIM_TEXT}[claim: {claim_id}]"
        for idx in REQUIRED
    )


def _claim(*, source: str = "2025_年报.md", chapters: list[int] | None = None) -> dict:
    return {
        "claim_id": "claim.moat",
        "claim": CLAIM_TEXT,
        "chapters": list(chapters or REQUIRED),
        "raw_facts": [{
            "evidence_id": "ev.retention",
            "source_id": source,
            "source_group_id": "issuer-fy2025",
            "fact": "年报披露续约率为90%。",
            "authority": "audited_filing",
            "claim_distance": "raw_data",
            "published_at": "2026-03-20",
            "data_as_of": "2025-12-31",
            "direct_support": True,
            "support_type": "supports",
            "basis_match": "exact",
            "conflict_of_interest": "公司披露，数字经审计",
            "cross_checked_by": [],
        }],
        "reasoning_steps": ["留存降低获客替换成本，因此提高收入可见性。"],
        "alternative_explanations": ["合同惯性而非真实议价能力也可能造成高留存。"],
        "applicability_conditions": ["续约统计口径保持一致。"],
        "confidence": {"kind": "analyst_subjective", "value": 0.65, "basis": "披露与竞争证据综合判断"},
        "decision_impact": {"valuation": "仅支持基准情景", "position": "不提高仓位上限", "action": "跟踪续约价格"},
        "decision_entry_ids": ["valuation.v_final@test"],
    }


def _valid_payload(output: Path, *, chapters: list[int] | None = None, freeze: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    (output / "2025_年报.md").write_text("# FY2025", encoding="utf-8")
    (output / "decision_ledger.json").write_text(json.dumps({
        "entries": [{"entry_id": "valuation.v_final@test"}],
    }), encoding="utf-8")
    return build_claim_evidence_ledger(
        output, [_claim(chapters=chapters)], change_reason="initial evidence chain", freeze=freeze
    )


def _valid_cjo_payload(output: Path, *, freeze: bool = True) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    (output / "analysis_contract.json").write_text(json.dumps({
        "ts_code": "000001.SZ", "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
    }), encoding="utf-8")
    (output / "2025_年报.md").write_text("# FY2025", encoding="utf-8")
    (output / "thesis_test.json").write_text(json.dumps({
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "forward_judgments": [{"judgment_id": "fj.owner_cash"}],
    }), encoding="utf-8")
    claim = _claim()
    claim.pop("decision_impact")
    claim.pop("decision_entry_ids")
    claim["judgment_impact"] = {
        "mechanism": "续约留存降低替换频率，先维持收入可见性。",
        "normalized_earnings_or_owner_cash": "若续约保持，正常化毛利与经营现金转化不应先于销量恶化而断裂。",
        "monitoring_or_forward_judgment": "跟踪续约率、单客价格与经营现金转化，并结算 fj.owner_cash。",
        "forward_judgment_ids": ["fj.owner_cash"],
    }
    return build_claim_evidence_ledger(
        output, [claim], change_reason="freeze company mechanism and owner-cash judgment",
        freeze=freeze, analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )


def test_compound_source_cannot_mask_invented_component(tmp_path: Path) -> None:
    (tmp_path / "compute_bundle.json").write_text("{}", encoding="utf-8")
    registry = EvidenceRegistry()
    registry.register_from_output_dir(str(tmp_path))

    canonical, unresolved = registry.canonicalize_anchor("compute_bundle.json + invented_secret_database")

    assert canonical == ["compute_bundle.json"]
    assert unresolved == ["invented_secret_database"]
    assert registry.validate_anchors("[source: compute_bundle.json + invented_secret_database]")


def test_numericless_evidence_coverage_is_na_not_free_pass() -> None:
    result = validate_evidence_coverage("治理机制仍需观察。")

    assert result["number_claims"] == 0
    assert result["coverage_ratio"] is None
    assert result["status"] == "N/A"


def test_company_judgment_claim_freezes_fact_to_mechanism_to_owner_cash_to_fj(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(
        tmp_path, run_id="cjo", enforced=True,
        analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )
    payload = _valid_cjo_payload(tmp_path)

    result = validate_claim_evidence_ledger(
        payload, report_text=_report(), output_dir=tmp_path, enforced=True,
    )

    assert result["state"] == "DECISION_READY"
    assert result["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"


def test_company_judgment_claim_can_bootstrap_planned_fj_but_cannot_freeze_it(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(
        tmp_path, run_id="cjo-bootstrap", enforced=True,
        analysis_purpose="COMPANY_JUDGMENT_ONLY",
    )
    payload = _valid_cjo_payload(tmp_path, freeze=False)
    (tmp_path / "thesis_test.json").unlink()

    bootstrap = validate_claim_evidence_ledger(
        payload, report_text=_report(), output_dir=tmp_path, enforced=True,
    )
    assert bootstrap["state"] == "INCOMPLETE"
    assert "claims[0]" not in "\n".join(bootstrap["invalid_findings"])
    assert any("forward_judgment_pending:fj.owner_cash" in item for item in bootstrap["incomplete_findings"])

    payload["freeze"]["frozen"] = True
    final = validate_claim_evidence_ledger(
        payload, report_text=_report(), output_dir=tmp_path, enforced=True,
    )
    assert final["state"] == "INVALID"
    assert any("unknown_forward_judgment:fj.owner_cash" in item for item in final["invalid_findings"])


def test_company_judgment_claim_rejects_decision_id_placeholder(tmp_path: Path) -> None:
    payload = _valid_cjo_payload(tmp_path, freeze=False)
    payload["claims"][0]["decision_entry_ids"] = []

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert "claim.moat:company_judgment_cannot_carry_decision_entry_ids" in result["invalid_findings"]


def test_atomic_numeric_support_handles_decimal_thousands_and_accounting_negatives() -> None:
    observation = {
        "raw_text": "現金 1,724.75；毛利率 (1.49)%",
        "raw_value": "1,724.75",
        "normalized_value": 1724.75,
    }

    assert _observation_covers_fact_numbers("net cash=1,724.75; change=-1.49%", observation)
    assert not _observation_covers_fact_numbers("net cash=1,724.75; change=-1.50%", observation)


def test_numericless_adjacency_is_na() -> None:
    ratio, claims, supported = _claim_evidence_adjacency("结论只涉及定性机制。")

    assert ratio is None
    assert claims == supported == 0


def test_table_level_source_supports_all_numeric_rows() -> None:
    text = "\n".join([
        "| 年度 | 收入 |",
        "|---|---:|",
        "| 2024 | 100亿元 |",
        "| 2025 | 110亿元 |",
        "[table-source: 2025_年报.md]",
    ])

    ratio, claims, supported = _claim_evidence_adjacency(text)

    assert ratio == 1.0
    assert claims == supported == 2


def test_numericless_chapter_diagnostic_marks_adjacency_not_applicable(tmp_path: Path) -> None:
    registry = EvidenceRegistry()
    result = score_chapter("## Ch1 测试\n治理机制仍需观察。", 1, str(tmp_path), registry, {})

    assert result["signals"]["claim_evidence_adjacency"] is None
    assert not any("numeric_claim_adjacency" in item for item in result["review_flags"])
    assert "score" not in result and "grade" not in result


def test_valid_major_claim_ledger_reaches_decision_ready(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(tmp_path, run_id="run", enforced=True)
    payload = _valid_payload(tmp_path)

    result = validate_claim_evidence_ledger(
        payload, report_text=_report(), output_dir=tmp_path, enforced=True
    )

    assert result["state"] == "DECISION_READY"
    assert result["evidence_quality"][0]["quality"] == 1.0


def test_internal_circular_reference_cannot_directly_support_claim(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["claims"][0]["raw_facts"][0]["source_id"] = "report_internal"
    payload["freeze"]["frozen"] = False

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert any("circular_internal_support" in item for item in result["invalid_findings"])


def test_basis_mismatch_cannot_be_marked_direct_support(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path)
    payload["claims"][0]["raw_facts"][0]["basis_match"] = "mismatch"
    payload["freeze"]["frozen"] = False

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert any("direct_support_basis_mismatch" in item for item in result["invalid_findings"])


def test_low_authority_distant_source_cannot_close_major_claim(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path, freeze=False)
    evidence = payload["claims"][0]["raw_facts"][0]
    evidence["authority"] = "other"
    evidence["claim_distance"] = "analysis"

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["state"] == "INCOMPLETE"
    assert any("qualified_direct_support_missing" in item for item in result["incomplete_findings"])


def test_same_origin_reposts_are_not_counted_as_independent_sources(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path, freeze=False)
    second = deepcopy(payload["claims"][0]["raw_facts"][0])
    second["evidence_id"] = "ev.repost"
    second["source_id"] = "2025_年报.md"
    payload["claims"][0]["raw_facts"].append(second)

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["independent_source_groups"] == 1
    assert any("same_origin_not_independent" in item for item in result["warnings"])


def test_unknown_decision_entry_is_invalid(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path, freeze=False)
    payload["claims"][0]["decision_entry_ids"] = ["valuation.nonexistent"]

    result = validate_claim_evidence_ledger(payload, report_text=_report(), output_dir=tmp_path)

    assert result["state"] == "INVALID"
    assert any("unknown_decision_entry" in item for item in result["invalid_findings"])


def test_missing_required_claim_chapter_is_incomplete(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path, chapters=[0], freeze=False)

    result = validate_claim_evidence_ledger(
        payload, report_text=f"## Ch0 测试\n{CLAIM_TEXT}[claim: claim.moat]", output_dir=tmp_path, enforced=True
    )

    assert result["state"] == "INCOMPLETE"
    assert "required_claim_chapter_missing:Ch3" in result["incomplete_findings"]


def test_unknown_report_claim_reference_is_invalid(tmp_path: Path) -> None:
    payload = _valid_payload(tmp_path, freeze=False)

    result = validate_claim_evidence_ledger(
        payload, report_text=_report() + "\n[claim: invented.claim]", output_dir=tmp_path
    )

    assert result["state"] == "INVALID"
    assert "unknown_claim_reference:invented.claim" in result["invalid_findings"]


def test_frozen_claim_ledger_rejects_changed_repair(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(tmp_path, run_id="run", enforced=True)
    original = _valid_payload(tmp_path)
    assert persist_claim_evidence_ledger(tmp_path, original, report_text=_report())["written"] is True
    changed = build_claim_evidence_ledger(
        tmp_path, [_claim()], change_reason="attempted silent drift", freeze=True
    )
    changed["claims"][0]["raw_facts"][0]["fact"] = "被静默改写的事实。"
    # Rebuild so the attempted payload itself has a valid fingerprint.
    changed = build_claim_evidence_ledger(
        tmp_path, changed["claims"], change_reason="attempted silent drift", freeze=True
    )

    result = persist_claim_evidence_ledger(tmp_path, changed, report_text=_report())

    assert result["written"] is False
    assert result["claim_evidence_frozen"] is True
    assert json.loads((tmp_path / "claim_evidence_diff.json").read_text(encoding="utf-8"))["status"] == "REJECTED_FROZEN"


def test_new_policy_missing_claim_ledger_maps_completion_to_incomplete(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(tmp_path, run_id="run", enforced=True)

    validation = evaluate_output_claim_evidence(tmp_path, persist=False)
    completion = evaluate_report_completion("draft", str(tmp_path))

    assert validation["state"] == "INCOMPLETE"
    assert completion.status == "INCOMPLETE"
    assert completion.validators["claim_evidence"]["state"] == "INCOMPLETE"


def test_invalid_claim_ledger_maps_completion_to_invalid(tmp_path: Path) -> None:
    initialize_claim_evidence_policy(tmp_path, run_id="run", enforced=True)
    payload = _valid_payload(tmp_path)
    payload["claims"][0]["raw_facts"][0]["source_id"] = "invented_database"
    (tmp_path / "claim_evidence.json").write_text(json.dumps(payload), encoding="utf-8")

    completion = evaluate_report_completion("draft", str(tmp_path))

    assert completion.status == "INVALID"
    assert completion.validators["claim_evidence"]["state"] == "INVALID"


def test_old_output_without_policy_remains_skip(tmp_path: Path) -> None:
    assert evaluate_output_claim_evidence(tmp_path, persist=False)["state"] == "SKIP"


def test_claim_evidence_tool_is_auto_discoverable() -> None:
    registry = ToolRegistry()
    registry.auto_discover("turtle_agent.tools.write_tools")

    assert "write_claim_evidence_ledger" in registry.list_tools()


def test_claim_evidence_failure_routes_major_claim_chapters() -> None:
    completion = {"blocking_findings": ["Claim evidence: INCOMPLETE: claim_evidence_missing"]}

    assert _repair_targets_from_completion(completion) == (14, 0)
