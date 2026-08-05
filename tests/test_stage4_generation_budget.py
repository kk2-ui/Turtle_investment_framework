from __future__ import annotations

from scripts.audit_rules import _check_evidence_density, _check_number_consistency
from scripts.evidence_citation import EvidenceRegistry
from scripts.report_audit import extract_data_points, audit_report_against_bundle
from scripts.turtle_agent.agent_loop import AgentConfig, TurtleAgent
from scripts.turtle_agent.llm_client import LlmResponse, ToolCall
from scripts.turtle_agent.tool_registry import ToolRegistry
from scripts.turtle_agent.tools.write_tools import _check_dividend_identity


class _DummyLlm:
    model = "dummy"


def test_gg_consistency_distinguishes_metric_identities() -> None:
    content = """
GG（AA口径）=5.0%。GG(FCFE口径)=6.0%。
GG(Normalized口径)=5.1%。折价后GG=3.9%。
"""

    assert _check_number_consistency(content) == []


def test_evidence_density_uses_semantic_claims_not_numeric_tokens() -> None:
    rows = "\n".join(f"| FY{year} | {year}.0% | {year * 2}M |" for year in range(21, 31))
    content = f"""## Ch13 测试

### 数据表

| 年份 | 毛利率 | 金额 |
|---|---:|---:|
{rows}

[source: compute_bundle.json]
[source: financial_trends.json]
[source: report_internal]
"""

    assert _check_evidence_density(content) == []


def test_evidence_density_ignores_compiler_owned_decision_registry() -> None:
    rows = "\n".join(
        f"- 指标{i}：{i}.0 pct [source: CALC:{i}]" for i in range(1, 9)
    )
    content = f"""## Ch0 测试

<!-- TURTLE:DECISION_BLOCK:Ch0:BEGIN fingerprint={'a' * 64} -->
### Canonical decision snapshot

{rows}
<!-- TURTLE:DECISION_BLOCK:Ch0:END -->

### 正文

公司有稳定经营历史，但结论仍取决于未来兑现。这里是正常段落级叙述，不需要逐句重复来源。[source: annual_report]
"""

    assert _check_evidence_density(content) == []


def test_persisted_chapter_payload_is_compacted(tmp_path) -> None:
    registry = ToolRegistry()
    registry.register(
        "write_chapter",
        lambda **kwargs: {
            "chapter_index": kwargs["chapter_index"],
            "char_count": len(kwargs["content"]),
            "depth": {"status": "PASS", "failures": []},
            "audit": {"passed": True, "verdict": "pass"},
        },
        parameters={"chapter_index": {"type": "integer"}, "content": {"type": "string"}},
    )
    agent = TurtleAgent(
        llm=_DummyLlm(),  # type: ignore[arg-type]
        tools=registry,
        config=AgentConfig(output_dir=str(tmp_path)),
    )
    body = "长正文" * 1000
    agent._handle_tool_calls(LlmResponse(tool_calls=[ToolCall(
        id="write",
        name="write_chapter",
        arguments={"chapter_index": 3, "content": body},
    )]))

    assistant_payload = agent._messages[0]["content"][0]["input"]["content"]
    metrics = agent.run_metrics()

    assert assistant_payload.startswith("[公司全局记忆·Ch3")
    # Stage 5 deliberately retains a bounded semantic company memory instead
    # of replacing the whole chapter with an empty placeholder.
    assert metrics["context_chars_compacted"] > 1000
    assert metrics["company_memory_chars"] > 1000


def test_dividend_identity_does_not_capture_payout_or_margin_thresholds() -> None:
    report = (
        "AA GG=5.0% < 股息率6.71%。GG低于股息率意味着分红率超过100%阈值。\n"
        "当前毛利率69.96%，与股息率6.71%不是同一指标。"
    )
    bundle = {
        "factor4": {
            "dividend_identity": {
                "yield_pretax_pct": 6.71,
                "yield_after_tax_pct": 6.04,
                "price_currency": "RMB",
                "period": "FY",
            }
        }
    }

    result = _check_dividend_identity(report, bundle)

    assert result["status"] == "PASS"
    assert result["contradictions"] == []


def test_generated_tool_and_derivation_sources_are_canonicalized() -> None:
    registry = EvidenceRegistry()
    registry.register_source("2025_年报.md", "2025 年报")

    sources = set(registry.extract_canonical_sources("\n".join([
        "[source: peer_comparison 净利率P98.1]",
        "[source: search_report FY2025 应收账款增长51.32%]",
        "[source: search_report 长期股权投资8.76亿]",
        "[source: 自算 P*=DPS×(1+g)/(r_req−g)]",
        "[source: 年报未披露接班人计划]",
        "[source: Ch12裁决表]",
        "[source: P\\*推导; position capped_pct=0.0%]",
        "[source: P\\\\*推导; position capped_pct=0.0%]",
        "[source: get_financial_statement income tax line]",
        "[source: balance_sheet FY2025 LTI]",
        "[source: investor preference]",
    ])))

    assert "industry_context.json" in sources
    assert "2025_年报.md" in sources
    assert "report_derivation" in sources
    assert "financial_statement_db" in sources
    assert "framework_method" in sources
    assert "unresolved_evidence" not in sources


def test_discounted_gg_is_not_audited_as_base_gg() -> None:
    report = "| gg_discounted(base) | 3.9% | compute_bundle gg_discounted.base |"
    bundle = {"factor3": {"gg": {"base": 5.0}}}

    result = audit_report_against_bundle(report, bundle, ratio=1.0, seed=1)

    assert result["matched_count"] == 0


def test_p_fcfe_price_is_not_audited_as_fcfe_gg() -> None:
    from scripts.report_audit import audit_report_against_bundle

    report = "| P_FCFE（GG_FCFE=II） | 90.45元 | compute_ddm p_fcfe |"
    bundle = {
        "factor3": {"gg_fcfe": {"base": 10.9}},
        "factor4": {"p_base": {"p_fcfe": {"price_hkd": 90.45}}},
    }

    result = audit_report_against_bundle(report, bundle, ratio=1.0, seed=1)

    assert result["matched_count"] == 1
    assert result["items"][0]["field"] == "P_FCFE"
    assert result["items"][0]["status"] == "PASS"


def test_dividend_identity_allows_explicit_component_yields() -> None:
    from scripts.turtle_agent.tools.write_tools import _check_dividend_identity

    report = (
        "## Ch7 股东回报路径\n"
        "当前股息率=8.03%。其中常规DPS=2.0元（股息率5.4%），"
        "中期DPS=1.0元（股息率2.7%）。"
    )
    bundle = {"factor4": {"dividend_identity": {"yield_pretax_pct": 8.03}}}

    assert _check_dividend_identity(report, bundle)["status"] == "PASS"


def test_ocf_np_reconciliation_recognizes_explicit_raw_mean(tmp_path) -> None:
    from scripts.turtle_agent.tools.write_tools import _run_quality_checks

    report = (
        "原始口径OCF/NP五年序列=0.08/1.14/1.94/0.91/1.60，raw_mean=1.13。"
        "经扰动调整剔除异常年份后，OCF/NP=1.49。"
    )
    bundle = {"factor2": {"ocf_np_analysis": {"raw_mean": 1.09}}}
    (tmp_path / "compute_bundle.json").write_text(
        __import__("json").dumps(bundle), encoding="utf-8"
    )

    result = _run_quality_checks(report, str(tmp_path))

    assert not any("OCF/NP" in warning for warning in result["warnings"])


def test_ap_dpo_reconciliation_does_not_warn_on_negated_fake_cash_flow(tmp_path, monkeypatch) -> None:
    from scripts.turtle_agent.tools.write_tools import _run_quality_checks
    from turtle_agent.tools import calc_tools

    report = (
        "AP增速未超过成本增速，DPO稳定或改善，"
        "不存在供应商融资膨胀伪装现金流的伪现金流问题。"
    )
    bundle = {}
    (tmp_path / "compute_bundle.json").write_text(
        __import__("json").dumps(bundle), encoding="utf-8"
    )
    monkeypatch.setattr(calc_tools, "compute_gg", lambda _: {})
    monkeypatch.setattr(
        calc_tools, "compute_aa",
        lambda _: {"ap_driven_analysis": {"ap_normal": True, "ap_pct": 0}},
    )

    result = _run_quality_checks(report, str(tmp_path))

    assert not any("AP/DPO恶化" in warning for warning in result["warnings"])


def test_ap_dpo_reconciliation_warns_on_positive_fake_cash_flow_claim(tmp_path, monkeypatch) -> None:
    from scripts.turtle_agent.tools.write_tools import _run_quality_checks
    from turtle_agent.tools import calc_tools

    report = "DPO拉长且AP延迟支付，形成伪现金流。"
    bundle = {}
    (tmp_path / "compute_bundle.json").write_text(
        __import__("json").dumps(bundle), encoding="utf-8"
    )
    monkeypatch.setattr(calc_tools, "compute_gg", lambda _: {})
    monkeypatch.setattr(
        calc_tools, "compute_aa",
        lambda _: {"ap_driven_analysis": {"ap_normal": True, "ap_pct": 0}},
    )

    result = _run_quality_checks(report, str(tmp_path))

    assert any("AP/DPO恶化" in warning for warning in result["warnings"])
