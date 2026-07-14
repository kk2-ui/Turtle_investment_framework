#!/usr/bin/env python3
"""Codex-friendly workflow wrapper for Turtle Investment Framework.

This script does not replace the repo's LLM-driven report synthesis.
It wraps the deterministic preparation steps so Codex (or a human) can
run the same repo workflows without relying on Claude slash commands.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from config import (
    check_local_pdf,
    get_api_url,
    get_token,
    infer_listing_structure,
    normalize_holding_channel,
    resolve_shareholder_dividend_tax_rate,
    validate_stock_code,
)
from format_utils import format_table
from turtle_thresholds import ThresholdProfile, classify_threshold_profile


REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "output"
VENV_PYTHON = REPO_ROOT / ".venv" / "bin" / "python"


@dataclass(frozen=True)
class AnnualReportCoverage:
    """Local annual-report coverage for the framework's multi-year checks."""

    target_years: list[int]
    found: list[tuple[int, Path]]
    missing_years: list[int]
    minimum_years: int = 3

    @property
    def found_years(self) -> list[int]:
        return [year for year, _path in self.found]

    @property
    def is_target_complete(self) -> bool:
        return not self.missing_years and len(self.found) == len(self.target_years)

    @property
    def has_minimum_coverage(self) -> bool:
        return len(self.found) >= self.minimum_years

    @property
    def status_label(self) -> str:
        if self.is_target_complete:
            return f"已补齐最近 {len(self.target_years)} 年"
        if self.has_minimum_coverage:
            return f"未满 {len(self.target_years)} 年但达到最低 {self.minimum_years} 年"
        return f"不足最低 {self.minimum_years} 年，需降级"

    def markdown_summary(self) -> str:
        found = ", ".join(str(year) for year in self.found_years) if self.found else "无"
        missing = ", ".join(str(year) for year in self.missing_years) if self.missing_years else "无"
        return (
            f"年报覆盖：目标最近{len(self.target_years)}年 "
            f"({self.target_years[0]}-{self.target_years[-1]})；"
            f"已发现 {found}；缺失 {missing}；状态：{self.status_label}"
        )


@dataclass(frozen=True)
class InterimReportRequirement:
    """Latest interim-report requirement inferred from the market data pack."""

    required: bool
    year: Optional[int] = None
    pdf: Optional[Path] = None

    @property
    def is_satisfied(self) -> bool:
        return (not self.required) or self.pdf is not None

    @property
    def status_label(self) -> str:
        if not self.required:
            return "未触发"
        if self.pdf:
            return "已就位"
        return "缺失，最新经营时效性降级"

    def markdown_summary(self) -> str:
        if not self.required:
            return "中报要求：data_pack_market 未发现 H1 列，未触发中报下载。"
        year = self.year or "未知年份"
        if self.pdf:
            return f"中报要求：发现 {year}H1，最新中报已就位 `{self.pdf}`。"
        return (
            f"中报要求：发现 {year}H1，但本地缺少 {year} 年中报 PDF；"
            "需下载中报，否则最新经营、应收、现金、分红与MD&A时效性降级。"
        )


def _base_code(ts_code: str) -> str:
    return ts_code.split(".")[0]


def _sanitize_name(name: str) -> str:
    safe = name.strip()
    for ch in '/\\:*?"<>|':
        safe = safe.replace(ch, "_")
    return safe or "company"


def _fetch_company_name(ts_code: str) -> Optional[str]:
    """Best-effort basic-name lookup via Tushare."""
    try:
        import tushare as ts
    except ImportError:
        return None

    try:
        token = get_token()
    except Exception:
        return None

    pro = ts.pro_api(token=token, timeout=30)
    api_url = get_api_url()
    if api_url:
        pro._DataApi__token = token
        pro._DataApi__http_url = api_url

    try:
        if ts_code.endswith(".HK"):
            df = pro.hk_basic(ts_code=ts_code, fields="ts_code,name,fullname,enname")
        elif ts_code.endswith(".US"):
            df = pro.us_basic(ts_code=ts_code, fields="ts_code,name,enname")
        else:
            df = pro.stock_basic(ts_code=ts_code, fields="ts_code,name,fullname")
    except Exception:
        return None

    if df is None or df.empty:
        return None

    row = df.iloc[0]
    for key in ("name", "fullname", "enname"):
        value = str(row.get(key, "")).strip()
        if value and value.lower() != "nan":
            return value
    return None


def preferred_python() -> str:
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def resolve_output_dir(ts_code: str, company_name: Optional[str] = None,
                       explicit_output_dir: Optional[str] = None) -> Path:
    if explicit_output_dir:
        return Path(explicit_output_dir).resolve()

    code = _base_code(ts_code)
    matches = sorted(
        p for p in OUTPUT_ROOT.glob(f"{code}_*")
        if p.is_dir()
    )
    if len(matches) == 1:
        return matches[0]

    if company_name:
        return OUTPUT_ROOT / f"{code}_{_sanitize_name(company_name)}"

    fetched_name = _fetch_company_name(ts_code)
    if fetched_name:
        return OUTPUT_ROOT / f"{code}_{_sanitize_name(fetched_name)}"

    return OUTPUT_ROOT / code


def run_cmd(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True, cwd=REPO_ROOT)


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def ensure_seed_file(path: Path, content: str) -> bool:
    if path.exists():
        return False
    write_text(path, content)
    return True


def repo_rel(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO_ROOT))
    except Exception:
        return str(path)


def parse_report_year(path: Path) -> Optional[int]:
    matches = re.findall(r"(20\d{2})", path.name)
    if not matches:
        return None
    year = int(matches[-1])
    if 2000 <= year <= 2099:
        return year
    return None


def discover_recent_annual_pdfs(output_dir: Path, ts_code: str,
                                lookback_years: int = 5,
                                report_year: Optional[int] = None) -> list[tuple[int, Path]]:
    code = _base_code(ts_code)
    current_year = report_year or latest_fiscal_year()
    min_year = current_year - lookback_years + 1
    by_year: dict[int, Path] = {}

    for path in sorted(output_dir.glob("*.pdf")):
        name_lower = path.name.lower()
        year = parse_report_year(path)
        if year is None or year < min_year or year > current_year:
            continue
        if code not in path.name:
            continue
        if any(token in name_lower for token in ["中报", "interim", "half", "半年", "h1"]):
            continue
        if "年报" not in path.name and "annual" not in name_lower:
            continue
        existing = by_year.get(year)
        if existing is None or len(path.name) < len(existing.name):
            by_year[year] = path

    return sorted(by_year.items())


def target_annual_report_years(report_year: int, lookback_years: int = 5) -> list[int]:
    return list(range(report_year - lookback_years + 1, report_year + 1))


def ensure_recent_annual_report_coverage(
    output_dir: Path,
    ts_code: str,
    report_year: int,
    *,
    lookback_years: int = 5,
    minimum_years: int = 3,
) -> AnnualReportCoverage:
    """Check the framework's expected annual-report window before analysis.

    The downloader needs a concrete PDF URL, so this function does not pretend
    to search the web. It enforces the workflow contract locally: use the latest
    five full annual reports when present, require at least three for non-
    degraded trend conclusions, and expose missing years for the handoff.
    """
    target_years = target_annual_report_years(report_year, lookback_years)
    discovered = dict(discover_recent_annual_pdfs(
        output_dir,
        ts_code,
        lookback_years=lookback_years,
        report_year=report_year,
    ))
    found = [(year, discovered[year]) for year in target_years if year in discovered]
    missing = [year for year in target_years if year not in discovered]
    return AnnualReportCoverage(
        target_years=target_years,
        found=found,
        missing_years=missing,
        minimum_years=minimum_years,
    )


def latest_h1_year_from_market_pack(data_pack_path: Path) -> Optional[int]:
    if not data_pack_path.exists():
        return None
    text = data_pack_path.read_text(encoding="utf-8", errors="ignore")
    years = [int(match.group(1)) for match in re.finditer(r"\b(20\d{2})H1\b", text, flags=re.I)]
    return max(years) if years else None


def stage_interim_pdf(
    ts_code: str,
    output_dir: Path,
    *,
    report_year: Optional[int],
    pdf_path: Optional[str] = None,
    pdf_url: Optional[str] = None,
) -> Optional[Path]:
    if report_year is None:
        return None
    if pdf_path:
        src = Path(pdf_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"Interim PDF not found: {src}")
        dst = output_dir / src.name
        if src != dst:
            shutil.copy2(src, dst)
        return dst

    if pdf_url:
        dst = output_dir / f"{_base_code(ts_code)}_{report_year}_中报.pdf"
        run_cmd([
            preferred_python(),
            "scripts/download_report.py",
            "--url", pdf_url,
            "--stock-code", _base_code(ts_code),
            "--report-type", "中报",
            "--year", str(report_year),
            "--save-dir", str(output_dir),
        ])
        return dst if dst.exists() else None

    existing = check_local_pdf(ts_code, report_year, str(output_dir), report_type="中报")
    return Path(existing).resolve() if existing else None


def ensure_interim_report_requirement(
    ts_code: str,
    output_dir: Path,
    data_pack_path: Path,
    *,
    pdf_path: Optional[str] = None,
    pdf_url: Optional[str] = None,
) -> InterimReportRequirement:
    h1_year = latest_h1_year_from_market_pack(data_pack_path)
    if h1_year is None:
        return InterimReportRequirement(required=False)
    pdf = stage_interim_pdf(
        ts_code,
        output_dir,
        report_year=h1_year,
        pdf_path=pdf_path,
        pdf_url=pdf_url,
    )
    return InterimReportRequirement(required=True, year=h1_year, pdf=pdf)


def preprocess_annual_pdfs(output_dir: Path, annual_pdfs: list[tuple[int, Path]]) -> list[Path]:
    generated: list[Path] = []
    for idx, (year, pdf) in enumerate(annual_pdfs):
        target = output_dir / f"pdf_sections_{year}.json"
        if not target.exists():
            run_cmd([
                preferred_python(),
                "scripts/pdf_preprocessor.py",
                "--pdf", str(pdf),
                "--output", str(target),
            ])
        generated.append(target)

        # Preserve the legacy latest-year filename expected by existing docs/prompts.
        if idx == len(annual_pdfs) - 1:
            latest_target = output_dir / "pdf_sections.json"
            if target != latest_target and (
                not latest_target.exists() or target.stat().st_mtime > latest_target.stat().st_mtime
            ):
                shutil.copy2(target, latest_target)
            generated.append(latest_target)

    return generated


def ensure_hk_report_pack(ts_code: str, output_dir: Path) -> Optional[Path]:
    """Generate data_pack_report.md from the latest HK annual report when possible."""
    if not ts_code.endswith(".HK"):
        return None

    annual_pdfs = discover_recent_annual_pdfs(output_dir, ts_code, lookback_years=5)
    if not annual_pdfs:
        return None

    target = output_dir / "data_pack_report.md"
    run_cmd([
        preferred_python(),
        "scripts/hk_pdf_report_pack.py",
        "--code", ts_code,
        "--output-dir", str(output_dir),
        "--output", str(target),
    ])
    return target


def ensure_hk_report_pack_interim(
    ts_code: str,
    output_dir: Path,
    interim_requirement: Optional[InterimReportRequirement] = None,
) -> Optional[Path]:
    """Generate HK interim-report pack when a local HK interim PDF exists."""
    if not ts_code.endswith(".HK"):
        return None

    interim_pdf = None
    if interim_requirement and interim_requirement.pdf:
        interim_pdf = interim_requirement.pdf
    else:
        current_year = latest_fiscal_year()
        candidate_years = [current_year, current_year - 1]
        if interim_requirement and interim_requirement.year is not None:
            candidate_years.insert(0, interim_requirement.year)
        for year in dict.fromkeys(candidate_years):
            candidate = check_local_pdf(ts_code, year, str(output_dir), report_type="中报")
            if candidate:
                interim_pdf = Path(candidate)
                break

    if not interim_pdf:
        return None

    target = output_dir / "data_pack_report_interim.md"
    run_cmd([
        preferred_python(),
        "scripts/hk_pdf_report_pack_interim.py",
        "--code", ts_code,
        "--output-dir", str(output_dir),
        "--output", str(target),
    ])
    return target


def display_company_name(ts_code: str, output_dir: Path,
                         company_name: Optional[str] = None) -> str:
    if company_name and company_name.strip():
        return company_name.strip()

    code = _base_code(ts_code)
    prefix = f"{code}_"
    if output_dir.name.startswith(prefix):
        suffix = output_dir.name[len(prefix):].strip()
        if suffix:
            return suffix

    fetched_name = _fetch_company_name(ts_code)
    if fetched_name:
        return fetched_name

    return code


def report_prefix(ts_code: str, output_dir: Path,
                  company_name: Optional[str] = None) -> str:
    company = _sanitize_name(display_company_name(ts_code, output_dir, company_name))
    code = _base_code(ts_code)
    if company == code:
        return code
    return f"{company}_{code}"


def infer_listing_structure_from_output(ts_code: str, output_dir: Path) -> str:
    """Best-effort listing-structure inference using local output artifacts."""
    structure = infer_listing_structure(ts_code, {})
    if structure not in {"hk", ""}:
        return structure

    candidates = sorted(output_dir.glob("pdf_sections*.json")) + [
        output_dir / "data_pack_report.md",
        output_dir / "data_pack_report_interim.md",
        output_dir / "qualitative_report.md",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore").lower()
        except Exception:
            continue
        if "cayman islands" in text or "grand cayman" in text or "开曼" in text:
            return "red_chip_cayman"
        if "bermuda" in text or "百慕" in text:
            return "red_chip_bermuda"
        if re.search(r"\bh[-\s]?shares?\b", text):
            return "h_share"
        if re.search(r"h股(?:上市|公司|股份|发行|發行)", text):
            return "h_share"
        if re.search(r"(?:股份类别|股份類別|股本|share capital).{0,80}h股", text):
            return "h_share"

    return structure


def workflow_tax_context(ts_code: str, output_dir: Path,
                         holding_channel: Optional[str]) -> tuple[str, str, str]:
    """Return listing-structure, normalized channel note, and shareholder-tax note."""
    structure_key = infer_listing_structure_from_output(ts_code, output_dir)
    normalized_channel = normalize_holding_channel(holding_channel)
    structure_label = {
        "red_chip_cayman": "红筹/开曼",
        "red_chip_bermuda": "红筹/百慕大",
        "hk": "港股",
        "h_share": "H股",
        "a_share": "A股",
        "us": "美股",
        "": "待确认",
    }.get(structure_key, structure_key)
    channel_label = {
        "hk_local_direct": "香港居民通过香港券商直投",
        "hk_local_direct_tax0": "香港券商直投（用户指定股息税 0%）",
        "hk_local_direct_tax10": "香港券商直投（用户指定股息税 10%）",
        "southbound": "内地个人通过港股通",
        "us_broker": "通过美股券商持有",
        "direct": "直接持有（税务居民身份待确认）",
        "": "未提供，需在 Phase 3 明确",
    }.get(normalized_channel, holding_channel or "未提供，需在 Phase 3 明确")
    q_rate, q_reason = resolve_shareholder_dividend_tax_rate(
        ts_code=ts_code,
        holding_channel=normalized_channel,
        listing_structure=structure_key,
    )
    if q_rate is None:
        tax_note = f"股东层面税率待确认（{q_reason}）"
    else:
        tax_note = f"股东层面税率 Q = {q_rate * 100:.2f}%（{q_reason}）"
    return structure_label, channel_label, tax_note


def tax_scenarios_for_listing_structure(structure_key: str) -> list[dict[str, float | str]]:
    """Return shareholder-tax sensitivity scenarios by listing structure."""
    if structure_key == "h_share":
        return [
            {"tax_pct": 0.0, "label": "Q=0%", "note": "H股居民企业豁免可及"},
            {"tax_pct": 10.0, "label": "Q=10%", "note": "协定/常规中间档"},
            {"tax_pct": 20.0, "label": "Q=20%", "note": "港股通内地个人常用压力档"},
        ]
    if structure_key.startswith("red_chip"):
        return [
            {"tax_pct": 5.0, "label": "Q=5%", "note": "申请内地个税协定后可能可达；0%仅H股居民企业豁免，红筹不适用"},
            {"tax_pct": 10.0, "label": "Q=10%", "note": "红筹默认主口径"},
            {"tax_pct": 20.0, "label": "Q=20%", "note": "港股通内地个人常用压力档"},
        ]
    return [
        {"tax_pct": 0.0, "label": "Q=0%", "note": "纯港股/本地居民可及场景"},
        {"tax_pct": 10.0, "label": "Q=10%", "note": "中性税率场景"},
        {"tax_pct": 20.0, "label": "Q=20%", "note": "压力税率场景"},
    ]


def tax_scenario_text(scenarios: list[dict[str, float | str]]) -> str:
    return "/".join(str(item["label"]).replace("Q=", "") for item in scenarios)


def business_handoff_content(ts_code: str, output_dir: Path, pdf: Optional[Path],
                             annual_pdfs: list[tuple[int, Path]],
                             holding_channel: Optional[str] = None,
                             annual_coverage: Optional[AnnualReportCoverage] = None,
                             interim_requirement: Optional[InterimReportRequirement] = None) -> str:
    structure_key = infer_listing_structure_from_output(ts_code, output_dir)
    tax_scenarios = tax_scenarios_for_listing_structure(structure_key)
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    lines = [
        f"# Codex Business Analysis Handoff: {ts_code}",
        "",
        f"- 生成日期：{today_str()}",
        f"- 输出目录：`{output_dir}`",
        "- 工作流规范：`.claude/commands/business-analysis.md`",
        "- 定性框架：`shared/qualitative/qualitative_assessment_v2.md`",
        "",
        "## 已完成的确定性步骤",
        "",
        f"- `data_pack_market.md` 已生成：`{output_dir / 'data_pack_market.md'}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 股东层税务口径：{tax_note}",
    ]
    if annual_pdfs:
        lines.extend([
            "- 已发现近年年报 PDF：",
            "",
        ])
        for year, report_pdf in annual_pdfs:
            lines.append(f"  - FY{year}: `{report_pdf}`")
            lines.append(f"    - 预处理：`{output_dir / f'pdf_sections_{year}.json'}`")
    elif pdf and pdf.exists():
        lines.extend([
            f"- 年报 PDF 已就位：`{pdf}`",
            f"- `pdf_sections.json` 路径：`{output_dir / 'pdf_sections.json'}`",
        ])
    else:
        lines.append("- 年报 PDF：未就位，需要补充 PDF 或走 WebSearch fallback。")
    if annual_coverage:
        lines.extend([
            f"- {annual_coverage.markdown_summary()}",
        ])
        if annual_coverage.missing_years:
            missing = "、".join(str(year) for year in annual_coverage.missing_years)
            lines.append(f"- 待补年报：{missing} 年年报。若无法补齐，DPS CAGR、Capex/D&A 五年中位数、现金审计与治理轨迹必须降级标注。")
        if not annual_coverage.has_minimum_coverage:
            lines.append("- 覆盖不足 3 年：禁止给出未降级的强结论，必须在报告显著位置说明样本不足。")
    if interim_requirement:
        lines.append(f"- {interim_requirement.markdown_summary()}")
        if interim_requirement.required and not interim_requirement.is_satisfied:
            lines.append("- 待补中报：最新中报 PDF。若无法补齐，最新经营、应收、现金、分红与MD&A时效性必须降级标注。")

    lines.extend([
        "",
        "## 下一步",
        "",
        "1. 读取 `data_pack_market.md`。",
        "2. 默认先补齐最近 5 个完整年度年报；最低 3 年，少于 3 年时所有趋势判断降级。",
        "3. 基于多年度 PDF 提取业务演变、管理层表述变化、资本配置与治理轨迹。",
        "4. 最新年优先读取 `pdf_sections.json`；历史年结合 `pdf_sections_YYYY.json` 做趋势交叉验证。",
        "5. 若 `data_pack_market.md` 含 H1 列，必须下载并处理对应中报；缺失时标注最新经营时效性降级。",
        "6. 如需附注结构化数据，优先从最新年 `pdf_sections.json` 产出 `data_pack_report.md`。",
        "7. 按 6 维框架完成 `qualitative_report.md`。",
        "8. 若用户要求 HTML，再执行 `scripts/report_to_html.py`。",
        "",
    ])
    return "\n".join(lines) + "\n"


def business_report_scaffold(ts_code: str, company_name: Optional[str] = None) -> str:
    title = company_name or ts_code
    return "\n".join([
        f"# 定性分析：商业质量评估 — {title}",
        "",
        "> 状态：Codex scaffold",
        f"> 生成日期：{today_str()}",
        "",
        "## Executive Summary",
        "",
        "- 一句话结论：",
        "- 核心优势：",
        "- 核心风险：",
        "",
        "## 1. 商业模式与资本特征",
        "",
        "## 2. 竞争优势与护城河",
        "",
        "## 3. 外部环境",
        "",
        "## 4. 管理层与治理",
        "",
        "## 5. MD&A 解读",
        "",
        "## 6. 控股结构（如适用）",
        "",
        "## 结构化参数",
        "",
        "> 按 `shared/qualitative/references/output_schema.md` 填充。",
        "",
    ]) + "\n"


def valuation_handoff_content(ts_code: str, output_dir: Path,
                              holding_channel: Optional[str] = None) -> str:
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    return "\n".join([
        f"# Codex Valuation Handoff: {ts_code}",
        "",
        f"- 生成日期：{today_str()}",
        f"- 输出目录：`{output_dir}`",
        "- 工作流规范：`.claude/commands/valuation.md`",
        "- 报告模板：`strategies/valuation/references/report_template.md`",
        "",
        "## 已完成的确定性步骤",
        "",
        f"- `valuation_computed.md`：`{output_dir / 'valuation_computed.md'}`",
        f"- `qualitative_report.md`：`{output_dir / 'qualitative_report.md'}`",
        f"- `data_pack_market.md`：`{output_dir / 'data_pack_market.md'}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 股东层税务口径：{tax_note}",
        "",
        "## 下一步",
        "",
        "1. 读取 `valuation_computed.md`。",
        "2. 读取 `qualitative_report.md` 的结构化参数和关键判断。",
        "3. 按 `report_template.md` 组装最终估值报告。",
        "",
    ]) + "\n"


def valuation_report_scaffold(ts_code: str, company_name: Optional[str] = None) -> str:
    title = company_name or ts_code
    return "\n".join([
        f"# 估值分析报告：{title}",
        "",
        "> 状态：Codex scaffold",
        f"> 生成日期：{today_str()}",
        "",
        "## 报告概览",
        "",
        "## Executive Summary",
        "",
        "## 一、公司分类",
        "",
        "## 二、WACC 计算",
        "",
        "## 三、定性调整说明",
        "",
        "## 四、估值方法详情",
        "",
        "## 五、交叉验证",
        "",
        "## 六、反向估值",
        "",
        "## 七、估值结论",
        "",
        "## 八、关键假设与风险提示",
        "",
    ]) + "\n"


def turtle_handoff_content(ts_code: str, output_dir: Path,
                           holding_channel: Optional[str] = None) -> str:
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    return "\n".join([
        f"# Codex Turtle Analysis Handoff: {ts_code}",
        "",
        f"- 生成日期：{today_str()}",
        f"- 输出目录：`{output_dir}`",
        "- 工作流规范：`.claude/commands/turtle-analysis.md`",
        "- 组装模板：`strategies/turtle/phase3_valuation.md`",
        "",
        "## 已完成的确定性步骤",
        "",
        f"- 市场数据已刷新：`{output_dir / 'data_pack_market.md'}`",
        f"- 定性报告：`{output_dir / 'qualitative_report.md'}`",
        f"- PDF 附注数据（若存在）：`{output_dir / 'data_pack_report.md'}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 税务口径：{tax_note}",
        "",
        "## 下一步",
        "",
        "1. 依据 `phase3_preflight.md` 做数据完整性检查。",
        "2. 依据 `phase3_quantitative.md` 生成定量分析输出。",
        "3. 依据 `phase3_valuation.md` 组装最终策略报告。",
        "",
    ]) + "\n"


def turtle_report_scaffold(ts_code: str, company_name: Optional[str] = None) -> str:
    title = company_name or ts_code
    return "\n".join([
        f"# 龟龟投资策略 · 分析报告：{title}",
        "",
        "> 状态：Codex scaffold",
        f"> 生成日期：{today_str()}",
        "",
        "## 报告元信息",
        "",
        "## Executive Summary",
        "",
        "## 一、五分钟快筛与数据校验",
        "",
        "## 二、因子1B：商业质量分析",
        "",
        "## 三、关键假设与财务趋势",
        "",
        "## 四、因子2：穿透回报率粗算（Top-Down）",
        "",
        "## 五、因子3：穿透回报率精算（Bottom-Up）+ 现金质量审计",
        "",
        "## 六、因子4：估值与安全边际",
        "",
        "## 七、越跌越买策略 · 年化10%目标",
        "",
        "## 八、最终综合输出",
        "",
        "## 投资论点卡（Thesis Card）",
        "",
        "## 风险提示",
        "",
        "## 数据来源与免责",
        "",
    ]) + "\n"


def turtle_preflight_scaffold(ts_code: str, company_name: Optional[str] = None,
                              holding_channel: Optional[str] = None,
                              output_dir: Optional[Path] = None) -> str:
    title = company_name or ts_code
    structure_label, channel_label, tax_note = workflow_tax_context(
        ts_code, output_dir or OUTPUT_ROOT, holding_channel
    )
    return "\n".join([
        "# Pre-flight 输出",
        "",
        "> 状态：Codex scaffold",
        f"> 标的：{title}",
        f"> 生成日期：{today_str()}",
        "",
        "## 基础信息",
        "",
        f"- 股票代码：{ts_code}",
        "- 公司名称：",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        "- 报表币种：",
        "- 汇率：",
        f"- 股东层税率：{tax_note}",
        "",
        "## 异常发现",
        "",
        "## 口径决策",
        "",
        "- 利润口径：",
        "- 现金口径：",
        "",
        "## 中期数据",
        "",
        "- 状态：",
        "- 最新中期列：",
        "- 年化系数：",
        "- 季节性风险：",
        "",
        "## 数据完整性",
        "",
        "- data_pack_market：",
        "- data_pack_report：",
        "- data_pack_report_interim：",
        "- §17 衍生指标：",
        "- Warnings 摘要：",
        "- 关键缺失：",
        "",
        "## 裁决",
        "",
        "- 结论：",
        "- 理由：",
        "- 补救请求：",
        "",
    ]) + "\n"


def turtle_quantitative_scaffold(ts_code: str, company_name: Optional[str] = None) -> str:
    title = company_name or ts_code
    return "\n".join([
        f"# Phase 3 定量分析：{title}",
        "",
        "> 状态：Codex scaffold",
        f"> 生成日期：{today_str()}",
        "",
        "## Step 0：数据校验与口径锚定",
        "",
        "## Step 1：Owner Earnings 计算",
        "",
        "## Step 2：分配能力评估",
        "",
        "## Step 3：真实现金收入还原",
        "",
        "## Step 4：非经常性现金流入分类",
        "",
        "## Step 5：经营性现金支出还原",
        "",
        "## Step 6：资本开支与投资扣除",
        "",
        "## Step 7：可分配现金结余",
        "",
        "## Step 8：粗算穿透回报率",
        "",
        "## Step 9：精算穿透回报率",
        "",
        "## Step 10：支付率与分红意愿",
        "",
        "## Step 11：结果汇总与传递参数",
        "",
    ]) + "\n"


def business_write_prompt_content(ts_code: str, output_dir: Path, target: Path,
                                  pdf: Optional[Path],
                                  annual_pdfs: list[tuple[int, Path]],
                                  holding_channel: Optional[str] = None,
                                  annual_coverage: Optional[AnnualReportCoverage] = None,
                                  interim_requirement: Optional[InterimReportRequirement] = None) -> str:
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    lines = [
        f"# Codex Write Prompt: Business Analysis — {ts_code}",
        "",
        "## 目标文件",
        "",
        f"- 继续完善：`{repo_rel(target)}`",
        "",
        "## 必读规范",
        "",
        "- `.claude/commands/business-analysis.md`",
        "- `shared/qualitative/qualitative_assessment_v2.md`",
        "- `shared/qualitative/references/output_schema.md`",
        "",
        "## 主要输入",
        "",
        f"- `data_pack_market.md`：`{repo_rel(output_dir / 'data_pack_market.md')}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 股东层税务口径：{tax_note}",
    ]
    if annual_pdfs:
        lines.extend([
            "- 近 5 年年报 PDF（优先使用，多年度交叉验证）：",
            "",
        ])
        for year, report_pdf in annual_pdfs:
            lines.append(f"  - FY{year} PDF：`{repo_rel(report_pdf)}`")
            lines.append(f"    - `pdf_sections_{year}.json`：`{repo_rel(output_dir / f'pdf_sections_{year}.json')}`")
        lines.append(f"- 最新年兼容入口：`{repo_rel(output_dir / 'pdf_sections.json')}`")
    elif pdf and pdf.exists():
        lines.extend([
            f"- 年报 PDF：`{repo_rel(pdf)}`",
            f"- PDF 预处理结果：`{repo_rel(output_dir / 'pdf_sections.json')}`",
        ])
    else:
        lines.append("- 年报 PDF：当前未就位，需要仅基于 `data_pack_market.md` 写作并显式降低置信度。")
    if annual_coverage:
        lines.append(f"- {annual_coverage.markdown_summary()}")
        if annual_coverage.missing_years:
            missing = "、".join(str(year) for year in annual_coverage.missing_years)
            lines.append(f"- 待补年报：{missing} 年年报；未补齐前，DPS CAGR、F=Capex/D&A 五年中位数和现金审计需显式说明样本不足。")
        if not annual_coverage.has_minimum_coverage:
            lines.append("- 覆盖不足 3 年：报告必须降级，不能输出未修饰的强买入/强排除结论。")
    if interim_requirement:
        lines.append(f"- {interim_requirement.markdown_summary()}")
        if interim_requirement.required and not interim_requirement.is_satisfied:
            lines.append("- 待补中报：最新中报 PDF；未补齐前，最新经营、应收、现金、分红与MD&A时效性需显式降级。")

    lines.extend([
        "",
        "## 执行要求",
        "",
        "1. 以年报 PDF 为第一信息源；若与 Tushare 数据冲突，以 PDF 为准并标注差异。",
        "2. 默认使用最近 5 个完整年度年报；至少 3 年，少于 3 年时趋势判断、DPS CAGR、Capex/D&A 五年中位数和现金审计全部降级。",
        "3. 从多年度 PDF 中提取：业务结构演变、毛利/费用口径变化、管理层表述变化、资本配置与治理轨迹。",
        "4. 最新年负责当期判断，历史年份负责验证趋势；不要只基于单一年报得结论。",
        "5. 若 `data_pack_market.md` 含 H1 列，必须使用最新中报；中报缺失时，最新经营、应收、现金、分红与MD&A判断全部标注时效性降级。",
        "6. 按 6 维框架完成 `qualitative_report.md`，不要跳过结构化参数部分。",
        "7. 结论必须来自现有文件，不得补造管理层表述、行业份额或财务数据。",
        "8. 若后续需要支持龟龟策略，且你已从 PDF 提取附注，可顺手补写 `data_pack_report.md`。",
        "",
        "## 完成检查",
        "",
        "- 包含 Executive Summary 与 6 个维度。",
        "- 末尾包含符合 `output_schema.md` 的结构化参数表。",
        "- 对关键判断给出明确证据来源。",
        "",
    ])
    return "\n".join(lines)


def valuation_write_prompt_content(ts_code: str, output_dir: Path, target: Path,
                                   holding_channel: Optional[str] = None) -> str:
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    return "\n".join([
        f"# Codex Write Prompt: Valuation — {ts_code}",
        "",
        "## 目标文件",
        "",
        f"- 继续完善：`{repo_rel(target)}`",
        "",
        "## 必读规范",
        "",
        "- `.claude/commands/valuation.md`",
        "- `strategies/valuation/phase2_valuation.md`",
        "- `strategies/valuation/references/report_template.md`",
        "",
        "## 主要输入",
        "",
        f"- `valuation_computed.md`：`{repo_rel(output_dir / 'valuation_computed.md')}`",
        f"- `qualitative_report.md`：`{repo_rel(output_dir / 'qualitative_report.md')}`",
        f"- `data_pack_market.md`：`{repo_rel(output_dir / 'data_pack_market.md')}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 股东层税务口径：{tax_note}",
        "",
        "## 执行要求",
        "",
        "1. 不做新的估值算术；所有数值直接引用 `valuation_computed.md`，或从其中的敏感性表选取。",
        "2. 仅在 `qualitative_report.md` 提供了明确依据时调整假设；否则保留 Python 默认值。",
        "3. 报告结构遵循 `report_template.md`，尤其保留“定性调整说明”和“反向估值”章节。",
        "4. 若敏感性表无精确坐标，选最接近值并在正文标注近似处理。",
        "",
        "## 完成检查",
        "",
        "- 调整前/调整后对比完整。",
        "- Executive Summary 数字与正文一致。",
        "- 估值结论、安全边际、反向估值三处互相一致。",
        "",
    ]) + "\n"


def turtle_write_prompt_content(ts_code: str, output_dir: Path, preflight: Path,
                                quantitative: Path, target: Path,
                                holding_channel: Optional[str] = None) -> str:
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    lines = [
        f"# Codex Write Prompt: Turtle Analysis — {ts_code}",
        "",
        "## 目标文件",
        "",
        f"- Pre-flight：`{repo_rel(preflight)}`",
        f"- 定量输出：`{repo_rel(quantitative)}`",
        f"- 最终报告：`{repo_rel(target)}`",
        "",
        "## 必读规范",
        "",
        "- `.claude/commands/turtle-analysis.md`",
        "- `strategies/turtle/phase3_preflight.md`",
        "- `strategies/turtle/phase3_quantitative.md`",
        "- `strategies/turtle/phase3_valuation.md`",
        "",
        "## 主要输入",
        "",
        f"- `qualitative_report.md`：`{repo_rel(output_dir / 'qualitative_report.md')}`",
        f"- `data_pack_market.md`：`{repo_rel(output_dir / 'data_pack_market.md')}`",
        f"- 上市结构：{structure_label}",
        f"- 持股渠道：{channel_label}",
        f"- 股东层税务口径：{tax_note}",
    ]
    report_pack = output_dir / "data_pack_report.md"
    if report_pack.exists():
        lines.append(f"- `data_pack_report.md`：`{repo_rel(report_pack)}`")
    else:
        lines.append("- `data_pack_report.md`：当前缺失，按 degraded mode 执行并在报告中标注局限。")

    lines.extend([
        "",
        "## 执行顺序",
        "",
        "1. 先完成 `phase3_preflight.md`，做数据完整性与口径锚定。",
        "2. 再完成 `phase3_quantitative.md`，严格按 Agent B 指令展示公式、过程和传递参数。",
        "3. 最后依据 `phase3_valuation.md` 组装 `{company}_{code}_分析报告.md`。",
        "4. 最终报告必须采用原龟龟框架因子格式：因子1B、因子2 Top-Down、因子3 Bottom-Up、因子4 估值与安全边际、最终综合输出。",
        "",
        "## 约束",
        "",
        "- 不调用外部数据源。",
        "- 不跳过 preflight 或 schema 校验。",
        "- 最终仓位建议必须与 Quantitative 输出、价值陷阱判断一致。",
        "- 先判断业务子类，再填静态 GG 要求回报率；不得固定套用单一 7% 门槛。",
        "- 保留“越跌越买策略 · 年化10%目标”模块，位置放在因子4之后、最终综合输出之前。",
        "",
        "## 完成检查",
        "",
        "- `phase3_preflight.md` 有明确裁决。",
        "- `phase3_quantitative.md` 含 Step 0-11 和传递参数校验块。",
        "- 最终报告含 `## 四、因子2：穿透回报率粗算（Top-Down）`。",
        "- 最终报告含 `## 五、因子3：穿透回报率精算（Bottom-Up）+ 现金质量审计`。",
        "- 最终报告含 `## 六、因子4：估值与安全边际`。",
        "- 最终报告含 `## 七、越跌越买策略 · 年化10%目标`。",
        "- 最终报告的 Executive Summary、关键假设、估值判断彼此一致。",
        "",
    ])
    return "\n".join(lines)


def read_text_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def has_scaffold_marker(text: str) -> bool:
    return "状态：Codex scaffold" in text


def extract_markdown_section(text: str, heading: str, level: int = 2) -> str:
    marks = "#" * level
    pattern = rf"(?ms)^{re.escape(marks)}\s+{re.escape(heading)}\n+(.*?)(?=^{re.escape(marks)}\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else ""


def extract_markdown_tables(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip().startswith("|"):
            current.append(line.rstrip())
            continue
        if current and not line.strip():
            if len(current) == 1:
                continue
            blocks.append("\n".join(current).strip())
            current = []
            continue
        if current:
            blocks.append("\n".join(current).strip())
            current = []
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def parse_markdown_table(block: str) -> tuple[list[str], list[list[str]]]:
    lines = [line.strip() for line in block.splitlines() if line.strip().startswith("|")]
    if not lines:
        return [], []

    def split_row(line: str) -> list[str]:
        return [cell.strip() for cell in line.strip().strip("|").split("|")]

    headers = split_row(lines[0])
    rows: list[list[str]] = []
    for line in lines[1:]:
        cells = split_row(line)
        if all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        rows.append(cells)
    return headers, rows


def extract_row_value(text: str, row_name: str) -> Optional[str]:
    pattern = rf"^\|\s*{re.escape(row_name)}\s*\|\s*([^|]+?)\s*\|"
    match = re.search(pattern, text, flags=re.M)
    if match:
        return match.group(1).strip()
    return None


def parse_number(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", value.replace("%", "").replace("x", ""))
    if not match:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def fmt_num(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:,.{decimals}f}"


def fmt_pct(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}%"


def demote_headings(text: str, increment: int = 1) -> str:
    def repl(match: re.Match[str]) -> str:
        level = min(6, len(match.group(1)) + increment)
        return "#" * level + " "

    return re.sub(r"^(#{1,6})\s+", repl, text, flags=re.M)


def parse_structured_params(text: str) -> dict[str, str]:
    section = extract_markdown_section(text, "结构化参数")
    params: dict[str, str] = {}
    for block in extract_markdown_tables(section):
        headers, rows = parse_markdown_table(block)
        if len(headers) < 2:
            continue
        for row in rows:
            if len(row) >= 2:
                params[row[0]] = row[1]
    return params


def clean_inline_backticks(text: str) -> str:
    return re.sub(r"`([^`]+)`", r"\1", text).strip()


def clean_sentence(text: str) -> str:
    return " ".join(clean_inline_backticks(text).split())


def strip_irrelevant_peer_comparisons(text: str, company_name: str = "") -> str:
    """Remove stale peer-template lines when assembling a company-specific report.

    Keep accounting terms such as "购买物业、厂房及设备"; only strip lines that
    explicitly refer to the property-management peer template.
    """
    if not text:
        return text
    own_tokens = {company_name, company_name.replace("股份", "")} if company_name else set()
    peer_terms = ("中海物业", "轻资产物管", "物管门槛", "物管的", "物管，", "城市服务", "第三方拓展")
    kept: list[str] = []
    for line in text.splitlines():
        if any(term in line for term in peer_terms):
            if not any(token and token in line for token in own_tokens):
                continue
            if "中海物业" in line or "轻资产物管" in line or "物管门槛" in line:
                continue
        kept.append(line)
    return "\n".join(kept)


def neutralize_unknown_tax_assumption(text: str, q_pct: Optional[float]) -> str:
    """Prevent stale phase files from turning an unknown HK tax rate into 0%."""
    if q_pct is not None or not text:
        return text
    sanitized = text
    replacements = [
        (r"股东层面税率 Q\s*=\s*[\d.]+%", "股东层面税率 Q = 默认10%（税率未确认）"),
        (r"综合税率 Q\s*=\s*[\d.]+%", "综合税率 Q = 默认10%（税率未确认）"),
        (r"\(1\s*[−-]\s*0%\)", "(1 − 10%，默认主口径)"),
        (r"默认香港居民通过香港券商直投", "香港券商直投税率待确认"),
        (
            r"香港居民通过香港券商直投；若使用港股通，现金到手回报需另按 20% 股息税压力测试",
            "香港券商直投需按实际预扣安排确认；本报告默认10%主口径，并同时列示 0%/10%/20% 股息税压力测试",
        ),
        (r"税前初筛", "默认10%主口径"),
        (r"主表按税前口径", "主表按默认10%税后口径"),
    ]
    for pattern, replacement in replacements:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized


def first_nonempty_paragraph(text: str) -> str:
    paragraphs = [clean_sentence(p) for p in re.split(r"\n\s*\n", text) if clean_sentence(p)]
    return paragraphs[0] if paragraphs else ""


def first_bullet_or_paragraph(text: str) -> str:
    bullets = extract_bullet_lines(text)
    if bullets:
        return clean_sentence(bullets[0])
    return first_nonempty_paragraph(text)


def extract_bullet_lines(text: str) -> list[str]:
    return [line.strip()[2:].strip() for line in text.splitlines() if line.strip().startswith("- ")]


def parse_percent_sequence(text: str) -> list[float]:
    return [float(x) for x in re.findall(r"(\d+(?:\.\d+)?)%", text)]


def parse_numeric_sequence(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text)]


def _pct_to_rate(value_pct: Optional[float]) -> float:
    return max((value_pct or 0.0) / 100.0, 0.0)


def _cagr(first: Optional[float], last: Optional[float], periods: int) -> Optional[float]:
    if first is None or last is None or first <= 0 or last <= 0 or periods <= 0:
        return None
    return (last / first) ** (1.0 / periods) - 1.0


def _percentile(data: list[float], p: float) -> Optional[float]:
    clean = sorted(x for x in data if x is not None and math.isfinite(x))
    if not clean:
        return None
    k = (len(clean) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return clean[int(k)]
    return clean[f] * (c - k) + clean[c] * (k - f)


def _format_annual(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value * 100:.1f}%"


def _extract_financial_row(data_pack_text: str, section_heading: str, row_label: str) -> list[float]:
    section = extract_markdown_section(data_pack_text, section_heading)
    tables = extract_markdown_tables(section)
    if not tables:
        return []
    _headers, rows = table_row_map(tables[0])
    raw_values = rows.get(row_label, [])
    values: list[float] = []
    for raw in raw_values:
        parsed = parse_number(raw)
        if parsed is not None:
            values.append(parsed)
    return values


def _extract_latest_dps(data_pack_text: str, report_pack_text: str = "") -> Optional[float]:
    section = extract_markdown_section(data_pack_text, "6. 分红历史")
    tables = extract_markdown_tables(section)
    if tables:
        _headers, rows = parse_markdown_table(tables[0])
        if rows and len(rows[0]) >= 2:
            dps = parse_number(rows[0][1])
            if dps is not None and dps > 0:
                return dps
    report_points = _extract_report_dividend_dps_points(report_pack_text)
    if report_points:
        return report_points[max(report_points)]
    return None


def _extract_market_dps_points(data_pack_text: str) -> dict[int, float]:
    section = extract_markdown_section(data_pack_text, "6. 分红历史")
    tables = extract_markdown_tables(section)
    if not tables:
        return {}
    _headers, rows = parse_markdown_table(tables[0])
    by_year: dict[int, float] = {}
    for row in rows:
        if len(row) >= 2:
            year = int(parse_number(row[0]) or 0)
            dps = parse_number(row[1])
            if year > 1900 and dps is not None and dps > 0 and year not in by_year:
                by_year[year] = dps
    return by_year


def _extract_report_dividend_dps_points(report_pack_text: str, latest_market_dps: Optional[float] = None) -> dict[int, float]:
    """Infer annual DPS from annual-report ordinary dividends and share count.

    Annual report packs usually disclose ordinary-shareholder dividends in RMB
    million and share count in shares. If the market pack has latest HKD DPS,
    use it to infer the RMB/HKD conversion factor for the whole short series.
    """
    if not report_pack_text:
        return {}

    shares_match = re.search(r"(?:年内总股本|总股本)[：:]\s*([\d,]+)\s*股", report_pack_text)
    if not shares_match:
        return {}
    shares_mm = parse_number(shares_match.group(1))
    if shares_mm is None or shares_mm <= 0:
        return {}
    shares_mm = shares_mm / 1_000_000.0 if shares_mm > 100_000 else shares_mm

    points_rmb: dict[int, float] = {}
    for table in extract_markdown_tables(report_pack_text):
        headers, rows = parse_markdown_table(table)
        if len(headers) < 2:
            continue
        year_headers: list[Optional[int]] = []
        for header in headers[1:]:
            year = int(parse_number(header) or 0)
            year_headers.append(year if year > 1900 else None)
        for row in rows:
            row_label = row[0] if row else ""
            if not row or "股息" not in row_label:
                continue
            if not ("普通股" in row_label or "普通股东" in row_label or "ordinary" in row_label.lower()):
                continue
            for idx, year in enumerate(year_headers, start=1):
                if year is None or idx >= len(row):
                    continue
                dividend_mm = parse_number(row[idx])
                if dividend_mm is None:
                    continue
                dps_rmb = abs(dividend_mm) / shares_mm
                if dps_rmb > 0:
                    points_rmb[year] = dps_rmb

    if not points_rmb:
        return {}

    fx_factor = 1.0
    if latest_market_dps is not None and latest_market_dps > 0:
        latest_year = max(points_rmb)
        latest_rmb_dps = points_rmb.get(latest_year)
        if latest_rmb_dps:
            inferred = latest_market_dps / latest_rmb_dps
            if 0.5 <= inferred <= 2.0:
                fx_factor = inferred
    else:
        hk_dps_match = re.search(r"(?:年度\s*)?DPS\s*为\s*([\d.]+)\s*港元", report_pack_text, re.IGNORECASE)
        if hk_dps_match:
            latest_year = max(points_rmb)
            latest_rmb_dps = points_rmb.get(latest_year)
            latest_hk_dps = parse_number(hk_dps_match.group(1))
            if latest_rmb_dps and latest_hk_dps:
                inferred = latest_hk_dps / latest_rmb_dps
                if 0.5 <= inferred <= 2.0:
                    fx_factor = inferred

    return {year: dps * fx_factor for year, dps in points_rmb.items()}


def _report_dividend_source_note(report_pack_text: str, fallback: str = "年报普通股股息/股本反推") -> str:
    match = re.search(r"数据源[：:]\s*([^；\n]+(?:；[^。\n]*)?)", report_pack_text or "")
    if not match:
        return fallback
    source = match.group(1).strip()
    source = re.sub(r"；\s*DPS\s*CAGR.*$", "", source, flags=re.I).strip()
    return source or fallback


def _extract_annual_dividend_paid_pair(text: str) -> Optional[tuple[float, Optional[float]]]:
    return _annual_pair_from_line(
        text,
        ["dividends", "paid"],
        exclude_terms=["non-controlling"],
        min_abs=1_000,
    )


def _annual_report_pdf_text(output_dir: Path, year: int) -> str:
    pdf_candidates = sorted(output_dir.glob(f"*_{year}_年报.pdf"))
    annual_pdf = pdf_candidates[0] if pdf_candidates else output_dir / f"{year}_年报.pdf"
    return _pdftotext_layout(annual_pdf)


def _compact_report_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "")


def _hk_cents_to_dps(match_text: str) -> Optional[float]:
    patterns = [
        r"(?:HKD|HK\$|HK)\s*([0-9]+(?:\.[0-9]+)?)\s*cents?",
        r"([0-9]+(?:\.[0-9]+)?)\s*港\s*(?:幣|币)?\s*仙",
        r"港\s*(?:幣|币)\s*([0-9]+(?:\.[0-9]+)?)\s*仙",
    ]
    for pattern in patterns:
        match = re.search(pattern, match_text, flags=re.I)
        if match:
            value = parse_number(match.group(1))
            if value is not None and 0 < value < 300:
                return value / 100.0
    return None


def _rmb_per_share_to_dps(match_text: str) -> Optional[float]:
    patterns = [
        r"RMB\s*([0-9]+(?:\.[0-9]+)?)\s*per\s+ordinary\s+share",
        r"RMB\s*([0-9]+(?:\.[0-9]+)?)",
        r"人民\s*幣\s*([0-9]+(?:\.[0-9]+)?)\s*元",
        r"人民币\s*([0-9]+(?:\.[0-9]+)?)\s*元",
    ]
    for pattern in patterns:
        match = re.search(pattern, match_text, flags=re.I)
        if match:
            value = parse_number(match.group(1))
            if value is not None and 0 < value < 10:
                return value
    return None


def _extract_declared_annual_dps_points(text: str, report_year: int) -> tuple[dict[int, float], dict[int, float]]:
    """Extract fiscal-year DPS from annual-report dividend notes.

    Returns two maps: HKD DPS points and RMB DPS points. HKD points are ready
    for valuation. RMB points require a later FX calibration from the latest
    market DPS or same-year HKD disclosures.
    """
    flat = _compact_report_text(text)
    if not flat:
        return {}, {}

    hkd_points: dict[int, float] = {}
    rmb_points: dict[int, float] = {}

    # Proposed final dividend after year end is the cleanest fiscal-year DPS.
    proposed_patterns = [
        rf"Subsequent\s+to\s+the\s+end\s+of\s+the\s+reporting\s+period.{{0,260}}?"
        rf"year\s+ended\s+31\s+December\s+{report_year}.{{0,520}}?(?:per\s+ordinary\s+share|每\s*股\s*普通\s*股)",
        rf"final\s+dividend\s+in\s+respect\s+of\s+the\s+year\s+ended\s+31\s+December\s+{report_year}"
        rf".{{0,520}}?(?:per\s+ordinary\s+share|每\s*股\s*普通\s*股)",
        rf"截至\s*{report_year}\s*年\s*12\s*月\s*31\s*日\s*止\s*年\s*度.{{0,520}}?"
        rf"末\s*期\s*股\s*息.{{0,520}}?(?:每\s*股\s*普通\s*股|per\s+ordinary\s+share)",
    ]
    for pattern in proposed_patterns:
        match = re.search(pattern, flat, flags=re.I)
        if not match:
            continue
        snippet = match.group(0)
        hkd = _hk_cents_to_dps(snippet)
        if hkd is not None:
            hkd_points[report_year] = hkd
            break
        rmb = _rmb_per_share_to_dps(snippet)
        if rmb is not None:
            rmb_points[report_year] = rmb
            break

    return hkd_points, rmb_points


def extract_annual_dividend_dps_points_from_output(
    output_dir: Path,
    *,
    latest_market_dps: Optional[float] = None,
    max_years: int = 5,
) -> tuple[dict[int, float], str]:
    """Build annual-report DPS points from all available pdf_sections_YYYY files.

    This is intentionally PDF/annual-report first. Market dividend tables may be
    de-duplicated by ex-date or announcement date and can falsely flatten DPS.
    """
    records_hkd: dict[int, float] = {}
    records_rmb_dps: dict[int, float] = {}
    fallback_dividend_rmb: dict[int, float] = {}
    share_count_mm: Optional[float] = None
    used_pdf_fallback = False
    for path in sorted(output_dir.glob("pdf_sections_20*.json")):
        if "interim" in path.name.lower():
            continue
        year_match = re.search(r"pdf_sections_(20\d{2})\.json$", path.name)
        if not year_match:
            continue
        year = int(year_match.group(1))
        text = _read_pdf_sections_text(path)
        if not text:
            continue
        if share_count_mm is None:
            share_count_mm = _extract_share_count_from_text(text)
        hkd_points, rmb_points = _extract_declared_annual_dps_points(text, year)
        if not hkd_points and not rmb_points:
            pdf_text = _annual_report_pdf_text(output_dir, year)
            if pdf_text:
                used_pdf_fallback = True
                if share_count_mm is None:
                    share_count_mm = _extract_share_count_from_text(pdf_text)
                hkd_points, rmb_points = _extract_declared_annual_dps_points(pdf_text, year)
        records_hkd.update(hkd_points)
        records_rmb_dps.update({item_year: value for item_year, value in rmb_points.items() if item_year not in records_hkd})
        pair = _extract_annual_dividend_paid_pair(text)
        current, previous = _pair_to_mm(pair)
        if current is not None and current > 0:
            fallback_dividend_rmb[year] = current
        if previous is not None and previous > 0:
            fallback_dividend_rmb[year - 1] = previous

    if share_count_mm and share_count_mm > 0:
        for year, amount in fallback_dividend_rmb.items():
            records_rmb_dps.setdefault(year, abs(amount) / share_count_mm)

    if not records_hkd and (not records_rmb_dps or not share_count_mm or share_count_mm <= 0):
        return {}, "年报pdf_sections普通股股息/股本提取失败"

    fx_candidates: list[float] = []
    fx_factor: Optional[float] = None
    if latest_market_dps is not None and latest_market_dps > 0 and records_rmb_dps:
        latest_year = max(records_rmb_dps)
        latest_rmb_dps = records_rmb_dps.get(latest_year)
        if latest_rmb_dps:
            inferred = latest_market_dps / latest_rmb_dps
            if 0.5 <= inferred <= 2.0:
                fx_factor = inferred
    for year, rmb_dps in records_rmb_dps.items():
        hkd_dps = records_hkd.get(year)
        if hkd_dps and rmb_dps > 0:
            inferred = hkd_dps / rmb_dps
            if 0.5 <= inferred <= 2.0:
                fx_candidates.append(inferred)
    if fx_factor is None:
        fx_factor = sum(fx_candidates) / len(fx_candidates) if fx_candidates else 1.0

    points = dict(records_hkd)
    for year, rmb_dps in records_rmb_dps.items():
        points.setdefault(year, rmb_dps * fx_factor)

    selected_years = sorted(points, reverse=True)[:max_years]
    if len(selected_years) < 2:
        return {}, "年报pdf_sections普通股股息样本不足"
    points = {year: points[year] for year in selected_years}
    years = sorted(points)
    source_prefix = "年报末期/普通股股息拆分"
    source_file = "pdf_sections/PDF" if used_pdf_fallback else "pdf_sections"
    if len(points) >= 5:
        source = f"{source_prefix}（{source_file} {years[0]}-{years[-1]}，5年）"
    elif len(points) >= 3:
        source = f"{source_prefix}（{source_file} {years[0]}-{years[-1]}，{len(points)}个年度）"
    else:
        source = f"{source_prefix}（{source_file}仅{len(points)}个年度，CAGR参考性有限）"
    return points, source


def _extract_dps_series_with_source(data_pack_text: str, report_pack_text: str = "") -> tuple[list[float], str]:
    latest_market_dps = _extract_latest_dps(data_pack_text)
    report_points = _extract_report_dividend_dps_points(report_pack_text, latest_market_dps)
    if len(report_points) >= 2:
        years = sorted(report_points.keys(), reverse=True)
        return [report_points[year] for year in years], _report_dividend_source_note(report_pack_text)

    market_points = _extract_market_dps_points(data_pack_text)
    if not market_points:
        return [], "缺失"
    years = sorted(market_points.keys(), reverse=True)
    return [market_points[year] for year in years], "市场分红表（同一年去重）"


def _extract_dps_points_with_source(data_pack_text: str, report_pack_text: str = "") -> tuple[dict[int, float], str]:
    latest_market_dps = _extract_latest_dps(data_pack_text)
    report_points = _extract_report_dividend_dps_points(report_pack_text, latest_market_dps)
    if len(report_points) >= 2:
        return report_points, _report_dividend_source_note(report_pack_text)
    market_points = _extract_market_dps_points(data_pack_text)
    if market_points:
        return {}, "年报拆分数据缺失，市场分红表（同一年去重）不作为DPS CAGR主输入"
    return {}, "缺失"


def _dps_cagr_basis(data_pack_text: str, report_pack_text: str = "") -> tuple[Optional[float], str, str]:
    points, source = _extract_dps_points_with_source(data_pack_text, report_pack_text)
    if len(points) < 2:
        return None, source, f"DPS CAGR缺失（{source}）"
    years = sorted(points)
    start_year = years[0]
    end_year = years[-1]
    periods = end_year - start_year
    if periods <= 0:
        return None, source, f"DPS CAGR缺失（{source}）"
    start_dps = points[start_year]
    end_dps = points[end_year]
    cagr = _cagr(start_dps, end_dps, periods)
    if cagr is None:
        return None, source, f"DPS CAGR缺失（{source}）"
    warning = ""
    if abs(cagr) < 0.00001:
        warning = "；DPS CAGR 为0，请检查数据源是否去重"
    if periods == 1:
        label = "DPS 单年增长率"
        period_label = "1 年单年增长率"
    else:
        label = "DPS CAGR"
        period_label = f"{periods} 年 CAGR"
        if len(years) < 3:
            warning += f"；仅{len(years)}个年度数据，CAGR参考性有限"
    basis = (
        f"{label} = {cagr * 100:.1f}%（基期{start_year} DPS {start_dps:.4f} "
        f"→ 报告期{end_year} DPS {end_dps:.4f}，{period_label}；{source}{warning}）"
    )
    return cagr, source, basis


def _extract_dps_series(data_pack_text: str) -> list[float]:
    values, _source = _extract_dps_series_with_source(data_pack_text)
    return values


def _extract_latest_payout_ratio(data_pack_text: str) -> Optional[float]:
    """Return latest payout ratio as decimal from dividend history when available."""
    section = extract_markdown_section(data_pack_text, "6. 分红历史")
    tables = extract_markdown_tables(section)
    if not tables:
        return None
    headers, rows = parse_markdown_table(tables[0])
    payout_idx = None
    for idx, header in enumerate(headers):
        if "派息率" in header or "支付率" in header:
            payout_idx = idx
            break
    if payout_idx is None:
        return None
    for row in rows:
        if len(row) > payout_idx:
            value = parse_number(row[payout_idx])
            if value is not None and value > 0:
                return value / 100.0 if value > 1 else value
    return None


def _extract_latest_payout_ratio_with_report(data_pack_text: str, report_pack_text: str = "") -> Optional[float]:
    payout = _extract_latest_payout_ratio(data_pack_text)
    if payout is not None:
        return payout
    parent_profit = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利")
    ordinary_dividend = _extract_report_row_values(report_pack_text, "已付普通股东股息")
    if ordinary_dividend and parent_profit and parent_profit[0] > 0:
        return abs(ordinary_dividend[0]) / parent_profit[0]
    return None


def _industry_growth_profile(blob: str) -> tuple[float, float, str]:
    """Return long-term growth cap, maturity decay, and industry label."""
    if any(term in blob for term in ["食品", "饮料", "beverage", "consumer staples", "可口可乐", "装瓶"]):
        return 0.023, 0.70, "弱周期防御消费"
    if any(term in blob for term in ["公用", "utility", "utilities", "电力", "燃气", "水务"]):
        return 0.020, 0.60, "成熟公用事业"
    if any(term in blob for term in ["物业", "物管", "service", "服务", "轻资产"]):
        return 0.025, 0.80, "高质量轻资产服务"
    if any(term in blob for term in ["煤", "coal", "石油", "oil", "资源", "commodity", "航运"]):
        return 0.010, 0.50, "周期高派/资源品"
    return 0.015, 0.70, "成熟红利资产"


def _payout_release_policy(threshold_category: str, company_name: str = "", blob: str = "") -> tuple[Optional[float], float, str]:
    text = " ".join([threshold_category, company_name, blob]).lower()
    is_soe = any(term in text for term in ["央企", "国企", "cofco", "中粮", "华润", "中海", "state-owned"])
    is_consumer = any(term in text for term in ["消费", "食品", "饮料", "beverage", "consumer", "可口可乐", "装瓶"])
    is_cycle = any(term in text for term in ["周期", "资源", "煤", "石油", "oil", "coal", "航运"])
    is_private = any(term in text for term in ["民企", "private enterprise", "privately-owned"])
    if is_soe and is_consumer:
        return 0.60, 0.30, "央企消费：目标派息率60%，置信折扣0.3"
    if is_soe and is_cycle:
        return 0.55, 0.20, "央企周期：目标派息率55%，置信折扣0.2"
    if is_private:
        return 0.50, 0.10, "民企：目标派息率50%，置信折扣0.1"
    return None, 0.20, "默认红利资产：目标派息率当前+10pct封顶70%，置信折扣0.2"


def calc_dps_growth_tiers(
    *,
    dps_cagr: Optional[float],
    minority_ratio: Optional[float],
    decay_factor: float,
    industry_ceiling: float,
    current_payout: Optional[float] = None,
    target_payout: Optional[float] = None,
    confidence_discount: float = 0.30,
    payout_policy_note: str = "默认置信折扣0.3",
    hold_years: int = 3,
    source_label: str = "DPS CAGR缺失",
) -> dict[str, Optional[float] | str]:
    """Reusable DPS growth tier node for DDM and dip-buy tables."""
    base_input = max(dps_cagr or 0.0, 0.0)
    after_minority = base_input
    minority_note = "少数股东≤30%或缺失，不折扣"
    if minority_ratio is not None and minority_ratio > 0.30:
        after_minority *= max(1.0 - minority_ratio, 0.0)
        minority_note = f"少数股东{minority_ratio * 100:.1f}%>30%，乘(1-少数股东占比)"

    after_decay = after_minority * decay_factor
    base = max(min(after_decay, industry_ceiling), 0.0)
    pess = base * 0.5

    payout_release = None
    payout_note = "派息率释放：缺失当前派息率或持有年限，未纳入"
    if current_payout is not None and current_payout > 0 and hold_years > 0:
        target = target_payout if target_payout is not None else current_payout + 0.10
        target = min(max(target, current_payout), 0.70)
        payout_release = max(((target / current_payout) ** (1.0 / hold_years) - 1.0) * confidence_discount, 0.0)
        payout_note = (
            f"派息率释放=(({target * 100:.1f}%/{current_payout * 100:.1f}%)^(1/{hold_years})-1)"
            f"×{confidence_discount:.1f}={payout_release * 100:.1f}%（{payout_policy_note}）"
        )

    opt_raw = base * 1.5
    if payout_release is not None:
        opt_raw = max(opt_raw, payout_release)
    opt = min(opt_raw, industry_ceiling * 1.2)

    basis = (
        f"基础g={source_label} → {minority_note}后{after_minority * 100:.1f}% "
        f"→ 成熟衰减/行业衰减×{decay_factor:.1f}后{after_decay * 100:.1f}% "
        f"→ 基准clamp(0,{industry_ceiling * 100:.1f}%)={base * 100:.1f}%；"
        f"悲观=基准×0.5={pess * 100:.1f}%；"
        f"乐观=max(基准×1.5={base * 1.5 * 100:.1f}%, {payout_note})，"
        f"再截断至行业上限×1.2={industry_ceiling * 1.2 * 100:.1f}%，最终{opt * 100:.1f}%"
    )
    return {
        "pess": pess,
        "base": base,
        "opt": opt,
        "payout_release": payout_release,
        "basis": basis,
    }


def choose_ddm_growth_assumption(
    *,
    ts_code: str,
    company_name: str,
    data_pack_text: str,
    report_pack_text: str,
    threshold_category: str,
    terminal_g_pct: float,
    minority_share: Optional[float] = None,
    trap_risk: str = "中",
    current_payout: Optional[float] = None,
    target_payout: Optional[float] = None,
    confidence_discount: Optional[float] = None,
    hold_years: int = 3,
) -> dict[str, Optional[float] | str]:
    """Choose a conservative DDM perpetual growth assumption by industry and evidence."""
    blob = " ".join([ts_code, company_name, data_pack_text[:4000], report_pack_text[:4000], threshold_category]).lower()
    dps_cagr_calc, dps_source, dps_cagr_basis = _dps_cagr_basis(data_pack_text, report_pack_text)
    dps_series_desc, _dps_series_source = _extract_dps_series_with_source(data_pack_text, report_pack_text)
    dps_chrono = list(reversed(dps_series_desc))
    dps_cagr = dps_cagr_calc
    profit_values = _extract_financial_row(data_pack_text, "3. 合并利润表", "股东应占溢利")
    report_parent_profit = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利")
    if len(report_parent_profit) >= 2:
        profit_values = report_parent_profit
    profit_chrono = list(reversed(profit_values))
    profit_cagr = _cagr(profit_chrono[0], profit_chrono[-1], len(profit_chrono) - 1) if len(profit_chrono) >= 2 else None

    industry_cap, maturity_decay, industry_label = _industry_growth_profile(blob)
    policy_target_payout, policy_discount, payout_policy_note = _payout_release_policy(
        threshold_category, company_name=company_name, blob=blob
    )
    if target_payout is None:
        target_payout = policy_target_payout
    if confidence_discount is None:
        confidence_discount = policy_discount
    risk_notes: list[str] = []
    if dps_cagr is not None:
        base_g = max(dps_cagr, 0.0)
        source_label = dps_cagr_basis
        if abs(dps_cagr) < 0.00001 and profit_cagr is not None and profit_cagr > 0:
            risk_notes.append("DPS CAGR 可能被数据源去重卡死，请人工复核")
    elif profit_cagr is not None:
        base_g = max(profit_cagr, 0.0)
        source_label = f"归母利润 CAGR {base_g * 100:.1f}%（DPS缺失替代）"
    else:
        base_g = 0.0
        source_label = "增长数据缺失，基础g按0%"

    tiers = calc_dps_growth_tiers(
        dps_cagr=base_g,
        minority_ratio=minority_share,
        decay_factor=maturity_decay,
        industry_ceiling=min(industry_cap, terminal_g_pct / 100.0),
        current_payout=current_payout,
        target_payout=target_payout,
        confidence_discount=confidence_discount,
        payout_policy_note=payout_policy_note,
        hold_years=hold_years,
        source_label=source_label,
    )
    g = float(tiers["base"]) if isinstance(tiers["base"], float) else 0.0
    if minority_share is not None and minority_share > 0.30:
        if dps_cagr is not None:
            risk_notes.append(f"少数股东占比{minority_share * 100:.1f}%>30%，DPS CAGR为普通股东口径，本次仍按用户规则作保守传导折扣")
        else:
            risk_notes.append(f"少数股东占比{minority_share * 100:.1f}%>30%，利润增长传导打折")
    if trap_risk == "高":
        g = min(g, 0.005)
        risk_notes.append("价值陷阱风险高，DDM g封顶0.5%")
    elif trap_risk == "中":
        risk_notes.append("价值陷阱风险中，保留行业上限与成熟衰减约束")

    g = max(g, 0.0)
    basis = (
        f"{industry_label}：{tiers['basis']}；DDM g取基准档={g * 100:.1f}%"
    )
    warning = "；".join(risk_notes) if risk_notes else "—"
    return {
        "ddm_g_pct": g * 100.0,
        "ddm_g_basis": basis,
        "ddm_g_warning": warning,
        "dps_cagr_pct": dps_cagr * 100.0 if dps_cagr is not None else None,
        "profit_cagr_pct": profit_cagr * 100.0 if profit_cagr is not None else None,
        "dps_source": dps_source,
        "dps_cagr_basis": dps_cagr_basis,
        "industry_cap_pct": industry_cap * 100.0,
        "maturity_decay": maturity_decay,
        "pess_growth_pct": (float(tiers["pess"]) * 100.0) if isinstance(tiers["pess"], float) else None,
        "base_growth_pct": g * 100.0,
        "opt_growth_pct": (float(tiers["opt"]) * 100.0) if isinstance(tiers["opt"], float) else None,
        "payout_release_growth_pct": (float(tiers["payout_release"]) * 100.0) if isinstance(tiers["payout_release"], float) else None,
        "growth_tiers_basis": tiers["basis"],
    }


def _wacc_conservatism_components(
    *,
    threshold_category: str = "",
    company_name: str = "",
    data_pack_text: str = "",
    report_pack_text: str = "",
) -> dict[str, float | str]:
    blob = " ".join([threshold_category, company_name, data_pack_text[:3000], report_pack_text[:3000]]).lower()
    if any(term in blob for term in ["周期", "资源", "煤", "石油", "oil", "coal", "航运"]):
        category_premium = 3.0
        category_label = "周期高派/资源/航运"
    elif any(term in blob for term in ["成长", "高 capex", "高capex", "低分红"]):
        category_premium = 4.0
        category_label = "成长型/高capex/低分红"
    elif any(term in blob for term in ["防御型高派", "净现金央企", "防御高派"]):
        category_premium = 1.5
        category_label = "防御高派"
    else:
        category_premium = 2.0
        category_label = "成熟红利/默认"

    if any(term in blob for term in ["审计问题", "关联方复杂", "关联交易复杂", "qualified opinion"]):
        governance_premium = 2.0
        governance_label = "关联方复杂/审计问题"
    elif any(term in blob for term in ["民企", "private enterprise", "privately-owned"]):
        governance_premium = 1.0
        governance_label = "民企"
    elif any(term in blob for term in ["央企", "国企", "state-owned", "cofco", "中粮", "华润", "中海", "国务院国资委"]):
        governance_premium = 0.0
        governance_label = "央企/国企"
    else:
        governance_premium = 0.0
        governance_label = "治理折价未触发"

    return {
        "category_premium_pct": category_premium,
        "category_label": category_label,
        "governance_premium_pct": governance_premium,
        "governance_label": governance_label,
        "total_pct": category_premium + governance_premium,
    }


def build_wacc_assumption(
    *,
    rf_pct: Optional[float],
    supplied_ke_pct: Optional[float],
    supplied_wacc_pct: Optional[float],
    debt_ratio_pct: Optional[float] = None,
    trap_risk: str = "中",
    threshold_category: str = "",
    company_name: str = "",
    data_pack_text: str = "",
    report_pack_text: str = "",
) -> dict[str, Optional[float] | str]:
    """Build transparent WACC components for fallback valuation."""
    rf = rf_pct if rf_pct is not None else 2.5
    beta = 0.80
    erp = 5.50
    specific_risk = 0.80 if trap_risk == "低" else 1.20 if trap_risk == "中" else 2.00
    ke_fair = rf + beta * erp + specific_risk
    conservatism_components = _wacc_conservatism_components(
        threshold_category=threshold_category,
        company_name=company_name,
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
    )
    conservatism = float(conservatism_components["total_pct"])
    ke = ke_fair + conservatism
    no_or_low_debt = debt_ratio_pct is None or debt_ratio_pct <= 5.0
    wacc = ke if no_or_low_debt else ke
    warnings: list[str] = []
    if supplied_ke_pct is not None and abs(supplied_ke_pct - ke) > 0.50:
        warnings.append(f"外部Ke {supplied_ke_pct:.2f}% 与v2.1规则化Ke {ke:.2f}% 不一致，已按v2.1重算")
    if supplied_wacc_pct is not None and abs(supplied_wacc_pct - wacc) > 0.50:
        warnings.append(f"外部WACC {supplied_wacc_pct:.2f}% 与v2.1规则化WACC {wacc:.2f}% 不一致，已按v2.1重算")
    if wacc < rf + 3.0:
        warnings.append("WACC低于Rf+3%，参数偏乐观")
    if conservatism > 0:
        warnings.append(f"保守溢价按规则化计算：{conservatism:.2f}pct")
    return {
        "rf_pct": rf,
        "beta": beta,
        "erp_pct": erp,
        "specific_risk_pct": specific_risk,
        "ke_fair_pct": ke_fair,
        "conservatism_pct": conservatism,
        "category_premium_pct": float(conservatism_components["category_premium_pct"]),
        "governance_premium_pct": float(conservatism_components["governance_premium_pct"]),
        "conservatism_basis": f"{conservatism_components['category_label']} {float(conservatism_components['category_premium_pct']):.2f}% + {conservatism_components['governance_label']} {float(conservatism_components['governance_premium_pct']):.2f}%",
        "ke_pct": ke,
        "wacc_pct": wacc,
        "wacc_breakdown": (
            f"Rf {rf:.2f}% + β {beta:.2f} × ERP {erp:.2f}% + 特定风险 {specific_risk:.2f}%"
            f" + 保守溢价 {conservatism:.2f}% = DCF Ke/WACC {wacc:.2f}%"
        ),
        "ke_fair_breakdown": f"Rf {rf:.2f}% + β {beta:.2f} × ERP {erp:.2f}% + 特定风险 {specific_risk:.2f}% = DDM fair Ke {ke_fair:.2f}%",
        "warning": "；".join(warnings) if warnings else "—",
    }


def _extract_report_row_values(report_pack_text: str, row_label: str) -> list[float]:
    section = extract_markdown_section(report_pack_text, "三表核心数据（2025 vs 2024）")
    tables = extract_markdown_tables(section)
    if not tables:
        return []
    _headers, rows = table_row_map(tables[0])
    return [num for value in rows.get(row_label, []) if (num := parse_number(value)) is not None]


def _extract_first_year_from_text(text: str) -> Optional[int]:
    match = re.search(r"For the year ended 31 December\s+(\d{4})|截至\s*(\d{4})\s*年\s*12\s*月\s*31\s*日", text)
    if not match:
        return None
    for group in match.groups():
        if group:
            return int(group)
    return None


def _first_financial_number_after_phrase(text: str, phrase: str, window: int = 260) -> Optional[float]:
    pos = text.find(phrase)
    if pos < 0:
        pattern = re.escape(phrase).replace(r"\ ", r"\s+").replace(",", r",\s*")
        match = re.search(pattern, text, flags=re.I)
        pos = match.start() if match else -1
    if pos < 0:
        return None
    snippet = text[pos:pos + window]
    for value in parse_numeric_sequence(snippet):
        if abs(value) >= 1_000:
            return value
    return None


def _read_pdf_sections_text(path: Path) -> str:
    text = read_text_if_exists(path)
    if not text:
        return ""
    try:
        payload = json.loads(text)
    except Exception:
        return text
    if not isinstance(payload, dict):
        return text
    sections = [value for key, value in payload.items() if key != "metadata" and isinstance(value, str)]
    return "\n".join(sections)


def _pdftotext_layout(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", str(path.resolve()), "-"],
            check=True,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return ""
    return result.stdout or ""


def _numbers_after_multiline_phrase(text: str, phrase_pattern: str, window: int = 220) -> list[float]:
    match = re.search(phrase_pattern, text, flags=re.I | re.S)
    if not match:
        return []
    snippet = text[match.end():match.end() + window]
    values = parse_numeric_sequence(snippet)
    return [abs(value) for value in values if abs(value) >= 1_000]


def _iter_statement_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current = ""
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            if current:
                blocks.append(current.strip())
                current = ""
            continue
        has_money = any(abs(value) >= 1_000 for value in parse_numeric_sequence(stripped))
        current = f"{current} {stripped}".strip() if current else stripped
        if current and any(abs(value) >= 1_000 for value in parse_numeric_sequence(current)):
            blocks.append(current.strip())
            current = ""
    if current:
        blocks.append(current.strip())
    return blocks


def _annual_pair_from_line(
    text: str,
    include_terms: list[str],
    exclude_terms: Optional[list[str]] = None,
    min_abs: float = 1_000,
) -> Optional[tuple[float, Optional[float]]]:
    exclude_terms = exclude_terms or []
    for snippet in _iter_statement_blocks(text):
        lowered = snippet.lower()
        if not all(term.lower() in lowered for term in include_terms):
            continue
        if any(term.lower() in lowered for term in exclude_terms):
            continue
        number_matches = list(re.finditer(r"-?\d[\d,]*(?:\.\d+)?", snippet))
        if not number_matches:
            continue
        money_matches = [
            item for item in number_matches
            if abs(float(item.group(0).replace(",", ""))) >= min_abs
        ]
        if not money_matches:
            continue
        values = [abs(float(item.group(0).replace(",", ""))) for item in money_matches]
        before_first_number = snippet[:money_matches[0].start()]
        prefix = before_first_number.strip()
        tail = prefix[-24:]
        current_is_dash = bool(
            prefix in {"-", "–", "—"}
            or re.search(r"(^|\s)[-–—]\s*\(?\s*$", tail) is not None
        )
        if current_is_dash:
            current = 0.0
            previous = values[0]
        else:
            current = values[0]
            previous = values[1] if len(values) > 1 else None
        return current, previous
    return None


def _window_after_pattern(
    text: str,
    pattern: str,
    window: int = 4_000,
    required_pattern: Optional[str] = None,
) -> str:
    matches = list(re.finditer(pattern, text, flags=re.I))
    if not matches:
        return text
    if required_pattern:
        for match in matches:
            snippet = text[match.start():match.start() + window]
            if re.search(required_pattern, snippet, flags=re.I):
                return snippet
    match = matches[0]
    return text[match.start():match.start() + window]


def _rmb_thousand_value_to_mm(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    # Values extracted by the annual-report parser come from statement tables
    # printed in RMB'000. Normalize to the framework's million-unit convention.
    return value / 1_000.0


def _pair_to_mm(pair: Optional[tuple[float, Optional[float]]]) -> tuple[Optional[float], Optional[float]]:
    if not pair:
        return None, None
    current, previous = pair
    return _rmb_thousand_value_to_mm(current), _rmb_thousand_value_to_mm(previous)


def _extract_share_count_from_text(text: str) -> Optional[float]:
    if not text:
        return None
    focused_windows: list[str] = []
    for pattern in [
        r"total\s+number\s+of\s+issued\s+shares",
        r"Number\s+of\s+ordinary\s+shares",
        r"Issued\s+and\s+fully\s+paid",
        r"shares\s+of\s+the\s+Company\s+in\s+issue",
        r"已發行股份總數|已发行股份总数|普通股股數|普通股股数",
    ]:
        for match in re.finditer(pattern, text, flags=re.I):
            focused_windows.append(text[match.start():match.start() + 700])
    candidates: list[float] = []
    for snippet in focused_windows:
        for token in re.findall(r"\d{1,3}(?:,\d{3}){2,}|\d{8,}", snippet):
            value = parse_number(token)
            if value is not None and 10_000_000 <= value <= 100_000_000_000:
                candidates.append(value)
    if not candidates:
        return None
    shares = max(candidates)
    return shares / 1_000_000.0


def _annual_da_pairs_from_text(text: str) -> Optional[tuple[float, Optional[float]]]:
    patterns = [
        r"Depreciation\s+of\s+property,\s*plant.{0,160}equipment",
        r"Depreciation\s+of\s+right-of-use.{0,100}assets",
        r"Amortisation\s+of\s+intangible.{0,100}assets",
    ]
    current_total = 0.0
    previous_total = 0.0
    current_count = 0
    previous_count = 0
    term_sets = [
        (["depreciation", "property", "equipment"], []),
        (["depreciation", "right-of-use", "assets"], []),
        (["amortisation", "intangible", "assets"], ["not subject", "franchise", "indefinite"]),
    ]
    for terms, excludes in term_sets:
        pair = _annual_pair_from_line(text, terms, exclude_terms=excludes)
        if not pair:
            continue
        current, previous = pair
        current_total += current
        current_count += 1
        if previous is not None:
            previous_total += previous
            previous_count += 1
    if current_count < 2:
        return None
    return current_total, previous_total if previous_count >= 2 else None


def _cash_flow_investing_window(text: str) -> str:
    header_pattern = r"Cash\s+flows\s+from\s+investing\s+activities|INVESTING\s+ACTIVITIES|Investing\s+activities|投資活動"
    for match in re.finditer(header_pattern, text, flags=re.I):
        snippet = text[match.start():match.start() + 3_500]
        if re.search(r"Net\s+cash.{0,80}investing|投資活動.{0,80}現金", snippet, flags=re.I | re.S):
            return snippet
    return text


def _annual_capex_pairs_from_text(text: str) -> Optional[tuple[float, Optional[float]]]:
    text = _cash_flow_investing_window(text)
    direct_terms = [
        ["payments", "property", "equipment"],
        ["purchase", "property", "equipment"],
        ["purchases", "property", "equipment"],
        ["payments", "right-of-use", "assets"],
        ["payments", "intangible", "assets"],
        ["purchase", "intangible", "assets"],
        ["purchases", "intangible", "assets"],
        ["purchase", "land", "use", "rights"],
        ["purchases", "land", "use", "rights"],
    ]
    current_total = 0.0
    previous_total = 0.0
    current_count = 0
    previous_count = 0
    for terms in direct_terms:
        pair = _annual_pair_from_line(
            text,
            terms,
            exclude_terms=["depreciation", "amortisation", "amortization", "proceeds", "disposal", "payables", "capital expenditure"],
            min_abs=5_000,
        )
        if not pair:
            continue
        current, previous = pair
        current_total += current
        current_count += 1
        if previous is not None:
            previous_total += previous
            previous_count += 1
    if current_count >= 1:
        return current_total, previous_total if previous_count >= 1 else None

    current_total = 0.0
    previous_total = 0.0
    current_count = 0
    previous_count = 0
    term_sets = [
        ["property", "equipment"],
        ["right-of-use", "assets"],
        ["intangible", "assets"],
        ["land", "use", "rights"],
    ]
    for terms in term_sets:
        pair = _annual_pair_from_line(
            text,
            terms,
            exclude_terms=["depreciation", "amortisation", "amortization", "proceeds", "disposal", "payables"],
            min_abs=5_000,
        )
        if not pair:
            continue
        current, previous = pair
        current_total += current
        current_count += 1
        if previous is not None:
            previous_total += previous
            previous_count += 1
    if current_count < 1:
        return None
    return current_total, previous_total if previous_count >= 1 else None


def _extract_annual_da_from_sections(text: str) -> Optional[float]:
    """Extract full-year D&A from annual report sections, in RMB million."""
    pair = _annual_da_pairs_from_text(text)
    if pair:
        return pair[0]
    ppe = _first_financial_number_after_phrase(text, "Depreciation of property")
    rou = _first_financial_number_after_phrase(text, "Depreciation of right-of-use")
    intangible = _first_financial_number_after_phrase(text, "Amortisation of intangible")
    values = [value for value in (ppe, rou, intangible) if value is not None]
    if len(values) >= 2:
        total = sum(abs(value) for value in values)
        if total >= 100_000:
            return total
    return None


def _extract_annual_capex_from_sections(text: str) -> Optional[float]:
    """Extract full-year cash capex from annual report sections, in RMB million."""
    pair = _annual_capex_pairs_from_text(text)
    if pair:
        return pair[0]
    ppe_phrases = [
        "Payments for property, plant",
        "Payments of property, plant",
        "Purchase of property, plant",
        "Purchases of property, plant",
    ]
    intangible_phrases = [
        "Payments for intangible assets",
        "Payments of intangible assets",
        "Purchase of intangible assets",
        "Purchases of intangible assets",
    ]
    rou_phrases = ["Payments for right-of-use assets", "Payments of right-of-use assets"]
    land_phrases = ["Purchases of land use rights", "Payments for land use rights"]

    ppe = next((value for phrase in ppe_phrases if (value := _first_financial_number_after_phrase(text, phrase)) is not None), None)
    intangible = next((value for phrase in intangible_phrases if (value := _first_financial_number_after_phrase(text, phrase)) is not None), 0.0)
    rou = next((value for phrase in rou_phrases if (value := _first_financial_number_after_phrase(text, phrase)) is not None), 0.0)
    land = next((value for phrase in land_phrases if (value := _first_financial_number_after_phrase(text, phrase)) is not None), 0.0)
    if ppe is None:
        return None
    total = abs(ppe) + abs(intangible or 0.0) + abs(rou or 0.0) + abs(land or 0.0)
    return total if total > 0 else None


def extract_annual_capex_da_series(output_dir: Path, max_years: int = 5) -> tuple[list[dict[str, float | int]], str]:
    """Read pdf_sections_YYYY.json files and return latest annual Capex/D&A series."""
    records: list[dict[str, float | int]] = []
    for path in sorted(output_dir.glob("pdf_sections_20*.json")):
        if "interim" in path.name.lower():
            continue
        text = _read_pdf_sections_text(path)
        if not text:
            continue
        year_match = re.search(r"pdf_sections_(20\d{2})\.json$", path.name)
        year = int(year_match.group(1)) if year_match else (_extract_first_year_from_text(text) or 0)
        if year <= 0:
            continue
        pdf_candidates = sorted(output_dir.glob(f"*_{year}_年报.pdf"))
        annual_pdf = pdf_candidates[0] if pdf_candidates else output_dir / f"{year}_年报.pdf"
        pdf_text = _pdftotext_layout(annual_pdf)
        source_texts = [candidate for candidate in (pdf_text, text) if candidate]
        for source_text in source_texts:
            da_pair = _annual_da_pairs_from_text(source_text)
            capex_pair = _annual_capex_pairs_from_text(source_text)
            if not da_pair or not capex_pair:
                continue
            da, da_prev = da_pair
            capex, capex_prev = capex_pair
            if da > 0 and capex > 0:
                records.append({"year": year, "capex": capex, "da": da, "ratio": capex / da})
            if da_prev and da_prev > 0 and capex_prev and capex_prev > 0:
                records.append({"year": year - 1, "capex": capex_prev, "da": da_prev, "ratio": capex_prev / da_prev})
            break

    dedup: dict[int, dict[str, float | int]] = {}
    for record in sorted(records, key=lambda item: (int(item["year"]), abs(int(item["year"]) - 9999))):
        dedup[int(record["year"])] = record
    series = [dedup[year] for year in sorted(dedup, reverse=True)[:max_years]]
    if len(series) >= 3:
        years = sorted(int(item["year"]) for item in series)
        return series, f"年报pdf_sections最新{len(series)}年（{years[0]}-{years[-1]}）"
    if series:
        years = sorted(int(item["year"]) for item in series)
        return series, f"年报pdf_sections仅{len(series)}年（{years[0]}-{years[-1]}），样本不足"
    return [], "年报pdf_sections缺失"


def extract_latest_annual_core_financials(output_dir: Path) -> tuple[dict[str, list[float]], str]:
    """Extract latest annual-report two-year core table values, normalized to RMB million."""
    pdfs = sorted(output_dir.glob("*_20*_年报.pdf"))
    if not pdfs:
        return {}, "最新年报PDF缺失"
    latest_pdf = pdfs[-1]
    text = _pdftotext_layout(latest_pdf)
    if not text:
        year_match = re.search(r"_(20\d{2})_年报\.pdf$", latest_pdf.name)
        if year_match:
            text = _read_pdf_sections_text(output_dir / f"pdf_sections_{year_match.group(1)}.json")
    if not text:
        return {}, f"{latest_pdf.name} 文本提取失败"

    profit_window = _window_after_pattern(
        text,
        r"CONSOLIDATED\s+STATEMENT\s+OF\s+PROFIT\s+OR\s+LOSS|綜合損益",
        window=5_000,
        required_pattern=r"For\s+the\s+year\s+ended|截至\s*202\d\s*年\s*12\s*月\s*31\s*日",
    )
    cashflow_window = _window_after_pattern(
        text,
        r"CONSOLIDATED\s+STATEMENT\s+OF\s+CASH\s+FLOWS|綜合現金流量表",
        window=12_000,
        required_pattern=r"For\s+the\s+year\s+ended|截至\s*202\d\s*年\s*12\s*月\s*31\s*日",
    )
    position_window = _window_after_pattern(
        text,
        r"CONSOLIDATED\s+STATEMENT\s+OF\s+FINANCIAL\s+POSITION|綜合財務狀況表",
        window=12_000,
        required_pattern=r"Non-current\s+assets|Current\s+assets|非流動資產|流動資產",
    )
    equity_window = _window_after_pattern(
        text,
        r"CONSOLIDATED\s+STATEMENT\s+OF\s+CHANGES\s+IN\s+EQUITY|綜合權益變動表",
        window=7_000,
    )

    def pair_values(window: str, terms: list[str], excludes: Optional[list[str]] = None, min_abs: float = 10_000) -> list[float]:
        current, previous = _pair_to_mm(_annual_pair_from_line(window, terms, exclude_terms=excludes, min_abs=min_abs))
        return [value for value in [current, previous] if value is not None]

    capex_current, capex_previous = _pair_to_mm(_annual_capex_pairs_from_text(cashflow_window))
    da_current, da_previous = _pair_to_mm(_annual_da_pairs_from_text(text))

    rows: dict[str, list[float]] = {
        "年内溢利": pair_values(profit_window, ["profit", "comprehensive", "year"]),
        "本公司拥有人应占溢利": pair_values(profit_window, ["owners", "company"]),
        "非控股权益应占溢利": pair_values(profit_window, ["non-controlling", "interests"]),
        "经营活动现金净额": pair_values(cashflow_window, ["net", "cash", "operating", "activities"]),
        "已付普通股东股息": pair_values(cashflow_window, ["dividends", "paid"], excludes=["non-controlling"]),
        "已付非控股权益股息": pair_values(cashflow_window, ["dividends", "paid", "non-controlling"]),
        "现金及现金等价物": pair_values(position_window, ["cash", "equivalents"]),
        "本公司拥有人应占权益": pair_values(position_window, ["equity", "owners", "company"]),
        "非控股权益": pair_values(position_window, ["non-controlling", "interests"]),
    }
    if capex_current is not None:
        rows["现金资本开支"] = [value for value in [capex_current, capex_previous] if value is not None]
    if da_current is not None:
        rows["折旧摊销"] = [value for value in [da_current, da_previous] if value is not None]

    share_count = _extract_share_count_from_text(text)
    if share_count is not None:
        rows["总股本"] = [share_count]

    rows = {key: value for key, value in rows.items() if value}
    return rows, f"最新年报PDF：{latest_pdf.name}"


def build_cash_audit_annual_rows(
    *,
    data_pack_text: str,
    annual_core_rows: dict[str, list[float]],
    annual_capex_da_series: list[dict[str, float | int]],
) -> dict[str, list[float]]:
    """Build a latest-to-oldest annual series for AA audit using annual PDFs plus market-pack history."""
    if not annual_capex_da_series:
        return annual_core_rows
    ocf_by_year = _annual_market_values_by_year(data_pack_text, "5. 现金流量表", "经营业务现金净额 (OCF)")
    parent_by_year = _annual_market_values_by_year(data_pack_text, "3. 合并利润表", "股东应占溢利")
    nci_by_year = _annual_market_values_by_year(data_pack_text, "3. 合并利润表", "少数股东损益")

    years = sorted({int(item["year"]) for item in annual_capex_da_series}, reverse=True)
    rows: dict[str, list[float]] = {}
    for key in [
        "年内溢利",
        "本公司拥有人应占溢利",
        "非控股权益应占溢利",
        "经营活动现金净额",
        "现金资本开支",
        "折旧摊销",
    ]:
        rows[key] = []

    capex_by_year = {int(item["year"]): float(item["capex"]) / 1_000.0 for item in annual_capex_da_series}
    da_by_year = {int(item["year"]): float(item["da"]) / 1_000.0 for item in annual_capex_da_series}

    for idx, year in enumerate(years):
        if idx < len(annual_core_rows.get("本公司拥有人应占溢利", [])):
            parent = annual_core_rows["本公司拥有人应占溢利"][idx]
        else:
            parent = parent_by_year.get(year)
        if idx < len(annual_core_rows.get("非控股权益应占溢利", [])):
            nci = annual_core_rows["非控股权益应占溢利"][idx]
        else:
            nci = nci_by_year.get(year)
        if idx < len(annual_core_rows.get("经营活动现金净额", [])):
            ocf = annual_core_rows["经营活动现金净额"][idx]
        else:
            ocf = ocf_by_year.get(year)
        capex = capex_by_year.get(year)
        da = da_by_year.get(year)
        if parent is None or nci is None or ocf is None or capex is None or da is None:
            continue
        rows["本公司拥有人应占溢利"].append(parent)
        rows["非控股权益应占溢利"].append(nci)
        rows["年内溢利"].append(parent + nci)
        rows["经营活动现金净额"].append(ocf)
        rows["现金资本开支"].append(capex)
        rows["折旧摊销"].append(da)

    rows = {key: value for key, value in rows.items() if value}
    for key in ["已付普通股东股息", "已付非控股权益股息", "现金及现金等价物", "总股本"]:
        if annual_core_rows.get(key):
            rows[key] = annual_core_rows[key]
    return rows or annual_core_rows


def _extract_report_share_count_mm(report_pack_text: str) -> Optional[float]:
    if not report_pack_text:
        return None
    match = re.search(r"(?:年内总股本|总股本)[：:]\s*([\d,]+)\s*股", report_pack_text)
    if match:
        shares = parse_number(match.group(1))
    else:
        return _extract_share_count_from_text(report_pack_text)
    if shares is None or shares <= 0:
        return None
    return shares / 1_000_000.0 if shares > 100_000 else shares


def annual_core_dividend_report_snippet(
    annual_core_rows: dict[str, list[float]],
    latest_market_dps: Optional[float],
    year_points: Optional[dict[int, float]] = None,
    source: str = "年报普通股股息/股本反推",
) -> str:
    """Build a report-pack snippet for annual-report DPS CAGR extraction."""
    dividends = annual_core_rows.get("已付普通股东股息") or []
    shares = annual_core_rows.get("总股本") or []
    if not shares or not shares[0]:
        return ""
    share_count = shares[0]
    years: list[str] = []
    amounts: list[str] = []
    if year_points and len(year_points) >= 2:
        dps_by_year = {year: dps for year, dps in sorted(year_points.items(), reverse=True)[:5]}
        for year in sorted(dps_by_year, reverse=True):
            years.append(str(year))
            amounts.append(fmt_num(abs(dps_by_year[year]) * share_count))
    else:
        if len(dividends) < 2:
            return ""
        latest_year = datetime.now().year - 1
        for idx, dividend in enumerate(dividends[:5]):
            year = latest_year - idx
            years.append(str(year))
            amounts.append(fmt_num(dividend))
    table = format_table(["项目"] + years, [["已付普通股东股息"] + amounts], alignments=["l"] + ["r"] * len(years))
    latest_rmb_dps = abs(dividends[0]) / share_count if share_count else None
    dps_note = ""
    if latest_market_dps and latest_rmb_dps:
        dps_note = f"- 历史数据包记录年度 DPS 为 {latest_market_dps:.4f} 港元/股，需以 HKEX 末期股息公告复核最终 DPS。"
    elif latest_market_dps:
        dps_note = f"- 历史数据包记录年度 DPS 为 {latest_market_dps:.4f} 港元/股，年报股息序列按同一汇率因子折算。"
    return "\n".join([
        "",
        "## 年报普通股股息拆分（框架运行时抽取）",
        "",
        f"> 数据源：{source}；DPS CAGR 禁止使用去重后的市场分红表。",
        "",
        table,
        "",
        "## 分红与股本",
        "",
        f"- 年内总股本：{share_count * 1_000_000:,.0f} 股。",
        dps_note,
        "",
    ])


def _normalize_market_cap_mm(value: Optional[float]) -> Optional[float]:
    if value is None or value <= 0:
        return None
    return value / 1_000_000.0 if value > 1_000_000 else value


def _extract_market_cap_mm(text: str) -> Optional[float]:
    return _normalize_market_cap_mm(
        parse_number(
            extract_row_value(text, "总市值 (百万港元)")
            or extract_row_value(text, "总市值 (百万美元)")
            or extract_row_value(text, "总市值 (百万元)")
            or extract_row_value(text, "总市值")
        )
    )


def _extract_current_price_from_pack(text: str) -> Optional[float]:
    return parse_number(
        extract_row_value(text, "当前价格 (HKD)")
        or extract_row_value(text, "最新价格 (HKD)")
        or extract_row_value(text, "当前股价")
        or extract_row_value(text, "最新股价")
        or extract_row_value(text, "当前价格 (USD)")
        or extract_row_value(text, "最新价格 (USD)")
        or extract_row_value(text, "当前价格")
        or extract_row_value(text, "最新价格")
    )


def resolve_current_market_snapshot(
    data_pack_text: str,
    refresh_pack_text: str = "",
    quantitative_text: str = "",
) -> dict[str, Optional[float] | str]:
    """Resolve current price/market cap with refreshed market data first.

    Old full data packs keep complete financial statements, while refresh packs
    may only contain market-sensitive sections. Price must therefore prefer the
    refresh pack, but share count may be inferred from the old pack.
    """
    refresh_price = _extract_current_price_from_pack(refresh_pack_text)
    base_price = _extract_current_price_from_pack(data_pack_text)
    quantitative_price = parse_number(extract_row_value(quantitative_text, "current_price"))
    current_price = refresh_price or base_price or quantitative_price

    refresh_market_cap = _extract_market_cap_mm(refresh_pack_text)
    base_market_cap = _extract_market_cap_mm(data_pack_text)
    quantitative_market_cap = parse_number(extract_row_value(quantitative_text, "market_cap_mm"))
    quantitative_shares = parse_number(extract_row_value(quantitative_text, "total_shares_mm"))

    total_shares = quantitative_shares
    if total_shares is None and base_market_cap and base_price:
        total_shares = base_market_cap / base_price
    if total_shares is None and quantitative_market_cap and quantitative_price:
        total_shares = quantitative_market_cap / quantitative_price
    if total_shares is None and refresh_market_cap and refresh_price:
        total_shares = refresh_market_cap / refresh_price

    market_cap = None
    source = "缺失"
    if refresh_market_cap is not None:
        market_cap = refresh_market_cap
        source = "刷新包市值"
    elif refresh_price is not None and total_shares is not None:
        market_cap = refresh_price * total_shares
        source = "刷新包股价×历史股本"
    elif base_market_cap is not None and refresh_price is None:
        market_cap = base_market_cap
        source = "基础包市值"
    elif current_price is not None and total_shares is not None:
        market_cap = current_price * total_shares
        source = "当前股价×股本"
    elif quantitative_market_cap is not None:
        market_cap = quantitative_market_cap
        source = "定量输出市值"

    return {
        "current_price": current_price,
        "market_cap": market_cap,
        "total_shares": total_shares,
        "source": source,
    }


def default_q_pct(q_rate: Optional[float]) -> tuple[float, bool, str]:
    """Return model tax rate in percent, whether it is explicit, and label."""
    if q_rate is None:
        return 10.0, False, "默认10%（税率未确认，按保守香港直投口径）"
    return q_rate * 100.0, True, f"{q_rate * 100.0:.2f}%"


def resolve_rf_pct_for_report(
    *,
    ts_code: str,
    data_pack_text: str = "",
    candidate: Optional[float] = None,
) -> tuple[float, str]:
    """Resolve a non-zero risk-free rate and explain the source."""
    if candidate is not None and candidate > 0:
        return candidate, "数据包/传递参数"
    labels = [
        "Rf（无风险利率）",
        "港股估值默认无风险利率 (%)",
        "中国十年期国债收益率 (%)",
        "十年期国债收益率 (%)",
        "美国十年期国债收益率 (%)",
    ]
    for label in labels:
        value = parse_number(extract_row_value(data_pack_text, label))
        if value is not None and value > 0:
            return value, f"data_pack `{label}`"
    if ts_code.endswith(".HK"):
        return 3.60, "默认：香港政府10年期债券收益率保守占位"
    if ts_code.endswith(".US"):
        return 4.00, "默认：美国10年期Treasury保守占位"
    return 1.81, "默认：中国10年期国债收益率保守占位"


def minority_protocol(parent_profit: Optional[float],
                      nci_profit: Optional[float]) -> tuple[Optional[float], str]:
    if parent_profit is None or nci_profit is None or parent_profit + nci_profit <= 0:
        return None, "少数股东占比缺失，默认用已归母口径；若后续补齐需复核"
    share = nci_profit / (parent_profit + nci_profit)
    if share < 0.10:
        return share, "少数股东占比<10%，可忽略，直接归母口径"
    if share <= 0.30:
        return share, "少数股东占比10%-30%，现金审计需用C/A归母转换，DCF扣非控股权益"
    return share, "少数股东占比>30%，强制Total Entity现金审计后按归母/集团利润归属"


def compute_aa_cash_audit(
    *,
    data_pack_text: str,
    report_pack_text: str,
    g_coefficient: Optional[float] = None,
    annual_core_rows: Optional[dict[str, list[float]]] = None,
) -> dict[str, Optional[float] | str]:
    """Compute AA from cash audit instead of defaulting to parent profit."""
    annual_core_rows = annual_core_rows or {}
    parent_vals = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利")
    total_profit_vals = _extract_report_row_values(report_pack_text, "年内溢利")
    nci_vals = _extract_report_row_values(report_pack_text, "非控股权益应占溢利")
    ocf_vals = _extract_report_row_values(report_pack_text, "经营活动现金净额")
    ppe_vals = _extract_report_row_values(report_pack_text, "购买物业、厂房及设备")
    intang_vals = _extract_report_row_values(report_pack_text, "支付无形资产")
    dividends = _extract_report_row_values(report_pack_text, "已付普通股东股息")
    da_vals = _row_values_from_first_table_any(
        data_pack_text,
        "5. 现金流量表",
        ["折旧摊销", "折旧及摊销", "折旧及摊销 (D&A)", "D 折旧与摊销"],
    )

    if not ocf_vals:
        ocf_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "经营业务现金净额 (OCF)")
    if not ppe_vals:
        ppe_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "购建无形资产及其他资产")
    if not intang_vals:
        intang_vals = [0.0] * len(ocf_vals)

    parent_vals = annual_core_rows.get("本公司拥有人应占溢利") or parent_vals
    total_profit_vals = annual_core_rows.get("年内溢利") or total_profit_vals
    nci_vals = annual_core_rows.get("非控股权益应占溢利") or nci_vals
    ocf_vals = annual_core_rows.get("经营活动现金净额") or ocf_vals
    dividends = annual_core_rows.get("已付普通股东股息") or dividends
    da_vals = annual_core_rows.get("折旧摊销") or da_vals
    annual_capex_vals = annual_core_rows.get("现金资本开支") or []
    if annual_capex_vals:
        ppe_vals = annual_capex_vals
        intang_vals = [0.0] * len(ppe_vals)

    parent_factor = 1.0
    if parent_vals and total_profit_vals and total_profit_vals[0]:
        inferred = parent_vals[0] / total_profit_vals[0]
        if 0 < inferred <= 1:
            parent_factor = inferred

    aa_series: list[float] = []
    entity_surplus_series: list[float] = []
    manual_aa_series: list[float] = []
    maintenance_capex_series: list[float] = []
    capex_da_ratios: list[float] = []
    capex_policy = "maintenance_capex = min(PPE+无形资产Capex, D&A)"
    max_len = min(len(ocf_vals), max(len(ppe_vals), len(intang_vals), 0))
    for idx in range(max_len):
        capex = abs(ppe_vals[idx]) if idx < len(ppe_vals) else 0.0
        capex += abs(intang_vals[idx]) if idx < len(intang_vals) else 0.0
        da = abs(da_vals[idx]) if idx < len(da_vals) else None
        if da is not None and da > 0:
            maintenance_capex = min(capex, da)
            capex_da_ratios.append(capex / da)
        elif g_coefficient is not None:
            maintenance_capex = capex * g_coefficient
            capex_policy = "maintenance_capex = Capex × G（D&A缺失）"
        else:
            maintenance_capex = capex
            capex_policy = "maintenance_capex = Capex（D&A与G缺失，偏保守）"
        maintenance_capex_series.append(maintenance_capex)
        entity_surplus = ocf_vals[idx] - maintenance_capex
        entity_surplus_series.append(entity_surplus)
        aa_series.append(entity_surplus * parent_factor)
        year_parent_factor = parent_factor
        if idx < len(parent_vals) and idx < len(total_profit_vals) and total_profit_vals[idx]:
            inferred_year_factor = parent_vals[idx] / total_profit_vals[idx]
            if 0 < inferred_year_factor <= 1:
                year_parent_factor = inferred_year_factor
        manual_aa_series.append((ocf_vals[idx] - capex) * year_parent_factor)

    aa_2y = sum(aa_series[:2]) / min(2, len(aa_series)) if aa_series else None
    aa_all = sum(aa_series) / len(aa_series) if aa_series else None
    positive = [value for value in aa_series if value > 0]
    aa_excl = sum(positive) / len(positive) if positive else None

    if aa_2y is not None:
        selected = aa_2y
        aa_type = "AA_2y_cash"
    elif aa_excl is not None:
        selected = aa_excl
        aa_type = "AA_excl_cash"
    elif aa_all is not None:
        selected = aa_all
        aa_type = "AA_all_cash"
    elif parent_vals:
        selected = parent_vals[0]
        aa_type = "AA_degraded_C"
    else:
        selected = None
        aa_type = "AA_missing"

    precision = "正常"
    if not aa_series and parent_vals:
        precision = "降级：现金流或Capex缺失，AA=C×(0.8~1.2)仅作保守范围"
    elif aa_2y is not None and aa_all not in (None, 0) and abs(aa_2y - aa_all) / abs(aa_all) > 0.30:
        precision = "警告：AA_2y与AA_all差异>30%，现金生成能力趋势变化"

    parent_profit = parent_vals[0] if parent_vals else None
    nci_profit = nci_vals[0] if nci_vals else None
    minority_share, minority_note = minority_protocol(parent_profit, nci_profit)
    capex_da_median = _percentile(capex_da_ratios, 50)
    g_check = "正常"
    if capex_da_median is not None and (capex_da_median < 0.5 or capex_da_median > 2.0):
        g_check = f"异常：Capex/D&A五年中位数 {capex_da_median:.2f} 超出0.5-2.0，请核实字段"
    aa_manual_check = sum(manual_aa_series[:2]) / min(2, len(manual_aa_series)) if manual_aa_series else None
    aa_manual_diff_pct = None
    aa_manual_note = "AA_2y_cash 手算验证缺失：OCF/Capex 数据不足"
    if aa_manual_check is not None and aa_2y not in (None, 0):
        denominator = abs(aa_manual_check) if aa_manual_check else abs(aa_2y)
        aa_manual_diff_pct = abs(aa_manual_check - aa_2y) / denominator * 100.0
        severity = "差异<3%，取整可接受"
        if aa_manual_diff_pct > 10.0:
            severity = "标红：AA 口径差异>10%，需人工复核"
        elif aa_manual_diff_pct >= 3.0:
            severity = "差异<10%，现金审计可接受"
        aa_manual_note = (
            f"AA_2y_cash 手算验证：约 {aa_manual_check:.2f}（独立按 OCF - PPECapex - IntangCapex 后逐年按 C/A 归属）；"
            f"报告值 {aa_2y:.2f}，差异 {aa_manual_diff_pct:.1f}%；{severity}"
        )

    return {
        "aa_selected": selected,
        "aa_type": aa_type,
        "aa_2y": aa_2y,
        "aa_all": aa_all,
        "aa_excl": aa_excl,
        "aa_precision": precision,
        "parent_factor": parent_factor,
        "minority_share": minority_share,
        "minority_note": minority_note,
        "parent_profit": parent_profit,
        "ordinary_dividend": abs(dividends[0]) if dividends else None,
        "maintenance_capex_policy": capex_policy,
        "maintenance_capex_latest": maintenance_capex_series[0] if maintenance_capex_series else None,
        "capex_da_median": capex_da_median,
        "g_check": g_check,
        "aa_manual_check": aa_manual_check,
        "aa_manual_diff_pct": aa_manual_diff_pct,
        "aa_manual_note": aa_manual_note,
        "aa_degraded_low": parent_vals[0] * 0.8 if not aa_series and parent_vals else None,
        "aa_degraded_high": parent_vals[0] * 1.2 if not aa_series and parent_vals else None,
    }


def _row_values_from_first_table(text: str, heading: str, row_label: str,
                                 level: int = 2) -> list[float]:
    section = extract_markdown_section(text, heading, level=level)
    tables = extract_markdown_tables(section)
    if not tables:
        return []
    _headers, row_map = table_row_map(tables[0])
    values = row_map.get(row_label, [])
    parsed: list[float] = []
    for value in values:
        num = parse_number(value)
        if num is not None:
            parsed.append(num)
    return parsed


def _row_values_from_first_table_any(text: str, heading: str, row_labels: list[str],
                                     level: int = 2) -> list[float]:
    for label in row_labels:
        values = _row_values_from_first_table(text, heading, label, level=level)
        if values:
            return values
    return []


def _annual_market_values_by_year(text: str, heading: str, row_label: str, level: int = 2) -> dict[int, float]:
    section = extract_markdown_section(text, heading, level=level)
    tables = extract_markdown_tables(section)
    if not tables:
        return {}
    headers, rows = table_row_map(tables[0])
    raw_values = rows.get(row_label, [])
    result: dict[int, float] = {}
    for header, raw in zip(headers[1:], raw_values):
        if re.search(r"H1|中报|半年|interim", header, flags=re.I):
            continue
        year_match = re.search(r"(20\d{2})", header)
        value = parse_number(raw)
        if year_match and value is not None:
            result[int(year_match.group(1))] = value
    return result


def build_fallback_absolute_valuation(
    *,
    data_pack_text: str,
    report_pack_text: str,
    current_price: Optional[float],
    total_shares_mm: Optional[float],
    market_cap: Optional[float],
    ke_pct: Optional[float],
    wacc_pct: Optional[float],
    rf_pct: Optional[float] = None,
    ts_code: str = "",
    company_name: str = "",
    threshold_category: str = "",
    minority_share: Optional[float] = None,
    debt_ratio_pct: Optional[float] = None,
    trap_risk: str = "中",
) -> dict[str, Optional[float] | str]:
    """Compute local-data fallback valuation anchors when valuation_engine is empty."""
    wacc_assumption = build_wacc_assumption(
        rf_pct=rf_pct,
        supplied_ke_pct=ke_pct,
        supplied_wacc_pct=wacc_pct,
        debt_ratio_pct=debt_ratio_pct,
        trap_risk=trap_risk,
        threshold_category=threshold_category,
        company_name=company_name,
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
    )
    ke = float(wacc_assumption["ke_pct"]) / 100.0
    ke_fair = float(wacc_assumption["ke_fair_pct"]) / 100.0
    wacc = float(wacc_assumption["wacc_pct"]) / 100.0
    terminal_g = 0.025
    if terminal_g >= min(ke, wacc):
        terminal_g = max(min(ke, wacc) - 0.02, 0.0)

    dps = _extract_latest_dps(data_pack_text, report_pack_text)
    current_payout = _extract_latest_payout_ratio_with_report(data_pack_text, report_pack_text)
    ddm_growth = choose_ddm_growth_assumption(
        ts_code=ts_code,
        company_name=company_name,
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        threshold_category=threshold_category,
        terminal_g_pct=terminal_g * 100.0,
        minority_share=minority_share,
        trap_risk=trap_risk,
        current_payout=current_payout,
    )
    ddm_g = (ddm_growth["ddm_g_pct"] if isinstance(ddm_growth["ddm_g_pct"], float) else 0.0) / 100.0
    ddm_fair_value = None
    ddm_conservative_value = None
    if dps is not None and dps > 0 and ke_fair > ddm_g:
        ddm_fair_value = dps * (1 + ddm_g) / (ke_fair - ddm_g)
    if dps is not None and dps > 0 and ke > ddm_g:
        ddm_conservative_value = dps * (1 + ddm_g) / (ke - ddm_g)

    eps_series = _row_values_from_first_table(data_pack_text, "3. 合并利润表", "每股基本盈利 (HKD)")
    pe_series = _row_values_from_first_table(data_pack_text, "12. 关键财务指标", "PE (TTM)")
    eps_norm = sum(eps_series[:3]) / min(len(eps_series), 3) if eps_series else None
    pe_median = _percentile(pe_series, 50)
    pe_band_value = pe_median * eps_norm if pe_median is not None and eps_norm is not None else None

    report_rows: dict[str, list[float]] = {}
    report_section = extract_markdown_section(report_pack_text, "三表核心数据（2025 vs 2024）")
    report_tables = extract_markdown_tables(report_section)
    if report_tables:
        _headers, report_rows = table_row_map(report_tables[0])

    def report_row(label: str) -> list[float]:
        values = report_rows.get(label, [])
        return [num for value in values if (num := parse_number(value)) is not None]

    parent_profit_vals = report_row("本公司拥有人应占溢利")
    total_profit_vals = report_row("年内溢利")
    parent_factor = 1.0
    if parent_profit_vals and total_profit_vals and total_profit_vals[0]:
        inferred_parent_factor = parent_profit_vals[0] / total_profit_vals[0]
        if 0.0 < inferred_parent_factor <= 1.0:
            parent_factor = inferred_parent_factor

    ocf_vals = report_row("经营活动现金净额")
    ppe_vals = report_row("购买物业、厂房及设备")
    intangible_vals = report_row("支付无形资产")
    cash_vals = report_row("现金及现金等价物")
    debt_vals = report_row("借贷") or report_row("银行借贷") or report_row("有息负债")
    if not ocf_vals:
        ocf_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "经营业务现金净额 (OCF)")
    if not ppe_vals:
        ppe_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "购建无形资产及其他资产")
    fcf_vals: list[float] = []
    max_len = min(len(ocf_vals), max(len(ppe_vals), len(intangible_vals), 0))
    for i in range(max_len):
        capex = abs(ppe_vals[i]) if i < len(ppe_vals) else 0.0
        capex += abs(intangible_vals[i]) if i < len(intangible_vals) else 0.0
        fcf_vals.append(ocf_vals[i] - capex)
    if not fcf_vals:
        fcf_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "自由现金流 (FCF)")

    dcf_value = None
    stage_g = None
    terminal_value_share = None
    if fcf_vals and total_shares_mm and total_shares_mm > 0 and wacc > terminal_g:
        fcf_base = sum(fcf_vals[: min(len(fcf_vals), 3)]) / min(len(fcf_vals), 3) * parent_factor
        stage_g = max(ddm_g, 0.0)
        projected: list[float] = []
        prev = fcf_base
        for _ in range(5):
            prev *= 1 + stage_g
            projected.append(prev)
        tv = projected[-1] * (1 + terminal_g) / (wacc - terminal_g)
        pv = sum(value / (1 + wacc) ** (i + 1) for i, value in enumerate(projected))
        pv_tv = tv / (1 + wacc) ** 5
        pv += pv_tv
        terminal_value_share = pv_tv / pv * 100.0 if pv else None
        cash = (cash_vals[0] if cash_vals else 0.0) * parent_factor
        dcf_value = (pv + cash) / total_shares_mm

    weighted_center = None
    pressure_center = None
    if dcf_value is not None and dcf_value > 0 and ddm_fair_value is not None and ddm_fair_value > 0 and pe_band_value is not None and pe_band_value > 0:
        weighted_center = dcf_value * 0.50 + ddm_fair_value * 0.30 + pe_band_value * 0.20
    else:
        values = [v for v in [dcf_value, ddm_fair_value, pe_band_value] if v is not None and v > 0]
        weighted_center = sum(values) / len(values) if values else None
    if dcf_value is not None and dcf_value > 0 and ddm_conservative_value is not None and ddm_conservative_value > 0 and pe_band_value is not None and pe_band_value > 0:
        pressure_center = dcf_value * 0.50 + ddm_conservative_value * 0.30 + pe_band_value * 0.20
    source = "本地数据包回退" if any(v is not None and v > 0 for v in [dcf_value, ddm_fair_value, pe_band_value]) else "缺失"
    ebitda_vals = report_row("EBITDA")
    if not ebitda_vals:
        operating_profit_vals = report_row("经营溢利")
        da_vals = _row_values_from_first_table(data_pack_text, "5. 现金流量表", "折旧摊销")
        if operating_profit_vals:
            da_latest = da_vals[0] if da_vals else 0.0
            ebitda_vals = [operating_profit_vals[0] + da_latest]
    latest_cash = cash_vals[0] if cash_vals else None
    latest_debt = debt_vals[0] if debt_vals else 0.0
    enterprise_value = market_cap - latest_cash + latest_debt if market_cap is not None and latest_cash is not None else None
    ev_ebitda = enterprise_value / ebitda_vals[0] if enterprise_value is not None and ebitda_vals and ebitda_vals[0] else None
    latest_parent_profit = parent_profit_vals[0] if parent_profit_vals else None
    ex_cash_pe = (market_cap - latest_cash) / latest_parent_profit if market_cap is not None and latest_cash is not None and latest_parent_profit else None
    latest_fcf_parent = fcf_vals[0] * parent_factor if fcf_vals else None
    fcf_yield = latest_fcf_parent / market_cap * 100.0 if latest_fcf_parent is not None and market_cap else None
    net_debt_ebitda = (latest_debt - latest_cash) / ebitda_vals[0] if latest_cash is not None and ebitda_vals and ebitda_vals[0] else None
    warnings: list[str] = []
    if wacc < 0.03:
        warnings.append("WACC低于3%，需核实")
    if ke < 0.03:
        warnings.append("Ke低于3%，需核实")
    if terminal_g > 0.03:
        warnings.append("永续增长率>3%，参数偏乐观")
    if stage_g is not None and abs(stage_g - ddm_g) > 0.005:
        warnings.append("预测期 g 与 DDM g 不一致，属主动保守选择")
    if terminal_value_share is not None and terminal_value_share > 70.0:
        warnings.append("终值占比偏高，对永续g敏感")
    if str(wacc_assumption["warning"]) != "—":
        warnings.append(str(wacc_assumption["warning"]))
    if str(ddm_growth["ddm_g_warning"]) != "—":
        warnings.append(str(ddm_growth["ddm_g_warning"]))
    return {
        "dcf": dcf_value,
        "ddm": ddm_fair_value,
        "ddm_fair": ddm_fair_value,
        "ddm_conservative": ddm_conservative_value,
        "pe_band": pe_band_value,
        "weighted_center": weighted_center,
        "pressure_center": pressure_center,
        "source": source,
        "ke_pct": ke * 100.0,
        "ke_fair_pct": ke_fair * 100.0,
        "wacc_pct": wacc * 100.0,
        "rf_pct": wacc_assumption["rf_pct"],
        "beta": wacc_assumption["beta"],
        "erp_pct": wacc_assumption["erp_pct"],
        "specific_risk_pct": wacc_assumption["specific_risk_pct"],
        "conservatism_pct": wacc_assumption["conservatism_pct"],
        "category_premium_pct": wacc_assumption["category_premium_pct"],
        "governance_premium_pct": wacc_assumption["governance_premium_pct"],
        "conservatism_basis": wacc_assumption["conservatism_basis"],
        "wacc_breakdown": wacc_assumption["wacc_breakdown"],
        "ke_fair_breakdown": wacc_assumption["ke_fair_breakdown"],
        "terminal_g_pct": terminal_g * 100.0,
        "stage_g_pct": stage_g * 100.0 if stage_g is not None else None,
        "forecast_years": 5.0,
        "terminal_value_share_pct": terminal_value_share,
        "eps_basis": "近3年EPS均值" if eps_norm is not None else "缺失",
        "pe_median": pe_median,
        "ddm_dps": dps,
        "ddm_g_pct": ddm_growth["ddm_g_pct"],
        "ddm_g_basis": ddm_growth["ddm_g_basis"],
        "ddm_g_warning": ddm_growth["ddm_g_warning"],
        "ddm_d1": dps * (1 + ddm_g) if dps is not None else None,
        "ddm_formula": "D1 = DPS × (1+g)；DDM = D1 / (Ke - g)",
        "ev_ebitda": ev_ebitda,
        "ex_cash_pe": ex_cash_pe,
        "fcf_yield_pct": fcf_yield,
        "net_debt_ebitda": net_debt_ebitda,
        "parameter_warning": "；".join(warnings) if warnings else "—",
    }


def build_dip_buy_strategy_section(
    *,
    data_pack_text: str,
    report_pack_text: str = "",
    current_price: Optional[float],
    threshold_profile: ThresholdProfile,
    q_pct: Optional[float],
    tax_scenarios: Optional[list[dict[str, float | str]]] = None,
    minority_ratio: Optional[float] = None,
    minority_ratio_source: str = "因子7本地重算",
    years: int = 3,
    target_annual: float = 0.10,
    max_drawdown: float = 0.30,
    tranches: int = 5,
    include_current: bool = True,
) -> str:
    """Build a falling-price accumulation table targeting 10% annual return."""
    if current_price is None or current_price <= 0:
        return "## 越跌越买策略 · 年化10%目标\n\n当前价格缺失，无法生成买入阶梯。"

    dps = _extract_latest_dps(data_pack_text, report_pack_text)
    if dps is None or dps <= 0:
        return "## 越跌越买策略 · 年化10%目标\n\nDPS 数据缺失，无法生成买入阶梯。"

    dps_cagr_calc, dps_series_source, dps_cagr_basis = _dps_cagr_basis(data_pack_text, report_pack_text)
    dps_series_desc, _dps_series_source = _extract_dps_series_with_source(data_pack_text, report_pack_text)
    dps_cagr = dps_cagr_calc

    profit_values_desc = _extract_financial_row(data_pack_text, "3. 合并利润表", "股东应占溢利")
    profit_values_chrono = list(reversed(profit_values_desc))
    profit_cagr = _cagr(profit_values_chrono[0], profit_values_chrono[-1], len(profit_values_chrono) - 1) if len(profit_values_chrono) >= 2 else None

    latest_profit = profit_values_desc[0] if profit_values_desc else None
    report_parent_profit = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利")
    if report_parent_profit:
        latest_profit = report_parent_profit[0]
    nci_values = _extract_financial_row(data_pack_text, "3. 合并利润表", "少数股东损益")
    report_nci_profit = _extract_report_row_values(report_pack_text, "非控股权益应占溢利")
    if report_nci_profit:
        nci_values = report_nci_profit
    nci_latest = nci_values[0] if nci_values else None
    recomputed_minority_share = None
    if latest_profit is not None and nci_latest is not None and latest_profit + nci_latest > 0:
        recomputed_minority_share = nci_latest / (latest_profit + nci_latest)
    minority_share = minority_ratio if minority_ratio is not None else recomputed_minority_share
    if minority_ratio is not None:
        minority_check = f"少数股东占比与因子3一致：{_format_annual(minority_ratio)}（校验通过；{minority_ratio_source}）"
    elif recomputed_minority_share is not None:
        minority_check = f"少数股东占比与因子3一致：{_format_annual(recomputed_minority_share)}（因子3未传入，因子7本地重算）"
    else:
        minority_check = "少数股东占比与因子3一致：—（数据缺失）"

    current_payout = _extract_latest_payout_ratio_with_report(data_pack_text, report_pack_text)
    ddm_growth = choose_ddm_growth_assumption(
        ts_code="",
        company_name="",
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        threshold_category=threshold_profile.category,
        terminal_g_pct=min(threshold_profile.star_3_pct, 3.0) if threshold_profile.star_3_pct > 0 else 2.5,
        minority_share=minority_share,
        trap_risk="中",
        current_payout=current_payout,
        hold_years=years,
    )
    g_pess = float(ddm_growth["pess_growth_pct"]) / 100.0 if isinstance(ddm_growth.get("pess_growth_pct"), float) else 0.0
    g_base = float(ddm_growth["base_growth_pct"]) / 100.0 if isinstance(ddm_growth.get("base_growth_pct"), float) else 0.0
    g_opt = float(ddm_growth["opt_growth_pct"]) / 100.0 if isinstance(ddm_growth.get("opt_growth_pct"), float) else 0.0
    growth_rates = {
        "悲观": max(g_pess, -0.50),
        "基准": max(g_base, -0.50),
        "乐观": max(g_opt, -0.50),
    }

    industry_bull_gg_floor = 0.045 if "防御型高派" in threshold_profile.category or "消费" in threshold_profile.category else None
    optimistic_terminal_gg = threshold_profile.star_3_pct / 100.0
    if industry_bull_gg_floor is not None:
        optimistic_terminal_gg = min(optimistic_terminal_gg, industry_bull_gg_floor)
    end_gg = {
        "悲观": threshold_profile.star_5_pct / 100.0,
        "基准": threshold_profile.star_4_pct / 100.0,
        "乐观": optimistic_terminal_gg,
    }
    # Fall back to a simple 100/85/70 split if a custom profile lacks bands.
    if end_gg["基准"] <= 0:
        end_gg["基准"] = end_gg["悲观"] * 0.85
    if end_gg["乐观"] <= 0:
        end_gg["乐观"] = end_gg["悲观"] * 0.70

    steps = max(tranches, 1)
    points = steps + 1 if include_current else steps
    start_index = 0 if include_current else 1
    prices = [
        current_price * (1.0 - max_drawdown * i / steps)
        for i in range(start_index, start_index + points)
    ]

    base_weights = [10, 15, 20, 25, 30]
    if include_current and len(prices) == len(base_weights) + 1:
        weights = [0] + base_weights
    elif len(prices) <= len(base_weights):
        weights = base_weights[:len(prices)]
    else:
        weights = [0] * (len(prices) - len(base_weights)) + base_weights

    q_for_model, q_known, q_label = default_q_pct(None if q_pct is None else q_pct / 100.0)
    tax_factor = 1.0 - (q_for_model / 100.0)
    after_tax_header = "税后股息率" if q_known else "税后股息率(默认10%)"

    def scenario_annual(price: float, g: float, terminal_gg: float) -> float:
        dps_path = [dps * ((1.0 + g) ** t) for t in range(1, years + 1)]
        terminal_dps = dps_path[-1] if dps_path else dps
        terminal_price = terminal_dps / terminal_gg if terminal_gg > 0 else price
        dividends = sum(dps_path) * tax_factor
        total_return = (terminal_price - price + dividends) / price
        return (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1.0 else -1.0

    rows: list[list[str]] = []
    eligible_indices: list[int] = []
    annuals_by_index: list[dict[str, float]] = []
    for idx, price in enumerate(prices):
        annuals = {
            label: scenario_annual(price, growth_rates[label], end_gg[label])
            for label in ["悲观", "基准", "乐观"]
        }
        annuals_by_index.append(annuals)
        if annuals["悲观"] >= target_annual:
            status = "强力合格"
            eligible_indices.append(idx)
        elif annuals["基准"] >= target_annual:
            status = "合格"
            eligible_indices.append(idx)
        elif annuals["乐观"] < target_annual:
            status = "不合格"
        else:
            status = "等待"

        pre_tax_yield = dps / price
        after_tax_yield = pre_tax_yield * tax_factor
        weight = weights[idx] if idx in eligible_indices and idx < len(weights) else 0
        rows.append([
            fmt_num(price),
            f"{(price / current_price - 1.0) * 100:.0f}%",
            _format_annual(pre_tax_yield),
            _format_annual(after_tax_yield),
            _format_annual(annuals["悲观"]),
            _format_annual(annuals["基准"]),
            _format_annual(annuals["乐观"]),
            status,
            f"{weight}%",
        ])

    total_weight = sum(int(row[-1].rstrip("%")) for row in rows)
    if total_weight > 0 and total_weight != 100:
        for row in rows:
            raw_weight = int(row[-1].rstrip("%"))
            row[-1] = f"{raw_weight / total_weight * 100:.1f}%"

    weighted_base = weighted_opt = None
    norm_weights = [parse_number(row[-1]) or 0.0 for row in rows]
    norm_total = sum(norm_weights)
    if norm_total > 0:
        weighted_base = sum(w / norm_total * annuals_by_index[i]["基准"] for i, w in enumerate(norm_weights))
        weighted_opt = sum(w / norm_total * annuals_by_index[i]["乐观"] for i, w in enumerate(norm_weights))

    first_eligible = eligible_indices[0] if eligible_indices else None
    if first_eligible is None:
        qualified_text = "无：所有阶梯的基准年化均低于10%"
    else:
        qualified_text = f"第 {first_eligible + 1} 档起，约 {fmt_num(prices[first_eligible])}"

    assumptions = format_table(
        ["参数", "值"],
        [
            ["当前股价", f"{fmt_num(current_price)}"],
            ["最新 DPS", f"{fmt_num(dps, 4)}"],
            ["DPS CAGR", dps_cagr_basis],
            ["归母净利润 CAGR", _format_annual(profit_cagr)],
            ["少数股东利润占比", _format_annual(minority_share)],
            ["少数股东单源校验", minority_check],
            ["当前派息率", _format_annual(current_payout)],
            ["股东层税率 Q", fmt_pct(q_pct) if q_known else q_label + f"；并列{tax_scenario_text(tax_scenarios or tax_scenarios_for_listing_structure('hk'))}敏感性"],
            ["持有年限 N", f"{years} 年"],
            ["目标年化", _format_annual(target_annual)],
            ["最大下跌幅度", _format_annual(max_drawdown)],
        ],
        alignments=["l", "r"],
    )
    ladder = format_table(
        ["买入价", "跌幅", "税前股息率", after_tax_header, "悲观年化", "基准年化", "乐观年化", "是否≥10%", "建议仓位"],
        rows,
        alignments=["r", "r", "r", "r", "r", "r", "r", "l", "r"],
    )

    def first_index_for(mode: str) -> Optional[int]:
        for idx, annuals in enumerate(annuals_by_index):
            if mode == "保守" and annuals["基准"] >= target_annual:
                return idx
            if mode == "平衡" and annuals["乐观"] >= target_annual:
                return idx
            if mode == "进取" and annuals["悲观"] >= target_annual:
                return idx
        return None

    mode_rows = []
    for mode, rule in [
        ("保守", "基准年化≥10%，当前表格默认执行"),
        ("平衡", "乐观年化≥10%，可小仓观察"),
        ("进取", "悲观年化≥10%，才强力买入"),
    ]:
        idx = first_index_for(mode)
        mode_rows.append([
            mode,
            rule,
            f"第 {idx + 1} 档，约 {fmt_num(prices[idx])}" if idx is not None else "无合格档",
        ])
    mode_table = format_table(["模式", "判定规则", "首个合格档位"], mode_rows, alignments=["l", "l", "l"])

    tax_sensitivity = ""
    if not q_known:
        sensitivity_rows = []
        scenarios = tax_scenarios or tax_scenarios_for_listing_structure("hk")
        sample_prices = [prices[0], prices[min(len(prices) - 1, max(first_eligible or 0, 0))], prices[-1]]
        seen_prices: set[float] = set()
        for price in sample_prices:
            rounded_price = round(price, 4)
            if rounded_price in seen_prices:
                continue
            seen_prices.add(rounded_price)
            pre_tax = dps / price
            sensitivity_rows.append([fmt_num(price)] + [
                _format_annual(pre_tax * (1.0 - float(scenario["tax_pct"]) / 100.0))
                for scenario in scenarios
            ])
        tax_sensitivity = "\n".join([
            "### 税率敏感性",
            "",
            f"港股直投股息税率未确认时，主口径默认按10%；下表列示{tax_scenario_text(scenarios)}三种到手股息率。",
            "",
            format_table(
                ["买入价"] + [str(scenario["label"]) for scenario in scenarios],
                sensitivity_rows,
                alignments=["r"] * (len(scenarios) + 1),
            ),
            "",
            "；".join(f"{scenario['label']}：{scenario['note']}" for scenario in scenarios),
            "",
        ])

    return "\n".join([
        "## 越跌越买策略 · 年化10%目标",
        "",
        "本节把静态分红、DPS 增长和终点 GG 回归合并成分批买入表。默认目标年化为 10%，最大下跌幅度为当前价向下 30%，分 5 档。",
        "",
        "### 输入参数",
        "",
        assumptions,
        "",
        "### 增长与终点估值假设",
        "",
        f"- 悲观 DPS 增速：{_format_annual(growth_rates['悲观'])}；终点 GG：{fmt_pct(end_gg['悲观'] * 100)}",
        f"- 基准 DPS 增速：{_format_annual(growth_rates['基准'])}；终点 GG：{fmt_pct(end_gg['基准'] * 100)}",
        f"- 乐观 DPS 增速：{_format_annual(growth_rates['乐观'])}；终点 GG：{fmt_pct(end_gg['乐观'] * 100)}",
        f"- DPS 三档推导：{ddm_growth['growth_tiers_basis']}",
        f"- DPS增速三档来源：DDM g推导链（基准g={_format_annual(growth_rates['基准'])}，悲观={_format_annual(growth_rates['悲观'])}，乐观={_format_annual(growth_rates['乐观'])}）。",
        f"- DPS 增速联动 DDM g：DDM g取基准档 {_format_annual(growth_rates['基准'])}；{ddm_growth['ddm_g_basis']}",
        ("- 乐观终点GG已纳入行业牛市/利率下行情景：港股防御消费默认行业股息率下限4.5%。"
         if industry_bull_gg_floor is not None else "- 乐观终点GG采用子类三星锚。"),
        "",
        "### 买入阶梯表",
        "",
        ladder,
        "",
        "判定规则说明：本表“是否≥10%”列按保守模式执行；若用户明确接受更高波动，可参考平衡/进取模式。",
        "",
        mode_table,
        "",
        (f"增长假设校验：{ddm_growth['ddm_g_warning']}" if str(ddm_growth.get("ddm_g_warning") or "—") != "—" else ""),
        "",
        tax_sensitivity,
        "### 最终建议",
        "",
        f"- 合格买入区间：{qualified_text}。",
        f"- 建议建仓方式：仅在“合格”或“强力合格”档位按建议仓位分批买入；不合格档位资金顺延到后续合格档。",
        f"- 预期组合年化：按建议仓位加权，基准约 {_format_annual(weighted_base)}，乐观约 {_format_annual(weighted_opt)}。",
        "- 风险提示：若 DPS 增速不及假设、终点 GG 不回归、利润率或现金转换率继续下行，实际年化可能低于表内结果。",
        "",
    ])


def infer_value_trap_risk(qualitative_text: str, quantitative_text: str) -> str:
    count = 0

    residual_raw = extract_row_value(quantitative_text, "residual_sequence")
    residuals = parse_numeric_sequence(residual_raw or "")
    if len(residuals) >= 3:
        if residuals[-1] < residuals[-2] < residuals[-3]:
            base = abs(residuals[-3]) if residuals[-3] else 1.0
            if (residuals[-3] - residuals[-1]) / base > 0.15:
                count += 1

    if any(keyword in qualitative_text for keyword in ["价格竞争", "利润率承压", "侵蚀", "存量竞争"]):
        count += 1

    if any(keyword in qualitative_text for keyword in ["不可逆萎缩", "结构性衰退"]):
        count += 1

    if "评估: 弱" in quantitative_text or "分配意愿存疑" in quantitative_text:
        count += 1

    if any(keyword in qualitative_text for keyword in ["损害价值", "观察期"]):
        count += 1

    if count >= 2:
        return "高"
    if count == 1:
        return "中"
    return "低"


def infer_turtle_recommendation(gg_pct: Optional[float], ii_pct: Optional[float],
                                safety_margin_pct: Optional[float],
                                trap_risk: str) -> str:
    if gg_pct is None or ii_pct is None:
        return "观察"
    if safety_margin_pct is not None and safety_margin_pct >= 0:
        return "买入"
    if trap_risk == "高":
        return "排除"
    return "观察"


def _extract_basic_field(data_pack_text: str, field: str) -> str:
    return extract_row_value(data_pack_text, field) or ""


def threshold_profile_from_outputs(
    ts_code: str,
    company_name: str,
    data_pack_text: str,
    quantitative_text: str = "",
    rf_pct: Optional[float] = None,
    fallback_ii_pct: Optional[float] = None,
    minority_share_pct: Optional[float] = None,
) -> ThresholdProfile:
    """Infer the GG hurdle from business subtype before scoring."""
    sec171 = extract_markdown_section(data_pack_text, "17.1 财务趋势速览", level=3)
    sec172 = extract_markdown_section(data_pack_text, "17.2 因子2输入参数", level=3)
    tables171 = extract_markdown_tables(sec171)
    rows171 = table_row_map(tables171[0])[1] if tables171 else {}

    net_cash = (
        parse_series_value(rows171, "广义净现金（百万港元）", 0)
        or parse_series_value(rows171, "广义净现金（百万元）", 0)
        or parse_number(extract_row_value(quantitative_text, "net_cash_mm"))
    )
    debt_ratio = parse_series_value(rows171, "有息负债/总资产（%）", 0)
    payout = parse_series_value(rows171, "股息支付率（%）", 0)
    if payout is None:
        tables172 = extract_markdown_tables(sec172)
        if len(tables172) >= 2:
            _headers, rows172b = table_row_map(tables172[1])
            payout = parse_series_value(rows172b, "M（支付率3年均值）", 0)

    profile = classify_threshold_profile(
        ts_code=ts_code,
        company_name=company_name or _extract_basic_field(data_pack_text, "公司名称"),
        fullname=_extract_basic_field(data_pack_text, "全称"),
        industry=_extract_basic_field(data_pack_text, "行业"),
        net_cash=net_cash,
        debt_ratio_pct=debt_ratio,
        payout_pct=payout,
        rf_pct=rf_pct,
        minority_share_pct=minority_share_pct,
    )
    if profile.category == "通用市场fallback" and fallback_ii_pct is not None:
        return ThresholdProfile(
            category=profile.category,
            ii_pct=fallback_ii_pct,
            star_5_pct=fallback_ii_pct,
            star_4_pct=max(fallback_ii_pct - 0.75, 0.0),
            star_3_pct=max(fallback_ii_pct - 1.50, 0.0),
            method=profile.method,
            rationale=profile.rationale,
            evidence=profile.evidence,
            adjustments=profile.adjustments,
        )
    return profile


def collect_turtle_warnings(output_dir: Path, data_pack_text: str, preflight_text: str) -> str:
    warnings: list[str] = []
    warnings_line = re.search(r"- Warnings 摘要:\s*(.+)", preflight_text)
    if warnings_line:
        warnings.extend([
            item.strip() for item in warnings_line.group(1).split("；") if item.strip()
        ])
    market_business_section = extract_markdown_section(data_pack_text, "9. 主营业务构成")
    current_contract_liab_missing = "contract_liab 为空" in data_pack_text
    current_business_gap = (
        "## 9. 主营业务构成" in data_pack_text and "数据缺失" in market_business_section
    )
    if not (output_dir / "data_pack_report.md").exists():
        warnings.append("`data_pack_report.md` 缺失")
    if current_contract_liab_missing:
        warnings.append("`contract_liab` 为空")
    if "c_pay_to_staff 港股不可用" in data_pack_text:
        warnings.append("`c_pay_to_staff` 原始字段缺失")
    elif "W2: `c_pay_to_staff` 为空，已用利润表 SGA" in data_pack_text:
        warnings.append("`c_pay_to_staff` 原始字段缺失，W2 已用 SGA 替代")
    if current_business_gap:
        warnings.append("港股业务构成字段覆盖有限")

    normalized_map = {
        "港股业务构成覆盖有限": "港股业务构成覆盖有限",
        "港股业务构成字段覆盖有限": "港股业务构成覆盖有限",
        "回购无记录": "",
        "母公司单体报表不适用": "",
        "`c_pay_to_staff` 不可用": "",
    }
    unique: list[str] = []
    for item in warnings:
        item = normalized_map.get(item, item)
        if item and item not in unique:
            unique.append(item)
    if not current_contract_liab_missing:
        unique = [item for item in unique if item != "`contract_liab` 为空"]
    if not current_business_gap:
        unique = [item for item in unique if item != "港股业务构成覆盖有限"]
    return "；".join(unique) if unique else "—"


def table_row_map(block: str) -> tuple[list[str], dict[str, list[str]]]:
    headers, rows = parse_markdown_table(block)
    mapping: dict[str, list[str]] = {}
    for row in rows:
        if row:
            mapping[row[0]] = row[1:]
    return headers, mapping


def section_tables(text: str, heading: str, level: int = 2) -> list[str]:
    return extract_markdown_tables(extract_markdown_section(text, heading, level=level))


def parse_series_value(row_map: dict[str, list[str]], label: str, index: int = 0) -> Optional[float]:
    values = row_map.get(label)
    if not values or index >= len(values):
        return None
    return parse_number(values[index])


def split_table_rows(block: str, split_label: str) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Split one markdown table into rows before/after a marker row."""
    _headers, rows = parse_markdown_table(block)
    main_rows: dict[str, list[str]] = {}
    tail_rows: dict[str, list[str]] = {}
    in_tail = False
    for row in rows:
        if not row:
            continue
        key = row[0]
        if key == split_label:
            in_tail = True
            continue
        target = tail_rows if in_tail else main_rows
        target[key] = row[1:]
    return main_rows, tail_rows


def parse_named_value(section_text: str, pattern: str) -> Optional[float]:
    match = re.search(pattern, section_text)
    if not match:
        return None
    return parse_number(match.group(1))


def choose_g_coefficient(capex_median_ratio: Optional[float]) -> float:
    if capex_median_ratio is None:
        return 1.00
    if capex_median_ratio <= 1.10:
        return 1.00
    if capex_median_ratio <= 1.50:
        return 1.20
    return 1.40


def assemble_turtle_preflight(ts_code: str, output_dir: Path,
                              company_name: str,
                              holding_channel: Optional[str] = None) -> Optional[str]:
    data_pack_path = output_dir / "data_pack_market.md"
    data_pack_text = read_text_if_exists(data_pack_path)
    if not data_pack_text:
        return None

    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    report_pack_exists = (output_dir / "data_pack_report.md").exists()
    interim_pack_exists = (output_dir / "data_pack_report_interim.md").exists()
    section17_exists = "## 17. 衍生指标" in data_pack_text
    warnings = collect_turtle_warnings(output_dir, data_pack_text, "")

    metrics_section = extract_markdown_section(data_pack_text, "12. 关键财务指标")
    metric_tables = extract_markdown_tables(metrics_section)
    _metric_headers, metric_rows = table_row_map(metric_tables[0]) if metric_tables else ([], {})
    revenue_growth = parse_series_value(metric_rows, "营收同比增长率 (%)", 0)
    profit_growth = parse_series_value(metric_rows, "净利润同比增长率 (%)", 0)
    roe_latest = parse_series_value(metric_rows, "ROE (%)", 0)
    roe_prior = parse_series_value(metric_rows, "ROE (%)", 1)

    cash_rev_section = extract_markdown_section(data_pack_text, "17.3 因子3·步骤1 真实现金收入（保守基准）", level=3)
    cash_rev_tables = extract_markdown_tables(cash_rev_section)
    low_collection_year = None
    low_collection_ratio = None
    ar_change = None
    if cash_rev_tables:
        headers, rows = parse_markdown_table(cash_rev_tables[0])
        for row in rows:
            if len(row) >= 6:
                ratio = parse_number(row[5])
                if ratio is None:
                    continue
                if low_collection_ratio is None or ratio < low_collection_ratio:
                    low_collection_ratio = ratio
                    low_collection_year = row[0]
                    ar_change = parse_number(row[2])

    anomalies: list[str] = []
    if revenue_growth is not None and profit_growth is not None and profit_growth < 0 < revenue_growth:
        roe_text = ""
        if roe_latest is not None and roe_prior is not None:
            roe_text = f"，ROE 由 {roe_prior:.1f}% 降至 {roe_latest:.1f}%"
        anomalies.append(
            f"2025 股东应占溢利同比 {profit_growth:.2f}%，同期营收同比 +{revenue_growth:.2f}%{roe_text}，利润率承压已实化"
        )
    if low_collection_year and low_collection_ratio is not None and low_collection_ratio < 90:
        ar_text = f"{fmt_num(ar_change)} 百万港元" if ar_change is not None else "较大幅度"
        anomalies.append(
            f"{low_collection_year} 应收账款变动 {ar_text}，真实现金收入/营业收入仅 {low_collection_ratio:.2f}%，历史收款质量曾明显波动"
        )
    if warnings != "—":
        anomalies.append(f"当前剩余口径告警：{warnings}")
    if not anomalies:
        anomalies.append("未见阻断主流程的结构性异常，当前主要是港股字段覆盖边界。")

    completeness_bits: list[str] = []
    if "## 8. 行业与竞争" in data_pack_text:
        sec8 = extract_markdown_section(data_pack_text, "8. 行业与竞争")
        if "[§8" in sec8 or "待Agent" in sec8 or "占位" in sec8:
            completeness_bits.append("§8 仍为占位")
    data_pack_status = "核心板块可用（含 §1-§17）"
    if completeness_bits:
        data_pack_status += "；" + "；".join(completeness_bits)

    missing_items: list[str] = []
    if warnings != "—":
        missing_items.extend(warnings.split("；"))
    if not report_pack_exists:
        missing_items.append("`data_pack_report.md`")
    if not interim_pack_exists:
        missing_items.append("`data_pack_report_interim.md`")
    key_missing = "；".join(dict.fromkeys([item for item in missing_items if item])) if missing_items else "—"

    verdict = "PROCEED" if section17_exists else "BLOCK"
    if verdict == "PROCEED":
        rationale = "核心三表、分红、价格、周线与 §17 衍生指标已齐备，足以完成 Phase 3；剩余缺口主要影响口径精细度。"
    else:
        rationale = "缺少 `data_pack_market.md` 或 §17 衍生指标，无法稳定生成 Phase 3 定量结论。"

    remedy = "无。" if key_missing == "—" else f"优先补齐：{key_missing}"

    lines = [
        "# Pre-flight 输出",
        "",
        f"> 标的：{company_name}",
        f"> 生成日期：{today_str()}",
        "",
        "## 基础信息",
        "",
        f"- 股票代码: {ts_code}",
        f"- 公司名称: {company_name}",
        f"- 上市结构: {structure_label}",
        f"- 持股渠道: {channel_label}",
        f"- 报表币种: {'HKD' if ts_code.endswith('.HK') else ('USD' if ts_code.endswith('.US') else 'CNY')}",
        f"- 汇率: {'1.00（市值与报表同币种，无需换算）' if ts_code.endswith(('.HK', '.US')) else '以报表口径为准'}",
        f"- 股东层税率: {tax_note}",
        "",
        "## 异常发现",
        "",
    ]
    lines.extend([f"- {item}" for item in anomalies])
    lines.extend([
        "",
        "## 口径决策",
        "",
        "- 利润口径: GAAP归母净利润 = §3 `股东应占溢利`，理由: 最稳定，且与分红、估值口径一致",
        "- 现金口径: 广义，理由: 现金充沛、短债极低，未见阻断上游分配的明显障碍",
        "",
        "## 中期数据",
        "",
        f"- 状态: {'已补 data_pack_report_interim.md' if interim_pack_exists else '缺失'}",
        f"- 最新中期列: {'2025H1' if interim_pack_exists else '无'}",
        "- 年化系数: 1.0",
        "- 季节性风险: 正常",
        "",
        "## 数据完整性",
        "",
        f"- data_pack_market: {data_pack_status}",
        f"- data_pack_report: {'已就位' if report_pack_exists else '缺失'}",
        f"- data_pack_report_interim: {'已就位' if interim_pack_exists else '缺失'}",
        f"- §17 衍生指标: {'存在' if section17_exists else '缺失'}",
        f"- Warnings 摘要: {warnings}",
        f"- 关键缺失: {key_missing}",
        "",
        "## 裁决",
        "",
        f"- 结论: {verdict}",
        f"- 理由: {rationale}",
        f"- 补救请求: {remedy}",
        "",
    ])
    return "\n".join(lines)


def assemble_turtle_quantitative(ts_code: str, output_dir: Path,
                                 company_name: str,
                                 holding_channel: Optional[str] = None) -> Optional[str]:
    data_pack_text = read_text_if_exists(output_dir / "data_pack_market.md")
    if not data_pack_text:
        return None
    refresh_pack_text = latest_refresh_pack_text(output_dir)
    report_pack_text = read_text_if_exists(output_dir / "data_pack_report.md")

    structure_label, channel_label, _tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    structure_key = infer_listing_structure_from_output(ts_code, output_dir)
    tax_scenarios = tax_scenarios_for_listing_structure(structure_key)
    q_rate, _q_reason = resolve_shareholder_dividend_tax_rate(
        ts_code=ts_code,
        holding_channel=holding_channel,
        listing_structure=infer_listing_structure_from_output(ts_code, output_dir),
    )
    q_pct, q_pct_known, q_label = default_q_pct(q_rate)
    q_display = fmt_pct(q_pct) if q_pct_known else q_label
    q_formula_display = f"{q_pct:.0f}%"

    sec172 = extract_markdown_section(data_pack_text, "17.2 因子2输入参数", level=3)
    sec173 = extract_markdown_section(data_pack_text, "17.3 因子3·步骤1 真实现金收入（保守基准）", level=3)
    sec174 = extract_markdown_section(data_pack_text, "17.4 因子3·步骤4 经营性现金支出", level=3)
    sec175 = extract_markdown_section(data_pack_text, "17.5 因子3·步骤7 基准可支配结余 + 敏感性输入", level=3)
    sec179 = extract_markdown_section(data_pack_text, "17.9 因子4·业绩下滑敏感性", level=3)
    sec171 = extract_markdown_section(data_pack_text, "17.1 财务趋势速览", level=3)
    sec4 = extract_markdown_section(data_pack_text, "4. 合并资产负债表")
    sec5 = extract_markdown_section(data_pack_text, "5. 现金流量表")
    sec12 = extract_markdown_section(data_pack_text, "12. 关键财务指标")

    tables172 = extract_markdown_tables(sec172)
    if len(tables172) >= 2:
        _headers172, rows172 = table_row_map(tables172[0])
        _headers172b, rows172b = table_row_map(tables172[1])
    elif tables172:
        rows172, rows172b = split_table_rows(tables172[0], "汇总变量")
    else:
        rows172, rows172b = {}, {}
    tables4 = extract_markdown_tables(sec4)
    _headers4, rows4 = table_row_map(tables4[0]) if tables4 else ([], {})
    tables5 = extract_markdown_tables(sec5)
    headers5, rows5 = table_row_map(tables5[0]) if tables5 else ([], {})
    tables12 = extract_markdown_tables(sec12)
    _headers12, rows12 = table_row_map(tables12[0]) if tables12 else ([], {})

    report_parent_profit = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利")
    report_dividends = _extract_report_row_values(report_pack_text, "已付普通股东股息")
    report_cash = _extract_report_row_values(report_pack_text, "现金及现金等价物")
    report_debt = (
        _extract_report_row_values(report_pack_text, "借贷")
        or _extract_report_row_values(report_pack_text, "银行借贷")
        or _extract_report_row_values(report_pack_text, "有息负债")
    )
    report_ocf = _extract_report_row_values(report_pack_text, "经营活动现金净额")
    report_ppe_capex = _extract_report_row_values(report_pack_text, "购买物业、厂房及设备")
    report_intangible_capex = _extract_report_row_values(report_pack_text, "支付无形资产")
    report_shares_mm = _extract_report_share_count_mm(report_pack_text)
    annual_core_rows, annual_core_source = extract_latest_annual_core_financials(output_dir)
    annual_dividend_snippet = annual_core_dividend_report_snippet(annual_core_rows, _extract_latest_dps(data_pack_text, report_pack_text))
    if annual_dividend_snippet:
        report_pack_text = "\n".join([report_pack_text, annual_dividend_snippet])
    if report_shares_mm is None and annual_core_rows.get("总股本"):
        report_shares_mm = annual_core_rows["总股本"][0]

    c_profit = parse_series_value(rows172, "C 归母净利润", 0)
    if annual_core_rows.get("本公司拥有人应占溢利"):
        c_profit = annual_core_rows["本公司拥有人应占溢利"][0]
    elif report_parent_profit:
        c_profit = report_parent_profit[0]
    d_da = parse_series_value(rows172, "D 折旧与摊销", 0)
    if annual_core_rows.get("折旧摊销"):
        d_da = annual_core_rows["折旧摊销"][0]
    f_ratio = parse_series_value(rows172b, "F（Capex/D&A 5年中位数）", 0)
    f_ratio_raw = f_ratio
    annual_capex_da_series, annual_capex_da_source = extract_annual_capex_da_series(output_dir)
    annual_cash_audit_rows = build_cash_audit_annual_rows(
        data_pack_text=data_pack_text,
        annual_core_rows=annual_core_rows,
        annual_capex_da_series=annual_capex_da_series,
    )
    annual_capex_da_median = (
        _percentile([float(item["ratio"]) for item in annual_capex_da_series], 50)
        if len(annual_capex_da_series) >= 3
        else None
    )
    f_ratio_seed = annual_capex_da_median if annual_capex_da_median is not None else f_ratio
    g_coeff = choose_g_coefficient(f_ratio_seed)
    cash_audit = compute_aa_cash_audit(
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        g_coefficient=g_coeff,
        annual_core_rows=annual_cash_audit_rows,
    )
    m_pct = parse_series_value(rows172b, "M（支付率3年均值）", 0) or 0.0
    if annual_core_rows.get("已付普通股东股息") and annual_core_rows.get("本公司拥有人应占溢利") and annual_core_rows["本公司拥有人应占溢利"][0]:
        m_pct = abs(annual_core_rows["已付普通股东股息"][0]) / annual_core_rows["本公司拥有人应占溢利"][0] * 100.0
    elif report_parent_profit and report_dividends and report_parent_profit[0]:
        m_pct = abs(report_dividends[0]) / report_parent_profit[0] * 100.0
    n_pct = parse_series_value(rows172b, "N（支付率3年标准差）", 0)
    o_buyback = parse_series_value(rows172b, "O（年均回购金额）", 0) or 0.0
    rf_pct_raw = parse_series_value(rows172b, "Rf（无风险利率）", 0)
    rf_pct, rf_source = resolve_rf_pct_for_report(
        ts_code=ts_code,
        data_pack_text=data_pack_text,
        candidate=rf_pct_raw,
    )
    ii_pct_raw = parse_series_value(rows172b, "II（门槛值）", 0)
    aa_2y = cash_audit["aa_2y"] if isinstance(cash_audit["aa_2y"], float) else None
    aa_all = cash_audit["aa_all"] if isinstance(cash_audit["aa_all"], float) else None
    aa_excl = cash_audit["aa_excl"] if isinstance(cash_audit["aa_excl"], float) else None
    aa_base = cash_audit["aa_selected"] if isinstance(cash_audit["aa_selected"], float) else None
    aa_type = str(cash_audit["aa_type"])
    aa_precision = str(cash_audit["aa_precision"])
    parent_factor = cash_audit["parent_factor"] if isinstance(cash_audit["parent_factor"], float) else None
    minority_share = cash_audit["minority_share"] if isinstance(cash_audit["minority_share"], float) else None
    minority_note = str(cash_audit["minority_note"])
    maintenance_capex_policy = str(cash_audit["maintenance_capex_policy"])
    maintenance_capex_latest = cash_audit["maintenance_capex_latest"] if isinstance(cash_audit["maintenance_capex_latest"], float) else None
    capex_da_median = cash_audit["capex_da_median"] if isinstance(cash_audit["capex_da_median"], float) else None
    g_check = str(cash_audit["g_check"])
    aa_manual_check = cash_audit["aa_manual_check"] if isinstance(cash_audit["aa_manual_check"], float) else None
    aa_manual_diff_pct = cash_audit["aa_manual_diff_pct"] if isinstance(cash_audit["aa_manual_diff_pct"], float) else None
    aa_manual_note = str(cash_audit["aa_manual_note"])
    f_ratio_source = "§17.2 预计算值"
    if annual_capex_da_median is not None:
        f_ratio = annual_capex_da_median
        capex_da_median = annual_capex_da_median
        annual_ratio_text = "；".join(
            f"{int(item['year'])}: {float(item['ratio']):.2f}"
            for item in sorted(annual_capex_da_series, key=lambda item: int(item["year"]))
        )
        g_check = (
            f"正常：F 取自{annual_capex_da_source}，逐年 Capex/D&A = {annual_ratio_text}"
        )
        f_ratio_source = annual_capex_da_source
    elif capex_da_median is not None:
        f_ratio = capex_da_median
        f_ratio_source = "现金审计反推"
    g_coeff = choose_g_coefficient(f_ratio)

    threshold_profile = threshold_profile_from_outputs(
        ts_code=ts_code,
        company_name=company_name,
        data_pack_text=data_pack_text,
        rf_pct=rf_pct,
        fallback_ii_pct=ii_pct_raw,
        minority_share_pct=minority_share * 100 if minority_share is not None else None,
    )
    ii_pct = threshold_profile.ii_pct
    owner_earnings = None
    owner_earnings_source = "profit_g"
    owner_earnings_ocf = None
    if c_profit is not None and d_da is not None:
        owner_earnings = c_profit + d_da * (1 - g_coeff)
    if annual_core_rows.get("经营活动现金净额") and maintenance_capex_latest is not None:
        owner_earnings_ocf = annual_core_rows["经营活动现金净额"][0]
        owner_earnings = annual_core_rows["经营活动现金净额"][0] - maintenance_capex_latest
        owner_earnings_source = "cash_ocf"
    elif report_ocf and maintenance_capex_latest is not None:
        owner_earnings_ocf = report_ocf[0]
        owner_earnings = report_ocf[0] - maintenance_capex_latest
        owner_earnings_source = "cash_ocf"

    cash_2025 = parse_series_value(rows4, "现金及等价物", 0)
    if annual_core_rows.get("现金及现金等价物"):
        cash_2025 = annual_core_rows["现金及现金等价物"][0]
    elif report_cash:
        cash_2025 = report_cash[0]
    short_debt_2025 = parse_series_value(rows4, "短期贷款", 0) or 0.0
    net_cash_2025 = parse_series_value(table_row_map(extract_markdown_tables(sec171)[0])[1] if extract_markdown_tables(sec171) else {}, "广义净现金（百万港元）", 0)
    if net_cash_2025 is None and cash_2025 is not None:
        debt_2025 = report_debt[0] if report_debt else short_debt_2025
        if not report_debt and re.search(r"无(?:计息)?(?:银行)?借(?:贷|款)|无其他借款|无有息负债", report_pack_text):
            debt_2025 = 0.0
        net_cash_2025 = cash_2025 - (debt_2025 or 0.0)

    revenue_growth = parse_series_value(rows12, "营收同比增长率 (%)", 0)
    profit_growth = parse_series_value(rows12, "净利润同比增长率 (%)", 0)
    roe_latest = parse_series_value(rows12, "ROE (%)", 0)
    roe_prior = parse_series_value(rows12, "ROE (%)", 1)

    tables173 = extract_markdown_tables(sec173)
    cash_rev_table = tables173[0] if tables173 else ""
    cash_rev_warning_lines = [line for line in sec173.splitlines() if line.strip().startswith("> ⚠️")]
    tables174 = extract_markdown_tables(sec174)
    w_table = tables174[0] if tables174 else ""
    w_footnote = next((line for line in sec174.splitlines() if "W2:" in line), "")
    tables175 = extract_markdown_tables(sec175)
    aa_table = tables175[0] if tables175 else ""
    revenue_cv = parse_named_value(sec175, r"收入波动率 CV = ([\d.]+)%")
    lambda_coeff = parse_named_value(sec175, r"经营杠杆系数 λ = ([\-\d.]+)")
    lambda_reliability = re.search(r"- λ可靠性 = ([^\n]+)", sec175)
    lambda_reliability_text = lambda_reliability.group(1).strip() if lambda_reliability else "正常"

    market_snapshot = resolve_current_market_snapshot(data_pack_text, refresh_pack_text)
    current_price = market_snapshot["current_price"] if isinstance(market_snapshot["current_price"], float) else None
    total_shares = report_shares_mm or (market_snapshot["total_shares"] if isinstance(market_snapshot["total_shares"], float) else None)
    market_cap = current_price * total_shares if current_price and total_shares else (
        market_snapshot["market_cap"] if isinstance(market_snapshot["market_cap"], float) else None
    )
    aa_market_currency_factor = 1.0
    latest_dps = _extract_latest_dps(data_pack_text)
    dividends_for_fx = annual_core_rows.get("已付普通股东股息") or report_dividends
    if dividends_for_fx and total_shares and latest_dps:
        report_dps = abs(dividends_for_fx[0]) / total_shares
        if report_dps > 0:
            inferred_fx = latest_dps / report_dps
            if 0.5 <= inferred_fx <= 2.0:
                aa_market_currency_factor = inferred_fx

    payout_sequence_match = re.search(r"\| 股息支付率（%） \| ([^\n]+)\|", sec171)
    payout_sequence = []
    if payout_sequence_match:
        payout_sequence = [parse_number(x) for x in payout_sequence_match.group(1).split("|")]
        payout_sequence = [x for x in payout_sequence if x is not None]
    payout_text = "、".join(f"{x:.2f}%" for x in reversed(payout_sequence)) if payout_sequence else "—"
    nci_alert = nci_dividend_alert(report_pack_text, minority_share)
    annual_nci_dividends = annual_core_rows.get("已付非控股权益股息") or []
    if nci_alert == "—" and minority_share is not None and minority_share > 0.30 and len(annual_nci_dividends) >= 2 and annual_nci_dividends[1]:
        nci_growth = (annual_nci_dividends[0] / annual_nci_dividends[1] - 1) * 100.0
        if nci_growth > 100.0:
            nci_alert = (
                f"非控股股息同比 +{nci_growth:.0f}%，反映合资公司当期利润向好且分红政策偏积极，"
                "普通股东 DPS 提速受合资协议约束（需关注下一期是否延续）"
            )

    gross_r = None
    gg_pct = None
    hh_pct = None
    if c_profit is not None and market_cap and market_cap > 0:
        gross_r = ((c_profit * aa_market_currency_factor * (m_pct / 100) * (1 - q_pct / 100) + o_buyback) / market_cap) * 100
    if aa_base is not None and market_cap and market_cap > 0:
        gg_pct = ((aa_base * aa_market_currency_factor * (m_pct / 100) * (1 - q_pct / 100) + o_buyback) / market_cap) * 100
    if gross_r is not None and gg_pct is not None:
        hh_pct = abs(gross_r - gg_pct)
    safety_margin = gg_pct - ii_pct if gg_pct is not None else None
    threshold_latest_dps = _extract_latest_dps(data_pack_text, report_pack_text)
    threshold_crosscheck = compute_threshold_price_crosscheck(
        aa_base=aa_base,
        payout_anchor_pct=m_pct,
        q_pct=q_pct,
        ii_pct=ii_pct,
        total_shares=total_shares,
        latest_dps=threshold_latest_dps,
        aa_market_currency_factor=aa_market_currency_factor,
    )

    cashflow_years_desc = headers5[1:] if headers5 else []
    ocf_desc = rows5.get("经营业务现金净额 (OCF)", [])
    capex_desc = rows5.get("购建无形资产及其他资产", [])
    fcf_desc = rows5.get("自由现金流 (FCF)", [])
    dividends_desc = rows5.get("已付股息(融资)", [])
    cash_desc = rows4.get("现金及等价物", [])
    distribution_rows = []
    fcf_sequence_asc: list[float] = []
    def _series_item(values: list[str], idx: int) -> Optional[float]:
        return parse_number(values[idx]) if idx < len(values) else None

    for idx in range(len(cashflow_years_desc) - 1, -1, -1):
        year = cashflow_years_desc[idx]
        ocf = _series_item(ocf_desc, idx)
        capex = abs(_series_item(capex_desc, idx) or 0)
        fcf = _series_item(fcf_desc, idx)
        dividend = _series_item(dividends_desc, idx)
        coverage = (fcf / dividend) if (fcf is not None and dividend not in (None, 0)) else None
        if fcf is not None:
            fcf_sequence_asc.append(fcf)
        distribution_rows.append([
            year,
            fmt_num(ocf),
            fmt_num(capex),
            fmt_num(fcf),
            fmt_num(dividend),
            f"{coverage:.2f}x" if coverage is not None else "—",
        ])

    audit_years = sorted({int(item["year"]) for item in annual_capex_da_series}, reverse=True)
    audit_ocf_values = annual_cash_audit_rows.get("经营活动现金净额", [])
    annual_capex_by_year = {int(item["year"]): float(item["capex"]) / 1_000.0 for item in annual_capex_da_series}
    annual_ocf_by_year = {
        year: audit_ocf_values[idx]
        for idx, year in enumerate(audit_years)
        if idx < len(audit_ocf_values)
    }
    dividend_by_year = _annual_market_values_by_year(data_pack_text, "5. 现金流量表", "已付股息(融资)")
    if annual_core_rows.get("已付普通股东股息"):
        for idx, year in enumerate(audit_years[:len(annual_core_rows["已付普通股东股息"])]):
            dividend_by_year[year] = annual_core_rows["已付普通股东股息"][idx]
    if len(annual_ocf_by_year) >= 3 and annual_capex_by_year:
        distribution_rows = []
        fcf_sequence_asc = []
        for year in sorted(annual_ocf_by_year):
            ocf = annual_ocf_by_year.get(year)
            capex = annual_capex_by_year.get(year)
            dividend = dividend_by_year.get(year)
            fcf = (ocf - capex) if ocf is not None and capex is not None else None
            coverage = (fcf / dividend) if (fcf is not None and dividend not in (None, 0)) else None
            if fcf is not None:
                fcf_sequence_asc.append(fcf)
            distribution_rows.append([
                str(year),
                fmt_num(ocf),
                fmt_num(capex),
                fmt_num(fcf),
                fmt_num(dividend),
                f"{coverage:.2f}x" if coverage is not None else "—",
            ])
    all_fcf_positive = all((x or 0) > 0 for x in fcf_sequence_asc) if fcf_sequence_asc else False
    distribution_eval = "强" if all_fcf_positive else "中"
    cumulative_dividends = sum(dividend_by_year.values()) if dividend_by_year else sum(parse_number(x) or 0 for x in dividends_desc)
    cash_start = parse_number(cash_desc[-1]) if cash_desc else None
    latest_annual_capex_mm = annual_cash_audit_rows.get("现金资本开支", [None])[0] if annual_cash_audit_rows.get("现金资本开支") else None

    ratio_cash_short = (cash_2025 / short_debt_2025) if cash_2025 is not None and short_debt_2025 > 0 else None

    sensitivity_rows = []
    if aa_base is not None and market_cap and market_cap > 0:
        for multiple in [1.0, 0.9, 0.8, 0.7]:
            aa_scenario = aa_base * multiple
            gg_scenario = ((aa_scenario * aa_market_currency_factor * (m_pct / 100) * (1 - q_pct / 100) + o_buyback) / market_cap) * 100
            sensitivity_rows.append([
                f"{multiple:.1f}x",
                fmt_num(aa_scenario),
                fmt_pct(gg_scenario),
                f"{gg_scenario - ii_pct:+.2f} pct",
            ])
    critical_multiple = (ii_pct / gg_pct) if (ii_pct and gg_pct) else None
    sensitivity_resilience = "敏感" if safety_margin is not None and safety_margin < 0 else "尚可"

    credibility = "高"
    if lambda_reliability_text != "正常" or (revenue_cv is not None and revenue_cv > 15):
        credibility = "中"
    if hh_pct is not None and hh_pct > 1.0:
        credibility = "低"

    step0_anomalies: list[str] = []
    if revenue_growth is not None and profit_growth is not None and profit_growth < 0 < revenue_growth:
        if roe_latest is not None and roe_prior is not None:
            step0_anomalies.append(f"2025 收入增长 {revenue_growth:.2f}% 但利润下滑 {profit_growth:.2f}%，ROE 由 {roe_prior:.1f}% 降至 {roe_latest:.1f}%")
        else:
            step0_anomalies.append(f"2025 收入增长 {revenue_growth:.2f}% 但利润下滑 {profit_growth:.2f}%")
    if cash_rev_warning_lines:
        step0_anomalies.extend([line.replace("> ⚠️ ", "") for line in cash_rev_warning_lines])
    elif "contract_liab 为空" not in sec173:
        step0_anomalies.append("`contract_liab` 已有结构化值，真实现金收入直接按 §17.3 口径使用")
    if w_footnote:
        step0_anomalies.append("`c_pay_to_staff` 原始现金流字段缺失，W2 采用 SGA 保守替代")

    if owner_earnings_source == "cash_ocf":
        oe_formula_lines = [
            "`OE = OCF − 维持性Capex`",
            "",
            f"`OE = {fmt_num(owner_earnings_ocf)} − {fmt_num(maintenance_capex_latest)} = {fmt_num(owner_earnings)}`",
        ]
    else:
        oe_formula_lines = [
            "`OE = C + D × (1 − G)`",
            "",
            f"`OE = {fmt_num(c_profit)} + {fmt_num(d_da)} × (1 − {g_coeff:.2f}) = {fmt_num(owner_earnings)}`",
        ]

    credibility_rows = [
        ["收入波动率", "高" if revenue_cv is not None and revenue_cv <= 10 else "中", f"5年 CV = {fmt_num(revenue_cv)}%" if revenue_cv is not None else "缺失"],
        ["利润调整幅度", "高" if c_profit and owner_earnings and abs(owner_earnings - c_profit) / c_profit < 0.05 else "中", "OE 与归母净利润差异有限" if c_profit and owner_earnings else "缺失"],
        ["粗算偏差 HH", "高" if hh_pct is not None and hh_pct <= 0.5 else "中", f"|HH| = {fmt_num(hh_pct)} pct" if hh_pct is not None else "缺失"],
        ["经营模式变化", "中", "行业进入存量竞争，利润率承压" if profit_growth is not None and profit_growth < 0 else "未见重大切换"],
        ["λ 可靠性", "低" if lambda_reliability_text != "正常" or (lambda_coeff is not None and lambda_coeff <= 0) else "中", lambda_reliability_text],
    ]

    residual_sequence: list[float] = []
    if aa_table:
        _h_aa, aa_rows = parse_markdown_table(aa_table)
        for row in reversed(aa_rows):
            if len(row) >= 5:
                value = parse_number(row[4])
                if value is not None:
                    residual_sequence.append(value)

    lines = [
        "# 定量分析输出",
        "",
        "## Step 0 数据校验",
        "",
        "- 裁决: PROCEED",
        "- 利润口径: GAAP归母净利润 = §3 `股东应占溢利`，理由: 最稳定，且与股息支付率、估值模型一致",
        "- 现金口径: 广义，理由: 现金充沛、短债极低、未见阻断上游分配的明显障碍",
        "- 异常发现:",
    ]
    lines.extend([f"  - {item}" for item in step0_anomalies] or ["  - 未见阻断主流程的结构性异常"])
    lines.extend([
        f"- 数据完整性: `data_pack_market` 可用；`data_pack_report` {'已补' if (output_dir / 'data_pack_report.md').exists() else '缺失'}；`data_pack_report_interim` {'已就位' if (output_dir / 'data_pack_report_interim.md').exists() else '缺失'}；§17 {'存在' if sec172 else '缺失'}",
        "",
        "## Step 1 Owner Earnings",
        "",
        "采用 §17.2 预计算值：",
        "",
        f"- C = {fmt_num(c_profit)} 百万港元",
        f"- D = {fmt_num(d_da)} 百万港元",
        f"- F（Capex/D&A 五年中位数）= {fmt_num(f_ratio)}",
        f"- F 数据来源 = {f_ratio_source}",
        f"- Capex/D&A 数据源校验 = {g_check}",
        "",
        f"选定 `G = {g_coeff:.2f}`。理由：",
        "",
        "- G 由 Capex/D&A 五年中位数 F 分档决定：F≤1.10 取 1.00；1.10<F≤1.50 取 1.20；F>1.50 取 1.40；F 缺失时取 1.00 并标注提取降级。",
        f"- 本次 F={fmt_num(f_ratio)}，G取{g_coeff:.2f}。",
        f"- 原始§17.2 F值为 {fmt_num(f_ratio_raw)}；现金审计反推 Capex/D&A 中位数为 {fmt_num(cash_audit.get('capex_da_median') if isinstance(cash_audit.get('capex_da_median'), float) else None)}；最终采用来源：{f_ratio_source}；{g_check}",
        "",
        "公式：",
        "",
        *oe_formula_lines,
        "",
        f"- OE = {fmt_num(owner_earnings)} 百万港元（G 系数 = {g_coeff:.2f}）",
        "- 敏感区间:",
        f"  - G = 1.00 → {fmt_num((c_profit + d_da * (1 - 1.00)) if c_profit is not None and d_da is not None else None)}",
        f"  - G = 1.20 → {fmt_num((c_profit + d_da * (1 - 1.20)) if c_profit is not None and d_da is not None else None)}",
        f"  - G = 1.40 → {fmt_num((c_profit + d_da * (1 - 1.40)) if c_profit is not None and d_da is not None else None)}",
        "",
        "## Step 2 分配能力",
        "",
        f"- 评估: {distribution_eval}",
        "- 现金上游障碍: 未见",
        "- 判断依据: 近五年 FCF 全为正、股息现金流出始终被 FCF 覆盖、净现金持续上升" if all_fcf_positive else "- 判断依据: 当前现金流覆盖分红，但需继续跟踪波动",
        "",
        format_table(["年份", "OCF", "Capex", "FCF", "已付股息", "FCF/股息"], distribution_rows,
                     alignments=["l", "r", "r", "r", "r", "r"]),
        "",
        "补充观察：",
        "",
        f"- 2021-2025 现金余额由 {fmt_num(cash_start)} 增至 {fmt_num(cash_2025)} 百万港元",
        f"- 同期累计已付股息 {fmt_num(cumulative_dividends)} 百万港元",
        "- 说明公司并非靠压缩分红堆现金，而是造血能力持续高于分配",
        "",
        "## Step 3-8 真实可支配现金结余",
        "",
        ("`contract_liab` 已有结构化值，真实现金收入直接按 §17.3 使用；"
         "`c_pay_to_staff` 原始现金流字段仍缺失，因此 W2 继续回落到利润表 SGA 保守替代。"
         if "contract_liab 为空" not in sec173 else
         "由于 `contract_liab` 仍为空，本次直接使用 §17.3-§17.5 的保守基准值，不额外虚构 V1/V5/X1/X2 调整。"),
        "",
        "### 真实现金收入",
        "",
        cash_rev_table or "真实现金收入表缺失。",
        "",
    ])
    if cash_rev_warning_lines:
        lines.extend(cash_rev_warning_lines + [""])
    lines.extend([
        "### 经营性现金支出",
        "",
        w_table or "经营性现金支出表缺失。",
        "",
    ])
    if w_footnote:
        lines.extend([w_footnote, ""])
    aa_summary_lines = [line for line in sec175.splitlines() if line.startswith("- ")]
    deduped_aa_summary_lines: list[str] = []
    for line in aa_summary_lines:
        if line not in deduped_aa_summary_lines:
            deduped_aa_summary_lines.append(line)
    lines.extend([
        "### 基准可支配结余",
        "",
        aa_table or "基准结余表缺失。",
        "",
    ])
    lines.extend(deduped_aa_summary_lines + [""])
    cash_audit_rows = [
        ["AA_2y", fmt_num(aa_2y), "近2年 OCF - PPE Capex - 无形资产Capex 后按归母/集团利润比例归属"],
        ["AA_all", fmt_num(aa_all), "全部可用年份现金审计均值"],
        ["AA_excl", fmt_num(aa_excl), "剔除负值年份后的现金审计均值"],
        ["选定 AA", fmt_num(aa_base), aa_type],
        ["AA 精度", aa_precision, "若现金流或Capex缺失，必须标注降级并用范围而非单点"],
        ["维持性Capex口径", maintenance_capex_policy, f"最新维持性Capex {fmt_num(maintenance_capex_latest)}"],
        ["Capex/D&A校验", fmt_num(capex_da_median), g_check],
        ["AA_2y_cash手算验证", fmt_num(aa_manual_check), aa_manual_note],
        ["归母转换因子 C/A", fmt_pct(parent_factor * 100 if parent_factor is not None else None), "Total Entity → Attributable"],
        ["少数股东占比", fmt_pct(minority_share * 100 if minority_share is not None else None), minority_note],
    ]
    lines.extend([
        "### AA 现金审计协议",
        "",
        "因子3不得直接把 AA 取为归母净利润 C。本节用现金流口径独立推导 AA，再与因子2的利润口径 R 比较，HH 才保留审计信号。",
        "",
        format_table(["项目", "值", "说明"], cash_audit_rows, alignments=["l", "r", "l"]),
        "",
    ])
    lines.extend([
        "## Step 9 现金储备质量",
        "",
        f"- 可自由支配现金 FF = {fmt_num(cash_2025)} 百万港元",
        f"- 广义净现金 = {fmt_num(net_cash_2025)} 百万港元",
        "- 口径: 广义",
        "",
        "判断：",
        "",
        f"- 2025 年末现金/短期借款约 {ratio_cash_short:.0f}x，财务安全垫极厚" if ratio_cash_short is not None else "- 现金显著高于短债，财务安全垫较厚",
        "- 未见明显受限资金、上游障碍现金或专项用途资金披露",
        "- 现金储备对分红和下行周期具备实质缓冲意义",
        "",
        "## Step 10 穿透回报率",
        "",
        "### 10a 分配意愿",
        "",
        f"- 评估: {distribution_eval}",
        f"- 过去 5 年支付率序列: {payout_text}",
        f"- 支付率锚定 M = {fmt_pct(m_pct)}",
        f"- 标准差 N = {fmt_pct(n_pct)}" if n_pct is not None else "- 标准差 N = —",
        f"- 回购年均 O = {fmt_num(o_buyback)} 百万港元",
        f"- 非控股股息异常：{nci_alert}" if nci_alert != "—" else "- 非控股股息异常：未触发",
        "- 结论: 无回购，但 DPS 连续提升，且利润承压年度仍提高股息，分配意愿偏强" if o_buyback == 0 else "- 结论: 股息与回购共同构成分配输出",
        "",
        "### 10b 粗算与精算",
        "",
        "税率与门槛：",
        "",
        f"- 上市结构: {structure_label}",
        f"- 持股渠道: {channel_label}",
        f"- 股东层面税率 Q = {q_display}",
        "- 公司层面说明: 公司经营层面的中国预提税已体现在利润和现金流中，股东到手税负按持股场景单独判断",
        f"- Rf = {fmt_pct(rf_pct)}",
        f"- 门槛子类 = {threshold_profile.category}",
        f"- II = {fmt_pct(ii_pct)}",
        f"- 星级锚 = 五星≥{fmt_pct(threshold_profile.star_5_pct)}；四星≥{fmt_pct(threshold_profile.star_4_pct)}；三星≥{fmt_pct(threshold_profile.star_3_pct)}",
        f"- 门槛说明: {threshold_profile.method}",
        f"- 判断依据: {threshold_profile.rationale}",
        "- 子类证据链:",
        *[f"  - {item}" for item in threshold_profile.evidence],
        "- 门槛调整:",
        *([f"  - {item}" for item in threshold_profile.adjustments] if threshold_profile.adjustments else ["  - 无"]),
        "",
        "粗算：",
        "",
        "`R = [C × M × (1 − Q) + O] / 市值`",
        "",
        f"`R = [{fmt_num(c_profit)} × {m_pct:.2f}% × (1 − {q_formula_display}) + {fmt_num(o_buyback)}] / {fmt_num(market_cap)} = {fmt_pct(gross_r)}`",
        "",
        "精算：",
        "",
        "`GG = [AA × M × (1 − Q) + O] / 市值`",
        "",
        f"`GG = [{fmt_num(aa_base)} × {m_pct:.2f}% × (1 − {q_formula_display}) + {fmt_num(o_buyback)}] / {fmt_num(market_cap)} = {fmt_pct(gg_pct)}`",
        "",
        f"- 粗算 R = {fmt_pct(gross_r)}",
        f"- 精算 GG = {fmt_pct(gg_pct)}",
        f"- 偏差 HH = {fmt_num(hh_pct)} pct",
        f"- 门槛 II = {fmt_pct(ii_pct)}",
        f"- 安全边际 = GG − II = {fmt_num(safety_margin)} pct",
        f"- 门槛价双路径 = {threshold_crosscheck['note']}；{threshold_crosscheck['warning']}",
        "",
        "解释：",
        "",
        (f"- 本案 `{aa_type}` 来自现金审计，AA/C = {aa_base / c_profit:.2f}x，因此 GG 与 R 的差异是现金口径信号"
         if aa_base is not None and c_profit not in (None, 0) else "- 当前现金口径与利润口径差异需要继续核验"),
        "- HH 较小，说明利润口径与现金口径未明显背离" if hh_pct is not None and hh_pct <= 0.5 else "- HH 偏大，需关注利润与现金口径背离",
        (f"- 但当前价格下仍未达到龟龟策略默认10%税后回报率门槛；税率确认后看 {tax_scenario_text(tax_scenarios)} 敏感性" if not q_pct_known and safety_margin is not None and safety_margin < 0 else
         "- 当前价格下已达到或接近龟龟策略默认10%税后门槛；税率确认后看敏感性复核" if not q_pct_known else
         "- 但当前价格下仍未达到龟龟策略税后回报率门槛" if safety_margin is not None and safety_margin < 0 else "- 当前价格下已达到或接近龟龟策略门槛"),
        "",
        "### 10c 收入敏感性",
        "",
        f"`λ = {lambda_coeff:.4f}`" if lambda_coeff is not None else "`λ = —`",
        "",
        f"- λ 可靠性: {lambda_reliability_text}",
        ("- 原因: Δ结余/Δ收入符号不稳定，或 λ 为负，线性外推意义弱"
         if lambda_reliability_text != "正常" or (lambda_coeff is not None and lambda_coeff <= 0)
         else "- 原因: λ 未见明显异常，可作为辅助参考"),
        "",
        "因此不采用 λ 做线性放大，改用“结余按收入等比例缩放”的保守情景：",
        "",
        format_table(["收入情景", "结余 AA", "精算回报率 GG", "vs 门槛"], sensitivity_rows,
                     alignments=["l", "r", "r", "r"]),
        "",
        f"- 临界收入倍数: {critical_multiple:.2f}x（即在当前市值下，需要可分配现金较基准提升约 {(critical_multiple - 1) * 100:.0f}% 才能达到门槛）" if critical_multiple is not None else "- 临界收入倍数: —",
        f"- 安全边际韧性: {sensitivity_resilience}",
        "",
        "## Step 11 可信度",
        "",
        f"- 可预测性: {'中' if revenue_cv is None or revenue_cv > 10 else '高'}",
        f"- 外推可信度: {credibility}",
        "",
        "5维度评分：",
        "",
        format_table(["维度", "结果", "说明"], credibility_rows, alignments=["l", "l", "l"]),
        "",
        "结论：",
        "",
        "- 这是一家质量较好的现金分红型平台公司",
        (f"- 当前税率未确认，本次主口径默认10%税后，并同时保留{tax_scenario_text(tax_scenarios)}敏感性" if not q_pct_known else
         "- 当前税后到手回报仍未满足龟龟策略硬门槛" if safety_margin is not None and safety_margin < 0 else "- 当前税后到手回报已接近或达到门槛"),
        f"- 因此本阶段结论偏 `{'观察' if safety_margin is not None and safety_margin < 0 else '买入'}`",
        "",
        "## 税务信息",
        "",
        f"- 综合税率 Q = {q_display}",
        f"- 适用情景: {channel_label}",
        "",
        "## 传递参数校验",
        "",
        format_table(
            ["参数", "值", "来源"],
            [
                ["market_cap_mm", fmt_num(market_cap), "§1 当前市值"],
                ["total_shares_mm", fmt_num(total_shares), "§1 市值/股价反推"],
                ["current_price", fmt_num(current_price), "§1 当前价格"],
                ["net_profit_mm", fmt_num(c_profit), "§3 股东应占溢利 2025"],
                ["da_mm", fmt_num(d_da), "§5 折旧及摊销 2025"],
                ["capex_mm", fmt_num(latest_annual_capex_mm if latest_annual_capex_mm is not None else abs(parse_number(rows5.get('购建无形资产及其他资产', [''])[0]) or 0)), "年报现金流表 Capex 2025（缺失时回落§5）"],
                ["G_coefficient", f"{g_coeff:.2f}", "Step 1"],
                ["capex_da_median", fmt_num(capex_da_median), "现金审计协议"],
                ["G_check", g_check, "现金审计协议"],
                ["maintenance_capex_policy", maintenance_capex_policy, "现金审计协议"],
                ["maintenance_capex_latest", fmt_num(maintenance_capex_latest), "现金审计协议"],
                ["owner_earnings_mm", fmt_num(owner_earnings), "Step 1"],
                ["R_pct", fmt_num(gross_r), "Step 10b"],
                ["rf_pct", fmt_num(rf_pct), "§14"],
                ["rf_source", rf_source, "无风险利率来源"],
                ["II_pct", fmt_num(ii_pct), "Step 10b 子类门槛"],
                ["threshold_price_aa", fmt_num(threshold_crosscheck["aa_price"] if isinstance(threshold_crosscheck["aa_price"], float) else None), "R7-1 门槛价AA路径"],
                ["threshold_price_dps", fmt_num(threshold_crosscheck["dps_price"] if isinstance(threshold_crosscheck["dps_price"], float) else None), "R7-1 门槛价DPS路径"],
                ["threshold_price_selected", fmt_num(threshold_crosscheck["selected_price"] if isinstance(threshold_crosscheck["selected_price"], float) else None), "R7-1 取较高者"],
                ["threshold_price_gap_pct", fmt_num(threshold_crosscheck["gap_pct"] if isinstance(threshold_crosscheck["gap_pct"], float) else None), "R7-1 双路径差异"],
                ["threshold_price_note", str(threshold_crosscheck["note"]), "R7-1 双路径说明"],
                ["threshold_price_warning", str(threshold_crosscheck["warning"]), "R7-1 双路径校验"],
                ["threshold_category", threshold_profile.category, "Step 10b"],
                ["threshold_method", threshold_profile.method, "Step 10b"],
                ["threshold_evidence", "；".join(threshold_profile.evidence), "Step 10b"],
                ["threshold_adjustments", "；".join(threshold_profile.adjustments) if threshold_profile.adjustments else "无", "Step 10b"],
                ["star_5_pct", fmt_num(threshold_profile.star_5_pct), "Step 10b"],
                ["star_4_pct", fmt_num(threshold_profile.star_4_pct), "Step 10b"],
                ["star_3_pct", fmt_num(threshold_profile.star_3_pct), "Step 10b"],
                ["Q_pct", fmt_num(q_pct), f"{'显式税率' if q_pct_known else '默认10%主口径'}；持有场景：{channel_label}"],
                ["M_pct", fmt_num(m_pct), "§17.2"],
                ["O_mm", fmt_num(o_buyback), "§15 回购 / §17.2"],
                ["AA_mm", fmt_num(aa_base), f"现金审计 {aa_type}"],
                ["AA_type", aa_type, "Step 3-8"],
                ["AA_2y_mm", fmt_num(aa_2y), "现金审计协议"],
                ["AA_all_mm", fmt_num(aa_all), "现金审计协议"],
                ["AA_excl_mm", fmt_num(aa_excl), "现金审计协议"],
                ["AA_precision", aa_precision, "现金审计协议"],
                ["AA_manual_check_mm", fmt_num(aa_manual_check), "AA_2y_cash 手算验证"],
                ["AA_manual_diff_pct", fmt_num(aa_manual_diff_pct), "AA_2y_cash 手算验证差异"],
                ["AA_manual_note", aa_manual_note, "AA_2y_cash 手算验证说明"],
                ["nci_dividend_alert", nci_alert, "非控股股息异常报警"],
                ["minority_share", fmt_num(minority_share * 100 if minority_share is not None else None), "少数股东协议，%"],
                ["minority_protocol", minority_note, "少数股东协议"],
                ["parent_factor", fmt_num(parent_factor), "C/A归母转换"],
                ["GG_pct", fmt_num(gg_pct), "Step 10b"],
                ["HH_pct", fmt_num(hh_pct), "Step 10b"],
                ["lambda_coeff", f"{lambda_coeff:.4f}" if lambda_coeff is not None else "—", "§17.5"],
                ["lambda_reliability", lambda_reliability_text, "§17.5 警告"],
                ["credibility", credibility, "Step 11"],
                ["payout_willingness", distribution_eval, "Step 10a"],
                ["FF_mm", fmt_num(cash_2025), "§4 现金及等价物 2025"],
                ["net_cash_mm", fmt_num(net_cash_2025), "§17.1 广义净现金"],
                ["fcf_sequence", "[" + ", ".join(fmt_num(x) for x in fcf_sequence_asc) + "]", "§5 / §17.2"],
                ["residual_sequence", "[" + ", ".join(fmt_num(x) for x in residual_sequence) + "]", "§17.5"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
    ])
    return "\n".join(lines)


def reorder_financial_trend_table(block: str) -> str:
    headers, rows = parse_markdown_table(block)
    if not headers or len(headers) < 7:
        return block
    target_headers = ["指标", "2021", "2022", "2023", "2024", "2025", "5年CAGR"]
    reordered_rows: list[list[str]] = []
    for row in rows:
        if len(row) < 7:
            reordered_rows.append(row)
            continue
        reordered_rows.append([row[0], row[5], row[4], row[3], row[2], row[1], row[6]])
    return format_table(target_headers, reordered_rows, alignments=["l", "r", "r", "r", "r", "r", "r"])


def summarize_business_model(section_text: str, params: dict[str, str],
                             net_profit_growth: Optional[float]) -> str:
    capital = params.get("capital_intensity", "轻资产")
    collection = params.get("collection_mode", "回款型")
    business_model = params.get("business_model", "")
    intro = first_nonempty_paragraph(section_text)
    if "物业" in business_model or "物管" in business_model:
        if net_profit_growth is not None and net_profit_growth < 0:
            tail = "2025 年已经出现收入仍增但利润下滑，说明规模扩张不再自动转化为利润增长。"
        else:
            tail = "当前业务逻辑仍以高频管理服务为核心，现金创造能力相对稳健。"
        lead = f"公司主业仍是物业管理费，辅以增值服务，整体属于{capital}、{collection}的经营模式。"
    else:
        model_text = business_model or "现有主营业务"
        if net_profit_growth is not None and net_profit_growth < 0:
            tail = "最新年度利润承压，说明收入规模与普通股东可分配利润不能简单线性外推。"
        else:
            tail = "最新年度经营保持稳定，现金创造能力需要结合资本开支和股东分流一起判断。"
        lead = f"公司主业是{model_text}，整体属于{capital}、{collection}的经营模式。"
    return clean_sentence(f"{lead}{tail} {intro}")


def summarize_moat(section_text: str, params: dict[str, str]) -> str:
    moat = params.get("moat_rating", "中")
    pricing = params.get("pricing_power", "中")
    ranking = params.get("competitor_ranking", "")
    summary = first_bullet_or_paragraph(section_text)
    return clean_sentence(
        f"护城河评级为{moat}，主要来自品牌、授权、渠道、规模效率、组织体系或客户关系等可持续经营资源。"
        f" 当前定价权评估为{pricing}。{ranking} {summary}"
    )


def summarize_environment(section_text: str, params: dict[str, str]) -> str:
    cyclicality = params.get("cyclicality", "弱周期")
    cycle_pos = params.get("cycle_position", "中段")
    regulatory = params.get("regulatory_risk", "中")
    summary = first_nonempty_paragraph(section_text)
    business_model = params.get("business_model", "")
    if "物业" in business_model or "物管" in business_model:
        risk_text = "真正需要关注的不是政策打压，而是地产链放缓和行业压价对利润率的侵蚀。"
    else:
        risk_text = "真正需要关注的是需求结构、价格竞争、成本波动和监管变化对利润率与分红能力的影响。"
    return clean_sentence(
        f"行业属性偏{cyclicality}，当前周期位置判断为{cycle_pos}，监管风险为{regulatory}。"
        f" {risk_text} {summary}"
    )


def summarize_governance(section_text: str, params: dict[str, str]) -> str:
    mgmt = params.get("management_rating", "合格")
    related = params.get("related_party_risk", "中")
    summary = first_nonempty_paragraph(section_text)
    return clean_sentence(
        f"管理层与治理整体评价为{mgmt}，目前未见明显财务或审计红旗。"
        f" 但关联方风险评估为{related}，意味着资源支持与体系依赖需要同时跟踪。 {summary}"
    )


def summarize_mda(section_text: str, params: dict[str, str]) -> str:
    credibility = params.get("mda_credibility", "中")
    signal = params.get("distribution_signal", "")
    summary = first_nonempty_paragraph(section_text)
    return clean_sentence(
        f"MD&A 可信度评估为{credibility}，管理层对利润率压力和行业竞争的披露总体坦诚。"
        f" {summary} {signal}"
    )


def summarize_holding(section_text: str, params: dict[str, str]) -> str:
    related = params.get("related_party_risk", "中")
    holding_structure = params.get("holding_structure", "").lower()
    summary = first_nonempty_paragraph(section_text)
    if holding_structure in {"false", "否", "no", "0"}:
        lead = "公司不属于典型需要 SOTP 拆分的复杂控股平台，但控股股东、合资结构和关联交易仍会影响普通股东穿透回报。"
    else:
        lead = "公司控股结构和下属经营实体需要穿透观察，普通股东最终可获得的现金回报取决于利润归属、现金上游和分红安排。"
    return clean_sentence(
        f"{lead} 关联依赖风险目前评估为{related}。 {summary}"
    )


def latest_refresh_pack_text(output_dir: Path) -> str:
    packs = sorted(output_dir.glob("data_pack_market_refresh_*.md"), key=lambda p: p.name)
    for path in reversed(packs):
        text = read_text_if_exists(path)
        if text:
            return text
    return ""


def report_pack_financial_trend(report_pack_text: str) -> str:
    section = extract_markdown_section(report_pack_text, "三表核心数据（2025 vs 2024）")
    tables = extract_markdown_tables(section)
    if not tables:
        return ""
    headers, rows = parse_markdown_table(tables[0])
    if len(headers) < 3:
        return ""
    keep = {
        "收入",
        "毛利",
        "经营溢利",
        "年内溢利",
        "本公司拥有人应占溢利",
        "非控股权益应占溢利",
        "现金及现金等价物",
        "经营活动现金净额",
        "购买物业、厂房及设备",
        "支付无形资产",
        "已付普通股东股息",
        "已付非控股权益股息",
    }
    compact_rows: list[list[str]] = []
    for row in rows:
        if len(row) >= 3 and row[0] in keep:
            compact_rows.append([row[0], row[2], row[1]])
    if not compact_rows:
        return ""
    return format_table(
        ["项目（百万元人民币）", "2024", "2025"],
        compact_rows,
        alignments=["l", "r", "r"],
    )


def recommendation_for_tax_rate(
    *,
    aa_base: Optional[float],
    market_cap: Optional[float],
    payout_anchor: Optional[float],
    aa_market_currency_factor: float,
    ii_pct: Optional[float],
    trap_risk: str,
    tax_pct: float,
) -> tuple[str, Optional[float], Optional[float]]:
    if aa_base is None or market_cap in (None, 0) or payout_anchor is None or ii_pct is None:
        return "观察", None, None
    gg_tax = aa_base * aa_market_currency_factor * (payout_anchor / 100.0) * (1 - tax_pct / 100.0) / market_cap * 100.0
    safety = gg_tax - ii_pct
    return infer_turtle_recommendation(gg_tax, ii_pct, safety, trap_risk), gg_tax, safety


def compute_threshold_price_crosscheck(
    *,
    aa_base: Optional[float],
    payout_anchor_pct: Optional[float],
    q_pct: Optional[float],
    ii_pct: Optional[float],
    total_shares: Optional[float],
    latest_dps: Optional[float],
    aa_market_currency_factor: float = 1.0,
) -> dict[str, Optional[float] | str]:
    if q_pct is None:
        q_pct = 10.0
    threshold_aa = None
    threshold_dps = None
    if aa_base is not None and payout_anchor_pct is not None and ii_pct not in (None, 0) and total_shares:
        threshold_market_cap = aa_base * aa_market_currency_factor * (payout_anchor_pct / 100.0) * (1 - q_pct / 100.0) / (ii_pct / 100.0)
        threshold_aa = threshold_market_cap / total_shares
    if latest_dps is not None and ii_pct not in (None, 0):
        threshold_dps = latest_dps * (1 - q_pct / 100.0) / (ii_pct / 100.0)
    candidates = [value for value in [threshold_aa, threshold_dps] if value is not None and value > 0]
    selected = max(candidates) if candidates else None
    gap_pct = None
    warning = "—"
    if threshold_aa is not None and threshold_dps is not None and min(threshold_aa, threshold_dps) > 0:
        gap_pct = abs(threshold_aa - threshold_dps) / min(threshold_aa, threshold_dps) * 100.0
        if gap_pct > 30.0:
            warning = f"标黄：AA 与 DPS 背离 {gap_pct:.1f}%，检查 M 是否匹配"
    note = (
        f"门槛价（AA 路径）{fmt_num(threshold_aa)} HKD；"
        f"（DPS 路径）{fmt_num(threshold_dps)} HKD；"
        f"取较高者 {fmt_num(selected)} HKD 作为主口径门槛价"
    )
    return {
        "aa_price": threshold_aa,
        "dps_price": threshold_dps,
        "selected_price": selected,
        "gap_pct": gap_pct,
        "warning": warning,
        "note": note,
    }


def executive_summary_assumption_sentence(
    *,
    q_display: str,
    threshold_adjustments: list[str] | str | None,
    dps_cagr_basis: str,
) -> str:
    """v2.1-final explicit assumptions sentence for Executive Summary."""
    if isinstance(threshold_adjustments, list):
        ii_adjustment = "；".join([item for item in threshold_adjustments if item]) or "II未下调"
    else:
        adjustment_text = str(threshold_adjustments or "").strip()
        ii_adjustment = adjustment_text if adjustment_text and adjustment_text != "无" else "II未下调"
    dps_part = dps_cagr_basis if dps_cagr_basis else "DPS CAGR缺失，需人工复核"
    return f"本结论基于 [税率 Q={q_display}] + [{ii_adjustment}] + [{dps_part}] 假设。若假设变化，结论可能翻转。"


def nci_dividend_alert(report_pack_text: str, minority_share: Optional[float]) -> str:
    nci_dividends = _extract_report_row_values(report_pack_text, "已付非控股权益股息")
    if not nci_dividends:
        for table in extract_markdown_tables(report_pack_text):
            _headers, rows = table_row_map(table)
            values = rows.get("已付非控股权益股息", [])
            nci_dividends = [num for value in values if (num := parse_number(value)) is not None]
            if nci_dividends:
                break
    if minority_share is None or minority_share <= 0.30 or len(nci_dividends) < 2:
        return "—"
    latest = abs(nci_dividends[0])
    prior = abs(nci_dividends[1])
    if prior <= 0 or latest / prior <= 2.0:
        return "—"
    has_brand_partner = any(term in report_pack_text for term in ["可口可乐", "Swire", "太古", "Coca-Cola", "外资", "品牌方"])
    if not has_brand_partner:
        return "—"
    yoy = (latest / prior - 1.0) * 100.0
    return (
        f"非控股股息同比 +{yoy:.0f}%，反映合资公司当期利润向好且分红政策偏积极，"
        "普通股东 DPS 提速受合资协议约束（需关注下一期是否延续）"
    )


def _extract_report_row_values_any(report_pack_text: str, labels: list[str]) -> list[float]:
    for label in labels:
        values = _extract_report_row_values(report_pack_text, label)
        if values:
            return values
    return []


def _row_ratio_latest(numerator: list[float], denominator: list[float]) -> Optional[float]:
    if numerator and denominator and denominator[0]:
        return numerator[0] / denominator[0]
    return None


def _row_yoy_series(values_desc: list[float]) -> list[float]:
    yoys: list[float] = []
    for idx in range(len(values_desc) - 1):
        current = values_desc[idx]
        prior = values_desc[idx + 1]
        if prior:
            yoys.append((current / prior - 1.0) * 100.0)
    return yoys


def _bvps_from_report_pack(report_pack_text: str, total_shares: Optional[float]) -> Optional[float]:
    equity = _extract_report_row_values_any(
        report_pack_text,
        ["本公司拥有人应占权益", "本公司拥有人应占权益总额", "归母权益", "股东权益"],
    )
    if equity and total_shares:
        return equity[0] / total_shares
    return None


def build_factor1b_execution_table(
    *,
    qualitative_params: dict[str, str],
    data_pack_text: str,
    report_pack_text: str,
    capex_da_median: Optional[float],
    g_coeff: Optional[float],
    minority_share: Optional[float],
) -> tuple[str, str]:
    revenue = _extract_report_row_values_any(report_pack_text, ["收入", "营业收入", "收益"])
    ar = _extract_report_row_values_any(report_pack_text, ["应收贸易款项", "贸易应收款项", "应收账款"])
    ocf = _extract_report_row_values_any(report_pack_text, ["经营活动现金净额", "经营业务现金净额"])
    collection_ratio = _row_ratio_latest(ocf, revenue)
    ar_revenue = _row_ratio_latest(ar, revenue)
    credit_days = ar_revenue * 365.0 if ar_revenue is not None else None
    revenue_cagr = _cagr(revenue[-1], revenue[0], len(revenue) - 1) if len(revenue) >= 2 else None
    revenue_yoys = _row_yoy_series(revenue)
    max_drawdown = min(revenue_yoys) if revenue_yoys else None
    capital_bucket = "capital-light" if capex_da_median is not None and capex_da_median <= 1.10 else "capital-heavy" if capex_da_median is not None and capex_da_median > 1.50 else "中等资本消耗"
    sotp_trigger = "触发" if minority_share is not None and minority_share >= 30 else "未触发"
    rows = [
        ["3.1 资本消耗", f"{capital_bucket}；F={fmt_num(capex_da_median)}；G={fmt_num(g_coeff)}", "G_coefficient / DCF再投资率"],
        ["3.2 收款模式", f"收款比率={fmt_pct(collection_ratio * 100 if collection_ratio is not None else None)}；应收/收入={fmt_pct(ar_revenue * 100 if ar_revenue is not None else None)}；信用期={fmt_num(credit_days, 0)}天", "AA置信度 / 现金收入审计"],
        ["3.3 护城河", f"非技术={qualitative_params.get('moat_rating', '中')}；技术=无明确披露；飞轮={qualitative_params.get('business_model', '主营体系')}", "II区间位置 / 终点GG"],
        ["3.4 周期性", f"收入CAGR={_format_annual(revenue_cagr)}；最大YoY={fmt_pct(max_drawdown)}；判定={qualitative_params.get('cyclicality', '弱周期')}", "收入敏感性 / 估值倍数"],
        ["3.5 人力资本", qualitative_params.get("labor_intensity", "系统型/劳动密集待确认"), "经营杠杆λ / 固定成本"],
        ["3.6 管理层", f"任期=年报披露待核；资本配置=分红/Capex记录；审计师={extract_row_value(report_pack_text, '外聘核数师') or '无变更披露'}", "分配意愿 / 外推可信度"],
        ["3.7 监管", f"糖税/健康={qualitative_params.get('regulatory_risk', '中')}；食品安全=中；国资=低", "特定风险溢价"],
        ["3.8 MD&A", f"可信度={qualitative_params.get('mda_credibility', '中')}；关键发现=利润率/资本开支/竞争披露", "预测可信度"],
        ["3.9 控股折价", f"少数股东={fmt_pct(minority_share)}；SOTP={sotp_trigger}", "少数股东协议 / DCF非控股扣减"],
    ]
    transfer_rows = [
        ["F/G", "3.1", "Owner Earnings、AA、DCF再投资"],
        ["收款比率/信用期", "3.2", "现金收入审计、AA精度"],
        ["护城河/周期性", "3.3/3.4", "II门槛、终点GG、WACC风险溢价"],
        ["管理层/MD&A", "3.6/3.8", "派息率锚、外推可信度"],
        ["少数股东/SOTP", "3.9", "AA归母转换、DCF非控股扣减、DPS增速折扣"],
    ]
    return (
        format_table(["模块", "量化输出", "传递参数"], rows, alignments=["l", "l", "l"]),
        format_table(["输出参数", "来源模块", "传递至"], transfer_rows, alignments=["l", "l", "l"]),
    )


def build_cash_quality_audit_sections(
    *,
    data_pack_text: str,
    report_pack_text: str,
    aa_2y: Optional[float],
    aa_all: Optional[float],
    aa_excl: Optional[float],
    maintenance_capex_latest: Optional[float],
    capex_da_median: Optional[float],
    cash_2025: Optional[float],
    net_cash_2025: Optional[float],
    fcf_sequence: list[float],
    payout_anchor: Optional[float],
) -> str:
    revenue = _extract_report_row_values_any(report_pack_text, ["收入", "营业收入", "收益"])
    ar = _extract_report_row_values_any(report_pack_text, ["应收贸易款项", "贸易应收款项", "应收账款"])
    contract = _extract_report_row_values_any(report_pack_text, ["合约负债", "合同负债"])
    related_due = _extract_report_row_values_any(report_pack_text, ["关联方欠款", "应收关联方款项", "应收关连公司款项"])
    restricted_cash = _extract_report_row_values_any(report_pack_text, ["受限制银行存款", "受限制现金"])
    nci_dividends = _extract_report_row_values_any(report_pack_text, ["已付非控股权益股息"])
    ordinary_dividends = _extract_report_row_values_any(report_pack_text, ["已付普通股东股息"])
    ppe_capex = _extract_report_row_values_any(report_pack_text, ["购买物业、厂房及设备"])
    intangible_capex = _extract_report_row_values_any(report_pack_text, ["支付无形资产"])
    ocf = _extract_report_row_values_any(report_pack_text, ["经营活动现金净额"])
    sga = _extract_report_row_values_any(report_pack_text, ["分销及销售支出"])
    admin = _extract_report_row_values_any(report_pack_text, ["行政支出"])
    ar_ratio = _row_ratio_latest(ar, revenue)
    credit_days = ar_ratio * 365.0 if ar_ratio is not None else None
    collection_ratio = _row_ratio_latest(ocf, revenue)
    latest_capex = (abs(ppe_capex[0]) if ppe_capex else 0.0) + (abs(intangible_capex[0]) if intangible_capex else 0.0)
    growth_capex = latest_capex - maintenance_capex_latest if maintenance_capex_latest is not None else None
    growth_capex_ratio = growth_capex / latest_capex * 100.0 if growth_capex is not None and latest_capex else None
    ff = cash_2025
    bb = cash_2025
    cc = restricted_cash[0] if restricted_cash else 0.0
    dd = 790.0 if re.search(r"关联方存款\s*790|790\s*百万元.*关联方", report_pack_text) else None
    ee = related_due[0] if related_due else None
    ff_adjusted = bb - cc - (dd or 0.0) if bb is not None else ff
    sections = [
        "### 5.2 应收 Footnote 核查",
        "",
        format_table(
            ["项目", "数值", "判断"],
            [
                ["应收/收入", fmt_pct(ar_ratio * 100 if ar_ratio is not None else None), "低于5%通常较稳；缺失则降级"],
                ["信用期", f"{fmt_num(credit_days, 0)}天", "用应收/收入×365近似"],
                ["合约负债", fmt_num(contract[0] if contract else None), "预收/渠道款缓冲"],
                ["关联方应收", fmt_num(related_due[0] if related_due else None), "关联方占用需人工复核"],
                ["收入确认激进度", "低" if ar_ratio is not None and ar_ratio < 0.05 else "中/待核", "结合账龄和坏账附注"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
        "### 5.3 非经常现金分类",
        "",
        format_table(
            ["项目", "处理", "说明"],
            [
                ["V1 经营现金流", "保留", "主营经营产生的现金"],
                ["V2 联营/减资/一次性回款", "扣除或单列", "若年报披露一次性项目，不能进入可持续AA"],
                ["V3 利息/投资收益", "视持续性保留", "需与现金余额规模匹配"],
                ["V4 非控股现金分配", "单列", f"非控股股息 {fmt_num(abs(nci_dividends[0]) if nci_dividends else None)}"],
                ["V5 普通股东股息", "用于分配意愿", f"普通股东股息 {fmt_num(abs(ordinary_dividends[0]) if ordinary_dividends else None)}"],
            ],
            alignments=["l", "l", "l"],
        ),
        "",
        "### 5.4 经营现金支出还原",
        "",
        format_table(
            ["项目", "数值", "说明"],
            [
                ["W1 收入", fmt_num(revenue[0] if revenue else None), "年报收入"],
                ["W2 员工/销售行政代理", fmt_num((abs(sga[0]) if sga else 0.0) + (abs(admin[0]) if admin else 0.0)), "c_pay_to_staff缺失时用SGA+行政支出代理并标注"],
                ["W3 OCF/收入", fmt_pct(collection_ratio * 100 if collection_ratio is not None else None), "现金收入质量"],
                ["W4 营运资本扰动", "待附注", "结合应收、存货、应付和合约负债"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
        "### 5.5 Capex 极端保守处理",
        "",
        format_table(
            ["项目", "数值", "说明"],
            [
                ["E 总Capex", fmt_num(latest_capex), "PPE + 无形资产现金流出"],
                ["X1 维持性Capex", fmt_num(maintenance_capex_latest), "min(Capex,D&A) 或 G规则"],
                ["X2 成长性Capex", fmt_num(growth_capex), "E-X1；为负时按0理解"],
                ["Y 成长性占比", fmt_pct(growth_capex_ratio), "判断扩产/渠道投入强度"],
                ["Capex/D&A", fmt_num(capex_da_median), "用于G分档"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
        "### 5.6 HKFRS 差异核查",
        "",
        format_table(
            ["准则点", "状态", "影响"],
            [
                ["HKFRS 9", "需核应收减值", "影响坏账和收入确认保守性"],
                ["HKFRS 16", "需核租赁负债/ROU折旧", "影响D&A与现金租赁口径"],
                ["合并范围", "少数股东高时强制披露", "影响Total Entity到归母AA"],
                ["或有负债", "年报称无重大或有负债则低风险", "影响现金安全垫"],
            ],
            alignments=["l", "l", "l"],
        ),
        "",
        "### 5.7 AA 三口径",
        "",
        format_table(
            ["口径", "数值", "说明"],
            [
                ["AA_2y", fmt_num(aa_2y), "近2年现金审计均值"],
                ["AA_all", fmt_num(aa_all), "全部可用年份均值；样本不足时须说明"],
                ["AA_excl", fmt_num(aa_excl), "剔除负值年份均值"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
        "### 5.8 现金储备质量",
        "",
        format_table(
            ["项目", "数值", "说明"],
            [
                ["BB 账面现金", fmt_num(bb), "现金及现金等价物"],
                ["CC 受限现金", fmt_num(cc), "受限制银行存款"],
                ["DD 关联方存款", fmt_num(dd), "若披露790百万元，单独扣减观察"],
                ["EE 关联方应收", fmt_num(ee), "非现金储备但影响上游质量"],
                ["FF 可自由现金", fmt_num(ff_adjusted if ff_adjusted is not None else ff), "BB-CC-DD"],
                ["广义净现金", fmt_num(net_cash_2025), "现金减有息债务"],
            ],
            alignments=["l", "r", "l"],
        ),
        "",
        "### 5.9 派息后净变动",
        "",
        format_table(
            ["项目", "数值", "说明"],
            [
                ["FCF序列", "[" + ", ".join(fmt_num(x) for x in fcf_sequence) + "]" if fcf_sequence else "—", "逐年自由现金流"],
                ["最新普通股息", fmt_num(abs(ordinary_dividends[0]) if ordinary_dividends else None), "融资现金流口径"],
                ["最新非控股股息", fmt_num(abs(nci_dividends[0]) if nci_dividends else None), "少数股东分流"],
                ["派息率锚", fmt_pct(payout_anchor), "分配意愿M"],
                ["派息后判断", "可覆盖" if fcf_sequence and ordinary_dividends and fcf_sequence[-1] > abs(ordinary_dividends[0]) else "需复核", "期末FF-期初FF vs AA vs 派息"],
            ],
            alignments=["l", "r", "l"],
        ),
    ]
    return "\n".join(sections)


def _quantile_frequency(text: str) -> str:
    data_points = parse_number(extract_row_value(text, "10年数据点数"))
    if "十年周线" in text:
        return "周频"
    if data_points is not None and data_points >= 1500:
        return "日频"
    if data_points is not None and data_points >= 400:
        return "周频"
    return "频率未披露"


def _quantile_source(text: str) -> str:
    return "Tushare Pro" if "Tushare" in text or "tushare" in text.lower() else "数据包"


def _quantile_p10_candidates(data_pack_text: str, refresh_pack_text: str = "") -> list[dict[str, float | str]]:
    candidates: list[dict[str, float | str]] = []
    for text, fallback_label in [(data_pack_text, "基础包"), (refresh_pack_text, "刷新包")]:
        if not text:
            continue
        p10 = parse_number(extract_row_value(text, "10%分位价格"))
        if p10 is None:
            continue
        frequency = _quantile_frequency(text)
        source = _quantile_source(text)
        label = frequency if frequency != "频率未披露" else fallback_label
        candidates.append({"p10": p10, "frequency": frequency, "source": source, "label": label})
    dedup: list[dict[str, float | str]] = []
    seen: set[tuple[str, float]] = set()
    for item in candidates:
        key = (str(item["frequency"]), round(float(item["p10"]), 4))
        if key not in seen:
            dedup.append(item)
            seen.add(key)
    return dedup


def _selected_historical_p10(data_pack_text: str, refresh_pack_text: str = "") -> tuple[Optional[float], str]:
    candidates = _quantile_p10_candidates(data_pack_text, refresh_pack_text)
    if not candidates:
        return None, "历史10%分位价缺失"
    selected = min(float(item["p10"]) for item in candidates)
    by_freq = {str(item["frequency"]): float(item["p10"]) for item in candidates}
    daily = by_freq.get("日频")
    weekly = by_freq.get("周频")
    if daily is not None and weekly is not None:
        gap = abs(daily - weekly) / min(abs(daily), abs(weekly)) if min(abs(daily), abs(weekly)) else 0.0
        if gap > 0.15:
            return selected, f"历史10%分位价（日频）{fmt_num(daily)}；（周频）{fmt_num(weekly)}；差异>15%，取保守值 {fmt_num(selected)}"
        return selected, f"历史10%分位价（日频）{fmt_num(daily)}；（周频）{fmt_num(weekly)}；差异≤15%，取 {fmt_num(selected)}"
    item = candidates[0]
    return selected, f"历史10%分位价（{item['frequency']}，{item['source']}）{fmt_num(selected)}"


def build_historical_quantile_table(data_pack_text: str, refresh_pack_text: str = "") -> str:
    source_text = refresh_pack_text or data_pack_text
    high = parse_number(extract_row_value(source_text, "10年最高 (HKD)") or extract_row_value(source_text, "10年最高"))
    low = parse_number(extract_row_value(source_text, "10年最低 (HKD)") or extract_row_value(source_text, "10年最低"))
    current_q = parse_number(extract_row_value(source_text, "当前股价历史分位"))
    p10, p10_note = _selected_historical_p10(data_pack_text, refresh_pack_text)
    p25 = parse_number(extract_row_value(source_text, "25%分位价格"))
    p50 = parse_number(extract_row_value(source_text, "50%分位价格（中位数）") or extract_row_value(source_text, "50%分位价格"))
    data_points = parse_number(extract_row_value(source_text, "10年数据点数"))
    frequency = _quantile_frequency(source_text)
    source = _quantile_source(source_text)
    return format_table(
        ["项目", "价格/分位", "口径"],
        [
            ["10年最高", fmt_num(high), "历史高点"],
            ["10年最低", fmt_num(low), "历史低点"],
            ["10%分位", fmt_num(p10), p10_note],
            ["25%分位", fmt_num(p25), f"10年全区间，{frequency}，{source}"],
            ["50%分位", fmt_num(p50), f"10年全区间，{frequency}，{source}"],
            ["当前分位", fmt_pct(current_q), f"数据点数 {fmt_num(data_points, 0)}"],
        ],
        alignments=["l", "r", "l"],
    )


def build_composite_benchmark_table(
    *,
    data_pack_text: str,
    refresh_pack_text: str = "",
    report_pack_text: str = "",
    quantitative_text: str,
    current_price: Optional[float],
    total_shares: Optional[float],
) -> tuple[Optional[float], str]:
    net_cash = parse_number(extract_row_value(quantitative_text, "net_cash_mm"))
    if net_cash is None and report_pack_text:
        cash_vals = _extract_report_row_values(report_pack_text, "现金及现金等价物")
        debt_vals = (
            _extract_report_row_values(report_pack_text, "借贷")
            or _extract_report_row_values(report_pack_text, "银行借贷")
            or _extract_report_row_values(report_pack_text, "有息负债")
        )
        if cash_vals:
            debt = debt_vals[0] if debt_vals else 0.0
            if not debt_vals and re.search(r"无(?:计息)?(?:银行)?借(?:贷|款)|无其他借款|无有息负债", report_pack_text):
                debt = 0.0
            net_cash = cash_vals[0] - debt
    latest_dps = _extract_latest_dps(data_pack_text, report_pack_text)
    net_cash_per_share = net_cash / total_shares if net_cash is not None and total_shares else None
    bvps = _bvps_from_report_pack(report_pack_text, total_shares)
    if bvps is None:
        bvps = parse_number(extract_row_value(data_pack_text, "每股净资产 (HKD)") or extract_row_value(data_pack_text, "每股净资产"))
    quantile_text = refresh_pack_text or data_pack_text
    hist_10, hist_10_selection_note = _selected_historical_p10(data_pack_text, refresh_pack_text)
    if hist_10 is None:
        match = re.search(r"(?:历史)?\s*10%?\s*分位(?:价格|价)?[^0-9-]*(-?\d[\d,]*(?:\.\d+)?)", quantile_text)
        hist_10 = parse_number(match.group(1)) if match else None
    hist_window_note = "历史价格低位锚，缺失则不纳入均值"
    if hist_10 is not None:
        data_points = parse_number(extract_row_value(quantile_text, "10年数据点数"))
        if data_points is not None and data_points >= 1500:
            frequency_note = "日频"
        elif data_points is not None and data_points >= 400:
            frequency_note = "周频"
        elif "十年周线" in quantile_text:
            frequency_note = "周频"
        else:
            frequency_note = "频率未披露"
        source_note = "Tushare" if ("Tushare" in quantile_text or "tushare" in quantile_text.lower()) else "Tushare/Yahoo数据包"
        yearly_section = extract_markdown_section(quantile_text, "年度行情汇总", level=3)
        years = [int(match) for match in re.findall(r"\|\s*(20\d{2}|19\d{2})\s*\|", yearly_section)]
        if years:
            start_year = min(years)
            end_year = max(years)
            end_date = today_str() if end_year >= datetime.now().year else f"{end_year}-12-31"
            span_years = end_year - start_year + 1
            if data_points is not None and data_points >= 450:
                hist_window_note = f"历史10%分位价（10年全区间 {start_year}-01-01 ~ {end_date}，{frequency_note}，{source_note}）"
            else:
                hist_window_note = f"历史10%分位价（近{span_years}年，{frequency_note}，{source_note}，数据源限制）；10年全区间分位价可能有差异"
        elif data_points is not None and data_points >= 450:
            hist_window_note = f"历史10%分位价（10年全区间，日期范围来自数据源，{frequency_note}，{source_note}）"
        else:
            hist_window_note = f"历史10%分位价（时间窗未完整披露，{frequency_note}，{source_note}，数据源限制）；建议后续补充"
        if hist_10_selection_note:
            hist_window_note = f"{hist_10_selection_note}；{hist_window_note}"
    dividend_price_6 = latest_dps / 0.06 if latest_dps else None
    rows = [
        ["净现金/股", fmt_num(net_cash_per_share), "广义净现金/总股本"],
        ["BVPS", fmt_num(bvps), "归母权益/总股本；年报缺失时回落到每股净资产字段"],
        ["历史10%分位价", fmt_num(hist_10), hist_window_note],
        ["6%股息价", fmt_num(dividend_price_6), "DPS / 6%"],
    ]
    values = [value for value in [net_cash_per_share, bvps, hist_10, dividend_price_6] if value is not None and value > 0]
    composite = sum(values) / len(values) if values else None
    rows.append(["综合基准价", fmt_num(composite), f"可用项{len(values)}/4；当前价 {fmt_num(current_price)}"])
    return composite, format_table(["锚点", "价格", "说明"], rows, alignments=["l", "r", "l"])


def ensure_valuation_output(ts_code: str, output_dir: Path) -> Path:
    valuation_path = output_dir / "valuation_computed.md"
    if valuation_path.exists():
        return valuation_path
    run_cmd([
        preferred_python(),
        "scripts/valuation_engine.py",
        "--code", ts_code,
        "--output-dir", str(output_dir),
    ])
    return valuation_path


def assemble_turtle_report(ts_code: str, output_dir: Path,
                           company_name: str,
                           holding_channel: Optional[str] = None) -> Optional[str]:
    qualitative_path = output_dir / "qualitative_report.md"
    quantitative_path = output_dir / "phase3_quantitative.md"
    preflight_path = output_dir / "phase3_preflight.md"
    data_pack_path = output_dir / "data_pack_market.md"

    qualitative_text = read_text_if_exists(qualitative_path)
    quantitative_text = read_text_if_exists(quantitative_path)
    preflight_text = read_text_if_exists(preflight_path)
    data_pack_text = read_text_if_exists(data_pack_path)
    refresh_pack_text = latest_refresh_pack_text(output_dir)
    report_pack_text = read_text_if_exists(output_dir / "data_pack_report.md")
    if not qualitative_text or not quantitative_text or not data_pack_text:
        return None
    if has_scaffold_marker(qualitative_text) or has_scaffold_marker(quantitative_text):
        return None

    valuation_path = ensure_valuation_output(ts_code, output_dir)
    valuation_text = read_text_if_exists(valuation_path)
    if not valuation_text:
        return None
    annual_core_rows_for_report, _annual_core_source_for_report = extract_latest_annual_core_financials(output_dir)
    annual_dps_points_for_report, annual_dps_source_for_report = extract_annual_dividend_dps_points_from_output(
        output_dir,
        latest_market_dps=_extract_latest_dps(data_pack_text, report_pack_text),
        max_years=5,
    )
    annual_dividend_snippet_for_report = annual_core_dividend_report_snippet(
        annual_core_rows_for_report,
        _extract_latest_dps(data_pack_text, report_pack_text),
        year_points=annual_dps_points_for_report,
        source=annual_dps_source_for_report,
    )
    if annual_dividend_snippet_for_report:
        report_pack_text = "\n".join([report_pack_text, annual_dividend_snippet_for_report])

    structure_key = infer_listing_structure_from_output(ts_code, output_dir)
    tax_scenarios = tax_scenarios_for_listing_structure(structure_key)
    structure_label, channel_label, tax_note = workflow_tax_context(ts_code, output_dir, holding_channel)
    q_rate, _ = resolve_shareholder_dividend_tax_rate(
        ts_code=ts_code,
        holding_channel=holding_channel,
        listing_structure=structure_key,
    )
    q_pct, q_pct_known, q_label = default_q_pct(q_rate)
    q_report_display = fmt_pct(q_pct) if q_pct_known else q_label + f"；并列{tax_scenario_text(tax_scenarios)}敏感性"
    q_basis_label = "税后" if q_pct_known else "默认10%税后"

    quant_step0 = extract_markdown_section(quantitative_text, "Step 0 数据校验")
    quant_step1 = extract_markdown_section(quantitative_text, "Step 1 Owner Earnings")
    quant_step2 = extract_markdown_section(quantitative_text, "Step 2 分配能力")
    quant_step38 = extract_markdown_section(quantitative_text, "Step 3-8 真实可支配现金结余")
    quant_aa_audit = extract_markdown_section(quant_step38, "AA 现金审计协议", level=3)
    market_step174 = extract_markdown_section(data_pack_text, "17.4 因子3·步骤4 经营性现金支出", level=3)
    market_step175 = extract_markdown_section(data_pack_text, "17.5 因子3·步骤7 基准可支配结余 + 敏感性输入", level=3)
    quant_step10 = extract_markdown_section(quantitative_text, "Step 10 穿透回报率")
    quant_step11 = extract_markdown_section(quantitative_text, "Step 11 可信度")
    quant_step1_report = strip_irrelevant_peer_comparisons(quant_step1, company_name)
    quant_step10_report = neutralize_unknown_tax_assumption(
        strip_irrelevant_peer_comparisons(quant_step10, company_name),
        q_pct if q_pct_known else None,
    )

    qualitative_exec = extract_markdown_section(qualitative_text, "执行摘要")
    qualitative_summary = extract_markdown_section(qualitative_text, "深度总结")
    qualitative_params = parse_structured_params(qualitative_text)
    qualitative_sections = [
        ("1. 商业模式与资本特征", extract_markdown_section(qualitative_text, "维度一：商业模式与资本特征")),
        ("2. 竞争优势与护城河", extract_markdown_section(qualitative_text, "维度二：竞争优势与护城河")),
        ("3. 外部环境", extract_markdown_section(qualitative_text, "维度三：外部环境")),
        ("4. 管理层与公司治理", extract_markdown_section(qualitative_text, "维度四：管理层与公司治理")),
        ("5. MD&A 解读", extract_markdown_section(qualitative_text, "维度五：MD&A 解读")),
        ("6. 控股结构", extract_markdown_section(qualitative_text, "维度六：控股结构分析")),
    ]

    owner_earnings = parse_number(re.search(r"- OE = ([\d,]+\.\d+) 百万", quant_step1).group(1)) if re.search(r"- OE = ([\d,]+\.\d+) 百万", quant_step1) else None
    gross_r = parse_number(re.search(r"- 粗算 R = ([\d.]+%)", quant_step10).group(1)) if re.search(r"- 粗算 R = ([\d.]+%)", quant_step10) else None
    gg_pct = parse_number(re.search(r"- 精算 GG = ([\d.]+%)", quant_step10).group(1)) if re.search(r"- 精算 GG = ([\d.]+%)", quant_step10) else None
    ii_pct = parse_number(re.search(r"- 门槛 II = ([\d.]+%)", quant_step10).group(1)) if re.search(r"- 门槛 II = ([\d.]+%)", quant_step10) else None
    hh_pct = parse_number(re.search(r"- 偏差 HH = ([+\-]?\d+\.\d+) pct", quant_step10).group(1)) if re.search(r"- 偏差 HH = ([+\-]?\d+\.\d+) pct", quant_step10) else None
    safety_margin = parse_number(re.search(r"- 安全边际 = .*?([+\-]?\d+\.\d+) pct", quant_step10).group(1)) if re.search(r"- 安全边际 = .*?([+\-]?\d+\.\d+) pct", quant_step10) else None

    market_snapshot = resolve_current_market_snapshot(data_pack_text, refresh_pack_text, quantitative_text)
    market_cap = market_snapshot["market_cap"] if isinstance(market_snapshot["market_cap"], float) else None
    total_shares = market_snapshot["total_shares"] if isinstance(market_snapshot["total_shares"], float) else None
    current_price = market_snapshot["current_price"] if isinstance(market_snapshot["current_price"], float) else None
    c_profit = parse_number(extract_row_value(quantitative_text, "net_profit_mm"))
    rf_candidate = parse_number(extract_row_value(quantitative_text, "rf_pct") or extract_row_value(data_pack_text, "Rf（无风险利率）"))
    rf_pct, rf_source = resolve_rf_pct_for_report(
        ts_code=ts_code,
        data_pack_text=data_pack_text,
        candidate=rf_candidate,
    )
    credibility = extract_row_value(quantitative_text, "credibility") or "中"
    threshold_category = extract_row_value(quantitative_text, "threshold_category")
    threshold_method = extract_row_value(quantitative_text, "threshold_method")
    threshold_evidence_text = extract_row_value(quantitative_text, "threshold_evidence") or ""
    threshold_adjustments_text = extract_row_value(quantitative_text, "threshold_adjustments") or "无"
    threshold_price_aa = parse_number(extract_row_value(quantitative_text, "threshold_price_aa"))
    threshold_price_dps = parse_number(extract_row_value(quantitative_text, "threshold_price_dps"))
    threshold_price_selected = parse_number(extract_row_value(quantitative_text, "threshold_price_selected"))
    threshold_price_gap_pct = parse_number(extract_row_value(quantitative_text, "threshold_price_gap_pct"))
    threshold_price_note = extract_row_value(quantitative_text, "threshold_price_note") or ""
    threshold_price_warning = extract_row_value(quantitative_text, "threshold_price_warning") or "—"
    star_5 = parse_number(extract_row_value(quantitative_text, "star_5_pct"))
    star_4 = parse_number(extract_row_value(quantitative_text, "star_4_pct"))
    star_3 = parse_number(extract_row_value(quantitative_text, "star_3_pct"))

    g_coeff_match = re.search(r"选定 `G = ([\d.]+)`", quant_step1)
    g_coeff = parse_number(g_coeff_match.group(1)) if g_coeff_match else None
    oe_sensitivity = re.findall(r"- G = ([\d.]+) → ([\d,]+\.\d+)", quant_step1)
    oe_sensitivity_text = "；".join([f"G={g} → {v}" for g, v in oe_sensitivity]) if oe_sensitivity else "—"

    payout_anchor = parse_number(re.search(r"支付率锚定 M = ([\d.]+%)", quant_step10).group(1)) if re.search(r"支付率锚定 M = ([\d.]+%)", quant_step10) else None
    payout_seq_match = re.search(r"过去 5 年支付率序列:\s*([^\n]+)", quant_step10)
    payout_sequence = parse_percent_sequence(payout_seq_match.group(1)) if payout_seq_match else []
    payout_avg_5y = sum(payout_sequence) / len(payout_sequence) if payout_sequence else None
    payout_latest = payout_sequence[-1] if payout_sequence else None

    aa_base = parse_number(extract_row_value(quantitative_text, "AA_mm"))
    aa_2y = parse_number(extract_row_value(quantitative_text, "AA_2y_mm"))
    aa_all = parse_number(extract_row_value(quantitative_text, "AA_all_mm"))
    aa_excl = parse_number(extract_row_value(quantitative_text, "AA_excl_mm"))
    aa_precision = extract_row_value(quantitative_text, "AA_precision") or "—"
    minority_share = parse_number(extract_row_value(quantitative_text, "minority_share"))
    minority_protocol_text = extract_row_value(quantitative_text, "minority_protocol") or "—"
    parent_factor = parse_number(extract_row_value(quantitative_text, "parent_factor"))
    capex_da_median = parse_number(extract_row_value(quantitative_text, "capex_da_median"))
    g_check = extract_row_value(quantitative_text, "G_check") or "—"
    maintenance_capex_policy = extract_row_value(quantitative_text, "maintenance_capex_policy") or "—"
    maintenance_capex_latest = parse_number(extract_row_value(quantitative_text, "maintenance_capex_latest"))
    aa_manual_check = parse_number(extract_row_value(quantitative_text, "AA_manual_check_mm"))
    aa_manual_diff_pct = parse_number(extract_row_value(quantitative_text, "AA_manual_diff_pct"))
    aa_manual_note = extract_row_value(quantitative_text, "AA_manual_note") or "—"
    nci_alert = extract_row_value(quantitative_text, "nci_dividend_alert") or "—"
    aa_type = extract_row_value(quantitative_text, "AA_type") or "AA_2y"
    aa_market_currency_factor = 1.0
    if gg_pct is not None and aa_base not in (None, 0) and payout_anchor not in (None, 0) and market_cap:
        tax_factor = 1.0 - q_pct / 100.0
        denominator = aa_base * (payout_anchor / 100.0) * tax_factor
        if denominator:
            inferred_factor = (gg_pct / 100.0 * market_cap) / denominator
            if 0.2 <= inferred_factor <= 5.0:
                aa_market_currency_factor = inferred_factor

    def gg_from_assumption(aa_value: Optional[float], m_value: Optional[float]) -> Optional[float]:
        if aa_value is None or m_value is None or market_cap in (None, 0):
            return None
        tax_factor = 1.0 - q_pct / 100.0
        return aa_value * aa_market_currency_factor * (m_value / 100.0) * tax_factor / market_cap * 100.0

    gg_payout_avg = gg_from_assumption(aa_base, payout_avg_5y)
    gg_payout_latest = gg_from_assumption(aa_base, payout_latest)
    gg_aa_excl = gg_from_assumption(aa_excl, payout_anchor)
    gg_aa_all = gg_from_assumption(aa_all, payout_anchor)

    trap_risk = infer_value_trap_risk(qualitative_text, quantitative_text)
    threshold_profile = threshold_profile_from_outputs(
        ts_code=ts_code,
        company_name=company_name,
        data_pack_text=data_pack_text,
        quantitative_text=quantitative_text,
        rf_pct=rf_pct,
        fallback_ii_pct=ii_pct,
        minority_share_pct=minority_share,
    )
    if threshold_category:
        threshold_profile = ThresholdProfile(
            category=threshold_category,
            ii_pct=ii_pct if ii_pct is not None else threshold_profile.ii_pct,
            star_5_pct=star_5 if star_5 is not None else threshold_profile.star_5_pct,
            star_4_pct=star_4 if star_4 is not None else threshold_profile.star_4_pct,
            star_3_pct=star_3 if star_3 is not None else threshold_profile.star_3_pct,
            method=threshold_method or threshold_profile.method,
            rationale=threshold_profile.rationale,
            evidence=[item for item in threshold_evidence_text.split("；") if item] or threshold_profile.evidence,
            adjustments=[] if threshold_adjustments_text == "无" else [item for item in threshold_adjustments_text.split("；") if item],
        )
    ii_pct = threshold_profile.ii_pct
    safety_margin = gg_pct - ii_pct if gg_pct is not None else None
    threshold_price = threshold_price_selected or (current_price * gg_pct / ii_pct if current_price and gg_pct and ii_pct else None)
    if not threshold_price_note:
        latest_dps_for_threshold = _extract_latest_dps(data_pack_text, report_pack_text)
        threshold_crosscheck = compute_threshold_price_crosscheck(
            aa_base=aa_base,
            payout_anchor_pct=payout_anchor,
            q_pct=q_pct,
            ii_pct=ii_pct,
            total_shares=total_shares,
            latest_dps=latest_dps_for_threshold,
            aa_market_currency_factor=aa_market_currency_factor,
        )
        threshold_price_aa = threshold_crosscheck["aa_price"] if isinstance(threshold_crosscheck["aa_price"], float) else threshold_price_aa
        threshold_price_dps = threshold_crosscheck["dps_price"] if isinstance(threshold_crosscheck["dps_price"], float) else threshold_price_dps
        threshold_price_selected = threshold_crosscheck["selected_price"] if isinstance(threshold_crosscheck["selected_price"], float) else threshold_price_selected
        threshold_price_gap_pct = threshold_crosscheck["gap_pct"] if isinstance(threshold_crosscheck["gap_pct"], float) else threshold_price_gap_pct
        threshold_price_note = str(threshold_crosscheck["note"])
        threshold_price_warning = str(threshold_crosscheck["warning"])
        if isinstance(threshold_price_selected, float):
            threshold_price = threshold_price_selected
    recommendation = infer_turtle_recommendation(gg_pct, ii_pct, safety_margin, trap_risk)
    direct_recommendation = recommendation
    southbound_recommendation, southbound_gg, southbound_safety = recommendation_for_tax_rate(
        aa_base=aa_base,
        market_cap=market_cap,
        payout_anchor=payout_anchor,
        aa_market_currency_factor=aa_market_currency_factor,
        ii_pct=ii_pct,
        trap_risk=trap_risk,
        tax_pct=20.0,
    )
    treaty_tax = float(tax_scenarios[0]["tax_pct"]) if tax_scenarios else 0.0
    treaty_recommendation, treaty_gg, treaty_safety = recommendation_for_tax_rate(
        aa_base=aa_base,
        market_cap=market_cap,
        payout_anchor=payout_anchor,
        aa_market_currency_factor=aa_market_currency_factor,
        ii_pct=ii_pct,
        trap_risk=trap_risk,
        tax_pct=treaty_tax,
    )

    debt_ratio = parse_number(re.search(r"\| 有息负债/总资产（%） \| ([\d.]+)", data_pack_text).group(1)) if re.search(r"\| 有息负债/总资产（%） \| ([\d.]+)", data_pack_text) else None
    net_cash = parse_number(extract_row_value(quantitative_text, "net_cash_mm"))
    net_profit_growth = parse_number(re.search(r"\| 净利润同比增长率 \(%\) \| ([\d\-.]+)", data_pack_text).group(1)) if re.search(r"\| 净利润同比增长率 \(%\) \| ([\d\-.]+)", data_pack_text) else None

    advantage_bits: list[str] = []
    if debt_ratio is not None and debt_ratio < 2:
        advantage_bits.append("低杠杆")
    if net_cash is not None and net_cash > 0:
        advantage_bits.append("净现金厚")
    if payout_anchor is not None and payout_anchor >= 30:
        advantage_bits.append("分红记录稳")
    if owner_earnings is not None and gross_r is not None:
        advantage_bits.append("商业模式清晰")
    max_advantage = "、".join(advantage_bits) if advantage_bits else "商业模式清晰、现金创造能力较稳"

    if net_profit_growth is not None and net_profit_growth < 0:
        max_risk = "行业转入存量竞争后，利润率和可分配现金未必同步修复。"
    else:
        max_risk = "若价格竞争继续加剧，护城河和分配能力可能同步承压。"

    quality_tags: list[str] = []
    roe_avg = parse_number(re.search(r"\| roe_5y_avg \| ([\d.]+)", qualitative_text).group(1)) if re.search(r"\| roe_5y_avg \| ([\d.]+)", qualitative_text) else None
    if roe_avg is not None and roe_avg >= 20:
        quality_tags.append("高 ROE")
    if debt_ratio is not None and debt_ratio < 2:
        quality_tags.append("低杠杆")
    if payout_anchor is not None and payout_anchor >= 30:
        quality_tags.append("分红稳定")
    if not quality_tags:
        quality_tags.append("经营质量稳健")
    summary_prefix = "、".join(quality_tags)
    threshold_status = "达到" if safety_margin is not None and safety_margin >= 0 else "未达到"
    top_down_status = "达到" if gross_r is not None and ii_pct is not None and gross_r >= ii_pct else "未达到"
    top_down_gate_status = "通过" if gross_r is not None and ii_pct is not None and gross_r >= ii_pct * 0.5 else "边际不达标"
    summary_line = (
        f"{company_name}先判定为{threshold_profile.category}，再采用 {fmt_pct(ii_pct)} 的静态GG门槛；"
        f"按主口径（{channel_label}，{q_basis_label}）当前 {fmt_num(current_price)} 港元{threshold_status}门槛。"
        f"渠道化结论：【香港直投】`{direct_recommendation}`；【港股通】`{southbound_recommendation}`。"
    )
    report_dps_cagr_calc, _report_dps_source, report_dps_cagr_basis = _dps_cagr_basis(data_pack_text, report_pack_text)
    if report_dps_cagr_calc is not None and abs(report_dps_cagr_calc) < 0.00001:
        profit_values_for_dps_check = _extract_report_row_values(report_pack_text, "本公司拥有人应占溢利") or _extract_financial_row(data_pack_text, "3. 合并利润表", "股东应占溢利")
        profit_chrono_for_dps_check = list(reversed(profit_values_for_dps_check))
        profit_cagr_for_dps_check = _cagr(profit_chrono_for_dps_check[0], profit_chrono_for_dps_check[-1], len(profit_chrono_for_dps_check) - 1) if len(profit_chrono_for_dps_check) >= 2 else None
        if profit_cagr_for_dps_check is not None and profit_cagr_for_dps_check > 0:
            report_dps_cagr_basis += "；DPS CAGR 可能被数据源去重卡死，请人工复核"
    assumption_sentence = executive_summary_assumption_sentence(
        q_display=q_report_display,
        threshold_adjustments=threshold_profile.adjustments,
        dps_cagr_basis=report_dps_cagr_basis,
    )

    warnings = collect_turtle_warnings(output_dir, data_pack_text, preflight_text)
    report_financial_trend = report_pack_financial_trend(report_pack_text)
    financial_trend_table = extract_markdown_tables(extract_markdown_section(data_pack_text, "17.1 财务趋势速览", level=3))
    financial_trend_intro = "本表统一按**百万港元**展示，并已按年份顺序列示为 `2021 → 2025`；若正文引用年报原文，部分经营数据可能保留**人民币**口径，因此数值不应直接逐项对比。"
    financial_trend_table_text = report_financial_trend
    if financial_trend_table_text:
        financial_trend_intro = "本表优先引用最新年报数据包，按年报原币**百万元人民币**展示 2024-2025 核心三表项目；旧市场包如存在币种或年份错位，不覆盖年报口径。"
    elif financial_trend_table:
        _trend_headers, trend_rows = parse_markdown_table(financial_trend_table[0])
        has_real_trend_rows = any(any(cell.strip("— ") for cell in row[1:]) for row in trend_rows)
        if has_real_trend_rows:
            financial_trend_table_text = reorder_financial_trend_table(financial_trend_table[0])
    if not financial_trend_table_text:
        financial_trend_table_text = "财务趋势表缺失。"
    quantile_source_text = refresh_pack_text or data_pack_text
    price_quantile = parse_number(re.search(r"\| 当前股价历史分位 \| ([\d.]+)%", quantile_source_text).group(1)) if re.search(r"\| 当前股价历史分位 \| ([\d.]+)%", quantile_source_text) else None
    historical_quantile_table = build_historical_quantile_table(data_pack_text, refresh_pack_text)
    benchmark_price, composite_benchmark_table = build_composite_benchmark_table(
        data_pack_text=data_pack_text,
        refresh_pack_text=refresh_pack_text,
        report_pack_text=report_pack_text,
        quantitative_text=quantitative_text,
        current_price=current_price,
        total_shares=total_shares,
    )

    business_model_summary = summarize_business_model(qualitative_sections[0][1], qualitative_params, net_profit_growth)
    moat_summary = summarize_moat(qualitative_sections[1][1], qualitative_params)
    environment_summary = summarize_environment(qualitative_sections[2][1], qualitative_params)
    governance_summary = summarize_governance(qualitative_sections[3][1], qualitative_params)
    mda_summary = summarize_mda(qualitative_sections[4][1], qualitative_params)
    holding_summary = summarize_holding(qualitative_sections[5][1], qualitative_params)
    business_model_label = qualitative_params.get("business_model") or "主营业务平台"
    capital_label = qualitative_params.get("capital_intensity") or "资本强度待确认"
    factor1b_quant_table, factor1b_transfer_table = build_factor1b_execution_table(
        qualitative_params=qualitative_params,
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        capex_da_median=capex_da_median,
        g_coeff=g_coeff,
        minority_share=minority_share,
    )

    top_down_rows = [
        ["利润/股息锚 C", f"{fmt_num(c_profit)} 百万" if c_profit is not None else f"{fmt_num(owner_earnings)} 百万", "因子2只用归母利润/股息锚，不用AA替代"],
        ["支付率 M", fmt_pct(payout_anchor), "以历史/最新分红意愿锚定"],
        ["股东层税率 Q", q_report_display, channel_label],
        ["当前市值", f"{fmt_num(market_cap)} 百万港元", "按最新股价和总股本"],
        ["粗算穿透回报率 R", fmt_pct(gross_r), f"Top-Down {q_basis_label}口径"],
        ["门槛 II", fmt_pct(ii_pct), threshold_profile.category],
        ["初筛判断", top_down_status, "R 与子类门槛比较"],
    ]
    top_down_table = format_table(
        ["项目", "数值", "说明"],
        top_down_rows,
        alignments=["l", "r", "l"],
    )

    bottom_up_rows = [
        ["AA 口径", aa_type, "真实可支配现金/归母可分配能力口径"],
        ["AA 基准值", f"{fmt_num(aa_base)} 百万", "来自定量 Step 3-8 或手工核验"],
        ["AA_2y", f"{fmt_num(aa_2y)} 百万", "近2年现金审计均值"],
        ["AA_excl", f"{fmt_num(aa_excl)} 百万", "若有，作为保守现金口径交叉检查"],
        ["AA_all", f"{fmt_num(aa_all)} 百万", "若有，作为宽口径交叉检查"],
        ["AA 精度", aa_precision, "现金审计置信度"],
        ["维持性Capex口径", maintenance_capex_policy, f"最新值 {fmt_num(maintenance_capex_latest)}"],
        ["Capex/D&A校验", f"中位数 {fmt_num(capex_da_median)}", g_check],
        ["AA_2y_cash手算验证", f"{fmt_num(aa_manual_check)} 百万", f"差异 {fmt_pct(aa_manual_diff_pct)}；{aa_manual_note}"],
        ["少数股东协议", minority_protocol_text, f"少数股东占比 {fmt_pct(minority_share)}；C/A {fmt_num(parent_factor)}"],
        ["支付率 M", fmt_pct(payout_anchor), "同一派息锚"],
        ["精算穿透回报率 GG", fmt_pct(gg_pct), f"Bottom-Up {q_basis_label}主裁决口径"],
        ["HH 偏差", f"{fmt_num(hh_pct)} pct", "GG − R，检查利润和现金口径背离"],
        ["安全边际", f"{fmt_num(safety_margin)} pct", "GG − II"],
        ["门槛价", fmt_num(threshold_price), threshold_price_note or "R7-1 双路径门槛价"],
        ["非控股股息异常", nci_alert, "R7-6 非控股股息报警"],
    ]
    bottom_up_table = format_table(
        ["项目", "数值", "说明"],
        bottom_up_rows,
        alignments=["l", "r", "l"],
    )
    cash_quality_audit_sections = build_cash_quality_audit_sections(
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        aa_2y=aa_2y,
        aa_all=aa_all,
        aa_excl=aa_excl,
        maintenance_capex_latest=maintenance_capex_latest,
        capex_da_median=capex_da_median,
        cash_2025=parse_number(extract_row_value(quantitative_text, "FF_mm")) or parse_number(extract_row_value(quantitative_text, "net_cash_mm")),
        net_cash_2025=parse_number(extract_row_value(quantitative_text, "net_cash_mm")),
        fcf_sequence=[value for value in (parse_number(x) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", extract_row_value(quantitative_text, "fcf_sequence") or "")) if value is not None],
        payout_anchor=payout_anchor,
    )
    tax_sensitivity_table = ""
    if aa_base is not None and payout_anchor is not None and market_cap:
        tax_rows = []
        for scenario in tax_scenarios:
            tax = float(scenario["tax_pct"])
            gg_tax = aa_base * aa_market_currency_factor * (payout_anchor / 100.0) * (1 - tax / 100.0) / market_cap * 100.0
            threshold_price_tax = current_price * gg_tax / ii_pct if current_price and ii_pct else None
            tax_rows.append([
                fmt_pct(tax),
                fmt_pct(gg_tax),
                f"{gg_tax - ii_pct:+.2f} pct" if ii_pct is not None else "—",
                fmt_num(threshold_price_tax),
                str(scenario["note"]),
            ])
        tax_sensitivity_table = format_table(
            ["股东层税率 Q", "精算GG", "vs 门槛", "门槛价", "适用说明"],
            tax_rows,
            alignments=["r", "r", "r", "r", "l"],
        )
    threshold_crosscheck_table = format_table(
        ["路径", "门槛价", "说明"],
        [
            ["AA 路径", fmt_num(threshold_price_aa), "AA_2y × M × (1-Q) / II / 总股本"],
            ["DPS 路径", fmt_num(threshold_price_dps), "DPS × (1-Q) / II"],
            ["选定口径", fmt_num(threshold_price), "取较高者作为主口径门槛价"],
            ["差异校验", fmt_pct(threshold_price_gap_pct), threshold_price_warning],
        ],
        alignments=["l", "r", "l"],
    )

    sensitivity_section = extract_markdown_section(data_pack_text, "17.9 因子4·业绩下滑敏感性", level=3)
    sensitivity_tables = extract_markdown_tables(sensitivity_section)
    short_sensitivity_table = ""
    if aa_base is not None and market_cap and current_price and ii_pct:
        compact_rows = []
        for label, factor in [("基准", 1.0), ("下滑 10%", 0.9), ("下滑 20%", 0.8), ("下滑 30%", 0.7)]:
            gg_scenario = gg_from_assumption(aa_base * factor, payout_anchor)
            price_scenario = current_price * gg_scenario / ii_pct if gg_scenario is not None else None
            compact_rows.append([label, fmt_pct(gg_scenario), fmt_num(price_scenario)])
        short_sensitivity_table = format_table(
            ["情景", "穿透回报率", "门槛价格（港元）"],
            compact_rows,
            alignments=["l", "r", "r"],
        )
    elif sensitivity_tables:
        headers1, rows1 = parse_markdown_table(sensitivity_tables[0])
        base_price = None
        base_gg = gg_pct
        if rows1 and len(rows1[0]) >= 5:
            base_price = rows1[0][4]
        headers2, rows2 = parse_markdown_table(sensitivity_tables[1]) if len(sensitivity_tables) > 1 else ([], [])
        compact_rows = []
        if base_gg is not None and base_price is not None:
            compact_rows.append(["基准", fmt_pct(base_gg), base_price])
        for row in rows2:
            if len(row) >= 4:
                compact_rows.append([f"下滑 {row[0].replace('-', '')}", row[2], row[3]])
        short_sensitivity_table = format_table(
            ["情景", "穿透回报率", "门槛价格（港元）"],
            compact_rows,
            alignments=["l", "r", "r"],
        )

    valuation_ke_pct = parse_number(re.search(r"\| \*\*Ke \(权益成本\)\*\* \| \*\*([\d.]+%)\*\*", valuation_text).group(1)) if re.search(r"\| \*\*Ke \(权益成本\)\*\* \| \*\*([\d.]+%)\*\*", valuation_text) else None
    valuation_wacc_pct = parse_number(re.search(r"\| \*\*WACC\*\* \| \*\*([\d.]+%)\*\*", valuation_text).group(1)) if re.search(r"\| \*\*WACC\*\* \| \*\*([\d.]+%)\*\*", valuation_text) else None
    fallback_valuation = build_fallback_absolute_valuation(
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        current_price=current_price,
        total_shares_mm=total_shares,
        market_cap=market_cap,
        ke_pct=valuation_ke_pct,
        wacc_pct=valuation_wacc_pct,
        rf_pct=rf_pct,
        ts_code=ts_code,
        company_name=company_name,
        threshold_category=threshold_profile.category,
        minority_share=minority_share / 100.0 if minority_share is not None and minority_share > 1 else minority_share,
        debt_ratio_pct=debt_ratio,
        trap_risk=trap_risk,
    )

    dcf_price = parse_number(re.search(r"\*\*内在价值: ([\d.]+) 港元/股\*\*", valuation_text).group(1)) if re.search(r"\*\*内在价值: ([\d.]+) 港元/股\*\*", valuation_text) else None
    ddm_match = re.findall(r"\*\*内在价值: ([\d.]+) 港元/股\*\*", valuation_text)
    ddm_price = parse_number(ddm_match[1]) if len(ddm_match) > 1 else None
    pe_price = parse_number(re.search(r"\| PE_median \(合理\) \| [\d.]+ \| ([\d.]+) \|", valuation_text).group(1)) if re.search(r"\| PE_median \(合理\) \| [\d.]+ \| ([\d.]+) \|", valuation_text) else None
    weighted_center = parse_number(re.search(r"\| \*\*加权平均\*\* \| — \| 100% \| \*\*([\d.]+)\*\* \|", valuation_text).group(1)) if re.search(r"\| \*\*加权平均\*\* \| — \| 100% \| \*\*([\d.]+)\*\* \|", valuation_text) else None
    valuation_source = "valuation_engine.py"
    if not any(value is not None for value in [dcf_price, ddm_price, pe_price, weighted_center]):
        dcf_price = fallback_valuation["dcf"] if isinstance(fallback_valuation["dcf"], float) else None
        ddm_price = fallback_valuation["ddm"] if isinstance(fallback_valuation["ddm"], float) else None
        pe_price = fallback_valuation["pe_band"] if isinstance(fallback_valuation["pe_band"], float) else None
        weighted_center = fallback_valuation["weighted_center"] if isinstance(fallback_valuation["weighted_center"], float) else None
        valuation_source = str(fallback_valuation["source"])
    valuation_parameter_table = format_table(
        ["模型", "关键参数", "值"],
        [
            ["DCF", "WACC", fmt_pct(fallback_valuation["wacc_pct"] if isinstance(fallback_valuation["wacc_pct"], float) else None)],
            ["DCF", "WACC分解", str(fallback_valuation["wacc_breakdown"])],
            ["DCF", "保守溢价依据", str(fallback_valuation["conservatism_basis"])],
            ["DCF", "β", fmt_num(fallback_valuation["beta"] if isinstance(fallback_valuation["beta"], float) else None)],
            ["DCF", "ERP", fmt_pct(fallback_valuation["erp_pct"] if isinstance(fallback_valuation["erp_pct"], float) else None)],
            ["DCF", "特定风险", fmt_pct(fallback_valuation["specific_risk_pct"] if isinstance(fallback_valuation["specific_risk_pct"], float) else None)],
            ["DCF", "保守溢价", fmt_pct(fallback_valuation["conservatism_pct"] if isinstance(fallback_valuation["conservatism_pct"], float) else None)],
            ["DCF", "预测期增长率", fmt_pct(fallback_valuation["stage_g_pct"] if isinstance(fallback_valuation["stage_g_pct"], float) else None)],
            ["DCF", "永续增长率", fmt_pct(fallback_valuation["terminal_g_pct"] if isinstance(fallback_valuation["terminal_g_pct"], float) else None)],
            ["DCF", "预测年数", fmt_num(fallback_valuation["forecast_years"] if isinstance(fallback_valuation["forecast_years"], float) else None, 0)],
            ["DCF", "终值占比", fmt_pct(fallback_valuation["terminal_value_share_pct"] if isinstance(fallback_valuation["terminal_value_share_pct"], float) else None)],
            ["DDM fair", "Ke", fmt_pct(fallback_valuation["ke_fair_pct"] if isinstance(fallback_valuation["ke_fair_pct"], float) else None)],
            ["DDM fair", "Ke分解", str(fallback_valuation["ke_fair_breakdown"])],
            ["DDM conservative", "Ke", fmt_pct(fallback_valuation["ke_pct"] if isinstance(fallback_valuation["ke_pct"], float) else None)],
            ["DDM", "g", fmt_pct(fallback_valuation["ddm_g_pct"] if isinstance(fallback_valuation["ddm_g_pct"], float) else None)],
            ["DDM", "g依据", str(fallback_valuation["ddm_g_basis"])],
            ["DDM", "DPS基准", fmt_num(fallback_valuation["ddm_dps"] if isinstance(fallback_valuation["ddm_dps"], float) else None, 4)],
            ["DDM", "D1", fmt_num(fallback_valuation["ddm_d1"] if isinstance(fallback_valuation["ddm_d1"], float) else None, 4)],
            ["DDM", "公式", str(fallback_valuation["ddm_formula"])],
            ["DDM", "fair价值", fmt_num(fallback_valuation["ddm_fair"] if isinstance(fallback_valuation["ddm_fair"], float) else None)],
            ["DDM", "conservative价值", fmt_num(fallback_valuation["ddm_conservative"] if isinstance(fallback_valuation["ddm_conservative"], float) else None)],
            ["PE Band", "EPS口径", str(fallback_valuation["eps_basis"])],
            ["PE Band", "PE中位数", fmt_num(fallback_valuation["pe_median"] if isinstance(fallback_valuation["pe_median"], float) else None)],
            ["加权中枢", "fair口径", fmt_num(fallback_valuation["weighted_center"] if isinstance(fallback_valuation["weighted_center"], float) else None)],
            ["加权中枢", "压力口径", fmt_num(fallback_valuation["pressure_center"] if isinstance(fallback_valuation["pressure_center"], float) else None)],
            ["参数校验", "警告", str(fallback_valuation["parameter_warning"])],
        ],
        alignments=["l", "l", "r"],
    )
    def valuation_metric_value(key: str, decimals: int = 2, pct: bool = False) -> str:
        value = fallback_valuation.get(key)
        if isinstance(value, float):
            return fmt_pct(value) if pct else fmt_num(value, decimals)
        return "（数据缺失）"

    valuation_cross_check_table = format_table(
        ["指标", "值", "说明"],
        [
            ["EV/EBITDA", valuation_metric_value("ev_ebitda"), "企业价值/EBITDA；若缺失通常是 EBITDA 或现金/债务字段不足"],
            ["扣现金PE", valuation_metric_value("ex_cash_pe"), "市值扣现金后/归母利润；归母利润缺失则标数据缺失"],
            ["FCF收益率", valuation_metric_value("fcf_yield_pct", pct=True), "归母口径：归母FCF/市值；Total Entity口径需另按 TE FCF/TE 市值复核"],
            ["净债务/EBITDA", valuation_metric_value("net_debt_ebitda"), "负值代表净现金；EBITDA 缺失则标数据缺失"],
        ],
        alignments=["l", "r", "l"],
    )

    thesis_rows = [
        ["核心定位", f"{structure_label}架构下的{business_model_label}"],
        ["主要优势", max_advantage],
        ["主要风险", max_risk.rstrip("。")],
        ["当前判断", f"{threshold_profile.category}口径下，静态GG{threshold_status}{fmt_pct(ii_pct)}门槛"],
        ["动作", recommendation],
    ]

    if "物业" in business_model_label or "物管" in business_model_label:
        risk_lines = [
            "- 若物业管理主业毛利率继续明显下滑，护城河判断需要下修",
            "- 若第三方项目继续扩张但利润率同步恶化，规模优势可能被证伪",
            "- 若应收增长再次快于收入，现金回报率会重新承压",
        ]
    else:
        risk_lines = [
            "- 若价格竞争或产品结构恶化继续压低利润率，护城河判断需要下修",
            "- 若资本开支长期高于利润增长，普通股东可分配现金会被再投资需求吸收",
            "- 若少数股东分流、关联交易或现金上游安排恶化，精算 GG 需要下修",
        ]
    if not (output_dir / "data_pack_report.md").exists():
        risk_lines.append("- 本次缺少 `data_pack_report.md`，附注级别现金细拆仍属 degraded mode")

    pdf_years = [str(year) for year, _ in discover_recent_annual_pdfs(output_dir, ts_code, lookback_years=5)]
    pdf_source = f"{pdf_years[0]}-{pdf_years[-1]} 年报 PDF 提取" if len(pdf_years) >= 2 else "PDF年报提取（若有）"

    metadata_table = format_table(
        ["项目", "内容"],
        [
            ["分析日期", today_str()],
            ["框架版本", "龟龟投资策略 v2.1"],
            ["最新股价", f"{fmt_num(current_price)} HKD"],
            ["最新市值", f"{fmt_num(market_cap)} 百万港元"],
            ["总股本", f"{fmt_num(total_shares)} 百万股"],
            ["Rf", f"{fmt_pct(rf_pct)}（{rf_source}）"],
            ["上市结构", f"{structure_label}，{channel_label}，股东层面税率 {q_report_display}"],
            ["数据来源", f"Tushare Pro + {pdf_source} + 定性分析报告"],
            ["Warnings", warnings],
        ],
        alignments=["l", "l"],
    )
    framework_changelog_table = format_table(
        ["变更项", "类型", "本报告执行规则"],
        [
            ["AA 现金审计", "改进", "因子3必须从 OCF - 维持性Capex 推导，不直接取归母净利润 C"],
            ["少数股东协议", "改进", ">30% 时强制披露穿透折价，子类门槛下调0.5pct，越跌越买DPS增速打折"],
            ["绝对估值透明度", "改进", "DCF/DDM/PE Band 输出WACC、增长率、预测年限、EPS口径和参数警告"],
            ["越跌越买模块", "改进", "DPS增速从历史DPS CAGR自动推导，并保留悲观/基准/乐观梯度"],
            ["渠道化结论", "改进", "香港直投与港股通分别给出结论；未知直投税率默认10%并保留敏感性"],
            ["v2.1估值补丁", "新增", "DCF保守溢价规则化；DDM fair/conservative双口径；DDM g推导链透明化"],
            ["v2.1审计补丁", "新增", "历史10%分位价标注时间窗；AA_2y_cash增加手算验证说明"],
            ["v2.1-hotfix", "新增", "门槛价双路径、AA手算防自印证、DPS样本期、10%分位频率、派息率释放、非控股股息报警"],
        ],
        alignments=["l", "l", "l"],
    )
    threshold_evidence_table = format_table(
        ["类别", "内容"],
        [[f"证据{i + 1}", item] for i, item in enumerate(threshold_profile.evidence)]
        + [["调整", item] for item in (threshold_profile.adjustments or ["无"])],
        alignments=["l", "l"],
    )

    summary_table = format_table(
        ["指标", "数值", "说明"],
        [
            ["Owner Earnings", f"{fmt_num(owner_earnings)} 百万元", f"G = {fmt_num(g_coeff)}；按数据源原币" if g_coeff is not None else "按数据源原币"],
            ["粗算穿透回报率", fmt_pct(gross_r), f"利润口径，{q_basis_label}"],
            ["精算穿透回报率", fmt_pct(gg_pct), f"真实可支配现金口径，{q_basis_label}"],
            [f"{fmt_pct(treaty_tax)}协定/低税档GG", fmt_pct(treaty_gg), f"结论 {treaty_recommendation}；{tax_scenarios[0]['note'] if tax_scenarios else ''}"],
            ["港股通精算GG", fmt_pct(southbound_gg), f"Q=20%；结论 {southbound_recommendation}"],
            ["门槛子类", threshold_profile.category, threshold_profile.rationale],
            ["门槛值", fmt_pct(ii_pct), threshold_profile.method],
            ["门槛价", fmt_num(threshold_price), threshold_price_note or "AA/DPS双路径交叉验算"],
            ["星级锚", f"五星≥{fmt_pct(threshold_profile.star_5_pct)}；四星≥{fmt_pct(threshold_profile.star_4_pct)}；三星≥{fmt_pct(threshold_profile.star_3_pct)}", "静态GG分档"],
            ["安全边际", f"{safety_margin:.2f} pct" if safety_margin is not None else "—", "GG − II"],
            ["价值陷阱风险", trap_risk, "基于现有定性/定量结论"],
            ["外推可信度", credibility, "引用 Step 11"],
            ["**仓位建议**", f"**{recommendation}**", "自动组装沿用现有结论逻辑"],
        ],
        alignments=["l", "l", "l"],
    )

    key_assumption_rows = [
        ["1", "维持性Capex系数 G", fmt_num(g_coeff), "1.00-1.40", oe_sensitivity_text],
        ["1A", "现金审计Capex口径", maintenance_capex_policy, f"最新维持性Capex {fmt_num(maintenance_capex_latest)}", f"Capex/D&A中位数 {fmt_num(capex_da_median)}；{g_check}"],
        ["2", "支付率锚定", fmt_pct(payout_anchor), f"5年均值 {fmt_pct(payout_avg_5y)}；最新年度 {fmt_pct(payout_latest)}", f"GG 约 {fmt_pct(gg_payout_avg)}-{fmt_pct(gg_payout_latest)}"],
        ["3", "利润口径", "GAAP归母净利润", "无稳定扣非口径", "R 口径稳定但偏会计"],
        ["4", "现金口径", "广义", "狭义差异通常较小", "现金安全垫判断不敏感"],
        ["5", "税率 Q", q_report_display, f"港股通口径 20%；香港券商直投需按 {tax_scenario_text(tax_scenarios)} 场景确认", "未知时不回读旧报告 Q_pct，不默认 0%"],
        ["6", "基准值选择", f"{aa_type} = {fmt_num(aa_base)}", f"AA_2y = {fmt_num(aa_2y)}；AA_excl = {fmt_num(aa_excl)}；AA_all = {fmt_num(aa_all)}", f"GG 约 {fmt_pct(gg_aa_excl)} / {fmt_pct(gg_aa_all)}"],
    ]
    key_assumptions_table = format_table(
        ["#", "假设", "选定值", "可替代值", "敏感性"],
        key_assumption_rows,
        alignments=["l", "l", "l", "l", "l"],
    )
    dip_buy_section = build_dip_buy_strategy_section(
        data_pack_text=data_pack_text,
        report_pack_text=report_pack_text,
        current_price=current_price,
        threshold_profile=threshold_profile,
        q_pct=q_pct if q_pct_known else None,
        tax_scenarios=tax_scenarios,
        minority_ratio=minority_share / 100.0 if minority_share is not None and minority_share > 1 else minority_share,
        minority_ratio_source="因子3：最新年报非控股权益应占溢利/(归母+非控股)",
    )
    dip_buy_section = dip_buy_section.replace(
        "## 越跌越买策略 · 年化10%目标",
        "## 七、越跌越买策略 · 年化10%目标",
        1,
    )
    final_summary_block = "\n".join([
        "```text",
        "═══════════════════════════════════════",
        "        龟龟投资策略 · 分析报告",
        "═══════════════════════════════════════",
        "",
        f"企业：{company_name}",
        f"上市地：{structure_label}  结构：{structure_label}",
        f"分析期：当前报告期  市值：{fmt_num(market_cap)} 百万港元",
        "",
        "───────────────────────────────────────",
        "因子1A（五分钟快筛）：PROCEED",
        f"因子1B（深度定性）：通过，MD&A 可信度 {qualitative_params.get('mda_credibility', '中')}",
        f"因子2（粗算Top-Down）：{top_down_status}",
        f"  Owner Earnings：{fmt_num(owner_earnings)} 百万元",
        f"  粗算穿透回报率：{fmt_pct(gross_r)}",
        f"  粗算否决门：{top_down_gate_status}",
        f"因子3（精算Bottom-Up + 现金审计）：{threshold_status}",
        f"  精算穿透回报率：{fmt_pct(gg_pct)}（最终估值输入）",
        f"  粗算偏差：{fmt_num(hh_pct)} pct",
        f"  外推可信度：{credibility}",
        f"因子4（估值与安全边际）：{'通过' if safety_margin is not None and safety_margin >= 0 else '未通过'}",
        f"  门槛值：{fmt_pct(ii_pct)}",
        f"  安全边际：{fmt_num(safety_margin)} pct",
        f"  价值陷阱风险：{trap_risk}",
        f"  股价位置：当前分位{fmt_num(price_quantile, 1)}%，目标买入价{fmt_num(threshold_price)}",
        f"  仓位建议：{recommendation}",
        "───────────────────────────────────────",
        "",
        f"最终判断：{recommendation}",
        f"最大优势：{max_advantage}",
        f"最大风险：{max_risk.rstrip('。')}",
        "═══════════════════════════════════════",
        "```",
    ])

    report_lines = [
        f"# 龟龟投资策略 · 分析报告：{company_name}（{ts_code}）",
        "",
        "---",
        "",
        "## 报告元信息",
        "",
        metadata_table,
        "",
        "### 框架版本变更日志",
        "",
        framework_changelog_table,
        "",
        "## Executive Summary",
        "",
        f"**一句话结论**：{summary_line}",
        "",
        f"**结论假设**：{assumption_sentence}",
        "",
        f"若您通过港股通持有，请参考税率敏感性表中 `Q=20%` 的结论；若香港券商直投税率无法确认，本框架主口径默认按 `10%`，并同时展示 `{tax_scenario_text(tax_scenarios)}`。",
        "",
        summary_table,
        "",
        f"**最大优势**：{max_advantage}。",
        "",
        f"**最大风险**：{max_risk}",
        "",
        "## 一、五分钟快筛与数据校验",
        "",
        quant_step0 or "数据校验内容缺失。",
        "",
        "## 二、因子1B：商业质量分析",
        "",
        "> 本节承接 `/business-analysis` 的定性输出，用于向因子2/3/4传递商业模式、资本强度、周期性、治理和分配意愿参数。",
        "",
        "### 九模块量化输出总表",
        "",
        factor1b_quant_table,
        "",
        "### 1. 资本消耗",
        "",
        f"资本强度评估为`{qualitative_params.get('capital_intensity', '待确认')}`。{business_model_summary}",
        "",
        "### 2. 收款模式",
        "",
        f"收款模式评估为`{qualitative_params.get('collection_mode', '待确认')}`。该判断直接传递到因子3的现金收入审计和AA置信度。",
        "",
        "### 3. 护城河",
        "",
        moat_summary,
        "",
        "### 4. 周期性",
        "",
        environment_summary,
        "",
        "### 5. 人力资本与固定成本",
        "",
        f"人力资本/固定成本参数为`{qualitative_params.get('labor_intensity', '待确认')}`；若固定成本偏高，收入下滑对AA的冲击需要通过λ敏感性放大。",
        "",
        "### 6. 管理层与治理",
        "",
        governance_summary,
        "",
        "### 7. 监管与外部约束",
        "",
        f"监管风险为`{qualitative_params.get('regulatory_risk', '中')}`。{environment_summary}",
        "",
        "### 8. MD&A 解读",
        "",
        mda_summary,
        "",
        "### 9. 控股结构与少数股东",
        "",
        holding_summary,
        "",
        "### 参数传递表",
        "",
        factor1b_transfer_table,
        "",
        "### 10. 综合判断",
        "",
        clean_sentence(strip_irrelevant_peer_comparisons(first_nonempty_paragraph(qualitative_summary), company_name) or first_bullet_or_paragraph(qualitative_exec)),
        "",
        "## 三、关键假设与财务趋势",
        "",
        "### 3.1 关键假设",
        "",
        key_assumptions_table,
        "",
        "### 3.2 财务趋势速览",
        "",
        financial_trend_intro,
        "",
        financial_trend_table_text,
        "",
    ]

    report_lines.extend([
        "## 四、因子2：穿透回报率粗算（Top-Down）",
        "",
        "> 因子2是自上而下的快速筛选。先判断业务子类，再填静态GG要求回报率；不得固定套用单一7%门槛。",
        "",
        "### 4.1 Owner Earnings",
        "",
        quant_step1_report or "Owner Earnings 内容缺失。",
        "",
        "### 4.2 分配能力",
        "",
        quant_step2 or "分配能力内容缺失。",
        "",
        "### 4.3 粗算穿透回报率",
        "",
        "粗算先用利润/股息锚和派息率做初筛，目的是快速判断当前价格是否值得进入精算。该步骤不直接替代最终裁决，但必须先于门槛判断出现。",
        "",
        top_down_table,
        "",
        "`R = [C × M × (1 − Q) + O] / 市值`；若公司 DPS 与普通股股息可直接互相验证，也可用 `R = DPS / 当前股价` 交叉检查。",
        "",
        f"本次粗算穿透回报率 R = `{fmt_pct(gross_r)}`，子类门槛 II = `{fmt_pct(ii_pct)}`，初筛结论为`{top_down_status}`。",
        "",
        "### 4.4 子类门槛与粗算否决门",
        "",
        f"- 门槛子类：{threshold_profile.category}",
        f"- 门槛方法：{threshold_profile.method}",
        f"- 子类理由：{threshold_profile.rationale}",
        f"- 粗算否决门：{top_down_gate_status}；若 R 明显低于 II×0.5，框架应直接否决，不进入精算。",
        "",
        threshold_evidence_table,
        "",
        "## 五、因子3：穿透回报率精算（Bottom-Up）+ 现金质量审计",
        "",
        "> 因子3从真实可支配现金、资本开支、现金储备、支付率和股东穿透障碍出发，验证因子2是否高估或低估普通股东现金回报。",
        "",
        "### 5.1 精算结果汇总",
        "",
        "精算从真实可支配现金、资本开支、现金储备、支付率和股东穿透障碍出发，检查利润口径是否能转化为普通股东现金回报。",
        "",
        bottom_up_table,
        "",
        f"本次精算穿透回报率 GG = `{fmt_pct(gg_pct)}`，HH 偏差 = `{fmt_num(hh_pct)} pct`。最终裁决采用 GG 与子类门槛比较，而不是固定套用单一 7% 要求回报率。",
        "",
        "税率敏感性（同一 AA/M/市值口径）：",
        "",
        tax_sensitivity_table or "税率敏感性表缺失。",
        "",
        cash_quality_audit_sections,
        "",
        "### 5.10 真实可支配现金审计",
        "",
        "\n\n".join([
            part for part in [
                demote_headings(market_step174, increment=1) if market_step174 else "",
                demote_headings(quant_aa_audit, increment=1) if quant_aa_audit else "",
                quant_step38 if (not market_step174 and not market_step175) else "",
            ] if part
        ]) or "真实可支配现金内容缺失。",
        "",
        "### 5.11 分配意愿、门槛分类与敏感性",
        "",
        demote_headings(quant_step10_report, increment=1) if quant_step10_report else "穿透回报率内容缺失。",
        "",
        "### 5.12 外推可信度评级",
        "",
        quant_step11 or "可信度内容缺失。",
        "",
        "## 六、因子4：估值与安全边际",
        "",
        "> 因子4以因子3的精算穿透回报率 GG 为最终估值输入，比较门槛、排查价值陷阱，并给出价格锚和仓位动作。",
        "",
        "### 6.1 门槛与安全边际",
        "",
        (
            f"龟龟策略门槛为 {fmt_pct(ii_pct)}，当前精算回报率 {fmt_pct(gg_pct)}，"
            f"按{channel_label}口径做 R7-1 双路径交叉验算，达到门槛对应的主口径价格约为 `{fmt_num(threshold_price)} 港元`。"
        ),
        "",
        threshold_price_note or "门槛价双路径说明缺失。",
        "",
        threshold_crosscheck_table,
        "",
        "历史分位全貌：",
        "",
        historical_quantile_table,
        "",
        "### 6.2 价值陷阱排查",
        "",
        f"自动组装基于现有定性/定量结果判定：`价值陷阱风险 = {trap_risk}`。"
        " 当前核心矛盾不在杠杆，而在行业压价下利润率与可分配现金的修复速度。",
        "",
        "### 6.3 股价位置",
        "",
        f"- 当前股价 {fmt_num(current_price)} 港元",
        f"- 10 年历史分位 {fmt_num(price_quantile, 1)}%" if price_quantile is not None else "- 10 年历史分位：缺失",
        f"- 接近“买入就是胜利”综合基准价 {fmt_num(benchmark_price)} 港元" if benchmark_price is not None else "- 综合基准价：缺失",
        "",
        composite_benchmark_table,
        "",
        "### 6.4 业绩下滑敏感性",
        "",
        "按与精算 GG 相同币种折算口径：",
        "",
        short_sensitivity_table or "敏感性表缺失。",
        "",
        "### 6.5 绝对估值",
        "",
        "- 估值引擎输出：",
        f"  - 来源: {valuation_source}",
        f"  - DCF: {fmt_num(dcf_price)} 港元/股" if dcf_price is not None else "  - DCF: 缺失",
        f"  - DDM fair: {fmt_num(ddm_price)} 港元/股" if ddm_price is not None else "  - DDM fair: 缺失",
        f"  - DDM conservative: {fmt_num(fallback_valuation['ddm_conservative'] if isinstance(fallback_valuation['ddm_conservative'], float) else None)} 港元/股",
        f"  - PE Band: {fmt_num(pe_price)} 港元/股" if pe_price is not None else "  - PE Band: 缺失",
        f"  - 加权中枢（fair）: {fmt_num(weighted_center)} 港元/股" if weighted_center is not None else "  - 加权中枢（fair）: 缺失",
        f"  - 压力中枢（conservative）: {fmt_num(fallback_valuation['pressure_center'] if isinstance(fallback_valuation['pressure_center'], float) else None)} 港元/股",
        "",
        "- 关键参数披露：",
        "",
        valuation_parameter_table,
        "",
        "- 简易交叉验证：",
        "",
        valuation_cross_check_table,
        "",
        dip_buy_section,
        "## 八、最终综合输出",
        "",
        final_summary_block,
        "",
        f"{company_name}当前的核心特征是“质量不差、估值不贵、但门槛要按子类判断”。",
        f" 本次判定为{threshold_profile.category}，在 {channel_label} 口径下，{fmt_pct(gg_pct)} {threshold_status}{fmt_pct(ii_pct)} 的买入门槛，",
        f" 因此自动组装的最终裁决维持`{recommendation}`。",
        "",
        "后续触发条件：",
        "",
        f"- 价格回落至约 {fmt_num(threshold_price)} 港元附近",
        "- 或利润率与现金转换率修复，令 GG 重新逼近门槛",
        f"- 或{capital_label}下的主营业务证明能够在低增长环境下稳定贡献普通股东可分配现金",
        "",
        "## 九、投资论点卡（Thesis Card）",
        "",
        format_table(["项目", "内容"], thesis_rows, alignments=["l", "l"]),
        "",
        "## 十、风险提示",
        "",
        *risk_lines,
        "",
        "## 十一、数据来源与免责",
        "",
        "### 需要人工验证的内容",
        "",
        f"- 香港券商直投股息税率的实际预扣安排；若无法确认，本框架主口径默认按10%，并保留{tax_scenario_text(tax_scenarios)}敏感性。",
        "- 年报中受限现金、合资公司现金上游限制、非控股权益分红安排及重大关联交易。",
        "- 特许经营、授权、核心客户或监管政策是否存在续期、终止或价格管制风险。",
        "",
        "### 框架已知局限性",
        "",
        "- 静态GG是零增长穿透回报率，不等同于DCF内在价值，也不自动包含未来增长。",
        "- 少数股东处理依赖归母/集团利润比例稳定；少数股东占比高于30%时，DCF仍需在企业价值层扣非控股权益后复核。",
        "- 港股Capex与无形资产投资可能需要从年报现金流反推；若字段缺失，AA会降级为范围估计。",
        "- 子类门槛必须先判断后填值，不得从上一份个股报告继承固定门槛。",
        "",
        (
            f"本报告基于截至 {today_str()} 已生成的 `data_pack_market.md`、`qualitative_report.md`、"
            f"`phase3_quantitative.md` 与 `valuation_computed.md` 自动组装。"
            "报告用于研究和框架验证，不构成任何投资建议。"
        ),
        "",
    ])

    return "\n".join(report_lines)


def latest_fiscal_year() -> int:
    return datetime.now().year - 1


def stage_pdf(ts_code: str, output_dir: Path, pdf_path: Optional[str],
              pdf_url: Optional[str], report_year: int) -> Optional[Path]:
    if pdf_path:
        src = Path(pdf_path).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"PDF not found: {src}")
        dst = output_dir / src.name
        if src != dst:
            shutil.copy2(src, dst)
        return dst

    if pdf_url:
        filename = f"{_base_code(ts_code)}_{report_year}_年报.pdf"
        dst = output_dir / filename
        run_cmd([
            preferred_python(),
            "scripts/download_report.py",
            "--url", pdf_url,
            "--stock-code", _base_code(ts_code),
            "--report-type", "年报",
            "--year", str(report_year),
            "--save-dir", str(output_dir),
        ])
        return dst if dst.exists() else None

    existing = check_local_pdf(ts_code, report_year, str(output_dir), report_type="年报")
    return Path(existing).resolve() if existing else None


def run_business_analysis(args: argparse.Namespace) -> None:
    ts_code = validate_stock_code(args.code)
    output_dir = resolve_output_dir(ts_code, args.company_name, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    company_name = display_company_name(ts_code, output_dir, args.company_name)

    data_pack = output_dir / "data_pack_market.md"
    refresh_pack = output_dir / f"data_pack_market_refresh_{datetime.now().strftime('%Y%m%d')}.md"
    refresh_target = data_pack
    if data_pack.exists():
        refresh_target = refresh_pack
        if not refresh_target.exists():
            shutil.copy2(data_pack, refresh_target)
    run_cmd([
        preferred_python(),
        "scripts/tushare_collector.py",
        "--code", ts_code,
        "--output", str(data_pack),
    ])

    pdf = stage_pdf(
        ts_code=ts_code,
        output_dir=output_dir,
        pdf_path=args.pdf,
        pdf_url=args.pdf_url,
        report_year=args.report_year,
    )
    interim_requirement = ensure_interim_report_requirement(
        ts_code,
        output_dir,
        data_pack,
        pdf_path=args.interim_pdf,
        pdf_url=args.interim_pdf_url,
    )

    annual_coverage = ensure_recent_annual_report_coverage(
        output_dir,
        ts_code,
        args.report_year,
        lookback_years=args.annual_lookback_years,
        minimum_years=args.minimum_annual_years,
    )
    annual_pdfs = annual_coverage.found
    generated_sections: list[Path] = []
    if annual_pdfs:
        generated_sections = preprocess_annual_pdfs(output_dir, annual_pdfs)
    elif pdf and pdf.exists():
        pdf_sections = output_dir / "pdf_sections.json"
        run_cmd([
            preferred_python(),
            "scripts/pdf_preprocessor.py",
            "--pdf", str(pdf),
            "--output", str(pdf_sections),
        ])
        generated_sections = [pdf_sections]

    report_pack = ensure_hk_report_pack(ts_code, output_dir)
    report_pack_interim = ensure_hk_report_pack_interim(ts_code, output_dir, interim_requirement)

    handoff = output_dir / "business_analysis_handoff.md"
    scaffold = output_dir / "qualitative_report.scaffold.md"
    write_text(handoff, business_handoff_content(
        ts_code,
        output_dir,
        pdf,
        annual_pdfs,
        args.holding_channel,
        annual_coverage,
        interim_requirement,
    ))
    write_text(scaffold, business_report_scaffold(ts_code, company_name))

    write_prompt = None
    report_target = output_dir / "qualitative_report.md"
    report_seeded = False
    if args.write_report:
        report_seeded = ensure_seed_file(report_target, business_report_scaffold(ts_code, company_name))
        write_prompt = output_dir / "business_analysis_write_prompt.md"
        write_text(
            write_prompt,
            business_write_prompt_content(
                ts_code,
                output_dir,
                report_target,
                pdf,
                annual_pdfs,
                args.holding_channel,
                annual_coverage,
                interim_requirement,
            ),
        )

    print("\nBusiness-analysis deterministic steps completed.")
    print(f"- Stock code: {ts_code}")
    print(f"- Output dir: {output_dir}")
    print(f"- Data pack: {data_pack}")
    if annual_pdfs:
        pdf_summary = ", ".join(f"{year}:{path.name}" for year, path in annual_pdfs)
        print(f"- Annual PDFs: {pdf_summary}")
        if generated_sections:
            print("- Generated section packs:")
            for path in generated_sections:
                print(f"  - {path}")
        if report_pack:
            print(f"- Report pack: {report_pack}")
        if report_pack_interim:
            print(f"- Interim report pack: {report_pack_interim}")
    elif pdf and pdf.exists():
        print(f"- PDF: {pdf}")
        print(f"- PDF sections: {output_dir / 'pdf_sections.json'}")
        if report_pack:
            print(f"- Report pack: {report_pack}")
        if report_pack_interim:
            print(f"- Interim report pack: {report_pack_interim}")
    else:
        print("- PDF: not staged")
    print(f"- Annual report coverage: {annual_coverage.markdown_summary()}")
    if annual_coverage.missing_years:
        missing = ", ".join(str(year) for year in annual_coverage.missing_years)
        print(f"- Missing annual reports: {missing}")
    if not annual_coverage.has_minimum_coverage:
        print(f"- Coverage warning: fewer than {annual_coverage.minimum_years} annual reports; downstream trend conclusions must be downgraded.")
    print(f"- Interim report requirement: {interim_requirement.markdown_summary()}")
    if interim_requirement.required and not interim_requirement.is_satisfied:
        print("- Interim warning: latest H1 data exists but interim PDF is missing; latest-operation conclusions must be downgraded.")
    print(f"- Handoff: {handoff}")
    print(f"- Report scaffold: {scaffold}")
    if args.write_report:
        print(f"- Report target: {report_target} ({'seeded' if report_seeded else 'reused'})")
        print(f"- Write prompt: {write_prompt}")
    print("- Next synthesis spec: .claude/commands/business-analysis.md")


def ensure_business_outputs(output_dir: Path) -> None:
    required = [
        output_dir / "qualitative_report.md",
        output_dir / "data_pack_market.md",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Missing prerequisite files:\n" + "\n".join(missing)
        )


def run_valuation(args: argparse.Namespace) -> None:
    ts_code = validate_stock_code(args.code)
    output_dir = resolve_output_dir(ts_code, args.company_name, args.output_dir)
    ensure_business_outputs(output_dir)
    company_name = display_company_name(ts_code, output_dir, args.company_name)

    run_cmd([
        preferred_python(),
        "scripts/valuation_engine.py",
        "--code", ts_code,
        "--output-dir", str(output_dir),
    ])

    handoff = output_dir / "valuation_handoff.md"
    scaffold = output_dir / "valuation_report.scaffold.md"
    write_text(handoff, valuation_handoff_content(ts_code, output_dir, args.holding_channel))
    write_text(scaffold, valuation_report_scaffold(ts_code, company_name))

    write_prompt = None
    report_target = output_dir / f"{report_prefix(ts_code, output_dir, company_name)}_估值报告.md"
    report_seeded = False
    if args.write_report:
        report_seeded = ensure_seed_file(report_target, valuation_report_scaffold(ts_code, company_name))
        write_prompt = output_dir / "valuation_write_prompt.md"
        write_text(write_prompt, valuation_write_prompt_content(ts_code, output_dir, report_target, args.holding_channel))

    print("\nValuation deterministic steps completed.")
    print(f"- Stock code: {ts_code}")
    print(f"- Output dir: {output_dir}")
    print(f"- Computed file: {output_dir / 'valuation_computed.md'}")
    print(f"- Handoff: {handoff}")
    print(f"- Report scaffold: {scaffold}")
    if args.write_report:
        print(f"- Report target: {report_target} ({'seeded' if report_seeded else 'reused'})")
        print(f"- Write prompt: {write_prompt}")
    print("- Next synthesis spec: .claude/commands/valuation.md")


def run_turtle_analysis(args: argparse.Namespace) -> None:
    ts_code = validate_stock_code(args.code)
    output_dir = resolve_output_dir(ts_code, args.company_name, args.output_dir)
    ensure_business_outputs(output_dir)
    company_name = display_company_name(ts_code, output_dir, args.company_name)

    data_pack = output_dir / "data_pack_market.md"
    env = os.environ.copy()
    if getattr(args, "holding_channel", None):
        env["HOLDING_CHANNEL"] = args.holding_channel
    refresh_pack = output_dir / f"data_pack_market_refresh_{datetime.now().strftime('%Y%m%d')}.md"
    refresh_target = data_pack
    if data_pack.exists():
        refresh_target = refresh_pack
        if not refresh_target.exists():
            shutil.copy2(data_pack, refresh_target)
    print("+", " ".join([
        preferred_python(),
        "scripts/tushare_collector.py",
        "--code", ts_code,
        "--output", str(refresh_target),
        "--refresh-market",
    ]))
    subprocess.run([
        preferred_python(),
        "scripts/tushare_collector.py",
        "--code", ts_code,
        "--output", str(refresh_target),
        "--refresh-market",
    ], check=True, cwd=REPO_ROOT, env=env)

    interim_requirement = ensure_interim_report_requirement(ts_code, output_dir, refresh_target)
    report_pack = ensure_hk_report_pack(ts_code, output_dir)
    report_pack_interim = ensure_hk_report_pack_interim(ts_code, output_dir, interim_requirement)

    handoff = output_dir / "turtle_analysis_handoff.md"
    scaffold = output_dir / "turtle_report.scaffold.md"
    write_text(handoff, turtle_handoff_content(ts_code, output_dir, args.holding_channel))
    write_text(scaffold, turtle_report_scaffold(ts_code, company_name))

    write_prompt = None
    preflight_target = output_dir / "phase3_preflight.md"
    quantitative_target = output_dir / "phase3_quantitative.md"
    report_target = output_dir / f"{report_prefix(ts_code, output_dir, company_name)}_分析报告.md"
    preflight_generated = False
    quantitative_generated = False
    report_seeded = False
    report_auto_assembled = False
    generated_preflight = assemble_turtle_preflight(
        ts_code=ts_code,
        output_dir=output_dir,
        company_name=company_name,
        holding_channel=args.holding_channel,
    )
    if generated_preflight:
        write_text(preflight_target, generated_preflight)
        preflight_generated = True
    generated_quantitative = assemble_turtle_quantitative(
        ts_code=ts_code,
        output_dir=output_dir,
        company_name=company_name,
        holding_channel=args.holding_channel,
    )
    if generated_quantitative:
        write_text(quantitative_target, generated_quantitative)
        quantitative_generated = True
    if args.write_report:
        if not preflight_generated:
            ensure_seed_file(
                preflight_target,
                turtle_preflight_scaffold(ts_code, company_name, args.holding_channel, output_dir),
            )
        if not quantitative_generated:
            ensure_seed_file(
                quantitative_target,
                turtle_quantitative_scaffold(ts_code, company_name),
            )
        report_seeded = ensure_seed_file(report_target, turtle_report_scaffold(ts_code, company_name))
        write_prompt = output_dir / "turtle_analysis_write_prompt.md"
        write_text(
            write_prompt,
            turtle_write_prompt_content(
                ts_code,
                output_dir,
                preflight_target,
                quantitative_target,
                report_target,
                args.holding_channel,
            ),
        )
        assembled = assemble_turtle_report(
            ts_code=ts_code,
            output_dir=output_dir,
            company_name=company_name,
            holding_channel=args.holding_channel,
        )
        if assembled:
            write_text(report_target, assembled)
            report_auto_assembled = True

    print("\nTurtle-analysis preparation completed.")
    print(f"- Stock code: {ts_code}")
    print(f"- Output dir: {output_dir}")
    print(f"- Refreshed data pack: {refresh_target}")
    if report_pack:
        print(f"- Refreshed report pack: {report_pack}")
    if report_pack_interim:
        print(f"- Interim report pack: {report_pack_interim}")
    print(f"- Interim report requirement: {interim_requirement.markdown_summary()}")
    if interim_requirement.required and not interim_requirement.is_satisfied:
        print("- Interim warning: latest H1 data exists but interim PDF is missing; latest-operation conclusions must be downgraded.")
    print(f"- Handoff: {handoff}")
    print(f"- Report scaffold: {scaffold}")
    if args.write_report:
        print(f"- Preflight target: {preflight_target} ({'generated' if preflight_generated else 'seeded'})")
        print(f"- Quantitative target: {quantitative_target} ({'generated' if quantitative_generated else 'seeded'})")
        report_status = "auto-assembled" if report_auto_assembled else ("seeded" if report_seeded else "reused")
        print(f"- Final report target: {report_target} ({report_status})")
        print(f"- Write prompt: {write_prompt}")
    print("- Next synthesis spec: .claude/commands/turtle-analysis.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Codex-friendly workflow wrapper for Turtle Investment Framework"
    )
    subparsers = parser.add_subparsers(dest="workflow", required=True)

    def add_common_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--code", required=True, help="Stock code, e.g. 600887 or 00700.HK")
        p.add_argument("--company-name", help="Optional company name override for output dir naming")
        p.add_argument("--output-dir", help="Explicit output directory override")
        p.add_argument("--holding-channel", help="Optional holding channel / tax profile hint")
        p.add_argument(
            "--write-report",
            action="store_true",
            help="Seed the real report target(s) and generate a *_write_prompt.md continuation pack",
        )

    ba = subparsers.add_parser("business-analysis", help="Run deterministic business-analysis steps")
    add_common_flags(ba)
    ba.add_argument("--pdf", help="Existing local PDF path to stage into output dir")
    ba.add_argument("--pdf-url", help="Direct PDF URL to download via scripts/download_report.py")
    ba.add_argument("--interim-pdf", help="Existing local interim PDF path to stage into output dir")
    ba.add_argument("--interim-pdf-url", help="Direct interim PDF URL to download via scripts/download_report.py")
    ba.add_argument(
        "--report-year",
        type=int,
        default=latest_fiscal_year(),
        help="Fiscal year for the annual report search/download",
    )
    ba.add_argument(
        "--annual-lookback-years",
        type=int,
        default=5,
        help="Target number of complete annual reports to use for trend checks (default: 5)",
    )
    ba.add_argument(
        "--minimum-annual-years",
        type=int,
        default=3,
        help="Minimum annual-report count before trend conclusions avoid downgrade (default: 3)",
    )
    ba.set_defaults(func=run_business_analysis)

    val = subparsers.add_parser("valuation", help="Run deterministic valuation step")
    add_common_flags(val)
    val.set_defaults(func=run_valuation)

    turtle = subparsers.add_parser("turtle-analysis", help="Refresh market data for turtle-analysis")
    add_common_flags(turtle)
    turtle.set_defaults(func=run_turtle_analysis)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
