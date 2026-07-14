"""写作工具集 — 写章节、读章节、审计、组装报告。

对接现有 Python 模块：
- ``audit_rules.py`` — S1/E1/C1/C2/S2 审计规则
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


# ---------------------------------------------------------------------------
# 写作工具
# ---------------------------------------------------------------------------


def write_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
    title: str = "",
    content: str = "",
) -> dict[str, Any]:
    """写入单章内容到文件。

    自动运行可编程审计（S1占位符 / E1证据密度 / C2禁止项），
    将审计结果附带在返回值中。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号（1-9）。
        title: 章节标题。
        content: 章节 Markdown 内容。

    Returns:
        ``{path, char_count, audit: {violations}}``。
    """
    os.makedirs(output_dir, exist_ok=True)
    filename = f"_ch{chapter_index:02d}.md"
    path = os.path.join(output_dir, filename)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

    # 自动审计
    audit = _audit_content(content, chapter_index=chapter_index)

    # V12 P2: 执行追踪（每章指标）
    try:
        from scripts.execution_tracker import ExecutionTracker
        import json as _json
        tracker_file = os.path.join(output_dir, "_tracker.json")
        if os.path.exists(tracker_file):
            tracker = ExecutionTracker.from_file(tracker_file) if hasattr(ExecutionTracker, 'from_file') else ExecutionTracker()
        else:
            tracker = ExecutionTracker()
        tracker.record(chapter_index=chapter_index, title=title, char_count=len(content),
                       passed=audit.get("passed", False), violations=audit.get("error_count", 0))
        with open(tracker_file, 'w') as f:
            _json.dump(tracker.summary() if hasattr(tracker, 'summary') else {}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    return {
        "path": path,
        "chapter_index": chapter_index,
        "title": title,
        "char_count": len(content),
        "audit": audit,
    }


def read_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
) -> dict[str, Any]:
    """读取已写入的章节内容。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号（1-9）。

    Returns:
        ``{chapter_index, title, content, char_count}``。
    """
    filename = f"_ch{chapter_index:02d}.md"
    path = os.path.join(output_dir, filename)

    if not os.path.exists(path):
        return {"chapter_index": chapter_index, "error": f"章节 {filename} 不存在", "content": ""}

    with open(path, encoding="utf-8") as f:
        content = f.read()

    # 提取标题（匹配 # 或 ## 开头）
    title = ""
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("## "):
            title = stripped[2:].strip()
            break
        elif stripped.startswith("## "):
            title = stripped[3:].strip()
            if not title:
                continue
            break

    return {
        "chapter_index": chapter_index,
        "title": title,
        "content": content,
        "char_count": len(content),
    }


def assemble_report(
    output_dir: str = ".",
    company_name: str = "",
    ts_code: str = "",
) -> dict[str, Any]:
    """组装最终报告。

    拼接所有已写章节，添加来源清单，写入完整报告文件。

    Args:
        output_dir: 股票输出目录。
        company_name: 公司全称。
        ts_code: 股票代码。

    Returns:
        ``{path, chapter_count, char_count}``。
    """
    chapter_files = sorted(
        f for f in os.listdir(output_dir)
        if f.startswith("_ch") and f.endswith(".md")
    )

    header_parts: list[str] = [
        f"# {company_name} ({ts_code}) 龟龟策略分析报告",
        "",
        f"> 由 TurtleAgent V12 单 Agent 工具循环生成 | {len(chapter_files)} 章",
        "",
    ]

    body_parts: list[str] = []
    for cf in chapter_files:
        path = os.path.join(output_dir, cf)
        with open(path, encoding="utf-8") as f:
            body_parts.append(f.read().strip())

    # 组装正文（不含来源清单）→ 提取来源 → 追加来源清单
    body_text = "\n\n---\n\n".join(body_parts)
    temp_text = "\n".join(header_parts) + body_text

    # V12: 来源清单 — 从各章证据与出处聚合，去重
    from scripts.source_list_builder import build_source_list
    source_section = build_source_list(temp_text)
    if not source_section.strip() or len(source_section.strip()) < 50:
        # Fallback: 扫描各章的"证据与出处"表格，提取文件名
        seen = set()
        for cf in chapter_files:
            path = os.path.join(output_dir, cf)
            with open(path, encoding="utf-8") as f:
                import re as _re
                sources = _re.findall(r'\[source:\s*([^\]→]+)', f.read())
                seen.update(s.strip() for s in sources if s.strip())
        if seen:
            source_section = "## 来源清单\n\n" + "\n".join(f"- {s}" for s in sorted(seen))
        else:
            source_section = "## 来源清单\n\n各章「证据与出处」小节已列出详细来源。"

    report_text = "\n".join(header_parts) + body_text + "\n\n---\n\n" + source_section

    code_short = ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    report_path = os.path.join(output_dir, f"{code_short}_分析报告_v12.md")

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_text)

    # V12: 运行质量门禁
    quality_result = _run_quality_checks(report_text, output_dir)

    return {
        "path": report_path,
        "chapter_count": len(chapter_files),
        "char_count": len(report_text),
        "quality": quality_result,
    }


# ---------------------------------------------------------------------------
# 审计
# ---------------------------------------------------------------------------


def audit_chapter(
    output_dir: str = ".",
    chapter_index: int = 0,
) -> dict[str, Any]:
    """审计指定章节（S1/E1/C1/C2/S2）。

    读入章节文件，运行可编程审计规则，返回违规列表。

    Args:
        output_dir: 股票输出目录。
        chapter_index: 章序号。

    Returns:
        ``{violations: [...], passed: bool}``。
    """
    filename = f"_ch{chapter_index:02d}.md"
    path = os.path.join(output_dir, filename)

    if not os.path.exists(path):
        return {"violations": [{"rule": "NONE", "desc": "章节不存在"}], "passed": False}

    with open(path, encoding="utf-8") as f:
        content = f.read()

    audit = _audit_content(content)
    audit["path"] = path
    audit["chapter_index"] = chapter_index
    return audit


def _audit_content(content: str, chapter_index: int = 0) -> dict[str, Any]:
    """对内容运行可编程审计规则 — V12 使用 Dayu 移植的完整审计系统。

    对接 ``audit_rules.run_audit()``。
    """
    from scripts.audit_rules import run_audit

    result = run_audit(content, skeleton="", chapter_index=chapter_index)

    violations = [
        {"rule": v.rule_code, "severity": v.severity, "desc": v.description}
        for v in result.violations
    ]
    errors = [v for v in violations if v["severity"] == "error"]
    warns = [v for v in violations if v["severity"] == "warn"]

    return {
        "violations": violations,
        "error_count": len(errors),
        "warn_count": len(warns),
        "passed": result.verdict.value == "pass",
        "verdict": result.verdict.value,
        "repair_plan": result.repair_plan,
    }


def _run_quality_checks(report_text: str, output_dir: str) -> dict[str, Any]:
    """V12: 运行 quality_gate + evidence_citation 后置检查。"""
    result: dict[str, Any] = {"passed": True, "issues": [], "warnings": []}

    # 1. 基础质量门禁
    try:
        from scripts.quality_gate import check as quality_check
        qg = quality_check(report_text)
        if not qg.get("passed"):
            result["passed"] = False
            result["issues"].extend(qg.get("issues", []))
        result["warnings"].extend(qg.get("warnings", []))
    except Exception as e:
        result["warnings"].append(f"quality_gate error: {e}")

    # 2. 证据锚点验证
    try:
        from scripts.evidence_citation import validate_evidence_coverage
        cov = validate_evidence_coverage(report_text, output_dir)
        if cov.get("coverage_ratio", 1.0) < 0.3:
            result["issues"].append(f"证据覆盖率过低: {cov.get('coverage_ratio', 0):.1%} < 30%")
        result["evidence_coverage"] = cov
    except Exception as e:
        result["warnings"].append(f"evidence_citation error: {e}")

    # 3. enhanced_quality_gate: 结论一致性 + 风险披露 + Token效率
    try:
        from scripts.enhanced_quality_gate import enhanced_check
        cb_path = os.path.join(output_dir, "compute_bundle.json")
        cb = None
        if os.path.exists(cb_path):
            import json
            with open(cb_path) as f:
                cb = json.load(f)
        eq = enhanced_check(report_text, cb)
        if eq.get("issues"):
            result["passed"] = False
            result["issues"].extend(eq["issues"])
        result["warnings"].extend(eq.get("warnings", []))
    except Exception as e:
        result["warnings"].append(f"enhanced_quality_gate error: {e}")

    # 4. P2: 数据缺口扫描
    try:
        from scripts.data_gap_scanner import scan_report
        gaps = scan_report(report_text)
        if gaps.get("gaps"):
            result["warnings"].append(f"数据缺口: {len(gaps['gaps'])} 处 ⚠️ 标记")
            result["data_gaps"] = gaps
    except Exception as e:
        result["warnings"].append(f"data_gap_scanner error: {e}")

    # 5. V12 Content Audit：程序化内容深度检查（对标海螺报告）
    for ch_file in sorted(f for f in os.listdir(output_dir) if f.startswith("_ch") and f.endswith(".md")):
        try:
            ch_text = open(os.path.join(output_dir, ch_file)).read()
            ch_idx = int(ch_file.replace("_ch", "").replace(".md", ""))
            # 5a. M fallback 检查（GG 章 ~ch11）
            if ch_idx in (11, 12) and ("fallback" in ch_text.lower() or "M=0.7" in ch_text or "行业默认" in ch_text):
                if "M_adjusted" not in ch_text and "校正" not in ch_text:
                    result["warnings"].append(f"Ch{ch_idx}: M 值使用了 fallback/行业默认，请同时展示 GG_adjusted（用实际分红率校正）")
            # 5b. 关联交易量化检查（治理章 ~ch09）
            if ch_idx in (8, 9) and "关联交易" in ch_text:
                if not re.search(r"\d+[\.\d]*\s*(百万元|亿元|M|亿|万)", ch_text):
                    result["warnings"].append(f"Ch{ch_idx}: 关联交易分析缺具体金额，请用 get_financial_statement 补充定量数据")
            # 5c. GG/DDM 前提差异（决策章 ~ch14）
            if ch_idx in (13, 14) and "一致" in ch_text:
                if "隐含 PE" not in ch_text and "估值逻辑" not in ch_text and "前提" not in ch_text:
                    result["warnings"].append(f"Ch{ch_idx}: GG 和 DDM 估值逻辑前提不同（GG看利润/DDM看分红），请分析两者隐含假设差异")
        except Exception:
            pass

    # 6. 行数检查
    lines = [l for l in report_text.split("\n") if l.strip()]
    if len(lines) < 800:
        result["passed"] = False
        result["issues"].append(f"报告过短: {len(lines)} 行 < 800 行最低要求")
    elif len(lines) < 2000:
        result["warnings"].append(f"报告偏短: {len(lines)} 行 < 2000 行（建议≥3000行/300KB）")

    return result


def _collect_sources(output_dir: str) -> list[str]:
    """从所有章节文件中收集 [source: X] 引用。"""
    sources: set[str] = set()
    for f in sorted(os.listdir(output_dir)):
        if f.startswith("_ch") and f.endswith(".md"):
            path = os.path.join(output_dir, f)
            with open(path, encoding="utf-8") as fh:
                sources.update(
                    re.findall(r"\[source:\s*([^\]]+)\]", fh.read())
                )
    return sorted(sources)


write_chapter._tool_meta = {"name": "write_chapter", "description": "写入单章内容(含自动审计S1/E1/C2)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号1-9"}, "title": {"type": "string", "description": "章节标题"}, "content": {"type": "string", "description": "Markdown章节内容"}}}  # type: ignore[attr-defined]
read_chapter._tool_meta = {"name": "read_chapter", "description": "读取已写章节内容", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号"}}}  # type: ignore[attr-defined]
audit_chapter._tool_meta = {"name": "audit_chapter", "description": "审计指定章节(S1占位符/E1证据/C2禁止项)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "chapter_index": {"type": "integer", "description": "章序号"}}}  # type: ignore[attr-defined]
assemble_report._tool_meta = {"name": "assemble_report", "description": "组装最终报告(拼接所有章节+来源清单)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "company_name": {"type": "string", "description": "公司全称"}, "ts_code": {"type": "string", "description": "股票代码"}}}  # type: ignore[attr-defined]
