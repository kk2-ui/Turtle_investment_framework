"""全流程工具 — Phase 0/0.5/1/2/5。

对接已有 Python 模块，使 Agent 可以从 Phase 0 到 Phase 5 一站式完成分析。
使用 ``@tool`` 装饰器标注，支持 ``auto_discover`` 自动注册。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any

_scripts_dir = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_FRAMEWORK_DIR = os.path.normpath(os.path.join(_scripts_dir, ".."))
_OUTPUT_DIR = os.path.join(_FRAMEWORK_DIR, "output")



_VALID_TRACKING_REPORT_TYPES = {"annual", "q1", "h1", "q3"}


def _normalize_tracking_report_type(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in _VALID_TRACKING_REPORT_TYPES else "annual"


def _derive_tracking_fiscal_year(period_end: str) -> int | None:
    text = str(period_end or "").strip()
    if len(text) >= 4 and text[:4].isdigit():
        return int(text[:4])
    return None


def _default_tracking_period_end(report_type: str, fiscal_year: int | None) -> str:
    if not fiscal_year:
        return ""
    mapping = {
        "annual": f"{fiscal_year}-12-31",
        "q1": f"{fiscal_year}-03-31",
        "h1": f"{fiscal_year}-06-30",
        "q3": f"{fiscal_year}-09-30",
    }
    return mapping.get(report_type, "")


def _apply_tracking_metadata(
    contract: dict[str, Any],
    *,
    report_type: str = "annual",
    fiscal_year: int | None = None,
    period_end: str = "",
) -> dict[str, Any]:
    report_type = _normalize_tracking_report_type(report_type)
    period_end = str(period_end or "").strip()[:10]
    if fiscal_year in (None, ""):
        years = contract.get("effective_years") or []
        if isinstance(years, list):
            numeric_years = [int(y) for y in years if str(y).isdigit()]
            if numeric_years:
                fiscal_year = max(numeric_years)
    if fiscal_year in (None, ""):
        fiscal_year = _derive_tracking_fiscal_year(period_end)
    if fiscal_year not in (None, ""):
        fiscal_year = int(fiscal_year)
    if not period_end:
        period_end = _default_tracking_period_end(report_type, fiscal_year)

    tracking = {
        "report_type": report_type,
        "fiscal_year": fiscal_year,
        "period_end": period_end or None,
        "metric_comparison_basis": "unavailable" if report_type == "annual" else "yoy",
        "change_classification": "",
        "comparison_summary": "",
    }
    for key, value in tracking.items():
        contract[key] = value
    contract["tracking"] = dict(tracking)
    run_meta = contract.get("run_meta")
    if not isinstance(run_meta, dict):
        run_meta = {}
        contract["run_meta"] = run_meta
    run_meta.update(tracking)
    return tracking


# ---------------------------------------------------------------------------
# Phase 0: 前置诊断
# ---------------------------------------------------------------------------

def run_pre_analysis(
    code: str = "",
    verbose: bool = False,
    output_dir: str = "",
    report_type: str = "annual",
    fiscal_year: int | None = None,
    period_end: str = "",
) -> dict[str, Any]:
    """运行前置诊断（Phase 0）。直接 import + 保存 contract。"""
    import json as _json
    from pre_analysis_phase import build_analysis_contract
    try:
        contract = build_analysis_contract(code)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    if not contract:
        return {"ok": False, "error": "contract 为空"}
    if "error" in contract:
        return {"ok": False, "error": contract["error"]}

    tracking = _apply_tracking_metadata(
        contract,
        report_type=report_type,
        fiscal_year=fiscal_year,
        period_end=period_end,
    )

    # 使用传入的 output_dir，否则回退到自发现
    code_short = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
    if output_dir:
        stock_dir = output_dir
    else:
        stock_dir = ""
        if os.path.isdir(_OUTPUT_DIR):
            for d in os.listdir(_OUTPUT_DIR):
                dpath = os.path.join(_OUTPUT_DIR, d)
                if os.path.isdir(dpath) and d.startswith(code_short):
                    stock_dir = dpath; break
        if not stock_dir:
            stock_dir = os.path.join(_OUTPUT_DIR, f"{code_short}_分析")
    os.makedirs(stock_dir, exist_ok=True)

    # 保存 contract
    contract_path = os.path.join(stock_dir, "analysis_contract.json")
    with open(contract_path, "w", encoding="utf-8") as f:
        _json.dump(contract, f, ensure_ascii=False, indent=2)

    return {
        "ok": True,
        "contract_path": contract_path,
        "effective_years": contract.get("effective_years", []),
        "cycle_type": contract.get("cycle_type", ""),
        "breakpoints": contract.get("breakpoints", []),
        "analysis_start": contract.get("analysis_start_year"),
        "report_type": tracking.get("report_type"),
        "fiscal_year": tracking.get("fiscal_year"),
        "period_end": tracking.get("period_end"),
        "metric_comparison_basis": tracking.get("metric_comparison_basis"),
    }


# ---------------------------------------------------------------------------
# Phase 0.5: 年报下载
# ---------------------------------------------------------------------------

def download_annual_reports(
    code: str = "",
    report_type: str = "年报",
    save_dir: str = "",
    missing_years: str = "",
) -> dict[str, Any]:
    """下载缺失年份的年报（Phase 0.5）。仅下载指定的缺失年份。

    Args:
        code: 股票代码（如 ``06668``）。
        report_type: 财报类型（默认"年报"）。
        save_dir: 保存目录。
        missing_years: 逗号分隔的缺失年份（如 "2021,2023"），由 check_report_completeness 返回。

    Returns:
        ``{downloaded, failed, skipped, effective_years}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "download_report.py")

    if not save_dir:
        save_dir = _OUTPUT_DIR

    # 解析缺失年份（兼容 "2019,2020" 和 "[2019, 2020]" 两种格式）
    if missing_years:
        clean = missing_years.replace("[", "").replace("]", "").replace(" ", "")
        years = [int(y) for y in clean.split(",") if y.strip().isdigit()]
    else:
        # 回退：读取 contract 的所有年份（兼容旧调用）
        contract_path = os.path.join(save_dir, "analysis_contract.json")
        if os.path.exists(contract_path):
            with open(contract_path, encoding="utf-8") as f:
                contract = json.load(f)
            years = contract.get("effective_years", [])
        else:
            years = []

    pre_ipo_skipped: list[int] = []

    if not years:
        return {"ok": True, "mode": "none_missing", "downloaded": 0, "message": "无缺失年份"}

    # V12.18: 跳过上市前的年份（不可能有年报）
    contract_path = os.path.join(save_dir, "analysis_contract.json")
    listing_year = 0
    if os.path.exists(contract_path):
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        listing_year = contract.get("listing_year", 0)
    if listing_year:
        pre_ipo_skipped = [y for y in years if y < listing_year]
        years = [y for y in years if y >= listing_year]

    # 过滤后 years 为空 → 全部是 IPO 前年份
    if not years:
        return {"ok": True, "mode": "pre_ipo_only", "downloaded": 0,
                "pre_ipo_skipped": pre_ipo_skipped,
                "message": f"所有缺失年份均为IPO前({pre_ipo_skipped})，无需下载"}

    # 只下载缺失年份（逐年份，已存在的跳过）
    downloaded, failed, skipped = 0, 0, 0
    errors: list[str] = []
    for yr in years:
        # 检查是否已存在
        existing = [
            f for f in os.listdir(save_dir)
            if f.endswith(".pdf") and str(yr) in f and "年报" in f
        ] if os.path.isdir(save_dir) else []
        if existing:
            skipped += 1
            continue
        args = [
            py, script,
            "--stock-code", code,
            "--report-type", report_type,
            "--year", str(yr),
            "--save-dir", save_dir,
            "--auto",
        ]
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=120)
            combined = result.stdout + result.stderr
            # 检查 subprocess 是否报告成功
            subprocess_ok = "status: SUCCESS" in combined
            # 实际验证文件是否真的写入了
            fname = f"{code}_{yr}_{report_type}.pdf"
            fpath = os.path.join(save_dir, fname)
            file_exists = os.path.exists(fpath) and os.path.getsize(fpath) > 100000
            if file_exists:
                downloaded += 1
            elif subprocess_ok:
                # subprocess说成功但文件不存在——可能是路径问题
                failed += 1
                errors.append(f"FY{yr}: subprocess报告成功但文件不存在({fpath})")
            else:
                failed += 1
                err_lines = [l for l in combined.split("\n") if "Error" in l or "error" in l.lower()]
                errors.append(f"FY{yr}: {err_lines[0] if err_lines else str(result.returncode)}")
        except subprocess.TimeoutExpired:
            failed += 1
            errors.append(f"FY{yr}: 下载超时(>120s)")
        except Exception as e:
            failed += 1
            errors.append(f"FY{yr}: {e}")

    return {
        "ok": downloaded > 0 or skipped > 0,
        "mode": "missing_only",
        "downloaded": downloaded,
        "failed": failed,
        "skipped": skipped,
        "years": years,
        "pre_ipo_skipped": pre_ipo_skipped if pre_ipo_skipped else None,
        "errors": errors if errors else None,
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
    if not save_dir:
        save_dir = _OUTPUT_DIR

    # 从 analysis_contract 获取 effective_years
    contract_path = os.path.join(save_dir, "analysis_contract.json")
    years = []
    if os.path.exists(contract_path):
        with open(contract_path, encoding="utf-8") as f:
            contract = json.load(f)
        years = contract.get("effective_years", [])

    # 直接检查文件（兼容 00816_2022_年报.pdf 和 00816.HK_2022_年报.pdf 两种命名）
    found, missing = [], []
    if os.path.isdir(save_dir):
        existing_files = os.listdir(save_dir)
        for yr in years:
            matched = any(
                f.endswith(".pdf") and str(yr) in f and report_type in f
                for f in existing_files
            )
            if matched: found.append(yr)
            else: missing.append(yr)

    complete = len(missing) == 0

    return {
        "complete": complete,
        "found": str(found),
        "missing": str(missing) if missing else "",
        "effective_years": years,
    }


# ---------------------------------------------------------------------------
# Phase 1: 定量计算
# ---------------------------------------------------------------------------

def compute_bundle_db(
    code: str = "",
    output_dir: str = "",
    data_source: str = "",
    price_source: str = "",
) -> dict[str, Any]:
    """运行定量计算（Phase 1）。

    调用 ``compute_bundle.py --from-db --contract``。

    V12.19: 自动处理卫星上市标的（data_source_code）。
    当 stocks 表中该 code 有 data_source_code 指向母标的时，
    自动链接母标的 zone_j/pdf/contract 文件，使用母标财务数据 + 卫星标的价格。

    Args:
        code: 股票代码（如 ``06668.HK``）。
        output_dir: 输出目录。
        data_source: V12.19 卫星标的母标代码（如 ``600295.SH``）。
        price_source: 交易价格来源代码（如 ``900936.SH``）。

    Returns:
        ``{gg, ddm, ii, rejection, bundle_path, trading_note?}``。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "compute_bundle.py")

    if not output_dir:
        output_dir = _OUTPUT_DIR

    # ── V12.19: Satellite listing auto-setup ──
    trading_note = None
    parent_code = None
    try:
        db_path = os.path.join(_scripts_dir, "..", "stock_analysis.db")
        if os.path.exists(db_path):
            import sqlite3
            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT data_source_code, currency, name_cn FROM stocks WHERE ts_code=?",
                (code,)
            ).fetchone()
            conn.close()
            if row and row[0]:
                parent_code = row[0]
                currency = row[1] or "RMB"
                name = row[2] or code
                # Find parent output directory
                parent_base = parent_code.split(".")[0]
                parent_dir = None
                if os.path.isdir(_OUTPUT_DIR):
                    for entry in os.listdir(_OUTPUT_DIR):
                        if entry.startswith(parent_base) and os.path.isdir(os.path.join(_OUTPUT_DIR, entry)):
                            # Check it has compute_bundle.json (is an analyzed parent)
                            if os.path.exists(os.path.join(_OUTPUT_DIR, entry, "compute_bundle.json")):
                                parent_dir = os.path.join(_OUTPUT_DIR, entry)
                                break
                if parent_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    # Symlink zone_j files
                    for f in ["moat_assessment.json", "capex_classification.json",
                              "governance_tension.json", "earnings_quality.json",
                              "data_discount.json"]:
                        src = os.path.join(parent_dir, f)
                        dst = os.path.join(output_dir, f)
                        if os.path.exists(src) and not os.path.exists(dst):
                            os.symlink(os.path.relpath(src, output_dir), dst)
                    # Symlink Zone B master files (same company qualitative analysis)
                    for f in ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json",
                              "industry_context.json", "financial_trends.json"]:
                        src = os.path.join(parent_dir, f)
                        dst = os.path.join(output_dir, f)
                        if os.path.exists(src) and not os.path.exists(dst):
                            os.symlink(os.path.relpath(src, output_dir), dst)
                    # Symlink pdf_sections + zone_b partials
                    for f in os.listdir(parent_dir):
                        if f.startswith("pdf_sections_") or f.startswith("zone_b_"):
                            src = os.path.join(parent_dir, f)
                            dst = os.path.join(output_dir, f)
                            if os.path.exists(src) and not os.path.exists(dst):
                                os.symlink(os.path.relpath(src, output_dir), dst)
                    # Copy & fix contract
                    parent_contract = os.path.join(parent_dir, "analysis_contract.json")
                    target_contract = os.path.join(output_dir, "analysis_contract.json")
                    if os.path.exists(parent_contract) and not os.path.exists(target_contract):
                        import shutil
                        shutil.copy2(parent_contract, target_contract)
                        with open(target_contract) as f:
                            c = json.load(f)
                        c["ts_code"] = code
                        with open(target_contract, "w") as f:
                            json.dump(c, f, ensure_ascii=False, indent=2)
                    trading_note = (
                        f"⚠️ 卫星上市标的：{name} ({code})，"
                        f"财务数据来自母标的 {parent_code}，"
                        f"价格和市值按 {code} ({currency}) 独立计算。"
                        f"GG分母使用 {code} 市值，DDM/仓位按 {code} 价格。"
                    )
                    print(f"  🔗 {code}: 卫星标的 → 母标 {parent_code}，已自动链接 {parent_dir}")
    except Exception as e:
        print(f"  ⚠️ 卫星标的自动设置失败: {e}")

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
    # Current-run market truth comes from the mature standalone Niangao system.
    # Turtle reads its database only through a validated snapshot and never
    # duplicates quote-provider logic or writes back to Niangao.
    try:
        try:
            from scripts.niangao_market_bridge import write_snapshot
        except ModuleNotFoundError:
            from niangao_market_bridge import write_snapshot
        quote_code = price_source or code
        snapshot = write_snapshot(output_dir, quote_code, max_age_minutes=60)
        args.extend(["--market-snapshot", os.path.join(output_dir, "market_snapshot.json")])
    except ValueError as exc:
        # A missing current quote withdraws price/valuation actions; it does
        # not erase the company's operating evidence.  Persist an explicit
        # unresolved bundle so Phase 1.5, PDF extraction and synthesis can
        # continue without inventing a stale or fallback price.
        unresolved_reason = f"fresh_niangao_market_required:{exc}"
        unresolved_bundle = {
            "meta": {"code": code, "quantitative_status": "UNRESOLVED_CURRENT_MARKET"},
            "market": {"status": "UNAVAILABLE", "reason": unresolved_reason},
            "factor3": {
                "gg": {"pessimistic": None, "base": None, "optimistic": None},
                "gg_discounted": {"pessimistic": None, "base": None, "optimistic": None},
                "gg_unavailable": True,
                "gg_unavailable_reason": "current market capitalization unavailable",
            },
            "factor4": {
                "valuation_status": "UNRESOLVED_VALUATION",
                "valuation_unresolved_reason": unresolved_reason,
                "position": {"status": "UNRESOLVED_VALUATION", "recommended": None},
                "verdict": {
                    "final": "UNRESOLVED_VALUATION",
                    "framework": "企业判断继续；估值与当前价格动作暂不承保",
                },
            },
            "rejection_summary": {
                "valuation": "unresolved",
                "enterprise_judgment": "continue",
            },
        }
        os.makedirs(output_dir, exist_ok=True)
        with open(bundle_path, "w", encoding="utf-8") as f:
            json.dump(unresolved_bundle, f, indent=2, ensure_ascii=False)
        return {
            "ok": True,
            "degraded": True,
            "quantitative_status": "UNRESOLVED_CURRENT_MARKET",
            "bundle_path": bundle_path,
            "gg": unresolved_bundle["factor3"]["gg"],
            "gg_discounted": unresolved_bundle["factor3"]["gg_discounted"],
            "ddm": {"fair_value": None},
            "ii": None,
            "rf": None,
            "rejection": unresolved_bundle["rejection_summary"],
            "error": unresolved_reason,
        }
    # V12.19: 卫星标的 — 传递 data_source
    if data_source:
        args.extend(["--data-source", data_source])
    if price_source:
        args.extend(["--price-source", price_source])
    # V12: 接入 Zone J 参数（mcapex_split_pct, non_recurring_items, total_discount_pct）
    zone_j_dir = output_dir
    if os.path.isdir(zone_j_dir) and any(
        os.path.exists(os.path.join(zone_j_dir, f))
        for f in ["capex_classification.json", "moat_assessment.json"]
    ):
        args.extend(["--zone-j", zone_j_dir])
    # Never silently recycle a stale bundle price.  Historical/PIT runs use a
    # separate cutoff-bound market input and must not call this current quote path.
    result = subprocess.run(args, capture_output=True, text=True, timeout=120)

    if not os.path.exists(bundle_path):
        return {"ok": False, "error": result.stderr.strip() or "bundle not generated"}
    # DEGRADED 等 warning 不阻止分析——只要 compute_bundle.json 已生成就算 ok
    if result.returncode != 0:
        print(f"  ⚠️ compute_bundle warning (non-zero exit), but bundle exists — continuing")

    with open(bundle_path, encoding="utf-8") as f:
        bundle = json.load(f)

    result_dict = {
        "ok": True,
        "bundle_path": bundle_path,
        "gg": bundle.get("factor3", {}).get("gg", {}),
        "ddm": {"fair_value": bundle.get("factor4", {}).get("ddm_v_native", bundle.get("factor4", {}).get("ddm_v_hkd", "?"))},
        "gg_discounted": bundle.get("factor3", {}).get("gg_discounted", {}),
        "ii": bundle.get("ii"),
        "rf": bundle.get("rf"),
        "rejection": bundle.get("rejection_summary", {}),
    }
    if trading_note:
        result_dict["trading_note"] = trading_note
        result_dict["data_source_code"] = parent_code

    return result_dict


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
    # Handle both dict format {label: [pages]} and list format [{label, page_range}]
    if isinstance(sections, dict):
        section_list = [
            {"label": k, "pages": f"{v[0]}-{v[-1]}" if v else ""}
            for k, v in sections.items()
        ]
    else:
        section_list = [
            {"label": s.get("label", ""), "pages": s.get("page_range", "")}
            for s in sections
        ]
    return {
        "ok": True,
        "page_map_path": page_map_path,
        "sections_count": len(section_list),
        "sections": section_list,
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

    # Auto-detect: if report_path is a directory, find the report inside
    if report_path and os.path.isdir(report_path):
        for f in sorted(os.listdir(report_path), reverse=True):
            if f.endswith("_分析报告_v12.md"):
                report_path = os.path.join(report_path, f)
                break
    # If still a directory or not found, try output_dir
    if (not report_path or os.path.isdir(report_path)) and output_dir:
        for f in sorted(os.listdir(output_dir), reverse=True):
            if f.endswith("_分析报告_v12.md"):
                report_path = os.path.join(output_dir, f)
                break

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

def build_financial_trends(
    code: str = "",
    output_dir: str = "",
) -> dict[str, Any]:
    """生成财务趋势数据（Phase 1.5）。

    从 compute_bundle.json 提取关键指标的多年序列。
    """
    import json as _json
    bundle_path = os.path.join(output_dir, "compute_bundle.json")
    if not os.path.exists(bundle_path):
        return {"ok": False, "error": "compute_bundle.json 不存在"}

    with open(bundle_path, encoding="utf-8") as f:
        cb = _json.load(f)

    trends = {
        "_source": "compute_bundle.json",
        "factor2": cb.get("factor2", {}),
        "factor3": {"gg": cb.get("factor3", {}).get("gg", {}), "aa": cb.get("factor3", {}).get("aa", {})},
        "factor4": {"ddm": cb.get("factor4", {}).get("ddm", {})},
        "market": cb.get("market", {}),
    }

    # Zone J 增强：从 DB 查询 Capex/D&A/固定资产序列（capex agent 关键输入）
    try:
        import sqlite3 as _sqlite3
        db_path = os.path.join(_FRAMEWORK_DIR, "stock_analysis.db")
        if os.path.exists(db_path):
            conn = _sqlite3.connect(db_path)
            conn.row_factory = _sqlite3.Row
            rows = conn.execute("""
                SELECT fiscal_year, c_pay_acq_const_fiolta, d_a
                FROM annual_financials
                WHERE ts_code=? AND report_type='annual'
                ORDER BY fiscal_year
            """, (code,)).fetchall()
            conn.close()
            if rows:
                trends["capex_by_year"] = {str(r["fiscal_year"]): r["c_pay_acq_const_fiolta"] for r in rows}
                trends["d_a_by_year"] = {str(r["fiscal_year"]): r["d_a"] for r in rows}
                # Capex/D&A 比率：>1 扩张，<0.8 收缩
                recent = [r for r in rows if r["fiscal_year"] and int(r["fiscal_year"]) >= 2021]
                if recent:
                    avg_capex = sum(abs(r["c_pay_acq_const_fiolta"] or 0) for r in recent) / len(recent)
                    avg_da = sum(r["d_a"] or 0 for r in recent) / len(recent)
                    trends["capex_da_ratio"] = round(avg_capex / max(avg_da, 1), 2) if avg_da > 0 else None
                    trends["avg_capex_5y"] = round(avg_capex, 2)
                    trends["avg_da_5y"] = round(avg_da, 2)
    except Exception as exc:
        print(f"  ⚠️ financial_trends DB 查询失败: {exc}")

    out_path = os.path.join(output_dir, "financial_trends.json")
    with open(out_path, "w", encoding="utf-8") as f:
        _json.dump(trends, f, indent=2, ensure_ascii=False, default=str)

    return {"ok": True, "path": out_path}


def _company_identity_matches(value: Any, code: str) -> bool:
    left = str(value or "").strip().upper()
    right = str(code or "").strip().upper()
    if not left or not right:
        return False
    if left == right:
        return True
    left_digits = "".join(char for char in left if char.isdigit())
    right_digits = "".join(char for char in right if char.isdigit())
    return (
        len(left_digits) >= 5
        and len(right_digits) >= 5
        and left_digits[-6:] == right_digits[-6:]
    )


def _industry_block_contains_company(value: Any, code: str) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {
                "company_id", "company_code", "issuer_id", "member_id", "target_company_id",
                "ts_code",
            } and _company_identity_matches(item, code):
                return True
            if _industry_block_contains_company(item, code):
                return True
    elif isinstance(value, list):
        return any(_industry_block_contains_company(item, code) for item in value)
    return False


def _matching_industry_learning_blocks(code: str) -> list[str]:
    root = os.path.join(
        _FRAMEWORK_DIR, "docs", "development", "research", "industry_learning_blocks",
    )
    if not os.path.isdir(root):
        return []
    matches: list[str] = []
    for directory, _subdirs, filenames in os.walk(root):
        for filename in sorted(filenames):
            if "industry_learning_block" not in filename or not filename.endswith(".json"):
                continue
            path = os.path.join(directory, filename)
            try:
                with open(path, encoding="utf-8") as handle:
                    payload = json.load(handle)
            except (OSError, json.JSONDecodeError):
                continue
            if _industry_block_contains_company(payload, code):
                matches.append(path)
    return sorted(matches)


def _compile_report_industry_underwriting_context(
    *, code: str, output_dir: str, discovery_context: dict[str, Any],
) -> dict[str, Any]:
    try:
        from scripts.industry_underwriting_context import (
            DEFAULT_OUTPUT_NAME,
            compile_industry_underwriting_context,
        )
    except ModuleNotFoundError:
        try:
            from industry_underwriting_context import (  # type: ignore[no-redef]
                DEFAULT_OUTPUT_NAME,
                compile_industry_underwriting_context,
            )
        except ModuleNotFoundError:
            return {"status": "UNAVAILABLE", "warning": "industry_underwriting_compiler_missing"}

    contract: dict[str, Any] = {}
    contract_path = os.path.join(output_dir, "analysis_contract.json")
    try:
        with open(contract_path, encoding="utf-8") as handle:
            contract = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {"status": "UNAVAILABLE", "warning": "analysis_contract_missing_or_invalid"}
    pit = contract.get("pit_production") if isinstance(contract.get("pit_production"), dict) else {}
    cutoff_at = str(
        pit.get("cutoff_at") or contract.get("data_as_of") or contract.get("analysis_date")
        or contract.get("cutoff_at") or contract.get("pit_cutoff_at") or ""
    ).strip()
    company_id = str(contract.get("company_id") or code).strip()
    meta = discovery_context.get("meta") if isinstance(discovery_context.get("meta"), dict) else {}
    if not cutoff_at or not company_id:
        return {"status": "UNAVAILABLE", "warning": "analysis_contract_company_or_cutoff_missing"}
    industry_keys = list(dict.fromkeys(
        str(item).strip() for item in (
            meta.get("industry_group"), meta.get("industry_l2"), meta.get("industry_l1"),
        ) if str(item or "").strip()
    ))
    block_paths = _matching_industry_learning_blocks(code)
    try:
        payload = compile_industry_underwriting_context(
            company={
                "company_id": company_id,
                "company_name": str(contract.get("company_name") or company_id),
                "cutoff_at": cutoff_at,
                "knowledge_cutoff_at": cutoff_at,
                "pit_mode": bool(pit),
                "industry_keys": industry_keys,
            },
            industry_learning_blocks=block_paths,
            competitive_arena=discovery_context,
            industry_keys=industry_keys,
        )
    except (OSError, ValueError) as exc:
        return {"status": "UNAVAILABLE", "warning": str(exc)}
    destination = os.path.join(output_dir, DEFAULT_OUTPUT_NAME)
    with open(destination, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    return {
        "status": payload["context_status"],
        "path": destination,
        "industry_learning_block_count": len(block_paths),
        "representative_peer_count": len(payload["representative_peers"]),
        "near_miss_count": len(payload["near_misses"]),
    }


def build_industry_context(
    code: str = "",
    output_dir: str = "",
) -> dict[str, Any]:
    """生成行业发现数据与报告级行业承保上下文（Phase 1.5）。

    调用 zone_d_industry_context.py 获取发现宇宙，再从目标公司已归属的
    IndustryLearningBlock 编译非阻断的 IndustryUnderwritingContext。
    """
    py = sys.executable
    script = os.path.join(_scripts_dir, "zone_d_industry_context.py")
    out_path = os.path.join(output_dir, "industry_context.json")

    if not os.path.exists(script):
        # 脚本不存在 → 生成最小 stub
        stub = {"_source": "stub", "comparable_peers": [], "percentiles": {},
                "signals": [], "meta": {"error": "zone_d_industry_context.py 不可用"}}
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(stub, f, indent=2, ensure_ascii=False)
        underwriting = _compile_report_industry_underwriting_context(
            code=code, output_dir=output_dir, discovery_context=stub,
        )
        return {
            "ok": True, "path": out_path, "comparable_peers": [], "note": "stub",
            "industry_underwriting_context": underwriting,
        }

    args = [py, script, "--code", code, "--output", output_dir]
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=120)
        if result.returncode == 0 and os.path.exists(out_path):
            with open(out_path, encoding="utf-8") as f:
                data = json.load(f)
            underwriting = _compile_report_industry_underwriting_context(
                code=code, output_dir=output_dir, discovery_context=data,
            )
            return {
                "ok": True,
                "path": out_path,
                "comparable_peers": len(data.get("comparable_peers", [])),
                "industry_underwriting_context": underwriting,
            }
        # 脚本失败 → 生成 stub
        error_msg = (result.stderr + result.stdout).strip()[-200:]
        print(f"  ⚠️ zone_d_industry_context 失败: {error_msg}")
    except Exception as exc:
        print(f"  ⚠️ zone_d_industry_context 异常: {exc}")

    # 生成最小可用 stub
    stub = {"_source": "stub (script failed)", "comparable_peers": [],
            "percentiles": {}, "signals": [],
            "meta": {"error": f"zone_d_industry_context.py 执行失败"}}
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(stub, f, indent=2, ensure_ascii=False)
    underwriting = _compile_report_industry_underwriting_context(
        code=code, output_dir=output_dir, discovery_context=stub,
    )
    return {
        "ok": True,
        "path": out_path,
        "comparable_peers": 0,
        "note": "stub (script failed)",
        "industry_underwriting_context": underwriting,
    }


def extract_zone_j(
    ts_code: str = "",
    stock_dir: str = "",
    llm_client: Any = None,
) -> dict[str, Any]:
    """运行 Zone J 参数提取（Phase 3）— 4 个 LLM Agent 并行。

    从 Zone A/B JSON + qualitative_summary 中提取结构化判断参数，
    写入 moat_assessment.json / capex_classification.json / earnings_quality.json / data_discount.json。
    """
    if not llm_client:
        return {"ok": False, "error": "需要 llm_client 参数"}

    try:
        from zone_j_agent import (
            AGENTS,
            validate_economic_discount_semantics,
            build_context,
            build_prompt,
        )
    except ImportError as exc:
        return {"ok": False, "error": f"无法导入 zone_j_agent: {exc}"}

    # 加载 qualitative_summary（如果存在）
    qual_summary = None
    qual_path = os.path.join(stock_dir, "qualitative_summary.json")
    if os.path.exists(qual_path):
        try:
            with open(qual_path, encoding="utf-8") as f:
                qual_summary = json.load(f)
        except Exception:
            pass

    def _run_zone_j_agent(agent_name: str, agent_def: dict) -> dict:
        """运行单个 Zone J agent。"""
        output_file = agent_def["output_file"]
        out_path = os.path.join(stock_dir, output_file)
        # V12.20: 验证已有文件是否为垃圾数据
        REQUIRED_CHECK = {
            "moat": ["b_penalty", "g_base"],
            "capex": ["mcapex_split_pct"],
            "earnings_quality": ["non_recurring_items"],
            "data_quality": ["total_discount_pct"],
            "governance_tension": ["governance_discount"],
        }
        if os.path.exists(out_path):
            try:
                with open(out_path, encoding="utf-8") as f:
                    existing = json.load(f)
                expected = REQUIRED_CHECK.get(agent_name, [])
                semantic_errors = validate_economic_discount_semantics(agent_name, existing)
                if semantic_errors:
                    print(
                        f"  ♻️  Zone J/{agent_name} 现有文件使用旧折价语义，按当前经济载体规则重新生成",
                        file=sys.stderr,
                    )
                elif expected and not any(k in existing for k in expected):
                    print(f"  🗑️  Zone J/{agent_name} 现有文件为垃圾数据 (keys={list(existing.keys())[:5]})，重新生成", file=sys.stderr)
                    os.remove(out_path)
                else:
                    return {"agent": agent_name, "skipped": True, "file": output_file}
            except Exception:
                pass

        # Reuse the canonical builder.  AGENTS stores a prompt_template_file,
        # not an inline prompt_template; the old duplicate path therefore sent
        # an empty prompt from the unified runtime.
        context = build_context(
            agent_name,
            stock_dir,
            ts_code,
            qual_path if os.path.exists(qual_path) else None,
        )
        prompt = build_prompt(agent_name, context, qual_summary)

        try:
            resp = llm_client.chat_with_retry(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            content = resp.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[-1]
                if content.endswith("```"):
                    content = content[:-3]
            # Try direct parse
            # V12.20: 内容校验 — 必须有预期字段才接受
            REQUIRED = {
                "moat": ["b_penalty", "g_base"],
                "capex": ["mcapex_split_pct"],
                "earnings_quality": ["non_recurring_items"],
                "data_quality": ["total_discount_pct"],
                "governance_tension": ["governance_discount"],
            }
            expected = REQUIRED.get(agent_name, [])

            parse_ok = False
            try:
                data = json.loads(content)
                semantic_ok = not validate_economic_discount_semantics(agent_name, data)
                if (expected and not any(k in data for k in expected)) or not semantic_ok:
                    print(f"  ⚠️  Zone J/{agent_name} JSON合法但字段不对: {list(data.keys())[:5]} (需要 {expected})", file=sys.stderr)
                else:
                    parse_ok = True
            except json.JSONDecodeError:
                pass

            if not parse_ok:
                # Repair: try to close unterminated strings/braces
                repaired = content.rstrip(",\n\r")
                open_braces = repaired.count("{") - repaired.count("}")
                open_brackets = repaired.count("[") - repaired.count("]")
                if repaired.rstrip().endswith('"') and not repaired.rstrip().endswith('}"'):
                    repaired += '"'
                repaired += "}" * open_braces + "]" * open_brackets
                try:
                    data = json.loads(repaired)
                    semantic_ok = not validate_economic_discount_semantics(agent_name, data)
                    if (expected and not any(k in data for k in expected)) or not semantic_ok:
                        raise ValueError(f"Repaired JSON still missing {expected}")
                    parse_ok = True
                except (json.JSONDecodeError, ValueError):
                    pass

            if not parse_ok:
                # Retry once with fix instruction
                resp2 = llm_client.chat_with_retry(
                    messages=[
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": content[:200]},
                        {"role": "user", "content": f"你的回复内容不对。我需要的是一个包含 {expected} 字段的 JSON 对象，用于投资分析参数。请直接输出 JSON。"},
                    ],
                    temperature=0.1,
                )
                content2 = resp2.content.strip()
                if content2.startswith("```"):
                    content2 = content2.split("\n", 1)[-1]
                    if content2.endswith("```"):
                        content2 = content2[:-3]
                try:
                    data = json.loads(content2)
                    if validate_economic_discount_semantics(agent_name, data):
                        return {
                            "agent": agent_name,
                            "error": "重试结果缺少当前经济载体折价语义标记",
                            "file": output_file,
                        }
                except json.JSONDecodeError:
                    return {"agent": agent_name, "error": "两次尝试均无法解析JSON", "file": output_file}

            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return {"agent": agent_name, "ok": True, "file": output_file}
        except Exception as exc:
            return {"agent": agent_name, "error": str(exc)[:200]}

    # 4 个 Agent 并行
    results = []
    from concurrent.futures import ThreadPoolExecutor, as_completed
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(_run_zone_j_agent, name, AGENTS[name]): name for name in AGENTS}
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            agent = r.get("agent", "?")
            if r.get("skipped"):
                print(f"  ⏭ {agent} (已有)")
            elif r.get("ok"):
                print(f"  ✅ {agent} → {r.get('file')}")
            else:
                print(f"  ❌ {agent}: {r.get('error', 'unknown')[:100]}")

    return {
        "ok": all(r.get("ok") or r.get("skipped") for r in results),
        "results": results,
    }


_VERIFY_REPORT_META = {
    "name": "verify_report",
    "description": "运行报告质量验证(Phase 5): S1占位符/E1证据密度/enhanced_quality_gate",
    "parameters": {
        "report_path": {"type": "string", "description": "报告文件路径", "optional": True},
        "output_dir": {"type": "string", "description": "股票输出目录", "optional": True},
    },
}


# ---------------------------------------------------------------------------
# Phase 2.1: PDF 内容预提取 (pdf_preprocessor)
# ---------------------------------------------------------------------------

def run_pdf_preprocessor(
    pdf_path: str = "",
    output_dir: str = "",
    year: int = 0,
) -> dict[str, Any]:
    """运行 PDF 章节内容提取（Phase 2.1）。

    调用 ``pdf_preprocessor.run_pipeline()`` 从 PDF 提取 10 类章节文本
    （MDA/SEG/STMT/DAN/P2/P3/P4/P6/P13/SUB）+ regex 财务数字。

    纯 Python 操作，不需要 LLM。
    """
    if not pdf_path:
        return {"ok": False, "error": "需要 pdf_path 参数"}
    if not os.path.exists(pdf_path):
        return {"ok": False, "error": f"PDF 不存在: {pdf_path}"}

    output_path = os.path.join(output_dir, f"pdf_sections_{year}.json")
    if os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                existing = json.load(f)
            meta = existing.get("metadata", {})
            return {
                "ok": True,
                "skipped": True,
                "output_path": output_path,
                "sections_found": meta.get("sections_found", 0),
                "total_pages": meta.get("total_pages", 0),
            }
        except Exception:
            pass  # 文件损坏，重新生成

    try:
        from pdf_preprocessor import run_pipeline as _run_pipeline
        result = _run_pipeline(pdf_path=pdf_path, output_path=output_path)
        meta = result.get("metadata", {})
        return {
            "ok": True,
            "output_path": output_path,
            "sections_found": meta.get("sections_found", 0),
            "sections_total": meta.get("sections_total", 10),
            "total_pages": meta.get("total_pages", 0),
            "financial_fields": list(result.get("financials", {}).keys()),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 2.1b: PDF → 全量 Markdown (pdf_to_markdown)
# ---------------------------------------------------------------------------

def pdf_to_markdown(
    pdf_path: str = "",
    output_dir: str = "",
    year: int = 0,
) -> dict[str, Any]:
    """将 PDF 年报转为全量 markdown 文件（Phase 2.1b）。

    复用 ``pdf_preprocessor.extract_all_pages()`` 的逐页文本提取结果
    （已含 markdown table），拼接为完整 markdown 文件。

    纯 Python 操作，不需要 LLM。
    """
    if not pdf_path or not os.path.exists(pdf_path):
        return {"ok": False, "error": f"PDF 不存在: {pdf_path}"}

    out_path = os.path.join(output_dir, f"{year}_年报.md")
    if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
        return {"ok": True, "skipped": True, "path": out_path, "size": os.path.getsize(out_path)}

    try:
        from pdf_preprocessor import extract_all_pages
        pages = extract_all_pages(pdf_path, verbose=False)
        if not pages:
            return {"ok": False, "error": "PDF 无可提取页面"}

        code = os.path.basename(pdf_path).split("_")[0]
        lines = [f"# {code} FY{year} 年报全文", f"", f"*共 {len(pages)} 页*", ""]
        for page_num, text in pages:
            text = text.strip()
            if not text:
                continue
            lines.append(f"## 第 {page_num} 页")
            lines.append("")
            lines.append(text)
            lines.append("")

        md_content = "\n".join(lines)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        return {"ok": True, "path": out_path, "size": len(md_content), "pages": len(pages)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 2.2: 多年度全文组装 (build_full_text)
# ---------------------------------------------------------------------------

def build_full_text_phase(
    stock_dir: str = "",
    ts_code: str = "",
    num_years: int = 5,
) -> dict[str, Any]:
    """运行多年度定性文本组装（Phase 2.2）。

    从 ``pdf_sections_*.json`` 中提取高质量定性段落，
    跳过纯数字表格和样板文字，按信息密度评分。

    纯 Python 操作，不需要 LLM。
    """
    if not stock_dir or not os.path.isdir(stock_dir):
        return {"ok": False, "error": f"目录不存在: {stock_dir}"}

    output_path = os.path.join(stock_dir, "pdf_full_text.json")
    if os.path.exists(output_path):
        try:
            with open(output_path, encoding="utf-8") as f:
                existing = json.load(f)
            prov = existing.get("_provenance", {})
            return {
                "ok": True,
                "skipped": True,
                "output_path": output_path,
                "years_covered": prov.get("years_covered", []),
                "total_chars": prov.get("total_chars", 0),
            }
        except Exception:
            pass

    try:
        from build_full_text import build_full_text as _build
        result = _build(stock_dir=stock_dir, ts_code=ts_code, num_years=num_years)
        # build_full_text() returns a dict — write it to disk ourselves
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        prov = result.get("_provenance", {})
        return {
            "ok": True,
            "output_path": output_path,
            "years_covered": prov.get("years_covered", []),
            "total_chars": prov.get("total_chars", 0),
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Phase 2.3: Zone B 年度 Agent 提取 (每年一个独立 Agent)
# ---------------------------------------------------------------------------

def _to_million_amount(raw: str) -> float | None:
    text = str(raw or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return round(float(text) / 1_000_000.0, 4)
    except Exception:
        return None


def _page_markers_from_markdown(md_text: str) -> list[tuple[int, int]]:
    return [(m.start(), int(m.group(1))) for m in re.finditer(r"^## 第\s+(\d+)\s+页\s*$", md_text, re.MULTILINE)]


def _page_for_offset(markers: list[tuple[int, int]], offset: int) -> int | None:
    page = None
    for pos, value in markers:
        if pos > offset:
            break
        page = value
    return page


def _extract_labor_by_function_from_markdown(md_text: str) -> dict[str, Any] | None:
    """Best-effort fallback for sales/admin/R&D labor from fee-note markdown.

    This only repairs labor_by_function when the LLM misses a clearly disclosed
    fee-note breakdown. It does not guess production labor.
    """
    section_specs = [
        ("sales", "销售费用"),
        ("admin", "管理费用"),
        ("rd", "研发费用"),
    ]
    page_markers = _page_markers_from_markdown(md_text)
    values: dict[str, float | None] = {"production": None, "sales": None, "admin": None, "rd": None, "total": None}
    quote_parts: list[str] = []
    source_pages: list[int] = []

    for field, label in section_specs:
        pattern = re.compile(
            rf"(?:^|\n)\s*(?:\d+\.\s*)?{re.escape(label)}[\s\S]{{0,1200}}?职工薪酬\s+([0-9,]+(?:\.\d+)?)",
            re.MULTILINE,
        )
        match = pattern.search(md_text)
        if not match:
            continue
        amount_m = _to_million_amount(match.group(1))
        if amount_m is None:
            continue
        values[field] = amount_m
        quote_parts.append(f"{label} 职工薪酬 {match.group(1)}")
        page = _page_for_offset(page_markers, match.start())
        if page is not None and page not in source_pages:
            source_pages.append(page)

    if all(values[field] is None for field in ("sales", "admin", "rd")):
        return None

    return {
        **values,
        "quote": "；".join(quote_parts) + "。",
        "note_basis": "费用附注分别披露销售费用、管理费用、研发费用中的职工薪酬，可作为 sales/admin/rd 结构化事实；production 未单列。",
        "source_pages": sorted(source_pages),
    }


def _repair_zone_b_partial_from_markdown(data: dict[str, Any], md_text: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return data
    labor = data.get("labor_by_function")
    has_labor = isinstance(labor, dict) and any(
        labor.get(key) is not None for key in ("production", "sales", "admin", "rd", "total")
    )
    if not has_labor:
        repaired = _extract_labor_by_function_from_markdown(md_text)
        if repaired:
            data["labor_by_function"] = repaired
            repair_meta = data.get("_repair_meta")
            if not isinstance(repair_meta, dict):
                repair_meta = {}
                data["_repair_meta"] = repair_meta
            repair_meta["labor_by_function"] = "markdown_fee_note_fallback"
    return data

def _run_year_extraction_from_md(year: str, stock_dir: str, llm_client: Any) -> dict:
    """V8.4: 从全量 markdown 提取，不需要 pdf_full_text。

    直接读 {year}_年报.md → 构建 prompt → LLM 提取。
    跳过 build_full_text 步骤，markdown 文本更干净（连续段落、markdown table）。
    """
    from zone_b_v8 import YEAR_SCHEMA

    md_path = os.path.join(stock_dir, f"{year}_年报.md")
    if not os.path.exists(md_path):
        # fallback: 尝试 pdf_full_text 路径
        ft_path = os.path.join(stock_dir, "pdf_full_text.json")
        if os.path.exists(ft_path):
            return _run_year_extraction_direct(year, stock_dir, llm_client)
        return {"ok": False, "error": f"{year}_年报.md 不存在，请先运行 Phase 2.1 markdown 转换"}

    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    # 构建 prompt（markdown 版本，直接取全文前 50K chars）
    prompt = f"""你是数据提取器。从以下上市公司 FY{year} 年报 markdown 全文中提取结构化数据。

【年报全文 — FY{year}（markdown 格式，共 {len(md_text):,} chars）】
{md_text[:50000]}

【提取 Schema — 请输出以下 JSON】
```json
{json.dumps(YEAR_SCHEMA, indent=2, ensure_ascii=False)}
```

【强制规则】
1. 每个数字字段必须附带 "quote": "原文中包含该数字的完整句子"。无 quote 的字段填 null。
2. 只提取 FY{year} 的数据。若原文同时提到去年和今年，只取今年。
3. 全文搜索所有章节。markdown 中的 `[TABLE]` 标记是表格数据，优先从中提取数字。
4. **labor_by_function 是重点检查项**：必须二次搜索以下关键词后才能决定是否为 null：
   - `销售费用` + `职工薪酬`
   - `管理费用` + `职工薪酬`
   - `研发费用` + `职工薪酬`
   - `员工成本` / `雇员福利` / `staff cost` / `employee benefit expense`
5. **若只找到销售/管理/研发费用中的职工薪酬，也必须输出 labor_by_function**：
   - `production: null`
   - `sales/admin/rd`: 填提取值
   - `total: null`
   - `note_basis`: 说明来自费用附注而非总员工成本附注
6. **只有在“总员工成本附注”和“销售/管理/研发费用职工薪酬”都找不到时，labor_by_function 才能为 null。**
7. 缺失字段填 null，不编造，不推断。
8. _extracted 数组: 选取 10-15 段最有价值的原文，完整 verbatim，不截断。
9. 金额统一为百万元 RMB（原文用千元→÷1000；原文用亿元→×100）。

输出纯 JSON，不含 markdown fence。"""

    try:
        resp = llm_client.chat_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16384,
        )
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
        # 允许后置文本：解析失败时尝试截取 { 到 } 的 JSON 部分
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # 找最后一个完整 JSON 对象（处理 LLM 后置废话）
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                data = json.loads(content[brace_start:brace_end+1])
            else:
                raise
    except Exception as exc:
        return {"ok": False, "error": f"LLM 调用或 JSON 解析失败: {exc}"}

    data = _repair_zone_b_partial_from_markdown(data, md_text)

    out_path = os.path.join(stock_dir, f"zone_b_{year}_partial.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"ok": True, "path": out_path, "chars": len(json.dumps(data, ensure_ascii=False))}


def _run_year_extraction_direct(year: str, stock_dir: str, llm_client: Any) -> dict:
    """V8.3: 直接用 build_year_prompt + LLM 提取，使用预处理好的 pdf_full_text。

    替代旧的 agent-based 提取（读 PDF → 提取），现在所有规则 1-18 +
    去截断 + DB 上下文全部生效。
    """
    from zone_b_v8 import build_year_prompt, YEAR_SCHEMA

    ft_path = os.path.join(stock_dir, "pdf_full_text.json")
    if not os.path.exists(ft_path):
        return {"ok": False, "error": f"pdf_full_text.json 不存在，请先运行 Phase 2.2"}

    with open(ft_path, encoding="utf-8") as f:
        full_text = json.load(f)

    prompt = build_year_prompt(year, full_text)
    if not prompt:
        return {"ok": False, "error": f"FY{year} 不在 pdf_full_text 中"}

    # 直接调用 LLM（一次调用，零 agent loop）
    try:
        resp = llm_client.chat_with_retry(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16384,
        )
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[-1]
            if content.endswith("```"):
                content = content[:-3]
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            brace_start = content.find("{")
            brace_end = content.rfind("}")
            if brace_start >= 0 and brace_end > brace_start:
                data = json.loads(content[brace_start:brace_end+1])
            else:
                raise
    except Exception as exc:
        return {"ok": False, "error": f"LLM 调用或 JSON 解析失败: {exc}"}

    # 保存
    out_path = os.path.join(stock_dir, f"zone_b_{year}_partial.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return {"ok": True, "path": out_path, "chars": len(json.dumps(data, ensure_ascii=False))}


def _try_extract_json_from_text(text: str, year: int) -> dict | None:
    """尝试从 Agent 文本响应中提取符合 YEAR_SCHEMA 的 JSON 对象。"""
    import re as _re
    # 尝试匹配 ```json ... ``` 或直接的 { ... }
    candidates = []
    # Pattern 1: markdown code fence
    for m in _re.finditer(r"```(?:json)?\s*(\{.*?\})\s*```", text, _re.DOTALL):
        candidates.append(m.group(1))
    # Pattern 2: bare JSON object (greedy)
    for m in _re.finditer(r"\{[^{}]*\"fiscal_year\"[^{}]*\}", text, _re.DOTALL):
        candidates.append(m.group(0))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if "fiscal_year" in data or "revenue_highlights" in data:
                return data
        except json.JSONDecodeError:
            continue
    return None


def _run_year_extraction_agent(
    year: int,
    stock_dir: str,
    llm_client: Any,
    max_iterations: int = 12,
) -> dict[str, Any]:
    """V8.4: 委托给 _run_year_extraction_from_md（优先读 markdown，fallback pdf_full_text）。"""
    return _run_year_extraction_from_md(str(year), stock_dir, llm_client)


def extract_zone_b_years(
    stock_dir: str = "",
    ts_code: str = "",
    llm_client: Any = None,  # LlmClient instance
    years: list[int] | None = None,
) -> dict[str, Any]:
    """运行 Zone B 年度 Agent 提取（Phase 2.3）。

    每个年份启动一个独立 Agent：读 PDF → 提取结构化数据 → 保存 partial JSON。
    Agent 有 read_section 工具分段读 PDF，不会被单次输出 token 限制。

    需要 LLM API 访问。
    """
    if not llm_client:
        return {"ok": False, "error": "需要 llm_client 参数（LlmClient 实例）"}

    # V12: 优先从 markdown 文件读取（V8.4），fallback 到 pdf_full_text.json
    import re as _re
    md_years = []
    if os.path.isdir(stock_dir):
        for f in os.listdir(stock_dir):
            m = _re.match(r'(\d{4})_年报\.md', f)
            if m:
                md_years.append(int(m.group(1)))
    md_years = sorted(md_years)

    if md_years:
        available_years = md_years[-5:]  # 最近 5 年
    else:
        try:
            from zone_b_v8 import load_pdf_full_text
            full_text = load_pdf_full_text(stock_dir)
            if not full_text:
                return {"ok": False, "error": f"pdf_full_text.json 未找到于 {stock_dir}，且无 {{year}}_年报.md 文件。请先运行 Phase 2.1"}
            available_years = sorted(int(y) for y in full_text.get("years", {}).keys())
        except ImportError as exc:
            return {"ok": False, "error": f"无法导入 zone_b_v8: {exc}"}
    if years:
        available_years = [y for y in years if y in available_years]
    else:
        available_years = available_years[-5:]  # 最近 5 年

    if not available_years:
        return {"ok": False, "error": "pdf_full_text.json 中没有可用年份"}

    results = []
    errors = []
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _extract_with_agent(year: int) -> dict:
        return _run_year_extraction_from_md(str(year), stock_dir, llm_client)

    with ThreadPoolExecutor(max_workers=min(5, len(available_years))) as pool:
        futures = {pool.submit(_extract_with_agent, y): y for y in available_years}
        for f in as_completed(futures):
            r = f.result()
            r.setdefault("year", futures[f])
            results.append(r)
            if "error" in r:
                errors.append(r)

    results.sort(key=lambda item: int(item.get("year") or 0))
    succeeded = [item for item in results if item.get("ok")]
    failed_years = sorted(int(item["year"]) for item in errors if item.get("year") is not None)
    status = "COMPLETE" if not errors else "PARTIAL" if succeeded else "UNAVAILABLE"
    return {
        # One failed extractor is a local year gap, not a reason to discard
        # every successfully materialized year or stop enterprise judgment.
        "ok": bool(succeeded),
        "degraded": bool(errors and succeeded),
        "coverage_status": status,
        "years_requested": list(available_years),
        "years_succeeded": sorted(int(item["year"]) for item in succeeded),
        "failed_years": failed_years,
        "years_processed": len(results),
        "years_skipped": sum(1 for r in results if r.get("skipped")),
        "years_failed": len(errors),
        "results": results,
        "errors": errors if errors else None,
        "error": "all Zone B annual-year extractions failed" if not succeeded else None,
    }

def extract_zone_b_master(
    ts_code: str = "",
    stock_dir: str = "",
    llm_client: Any = None,  # LlmClient instance (V8.3: 仅用于 trend_analysis)
) -> dict[str, Any]:
    """运行 Zone B Master 汇总（Phase 2.4）— V8.3 纯 Python 聚合版。

    读取所有 zone_b_*_partial.json → aggregate_partials_to_zone_b() →
    写入 mda.json / segments.json / risks.json / governance.json / audit.json。

    不再需要 LLM master 调用（结构化合并用代码零信息丢失）。
    llm_client 参数保留用于 trend_analysis（可选）。
    """
    zone_b_files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
    optional_outputs = ["gg_override.json"]
    all_exist = all(os.path.exists(os.path.join(stock_dir, f)) for f in zone_b_files)
    gg_override_exists = os.path.exists(os.path.join(stock_dir, "gg_override.json"))
    if all_exist and gg_override_exists:
        return {
            "ok": True,
            "skipped": True,
            "files": zone_b_files + optional_outputs,
            "message": "所有 Zone B 文件已存在，跳过 master 汇总",
        }

    try:
        from zone_b_v8 import aggregate_partials_to_zone_b, write_zone_b_jsons
    except ImportError as exc:
        return {"ok": False, "error": f"无法导入 zone_b_v8: {exc}"}

    # 加载所有 partials
    partials = {}
    for fname in sorted(os.listdir(stock_dir)):
        if fname.startswith("zone_b_") and fname.endswith("_partial.json"):
            yr = fname.replace("zone_b_", "").replace("_partial.json", "")
            path = os.path.join(stock_dir, fname)
            with open(path) as f:
                partials[yr] = json.load(f)

    if not partials:
        return {"ok": False, "error": "无 zone_b_*_partial.json 文件，请先运行 Phase 2.3"}

    # 纯 Python 聚合（零信息丢失）
    master_output = aggregate_partials_to_zone_b(partials, stock_dir)

    write_zone_b_jsons(master_output, stock_dir, partials)
    written = [f for f in zone_b_files + optional_outputs if os.path.exists(os.path.join(stock_dir, f))]
    available_years = sorted(
        int(match.group(1))
        for name in os.listdir(stock_dir)
        if (match := re.fullmatch(r"(20\d{2})_年报\.md", name))
    )
    partial_years = sorted(int(year) for year in partials if str(year).isdigit())
    return {
        "ok": True,
        "files_written": written,
        "missing": [f for f in zone_b_files if f not in written],
        "source_years": partial_years,
        "available_annual_years": available_years,
        "unextracted_years": sorted(set(available_years) - set(partial_years)),
        "coverage_status": (
            "COMPLETE"
            if not set(available_years) - set(partial_years)
            else "PARTIAL"
        ),
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
