import json
from pathlib import Path

from scripts.report_completion import evaluate_report_completion
from scripts.quality_gate import check


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_completion_blocks_missing_and_short_chapters(tmp_path: Path) -> None:
    out = tmp_path / "stock"
    chapters = out / "chapters"
    for idx in range(15):
        if idx == 2:
            body = "## Ch2 标题\n\n### 证据与出处\n\n[source: source_receipt.json]\n"
        else:
            detail = "\n".join(["detail"] * (130 if idx == 11 else 20))
            body = f"## Ch{idx} 标题\n\n### 详细情况\n{detail}\n"
        _write(chapters / f"_ch{idx:02d}.md", body)
    ledger = {
        "chapters": {
            str(idx): {"final": {"passed": True, "verdict": "pass", "error_count": 0, "warn_count": 0, "violations": []}}
            for idx in range(15)
        }
    }
    (out / "chapter_audit_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    result = evaluate_report_completion("draft", str(out))
    assert result.status == "BLOCKED"
    assert any(
        "Ch2: short_depth:substantive_chars:0<10" in item
        for item in result.blocking_findings
    )


def test_completion_blocks_missing_gg_derivation(tmp_path: Path) -> None:
    out = tmp_path / "stock"
    chapters = out / "chapters"
    for idx in range(15):
        if idx == 11:
            gg_text = "## Ch11 穿透回报率 GG\n\n### 详细情况\n参数 AA 公式 情景 M HH 敏感\n" + "\n".join(["x"] * 140)
            _write(chapters / "_ch11.md", gg_text)
        else:
            _write(chapters / f"_ch{idx:02d}.md", f"## Ch{idx} 标题\n\n### 详细情况\n" + "\n".join(["x"] * 140))
    ledger = {
        "chapters": {
            str(idx): {"final": {"passed": True, "verdict": "pass", "error_count": 0, "warn_count": 0, "violations": []}}
            for idx in range(15)
        }
    }
    (out / "chapter_audit_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
    result = evaluate_report_completion("draft", str(out))
    assert result.status == "BLOCKED"
    assert any("gg_derivation_missing" in item for item in result.blocking_findings)


def test_company_judgment_completion_skips_investment_manifest_and_gg_contract(tmp_path: Path) -> None:
    out = tmp_path / "stock"
    chapters = out / "chapters"
    for idx in range(15):
        _write(
            chapters / f"_ch{idx:02d}.md",
            f"## Ch{idx} 公司判断\n\n### 经营机制\n" + "\n".join(["公司事实与可结算信号。"] * 145),
        )
    (out / "analysis_contract.json").write_text(
        json.dumps({"analysis_purpose": "COMPANY_JUDGMENT_ONLY"}), encoding="utf-8",
    )
    (out / "chapter_audit_ledger.json").write_text(json.dumps({"chapters": {
        str(idx): {"final": {"passed": True, "verdict": "pass", "error_count": 0, "warn_count": 0, "violations": []}}
        for idx in range(15)
    }}), encoding="utf-8")

    result = evaluate_report_completion("company judgment", str(out))

    assert result.validators["analysis_purpose"]["state"] == "COMPANY_JUDGMENT_ONLY"
    assert result.validators["decision_manifest"]["status"] == "SKIP"
    assert result.validators["gg_derivation"]["status"] == "SKIP"
    assert not any(item.startswith(("Decision:", "Valuation route:", "Decision ledger:")) for item in result.blocking_findings)


def test_quality_gate_detects_v13_structure() -> None:
    text = "## 投资要点概览\n" + "\n".join(f"## Ch{i} 标题" for i in range(1, 15)) + "\n## 来源清单\n" + ("有效分析内容123。" * 3000)
    result = check(text)
    assert result["report_version"] == "v13"
    assert result["status"] in {"PASS", "WARN"}


def test_quality_gate_detects_v13_structure() -> None:
    text = "## 投资要点概览\n" + "\n".join(f"## Ch{i} 标题" for i in range(1, 15)) + "\n## 来源清单\n" + ("有效分析内容123。" * 3000)
    result = check(text)
    assert result["report_version"] == "v13"
    assert result["status"] in {"PASS", "WARN"}


def test_quality_gate_accepts_explicit_ch0_heading() -> None:
    text = "## Ch0 投资要点概览\n" + "\n".join(
        f"## Ch{i} 标题" for i in range(1, 15)
    ) + "\n## 来源清单\n" + ("有效分析内容123。" * 3000)

    result = check(text)

    assert "v13_structure" not in result["blocks"]


def test_quality_gate_does_not_require_details_headings() -> None:
    text = "## 投资要点概览\n" + "\n".join(
        f"## Ch{i} 标题" for i in range(1, 15)
    ) + "\n## 来源清单\n" + ("有效分析内容123。" * 3000)

    result = check(text)

    assert "details_sections" not in result["warns"]
    assert all(item["name"] != "details_sections" for item in result["checks"])


def test_report_audit_distinguishes_fcfe_gg() -> None:
    from scripts.report_audit import extract_data_points, _match_candidate, _expected_candidates
    report = "GG(AA口径): 6.2%\nGG(FCFE口径): 8.0%\n"
    points = extract_data_points(report)
    bundle = {"factor3": {"gg": {"base": 6.2}, "gg_fcfe": {"base": 8.0}}}
    candidates = _expected_candidates(bundle)
    matches = {pt["label"]: _match_candidate(pt, candidates)["field"] for pt in points if _match_candidate(pt, candidates)}
    assert matches["GG(AA口径)"] == "GG"
    assert matches["GG(FCFE口径)"] == "GG_FCFE"


def test_report_audit_does_not_treat_explanatory_p_fcfe_as_gg_value() -> None:
    from scripts.report_audit import audit_report_against_bundle

    report = "权重理由：P_base锚定GG与II；P_FCFE捕捉现金优势。综合区间：2.28~4.52 HKD。"
    bundle = {"factor3": {"gg_fcfe": {"base": 8.1}}}
    result = audit_report_against_bundle(report, bundle, ratio=1.0, seed=1)

    assert result["fail_count"] == 0


def test_citation_verifier_does_not_confuse_roe_with_r_oe() -> None:
    from scripts.citation_verifier import extract_numbers_from_report

    findings = extract_numbers_from_report("ROE 7.99%\nR(OE): 32.07%\nR_OE: 31.50%\n")
    r_oe_values = [item["reported_value"] for item in findings if item["metric"] == "R_OE"]

    assert r_oe_values == [32.07, 31.5]


def test_citation_verifier_selects_ocf_np_identity() -> None:
    from scripts.citation_verifier import _nearest_source

    candidates = [
        (1.32, "compute_bundle.factor2.ocf_np_ratio"),
        (1.46, "industry_context.percentiles.ocf_np_ratio.value"),
    ]

    assert _nearest_source(1.32, candidates)[1].startswith("compute_bundle")
    assert _nearest_source(1.46, candidates)[1].startswith("industry_context")


def test_citation_verifier_can_select_historical_perturbation_identity() -> None:
    from scripts.citation_verifier import _nearest_source

    candidates = [
        (1.49, "compute_bundle.factor2.ocf_np_ratio"),
        (0.08, "compute_bundle.factor2.perturbation_waiver.anomalous_years"),
    ]

    assert "perturbation_waiver" in _nearest_source(0.08, candidates)[1]


def test_citation_verifier_does_not_parse_ocf_np_window_as_ratio() -> None:
    from scripts.citation_verifier import extract_numbers_from_report

    findings = extract_numbers_from_report(
        "OCF/NP 3y均值=1.78\nOCF/NP比值为2.45\nOCF/NP近3年均值为1.78\n"
    )
    values = [item["reported_value"] for item in findings if item["metric"] == "OCF_NP_ratio"]

    assert values == [1.78, 2.45, 1.78]
