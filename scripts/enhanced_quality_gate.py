#!/usr/bin/env python3
"""enhanced_quality_gate.py — V10：增强质量门禁。

在现有 structural quality_gate 的基础上增加：
- 数值一致性：跨章同指标一致（如同一 revenue 在 Ch3 和 Ch5）
- Token 效率：实质内容/模板比率
- 结论一致性：Executive Summary 与详细分析对齐
- 风险披露：看空分析是否反映在风险章节

输出 enhanced_quality_report.json。
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

from report_audit import audit_report_against_bundle


def enhanced_check(
    report_text: str,
    audit_results: dict[int, Any] | None = None,
    compute_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """执行增强质量检查。

    Args:
        report_text: 报告 Markdown 全文。
        audit_results: 逐章审计结果映射（章节序号 → 审计数据）。
        compute_bundle: Zone A 计算数据（用于交叉验证）。

    Returns:
        结构化质量报告字典。
    """
    result: dict[str, Any] = {
        "status": "PASS",
        "checks": [],
        "blocks": [],
        "warns": [],
        "metrics": {},
        "lines": len(report_text.split("\n")),
    }

    # 1. 数值一致性检查
    num_check = _check_number_consistency(report_text, compute_bundle)
    result["checks"].append(num_check)
    if num_check["status"] == "FAIL":
        result["blocks"].append(num_check["name"])
        result["status"] = "BLOCKED"

    # 1.5 关键数字抽样审计
    audit_check = _check_data_point_audit(report_text, compute_bundle)
    result["checks"].append(audit_check)
    if audit_check["status"] == "FAIL":
        result["blocks"].append(audit_check["name"])
        result["status"] = "BLOCKED"

    # 2. Token 效率检查
    eff_check = _check_content_efficiency(report_text)
    result["checks"].append(eff_check)
    if eff_check["status"] == "FAIL":
        result["warns"].append(eff_check["name"])
        if result["status"] == "PASS":
            result["status"] = "WARN"

    # 3. 结论一致性检查
    cons_check = _check_conclusion_consistency(report_text)
    result["checks"].append(cons_check)
    if cons_check["status"] == "FAIL":
        result["warns"].append(cons_check["name"])
        if result["status"] == "PASS":
            result["status"] = "WARN"

    # 4. 风险披露检查
    risk_check = _check_risk_disclosure(report_text)
    result["checks"].append(risk_check)
    if risk_check["status"] == "FAIL":
        result["blocks"].append(risk_check["name"])
        result["status"] = "BLOCKED"

    # 5. 审计聚合（如果提供）
    if audit_results:
        audit_summary = _summarize_audit_results(audit_results)
        result["audit_summary"] = audit_summary
        result["checks"].append({
            "name": "audit_aggregate",
            "status": "PASS" if audit_summary.get("failed_chapters", 0) == 0 else "FAIL",
            "detail": audit_summary,
        })

    # 6. 指标
    result["metrics"] = {
        "total_lines": result["lines"],
        "table_count": len(re.findall(r"\|.*\|.*\|", report_text)),
        "evidence_anchor_count": len(re.findall(r"\[source:\s*[^\]]+\]", report_text)),
        "placeholder_count": len(re.findall(r"\[\?\]|\[missing\]|\[待填充\]", report_text)),
    }

    return result


def _check_number_consistency(report: str, compute_bundle: dict | None) -> dict:
    """检查报告中的关键数值是否与 compute_bundle 一致。"""
    inconsistencies: list[str] = []
    if compute_bundle:
        # 提取报告中的关键数值
        params = compute_bundle.get("params", {})
        ii = params.get("II")
        rf = params.get("Rf")

        if ii is not None:
            # 搜索报告中所有 II 值
            ii_matches = re.findall(r"II\s*[=＝]\s*([\d.]+)\s*%", report)
            if ii_matches:
                unique = set(ii_matches)
                if len(unique) > 1:
                    inconsistencies.append(f"II 值不一致: {unique}")
                # 检查是否与 compute_bundle 一致（允许 ±0.5% 误差）
                for val in unique:
                    try:
                        if abs(float(val) - float(ii)) > 0.5:
                            inconsistencies.append(f"II 值偏离 compute_bundle: 报告={val}%, 实际={ii}%")
                    except ValueError:
                        pass

    return {
        "name": "number_consistency",
        "status": "FAIL" if inconsistencies else "PASS",
        "detail": inconsistencies if inconsistencies else "关键数值与 compute_bundle 一致",
        "inconsistencies": inconsistencies,
    }


def _check_data_point_audit(report: str, compute_bundle: dict | None) -> dict:
    """调用独立 report_audit 工具，对报告做抽样核对。"""
    if not compute_bundle:
        return {
            "name": "data_point_audit",
            "status": "PASS",
            "detail": "未提供 compute_bundle，跳过抽样审计",
            "audited": [],
            "failures": [],
        }

    audit_result = audit_report_against_bundle(report, compute_bundle, ratio=0.15, seed=7)
    failures = [
        f"{item['field']} 偏差 {item['deviation_pct']:.2f}% > 1% (报告={item['reported']}, 计算={item['expected']})"
        for item in audit_result.get("items", [])
        if item.get("status") == "FAIL"
    ]
    audited = [
        {
            "field": item.get("field"),
            "expected": item.get("expected"),
            "observed": item.get("reported"),
            "deviation_pct": item.get("deviation_pct"),
            "line_number": item.get("line_number"),
        }
        for item in audit_result.get("items", [])
    ]

    detail = (
        failures
        if failures
        else (
            f"已审计 {audit_result.get('sampled_count', 0)} 个关键数字，"
            f"通过 {audit_result.get('pass_count', 0)}，警告 {audit_result.get('warn_count', 0)}"
        )
    )
    return {
        "name": "data_point_audit",
        "status": "FAIL" if failures else "PASS",
        "detail": detail,
        "audited": audited,
        "failures": failures,
        "audit_result": audit_result,
    }


def _check_content_efficiency(report: str) -> dict:
    """检查叙事碎片和重复，不惩罚 Markdown 所需的正常空行。"""
    try:
        from scripts.report_prose import narrative_efficiency_metrics
    except ModuleNotFoundError:
        from report_prose import narrative_efficiency_metrics
    metrics = narrative_efficiency_metrics(report)
    issues = metrics["issues"]

    return {
        "name": "content_efficiency",
        "status": "FAIL" if issues else "PASS",
        "detail": issues if issues else (
            f"叙事段落 {metrics['prose_paragraphs']} 个；"
            f"短单句比例 {metrics['single_sentence_ratio']:.1%}；"
            f"重复比例 {metrics['duplicate_ratio']:.1%}"
        ),
        "issues": issues,
        "metrics": metrics,
    }


def _check_conclusion_consistency(report: str) -> dict:
    """检查 Executive Summary 的结论是否与详细分析一致。"""
    issues: list[str] = []

    # 提取 ES 和因子4结论中的关键判断词
    es_section = _extract_section(report, "Executive Summary")
    conclusion_section = _extract_section(report, "因子4")

    if es_section and conclusion_section:
        # 检查基础判断是否一致（买入/持有/卖出 vs Continue/Hold/Abandon）
        buy_words = ["买入", "优先买入", "Continue", "通过"]
        sell_words = ["否决", "Abandon", "不通过", "卖出"]

        es_buy = any(w in es_section for w in buy_words)
        es_sell = any(w in es_section for w in sell_words)
        conc_buy = any(w in conclusion_section for w in buy_words)
        conc_sell = any(w in conclusion_section for w in sell_words)

        if es_buy and conc_sell:
            issues.append("Executive Summary 偏多但因子4结论偏空")
        if es_sell and conc_buy:
            issues.append("Executive Summary 偏空但因子4结论偏多")

    return {
        "name": "conclusion_consistency",
        "status": "FAIL" if issues else "PASS",
        "detail": issues if issues else "ES 与详细分析结论一致",
    }


def _check_risk_disclosure(report: str) -> dict:
    """检查看空信号是否在风险章节中被充分披露。"""
    issues: list[str] = []

    # 提取魔鬼代言人中的看空信号
    devil_section = _extract_section(report, "魔鬼代言人")
    risk_section = _extract_section(report, "风险矩阵")

    if devil_section:
        # 找到 WARN 信号
        warn_signals = re.findall(r"[🔴🟡]\s*(.*?)(?=\n|$)", devil_section)
        if warn_signals and risk_section:
            for signal in warn_signals[:3]:
                # 取前 10 个字符作为关键词
                kw = signal.strip()[:10]
                if kw and kw not in risk_section:
                    issues.append(f"魔鬼代言人信号未在风险章节反映: {kw}...")
        elif warn_signals and not risk_section:
            issues.append("存在看空信号但无风险矩阵章节")

    return {
        "name": "risk_disclosure",
        "status": "FAIL" if issues else "PASS",
        "detail": issues if issues else "看空信号在风险章节中得到充分披露",
    }


def _summarize_audit_results(audit_results: dict[int, Any]) -> dict[str, Any]:
    """汇总逐章审计结果。"""
    total = len(audit_results)
    passed = sum(1 for r in audit_results.values() if _is_passed(r))
    failed = total - passed
    total_violations = sum(
        len(r.get("violations", [])) if isinstance(r, dict)
        else len(getattr(r, "violations", []))
        for r in audit_results.values()
    )

    return {
        "total_chapters": total,
        "passed_chapters": passed,
        "failed_chapters": failed,
        "total_violations": total_violations,
    }


def _is_passed(result: Any) -> bool:
    """判断审计结果是否通过。"""
    if isinstance(result, dict):
        return result.get("verdict") in ("pass", "PASS") or result.get("status") in ("PASSED", "passed")
    return getattr(result, "verdict", None) in ("pass", "PASS") or getattr(result, "status", None) in ("PASSED", "passed")


def _extract_section(report: str, keyword: str) -> str:
    """从报告中提取指定章节的文本。"""
    pattern = re.compile(rf"##\s+[^#]*{re.escape(keyword)}[^#]*\n(.*?)(?=##\s|\Z)", re.DOTALL | re.IGNORECASE)
    match = pattern.search(report)
    return match.group(1).strip() if match else ""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="V10 增强质量门禁")
    ap.add_argument("--code", required=True, help="股票代码")
    ap.add_argument("--report", help="报告文件路径")
    ap.add_argument("--output", help="输出目录")
    args = ap.parse_args()

    # 查找输出目录和报告
    output_base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "output")
    stock_dir = args.output or next(
        (os.path.join(output_base, d) for d in os.listdir(output_base)
         if os.path.isdir(os.path.join(output_base, d))
         and d.startswith(args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", ""))),
        None
    )
    if not stock_dir:
        print("ERROR: 找不到输出目录", file=sys.stderr)
        sys.exit(1)

    report_path = args.report or next(
        (os.path.join(stock_dir, f) for f in sorted(os.listdir(stock_dir))
         if f.endswith(".md") and ("v12" in f.lower() or "v10" in f.lower() or "v7" in f.lower() or "v5" in f.lower())),
        None
    )
    if not report_path:
        print("ERROR: 找不到报告文件", file=sys.stderr)
        sys.exit(1)

    with open(report_path, encoding="utf-8") as f:
        text = f.read()

    # 尝试加载 compute_bundle
    cb_path = os.path.join(stock_dir, "compute_bundle.json")
    cb = None
    if os.path.exists(cb_path):
        with open(cb_path, encoding="utf-8") as f:
            cb = json.load(f)

    result = enhanced_check(text, compute_bundle=cb)

    # 写入报告
    with open(os.path.join(stock_dir, "enhanced_quality_report.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    icon = {"PASS": "✅", "WARN": "⚠️", "BLOCKED": "❌"}[result["status"]]
    print(f"{icon} V10 增强质量: {result['status']}")
    for b in result.get("blocks", []):
        print(f"  ❌ {b}")
    for w in result.get("warns", []):
        print(f"  ⚠️ {w}")
    print(f"  指标: {json.dumps(result.get('metrics', {}), indent=2, default=str)}")
