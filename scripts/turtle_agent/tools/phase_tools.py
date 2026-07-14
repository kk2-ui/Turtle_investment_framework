"""全流程工具 — Phase 0/0.5/1/2/5。

对接已有 Python 模块，使 Agent 可以从 Phase 0 到 Phase 5 一站式完成分析。
使用 ``@tool`` 装饰器标注，支持 ``auto_discover`` 自动注册。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Any

_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_OUTPUT_DIR = os.path.join(_scripts_dir, "..", "output")


# ---------------------------------------------------------------------------
# Phase 0: 前置诊断
# ---------------------------------------------------------------------------

def run_pre_analysis(code: str = "", verbose: bool = False) -> dict[str, Any]:
    """运行前置诊断（Phase 0）。

    调用 ``pre_analysis_phase.py`` 分析股票的历史财务数据，
    生成 ``analysis_contract.json``（包含断点检测、周期分类、有效分析窗口）。

    Args:
        code: 股票代码（如 ``06668.HK``）。
        verbose: 是否详细输出。

    Returns:
        ``{contract_path, effective_years, cycle_type, breakpoints}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "pre_analysis_phase.py")
    args = [py, script, "--code", code]
    if verbose:
        args.append("--verbose")

    result = subprocess.run(args, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        return {"ok": False, "error": result.stderr.strip() or result.stdout.strip()}

    # 解析输出目录中的 contract
    contract_path = os.path.join(_OUTPUT_DIR, "analysis_contract.json")
    if not os.path.exists(contract_path):
        return {"ok": False, "error": f"contract 未生成: {contract_path}"}

    with open(contract_path, encoding="utf-8") as f:
        contract = json.load(f)

    return {
        "ok": True,
        "contract_path": contract_path,
        "effective_years": contract.get("effective_years", []),
        "cycle_type": contract.get("cycle_type", ""),
        "breakpoints": contract.get("breakpoints", []),
        "analysis_start": contract.get("analysis_start_year"),
        "output": result.stdout.strip()[-500:],
    }


# ---------------------------------------------------------------------------
# Phase 0.5: 年报下载
# ---------------------------------------------------------------------------

def download_annual_reports(
    code: str = "",
    report_type: str = "年报",
    save_dir: str = "",
) -> dict[str, Any]:
    """下载所有缺失年份的年报（Phase 0.5）。

    优先使用 ``--auto --all-years`` 批量模式（读取 analysis_contract.json），
    回退到逐年份下载。

    Args:
        code: 股票代码（如 ``06668``）。
        report_type: 财报类型（默认"年报"）。
        save_dir: 保存目录（合同约目录或其父级 output/）。

    Returns:
        ``{downloaded, failed, skipped, effective_years}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "download_report.py")

    if not save_dir:
        save_dir = _OUTPUT_DIR

    # 1) 尝试 --all-years 批量模式
    contract_path = os.path.join(save_dir, "analysis_contract.json")
    if os.path.exists(contract_path):
        args = [
            py, script,
            "--stock-code", code,
            "--report-type", report_type,
            "--save-dir", save_dir,
            "--auto", "--all-years",
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=300)
        stdout = result.stdout + result.stderr
        downloaded = stdout.count("status: SUCCESS")
        failed = stdout.count("status: FAILED")
        if downloaded > 0:
            return {
                "ok": True,
                "mode": "all_years",
                "downloaded": downloaded,
                "failed": failed,
                "output": stdout.strip()[-500:],
            }

    # 2) 回退：逐年份下载
    with open(contract_path, encoding="utf-8") as f:
        contract = json.load(f)
    years = contract.get("effective_years", [])
    downloaded, failed = 0, 0
    for yr in years:
        args = [
            py, script,
            "--stock-code", code,
            "--report-type", report_type,
            "--year", str(yr),
            "--save-dir", save_dir,
            "--auto",
        ]
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if "status: SUCCESS" in (result.stdout + result.stderr):
            downloaded += 1
        else:
            failed += 1

    return {
        "ok": downloaded > 0,
        "mode": "per_year",
        "downloaded": downloaded,
        "failed": failed,
        "effective_years": years,
    }


def check_report_completeness(
    code: str = "",
    report_type: str = "年报",
    save_dir: str = "",
) -> dict[str, Any]:
    """检查年报 PDF 完整性（Phase 0 门禁）。

    调用 ``download_report.py --check``。

    Args:
        code: 股票代码。
        report_type: 财报类型。
        save_dir: 检查目录。

    Returns:
        ``{complete, found, missing, effective_years}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "download_report.py")

    if not save_dir:
        save_dir = _OUTPUT_DIR

    args = [
        py, script, "--check",
        "--stock-code", code,
        "--report-type", report_type,
        "--save-dir", save_dir,
    ]
    result = subprocess.run(args, capture_output=True, text=True, timeout=30)

    complete = result.returncode == 0
    stdout = result.stdout + result.stderr
    # 尝试从 stdout 提取信息
    found_str = ""
    missing_str = ""
    for line in stdout.split("\n"):
        if "已下载:" in line:
            found_str = line.split(":", 1)[-1].strip()
        if "缺失:" in line:
            missing_str = line.split(":", 1)[-1].strip()

    return {
        "complete": complete,
        "found": found_str,
        "missing": missing_str,
        "output": stdout.strip()[-500:],
    }


# ---------------------------------------------------------------------------
# Phase 1: 定量计算
# ---------------------------------------------------------------------------

def compute_bundle_db(
    code: str = "",
    output_dir: str = "",
) -> dict[str, Any]:
    """运行定量计算（Phase 1）。

    调用 ``compute_bundle.py --from-db --contract``。

    Args:
        code: 股票代码（如 ``06668.HK``）。
        output_dir: 输出目录。

    Returns:
        ``{gg, ddm, ii, rejection, bundle_path}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "compute_bundle.py")

    if not output_dir:
        output_dir = _OUTPUT_DIR

    contract_path = os.path.join(output_dir, "analysis_contract.json")
    if not os.path.exists(contract_path):
        contract_path = os.path.join(_OUTPUT_DIR, "analysis_contract.json")

    bundle_path = os.path.join(output_dir, "compute_bundle.json")

    args = [
        py, script, "--from-db",
        "--code", code,
        "--contract", contract_path,
        "--output", bundle_path,
    ]
    # V12: 接入 Zone J 参数（mcapex_split_pct, non_recurring_items, total_discount_pct）
    zone_j_dir = output_dir
    if os.path.isdir(zone_j_dir) and any(
        os.path.exists(os.path.join(zone_j_dir, f))
        for f in ["capex_classification.json", "moat_assessment.json"]
    ):
        args.extend(["--zone-j", zone_j_dir])
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)

    if result.returncode != 0 or not os.path.exists(bundle_path):
        return {"ok": False, "error": result.stderr.strip() or "bundle not generated"}

    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)

    return {
        "ok": True,
        "bundle_path": bundle_path,
        "gg": bundle.get("gg", {}),
        "ddm": bundle.get("ddm", {}),
        "ii": bundle.get("ii"),
        "rf": bundle.get("rf"),
        "rejection": bundle.get("rejection", {}),
    }


# ---------------------------------------------------------------------------
# Phase 2: PDF 处理
# ---------------------------------------------------------------------------

def extract_pdf_sections(
    pdf_path: str = "",
    output_dir: str = "",
    year: int = 0,
) -> dict[str, Any]:
    """提取 PDF 章节导航（Phase 2）。

    调用 ``pdf_page_locator.py``。

    Args:
        pdf_path: PDF 文件路径。
        output_dir: 输出目录。
        year: 财年。

    Returns:
        ``{page_map_path, sections_count, sections}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "pdf_page_locator.py")

    if not pdf_path:
        return {"ok": False, "error": "需要 pdf_path 参数"}

    if not output_dir:
        output_dir = os.path.dirname(pdf_path)

    page_map_path = os.path.join(
        output_dir, f"page_map_{year}.json" if year else "page_map.json"
    )

    args = [py, script, "--pdf", pdf_path, "--output", page_map_path]
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)

    if result.returncode != 0 or not os.path.exists(page_map_path):
        return {"ok": False, "error": result.stderr.strip() or "page_map not generated"}

    with open(page_map_path, encoding="utf-8") as f:
        pm = json.load(f)

    sections = pm.get("sections", [])
    return {
        "ok": True,
        "page_map_path": page_map_path,
        "sections_count": len(sections),
        "sections": [
            {"label": s.get("label", ""), "pages": s.get("page_range", "")}
            for s in sections
        ],
    }


# ---------------------------------------------------------------------------
# Phase 5: 质量验证
# ---------------------------------------------------------------------------

def verify_report(
    report_path: str = "",
    output_dir: str = "",
) -> dict[str, Any]:
    """运行报告质量验证（Phase 5）。

    尝试调用 ``enhanced_quality_gate.py`` 和 ``quality_gate.py``。

    Args:
        report_path: 报告文件路径。
        output_dir: 股票输出目录。

    Returns:
        ``{passed, issues, warnings}``。
    """
    issues: list[str] = []
    warnings: list[str] = []

    # 1) enhanced_quality_gate
    if report_path and os.path.exists(report_path):
        try:
            from enhanced_quality_gate import enhanced_check

            with open(report_path, encoding="utf-8") as f:
                report_text = f.read()
            result = enhanced_check(report_text, {}, {})
            if result.get("status") == "BLOCKED":
                issues.append(f"enhanced_quality: BLOCKED - {result.get('metrics', {})}")
            elif result.get("status") == "WARN":
                warnings.append(f"enhanced_quality: WARN - {result.get('metrics', {})}")
        except ImportError:
            warnings.append("enhanced_quality_gate not available")
        except Exception as exc:
            warnings.append(f"enhanced_quality_gate error: {exc}")

    # 2) basic S1 check
    if report_path and os.path.exists(report_path):
        with open(report_path, encoding="utf-8") as f:
            content = f.read()
        placeholders = ["[?]", "[missing]", "[待填充]"]
        for ph in placeholders:
            if ph in content:
                issues.append(f"S1: 残留占位符 {ph} (x{content.count(ph)})")

    # 3) source citation density
    import re
    numbers = len(re.findall(r"\d+[\d,.]*\s*(?:%|百万|亿|千元|百万元)", content)) if 'content' in dir() else 0
    sources = len(re.findall(r"\[source:\s*[^\]]+\]", content)) if 'content' in dir() else 0
    if numbers > 20 and sources < numbers / 10:
        warnings.append(f"E1: 证据密度不足 ({sources} sources / {numbers} numbers)")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# 工具元数据（供 @tool 装饰器使用）
# ---------------------------------------------------------------------------

_RUN_PRE_ANALYSIS_META = {
    "name": "run_pre_analysis",
    "description": "运行前置诊断(Phase 0): 断点检测、周期分类、确定分析窗口 → analysis_contract.json",
    "parameters": {
        "code": {"type": "string", "description": "股票代码(如06668.HK)"},
        "verbose": {"type": "boolean", "description": "是否详细输出", "optional": True},
    },
}

_DOWNLOAD_REPORTS_META = {
    "name": "download_annual_reports",
    "description": "下载所有缺失年份的年报PDF(Phase 0.5)",
    "parameters": {
        "code": {"type": "string", "description": "股票代码"},
        "report_type": {"type": "string", "description": "财报类型(默认:年报)", "optional": True},
        "save_dir": {"type": "string", "description": "保存目录", "optional": True},
    },
}

_CHECK_COMPLETENESS_META = {
    "name": "check_report_completeness",
    "description": "检查年报PDF完整性(Phase 0门禁)",
    "parameters": {
        "code": {"type": "string", "description": "股票代码"},
        "report_type": {"type": "string", "description": "财报类型", "optional": True},
        "save_dir": {"type": "string", "description": "检查目录", "optional": True},
    },
}

_COMPUTE_BUNDLE_META = {
    "name": "compute_bundle_db",
    "description": "运行定量计算(Phase 1): GG/DDM/II/否决门 → compute_bundle.json",
    "parameters": {
        "code": {"type": "string", "description": "股票代码(如06668.HK)"},
        "output_dir": {"type": "string", "description": "输出目录", "optional": True},
    },
}

_EXTRACT_PDF_META = {
    "name": "extract_pdf_sections",
    "description": "提取PDF章节导航(Phase 2): 定位MDA/风险/治理/财报等章节页码范围",
    "parameters": {
        "pdf_path": {"type": "string", "description": "PDF文件路径"},
        "output_dir": {"type": "string", "description": "输出目录", "optional": True},
        "year": {"type": "integer", "description": "财年", "optional": True},
    },
}

_VERIFY_REPORT_META = {
    "name": "verify_report",
    "description": "运行报告质量验证(Phase 5): S1占位符/E1证据密度/enhanced_quality_gate",
    "parameters": {
        "report_path": {"type": "string", "description": "报告文件路径", "optional": True},
        "output_dir": {"type": "string", "description": "股票输出目录", "optional": True},
    },
}


# 给函数打上 _tool_meta 标记（供 auto_discover 使用）
for _func, _meta in [
    (run_pre_analysis, _RUN_PRE_ANALYSIS_META),
    (download_annual_reports, _DOWNLOAD_REPORTS_META),
    (check_report_completeness, _CHECK_COMPLETENESS_META),
    (compute_bundle_db, _COMPUTE_BUNDLE_META),
    (extract_pdf_sections, _EXTRACT_PDF_META),
    (verify_report, _VERIFY_REPORT_META),
]:
    _func._tool_meta = _meta  # type: ignore[attr-defined]
