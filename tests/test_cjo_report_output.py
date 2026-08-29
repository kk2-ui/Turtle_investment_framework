from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.reader_coverage import evaluate_reader_coverage
from scripts import enterprise_judgment_core as enterprise_core
from scripts import judgment_generation_handoff
from scripts.judgment_handoff_receipts import record_judgment_handoff_read_receipt
from scripts.turtle_agent.tools import read_tools, write_tools
from tests.test_enterprise_judgment_core import (
    _frozen_cjo, _judgment_input, _ledger, _model, _review, _source_package,
)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _cjo_contract(output: Path) -> None:
    _write_json(output / "analysis_contract.json", {
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "company_name": "测试公司",
        "ts_code": "000001.SZ",
    })


def _cjo_reader_text() -> str:
    return "\n\n".join([
        "公司向客户提供核心产品，客户按产品定价购买，因此收入来自持续销售和服务。这个业务机制说明客户为什么付钱以及公司怎样形成收入。[source: annual.md]",
        "未来五年行业最可能从新增需求转向存量竞争，因为供给增加而客户选择变多，利润池将向高留存和低成本环节迁移。公司当前客户结构直接暴露于这条主路径，管理层调整渠道以后，正常盈利和经营现金更可能稳定；如果适应失败，客户流失会形成永久经营损失。[source: industry.md]",
        "收入、利润和经营现金要经过周期与维护投入调整，才能判断正常经营结果是否可持续；现金转换因此是检验业务质量的关键。[source: annual.md]",
        "主路径认为渠道重构后核心客户留存恢复；竞争解释认为替代品侵蚀导致结构性流失。两条机制的区别要由同口径留存信号来判别。[source: annual.md]",
        "未来应监测同口径留存和单位经济指标；若信号低于冻结阈值，就在披露后结算并重新检验机制，而不是事后改写解释。[source: annual.md]",
        "最强反方是需求下滑扩展为永久经营损失；如果客户流失持续且投入无法收回，替代解释将成立并推翻当前机制。[source: annual.md]",
        "年报提供了主要事实，但渠道库存尚未披露，因此库存吸收不计入基准经营改善，正常盈利区间维持折价；若后续同口径库存与销量匹配则升级支持，若库存增长快于销量则下修正常盈利。[source: annual.md]",
    ])


def test_cjo_reader_contract_replaces_investment_topics(tmp_path: Path) -> None:
    _cjo_contract(tmp_path)

    result = evaluate_reader_coverage(_cjo_reader_text(), tmp_path)

    assert result["status"] == "PASS"
    assert result["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert "valuation_return_price" not in result["topics"]
    assert "ordinary_share_cash_access" not in result["topics"]
    assert result["topics"]["rival_mechanisms"]["status"] == "PASS"
    assert result["topics"]["forward_settlement"]["status"] == "PASS"


def test_cjo_chapter_audit_uses_cjo_title_and_rejects_security_price(tmp_path: Path) -> None:
    _cjo_contract(tmp_path)

    result = write_tools.write_chapter(
        str(tmp_path), 12, "", "## 任意标题\n\n当前股价低于阈值，因此建议买入。",
    )

    stored = Path(result["path"]).read_text(encoding="utf-8")
    assert stored.startswith("## Ch12 终局经营结果与可证伪条件")
    assert any(item["rule"] == "CJO_OUTPUT_BOUNDARY" for item in result["audit"]["violations"])
    assert not any(item["rule"] == "GRAHAM_VFINAL_MISSING" for item in result["audit"]["violations"])


def test_cjo_output_allows_product_pricing_as_a_company_mechanism() -> None:
    result = write_tools._cjo_report_output_validation(
        "产品定价下降会先影响单位毛利，再通过渠道费用传导到经营现金。"
    )

    assert result["status"] == "PASS"


def test_cjo_summary_exposes_causal_trace_and_its_evidence_boundary(tmp_path: Path) -> None:
    _cjo_contract(tmp_path)
    _write_json(tmp_path / "thesis_test.json", {
        "central_path": {"statement": "主机制暂时更符合当前经营事实。"},
        "mechanism_chains": [
            {"chain_id": "MC:primary", "mechanism": "渠道重配保住单位经济性。"},
            {"chain_id": "MC:rival", "mechanism": "渠道竞争侵蚀单位经济性。"},
        ],
        "forward_judgments": [{
            "judgment_id": "FJ:channel", "statement": "同口径渠道份额将在六个月内保持稳定。",
            "prediction": {}, "observable_outcome": {},
        }],
        "competitive_tests": [],
        "rival_hypothesis_pairs": [{
            "primary_mechanism_chain_id": "MC:primary", "rival_mechanism_chain_id": "MC:rival",
            "discriminators": [{"signal_id": "RHPSIG:channel", "forward_judgment_id": "FJ:channel"}],
            "causal_trace": [{
                "mechanism_side": "PRIMARY", "from_state": "渠道重配", "to_state": "单位经济性稳定",
                "why_diagnostic": "主机制要求渠道结构先于现金稳定。", "status": "TESTABLE",
                "linked_discriminator_ids": ["RHPSIG:channel"],
            }, {
                "mechanism_side": "RIVAL", "from_state": "渠道竞争", "to_state": "单位经济性下降",
                "why_diagnostic": "竞争路径要求份额弱势先外溢。", "status": "UNKNOWN",
                "conservative_treatment": "不把单期毛利当作反方被否定。",
            }],
        }],
    })

    summary = write_tools._render_company_judgment_summary(tmp_path, "测试公司", "000001.SZ")

    assert "机制传导与检验" in summary
    assert "渠道重配 → 单位经济性稳定" in summary
    assert "将由前瞻信号检验：同口径渠道份额将在六个月内保持稳定" in summary
    assert "渠道竞争 → 单位经济性下降" in summary
    assert "仍属 UNKNOWN；保守处理：不把单期毛利当作反方被否定" in summary


def test_cjo_summary_exposes_critical_assumptions_and_their_boundary(tmp_path: Path) -> None:
    _cjo_contract(tmp_path)
    _write_json(tmp_path / "thesis_test.json", {
        "central_path": {"statement": "主路径仍待验证。"},
        "mechanism_chains": [
            {"chain_id": "MC:primary", "mechanism": "渠道重配。"},
            {"chain_id": "MC:rival", "mechanism": "全面竞争恶化。"},
        ],
        "forward_judgments": [{
            "judgment_id": "FJ:channel", "statement": "全渠道份额将在六个月内保持稳定。",
            "prediction": {}, "observable_outcome": {},
        }],
        "competitive_tests": [],
        "rival_hypothesis_pairs": [{
            "primary_mechanism_chain_id": "MC:primary", "rival_mechanism_chain_id": "MC:rival",
            "critical_assumptions": [{
                "mechanism_side": "PRIMARY", "statement": "离开低价渠道并未伤及全渠道份额。",
                "why_necessary": "否则渠道重配不能维持收入质量。", "status": "TESTABLE",
                "linked_discriminator_ids": ["RHPSIG:channel"],
            }, {
                "mechanism_side": "RIVAL", "statement": "线上滑落代表广泛份额流失。",
                "why_necessary": "否则不能外推到全渠道。", "status": "UNKNOWN",
                "conservative_treatment": "不以线上排名裁决。",
            }],
            "discriminators": [{"signal_id": "RHPSIG:channel", "forward_judgment_id": "FJ:channel"}],
        }],
    })

    summary = write_tools._render_company_judgment_summary(tmp_path, "测试公司", "000001.SZ")

    assert "关键前提与边界" in summary
    assert "离开低价渠道并未伤及全渠道份额" in summary
    assert "将由前瞻信号检验：全渠道份额将在六个月内保持稳定" in summary
    assert "线上滑落代表广泛份额流失" in summary
    assert "不以线上排名裁决" in summary


def test_bound_frozen_cjo_is_the_reader_summary_truth_source(tmp_path: Path) -> None:
    frozen = _frozen_cjo()
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    frozen_path = canonical / "frozen_cjo.json"
    _write_json(frozen_path, frozen)
    _write_json(tmp_path / "analysis_contract.json", {
        "report_id": frozen["company_id"],
        "company_id": frozen["company_id"],
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": frozen["cutoff_at"],
        "canonical_judgment_refs": {"frozen_cjo_ref": str(frozen_path)},
    })
    _write_json(tmp_path / "thesis_test.json", {
        "central_path": {"statement": "STALE LOCAL THESIS MUST NOT RENDER"},
        "forward_judgments": [], "mechanism_chains": [],
        "rival_hypothesis_pairs": [], "competitive_tests": [],
    })

    summary = write_tools._render_company_judgment_summary(
        tmp_path, "测试公司", "000001.SZ",
    )

    assert frozen["central_path"]["claim"] in summary
    assert frozen["strongest_counterargument"]["claim"] in summary
    assert "STALE LOCAL THESIS MUST NOT RENDER" not in summary
    assert "局部未知" in summary
    assert "本摘要仅限企业经营判断" in summary
    assert write_tools._cjo_report_output_validation(summary)["status"] == "PASS"
    for heading in (
        "企业责任边界", "产品、客户任务与竞争场", "经营状态与状态变化",
        "管理层决策事件与截至时点状态", "因果机制", "公司判断摘要", "Trace 对照",
        "来源与证据边界",
    ):
        assert heading in summary
    assert frozen["enterprise_system_ref"]["arenas"][0]["customer_task"] in summary
    assert frozen["enterprise_system_ref"]["state_changes"][0]["change_id"] in summary
    assert frozen["management_decision_ledger_ref"]["decisions"][0]["decision_id"] in summary
    assert frozen["management_decision_ledger_ref"]["events"][1]["event_type"] in summary
    assert frozen["management_decision_ledger_ref"]["events"][1]["rationale"] in summary
    arena = frozen["enterprise_system_ref"]["arenas"][0]
    mechanism = frozen["enterprise_system_ref"]["mechanisms"][0]
    assert f"责任单元={arena['responsibility_unit_id']}" in summary
    assert f"责任单元={mechanism['responsibility_unit_id']}" in summary
    assert f"经营场={mechanism['arena_id']}" in summary
    assert "记录状态=PLANNED" in summary
    assert "状态变化=PLANNED → COMMITTED" in summary
    for trace in frozen["traceability"]:
        assert trace["trace_id"] in summary
        assert trace["source_ref"] in summary
    for source in frozen["source_package"]["sources"]:
        assert source["locator"] in summary


def test_no_primary_frozen_cjo_keeps_local_company_judgments_in_summary(tmp_path: Path) -> None:
    package = _source_package()
    candidate = enterprise_core.compile_cjo_candidate(
        model=_model(source_package=package), ledger=_ledger(), source_package=package,
        judgment_input=_judgment_input(resolution="NO_PRIMARY", central=False),
    )
    frozen = enterprise_core.freeze_cjo(
        candidate=candidate, independent_review=_review(candidate),
    )
    frozen_path = tmp_path / "frozen_cjo.json"
    _write_json(frozen_path, frozen)
    _write_json(tmp_path / "analysis_contract.json", {
        "report_id": frozen["company_id"], "company_id": frozen["company_id"],
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "data_as_of": frozen["cutoff_at"],
        "canonical_judgment_refs": {"frozen_cjo_ref": str(frozen_path)},
    })

    summary = write_tools._render_company_judgment_summary(
        tmp_path, "测试公司", "000001.SZ",
    )

    assert "只限制唯一主路径选择，不撤回下列仍有证据的公司级判断" in summary
    assert frozen["forward_judgments"][0]["claim"] in summary
    assert frozen["strongest_counterargument"]["claim"] in summary
    assert "需要先补足公司层面的可判别事实" not in summary


def test_bound_frozen_cjo_assembly_ignores_all_free_files_and_writes_research_artifact(
    tmp_path: Path, monkeypatch,
) -> None:
    from scripts.report_completion import evaluate_report_completion

    frozen = _frozen_cjo()
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    frozen_path = canonical / "frozen_cjo.json"
    _write_json(frozen_path, frozen)
    _write_json(tmp_path / "analysis_contract.json", {
        "report_id": frozen["company_id"],
        "company_id": frozen["company_id"],
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY",
        "data_as_of": frozen["cutoff_at"],
        "canonical_judgment_refs": {"frozen_cjo_ref": str(frozen_path)},
    })
    # Invalid UTF-8 proves this route does not even read free chapter bytes.
    (tmp_path / "_ch05.md").write_bytes(b"\xffFREE_OPPOSITE_CONCLUSION")
    (tmp_path / "_technical_appendix.md").write_bytes(b"\xffFREE_TECHNICAL_CONCLUSION")
    handoff = judgment_generation_handoff.build_judgment_generation_handoff(
        tmp_path, "JUDGMENT_SYNTHESIS", frozen_cjo_path=frozen_path,
    )
    assert record_judgment_handoff_read_receipt(tmp_path, handoff)["state"] == "RECORDED"
    monkeypatch.setattr(write_tools, "_render_report_html", lambda *a, **k: None)

    result = write_tools.assemble_report(str(tmp_path), "被忽略的本地名称", "000001.SZ")
    report = Path(result["path"]).read_text(encoding="utf-8")

    assert result["chapter_count"] == 0
    assert result["research_artifact_written"] is True
    assert result["published"] is False
    assert result["authority"] == {
        "artifact_class": "COMPANY_JUDGMENT_RESEARCH",
        "company_judgment_read_allowed": True,
        "publication_authority": False,
        "investment_authority": False,
    }
    assert "15 章" not in report
    assert "FREE_OPPOSITE_CONCLUSION" not in report
    assert "FREE_TECHNICAL_CONCLUSION" not in report
    assert frozen["central_path"]["claim"] in report
    assert frozen["strongest_counterargument"]["claim"] in report
    assert result["completion"]["status"] == "COMPLETE"
    for validator in ("structure", "depth", "audit", "absolute_quality"):
        assert result["completion"]["validators"][validator]["status"] == "SKIP"

    changed = evaluate_report_completion(
        report + "\n\n渠道重置导致结构性恶化。", str(tmp_path),
    )
    assert changed.status == "BLOCKED"
    assert "Deterministic CJO output does not equal canonical renderer" in changed.blocking_findings


def test_bound_frozen_cjo_renderer_preserves_three_axes_and_ineligible_locality() -> None:
    mixed = _frozen_cjo(owner_cash_direction="MIXED")
    mixed_report = write_tools._render_bound_frozen_cjo_research_artifact(mixed)
    assert "当前多条竞争机制仍需共同保留" in mixed_report
    assert "正常盈利**：改善" in mixed_report
    assert "Owner Cash**：正反信号并存" in mixed_report
    assert "永久损失**：恶化" in mixed_report

    package = _source_package(cash_eligibility="EVIDENCE_INELIGIBLE")
    candidate = enterprise_core.compile_cjo_candidate(
        model=_model(source_package=package), ledger=_ledger(), source_package=package,
        judgment_input=_judgment_input(cash_evidence_state="EVIDENCE_INELIGIBLE"),
    )
    frozen = enterprise_core.freeze_cjo(
        candidate=candidate, independent_review=_review(candidate),
    )

    report = write_tools._render_bound_frozen_cjo_research_artifact(frozen)

    assert "证据：现有证据不适用" in report
    assert "局部未知" in report
    assert frozen["unknowns"][0]["closing_evidence"] in report
    assert write_tools._cjo_report_output_validation(report)["status"] == "PASS"


def test_old_v1_frozen_cjo_renders_local_projection_absence_without_invention() -> None:
    frozen = _frozen_cjo()
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    for field in ("arenas", "operating_variables", "operating_states", "state_changes"):
        frozen["enterprise_system_ref"].pop(field)
    frozen["management_decision_ledger_ref"].pop("events")

    report = write_tools._render_bound_frozen_cjo_research_artifact(frozen)

    assert "旧版冻结对象未冻结产品、客户任务与竞争场投影" in report
    assert "旧版冻结对象未冻结经营状态投影" in report
    assert "事件序列未冻结" in report
    assert "的决策 snapshot" in report
    assert frozen["management_decision_ledger_ref"]["decisions"][0]["problem_statement"] in report


def test_empty_state_changes_and_decisions_are_local_absence_not_global_failure() -> None:
    frozen = _frozen_cjo()
    frozen["enterprise_system_ref"]["state_changes"] = []
    for mechanism in frozen["enterprise_system_ref"]["mechanisms"]:
        mechanism["management_decision_ids"] = []
    frozen["management_decision_ledger_ref"]["decisions"] = []
    frozen["management_decision_ledger_ref"].pop("events")
    frozen["independent_review_receipt"]["reviewed_reader_projection"] = {
        "enterprise_system_ref": frozen["enterprise_system_ref"],
        "management_decision_ledger_ref": frozen["management_decision_ledger_ref"],
    }

    assert enterprise_core.validate_frozen_cjo(frozen)["state"] == "VALID"
    report = write_tools._render_bound_frozen_cjo_research_artifact(frozen)
    assert "未观察到合格状态变化" in report
    assert "资料不足以区分 no-action 与未披露" in report
    assert frozen["central_path"]["claim"] in report


def test_rerecorded_receipt_cannot_complete_a_mutated_frozen_projection(tmp_path: Path) -> None:
    from scripts.report_completion import evaluate_report_completion

    frozen = _frozen_cjo()
    original_report = write_tools._render_bound_frozen_cjo_research_artifact(frozen)
    frozen["independent_review_receipt"].pop("reviewed_reader_projection")
    frozen["enterprise_system_ref"]["arenas"][0]["customer_task"] = (
        "post-outcome customer success rewritten after review"
    )
    frozen["enterprise_system_ref"]["operating_states"][0]["variable_states"] = {
        "VAR:CUSTOMER_RETENTION": "POST_OUTCOME_WIN"
    }
    frozen["management_decision_ledger_ref"]["decisions"][0]["problem_statement"] = (
        "post-outcome success rewritten as the original problem"
    )
    canonical = tmp_path / "canonical"
    canonical.mkdir()
    frozen_path = canonical / "frozen_cjo.json"
    _write_json(frozen_path, frozen)
    _write_json(tmp_path / "analysis_contract.json", {
        "report_id": frozen["company_id"], "company_id": frozen["company_id"],
        "analysis_purpose": "COMPANY_JUDGMENT_ONLY", "data_as_of": frozen["cutoff_at"],
        "canonical_judgment_refs": {"frozen_cjo_ref": str(frozen_path)},
    })
    handoff = judgment_generation_handoff.build_judgment_generation_handoff(
        tmp_path, "JUDGMENT_SYNTHESIS", frozen_cjo_path=frozen_path,
    )
    recorded = record_judgment_handoff_read_receipt(tmp_path, handoff)
    assert recorded["state"] == "RECORDED"
    assert recorded["readiness_state"] != "READY"

    completion = evaluate_report_completion(original_report, str(tmp_path))

    assert completion.status == "BLOCKED"
    assert any(
        "reviewed_reader_projection_missing_for_new_shape" in item
        for item in completion.blocking_findings
    )


def test_cjo_assembly_skips_decision_compiler_manifest_and_investment_memo(
    tmp_path: Path, monkeypatch,
) -> None:
    import scripts.report_completion as completion_module
    import scripts.research_calibration as calibration_module

    _cjo_contract(tmp_path)
    _write_json(tmp_path / "insight_policy.json", {"enforced": True})
    for idx in range(15):
        (tmp_path / f"_ch{idx:02d}.md").write_text(
            f"## Ch{idx} 公司判断\n\n公司经营事实、机制和未来信号。[source: annual{idx}.md]",
            encoding="utf-8",
        )
    fake_completion = SimpleNamespace(
        status="COMPLETE",
        to_dict=lambda: {"status": "COMPLETE", "blocking_findings": [], "warning_findings": [], "validators": {}},
    )
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)
    monkeypatch.setattr(write_tools, "_run_quality_checks", lambda *a, **k: {"passed": True, "issues": [], "warnings": []})
    monkeypatch.setattr(write_tools, "_render_report_html", lambda *a, **k: None)
    monkeypatch.setattr(calibration_module, "create_publication_snapshot", lambda *a, **k: {"written": True})

    result = write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")
    report = Path(result["path"]).read_text(encoding="utf-8")

    assert result["published"] is True
    assert result["decision_compiler"]["state"] == "SKIP"
    assert result["memo_preservation"] is None
    assert result["technical_report_path"] is None
    assert result["cjo_report_output"]["status"] == "PASS"
    assert not (tmp_path / "decision_manifest.json").exists()
    assert "公司判断摘要" in report
    assert "投资备忘录" not in report


def test_cjo_assembly_blocks_a_security_price_even_if_other_gates_pass(
    tmp_path: Path, monkeypatch,
) -> None:
    import scripts.report_completion as completion_module

    _cjo_contract(tmp_path)
    for idx in range(15):
        text = f"## Ch{idx} 公司判断\n\n公司经营事实、机制和未来信号。[source: annual{idx}.md]"
        if idx == 14:
            text += "\n\n当前股价低于阈值。"
        (tmp_path / f"_ch{idx:02d}.md").write_text(text, encoding="utf-8")
    fake_completion = SimpleNamespace(
        status="COMPLETE",
        to_dict=lambda: {"status": "COMPLETE", "blocking_findings": [], "warning_findings": [], "validators": {}},
    )
    monkeypatch.setattr(completion_module, "evaluate_report_completion", lambda *a, **k: fake_completion)

    result = write_tools.assemble_report(str(tmp_path), "测试公司", "000001.SZ")

    assert result["published"] is False
    assert "cjo_forbidden_security_price" in result["cjo_report_output"]["blocking_findings"]


def test_cjo_ledger_writers_inherit_contract_purpose_and_reject_mismatch(tmp_path: Path) -> None:
    _cjo_contract(tmp_path)

    bridge = write_tools.write_financial_driver_bridge(
        str(tmp_path), change_reason="purpose propagation smoke",
    )
    thesis = write_tools.write_thesis_test_ledger(
        str(tmp_path), change_reason="purpose propagation smoke", freeze=False,
    )
    assert bridge["written"] is True
    assert json.loads((tmp_path / "financial_driver_bridge.json").read_text(encoding="utf-8"))["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert thesis["ledger"]["analysis_purpose"] == "COMPANY_JUDGMENT_ONLY"
    assert write_tools.write_financial_driver_bridge(
        str(tmp_path), analysis_purpose="INVESTMENT_DECISION"
    )["error"] == "analysis_purpose_contract_mismatch"
    assert write_tools.write_thesis_test_ledger(
        str(tmp_path), analysis_purpose="INVESTMENT_DECISION"
    )["error"] == "analysis_purpose_contract_mismatch"


def test_investment_thesis_contract_exposes_the_frozen_cjo_predecessor(tmp_path: Path) -> None:
    _write_json(tmp_path / "analysis_contract.json", {
        "analysis_purpose": "INVESTMENT_DECISION", "ts_code": "000001.SZ",
    })
    _write_json(tmp_path / "company_judgment_predecessor.json", {
        "source": {
            "snapshot_fingerprint": "cjo-snapshot", "report_id": "000001.SZ",
            "data_as_of": "2026-08-02", "thesis_sha256": "cjo-thesis",
        },
        "central_path": {"path_id": "CJO:path", "statement": "经营中心路径"},
        "forward_judgments": [{"judgment_id": "FJ:CJO:channel"}],
        "mechanism_chains": [{"chain_id": "MC:CJO:channel"}],
    })

    contract = read_tools.read_structured_ledger_contract(str(tmp_path), ledger="thesis")

    predecessor = contract["company_judgment_predecessor"]
    assert predecessor["central_path"]["path_id"] == "CJO:path"
    assert predecessor["forward_judgments"][0]["judgment_id"] == "FJ:CJO:channel"
    assert "不得因价格、估值或回报改写" in predecessor["rule"]
