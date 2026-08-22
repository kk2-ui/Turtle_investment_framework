from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from scripts.reader_coverage import evaluate_reader_coverage
from scripts.turtle_agent.tools import read_tools, write_tools


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
        "收入、利润和经营现金要经过周期与维护投入调整，才能判断正常经营结果是否可持续；现金转换因此是检验业务质量的关键。[source: annual.md]",
        "主路径认为渠道重构后核心客户留存恢复；竞争解释认为替代品侵蚀导致结构性流失。两条机制的区别要由同口径留存信号来判别。[source: annual.md]",
        "未来应监测同口径留存和单位经济指标；若信号低于冻结阈值，就在披露后结算并重新检验机制，而不是事后改写解释。[source: annual.md]",
        "最强反方是需求下滑扩展为永久经营损失；如果客户流失持续且投入无法收回，替代解释将成立并推翻当前机制。[source: annual.md]",
        "年报提供了主要事实，但渠道库存尚未披露，属于 UNKNOWN；这个证据边界限制了当前判断，只能等待公司层面的同口径数据。[source: annual.md]",
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
