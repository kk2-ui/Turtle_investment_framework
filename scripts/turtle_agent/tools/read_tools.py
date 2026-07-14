"""读取工具集 — PDF 章节、财务数据、文档列表。

对接现有 Python 模块：
- ``pdf_page_locator.py`` — 章节导航
- ``build_full_text.py`` — 全文提取
- ``compute_bundle.py`` — 财务计算
- ``build_financial_trends.py`` — 财务趋势
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# 确保 scripts/ 可导入
_scripts_dir = os.path.join(os.path.dirname(__file__), "..", "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)


def _read_json(path: str) -> dict[str, Any] | None:
    """安全读取 JSON 文件。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: str, max_chars: int = 0) -> str | None:
    """安全读取文本文件。"""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            text = f.read()
            return text[:max_chars] if max_chars > 0 else text
    except OSError:
        return None


# ---------------------------------------------------------------------------
# 工具函数（由 ToolRegistry 注册）
# ---------------------------------------------------------------------------


def list_documents(output_dir: str = ".") -> dict[str, Any]:
    """列出股票输出目录中所有可用文档和 JSON 数据文件。

    Args:
        output_dir: 股票输出目录路径。

    Returns:
        ``{documents: [...], data_files: [...]}``。
    """
    docs: list[dict[str, Any]] = []
    data_files: list[str] = []

    for f in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, f)
        if f.endswith(".json"):
            data_files.append(f)
        elif f.endswith(".pdf"):
            docs.append({"file": f, "size": os.path.getsize(path)})
        elif f.endswith(".md") and f.startswith("_ch"):
            docs.append({"file": f, "type": "chapter"})

    # 检查 page_map
    for f in os.listdir(output_dir):
        if f.startswith("page_map") and f.endswith(".json"):
            docs.append({"file": f, "type": "page_map"})

    return {"documents": docs, "data_files": data_files}


def read_section(
    output_dir: str = ".",
    year: int = 2024,
    section: str = "MDA",
    max_chars: int = 30000,
) -> dict[str, Any]:
    """读取年报特定章节的文本内容。

    优先使用 pre-built page_map.json（页级随机访问，快）；
    无 page_map 时直接扫 PDF 提取文本（无需预生成）。

    Args:
        output_dir: 股票输出目录。
        year: 财年。
        section: 章节标签（MDA, SEG, STMT, GOV, AUDIT, NOTES, RISK, P2, P3, P4, SUB）。
        max_chars: 最大返回字符数（默认30000）。

    Returns:
        ``{section, year, text, page_range, char_count, source}``。
    """
    # 1) 尝试 page_map 路径（快）
    pm_path = os.path.join(output_dir, f"page_map_{year}.json")
    if not os.path.exists(pm_path):
        pm_path = os.path.join(output_dir, "page_map.json")
    pm = _read_json(pm_path)

    page_range: list[int] = []
    if pm and "sections" in pm:
        sections = pm["sections"]
        # 支持两种格式: dict {label: [start, end]} 或 list [{label, start, end}]
        if isinstance(sections, dict):
            for label, pages in sections.items():
                if label.upper() == section.upper():
                    if isinstance(pages, list) and len(pages) >= 1:
                        page_range = [int(pages[0]), int(pages[-1])]
                    break
        elif isinstance(sections, list):
            for s in sections:
                if isinstance(s, dict) and s.get("label", "").upper() == section.upper():
                    page_range = [
                        int(s.get("start_page", s.get("start", 0))),
                        int(s.get("end_page", s.get("end", 0))),
                    ]
                    break

    # 2) 找 PDF 文件
    pdf_path = os.path.join(output_dir, f"{year}_年报.pdf")
    if not os.path.exists(pdf_path):
        # 模糊匹配
        for f in os.listdir(output_dir):
            if f.endswith(".pdf") and str(year) in f and "年报" in f:
                pdf_path = os.path.join(output_dir, f)
                break
    if not os.path.exists(pdf_path):
        # 取任意年报 PDF
        for f in sorted(os.listdir(output_dir)):
            if f.endswith(".pdf") and "年报" in f:
                pdf_path = os.path.join(output_dir, f)
                break

    if not os.path.exists(pdf_path):
        return {"section": section, "year": year, "text": "", "error": "未找到年报 PDF"}

    # 3) 有 page_map → 精准按页读
    if page_range:
        try:
            import pdfplumber
            with pdfplumber.open(pdf_path) as pdf:
                texts = []
                for pg in range(page_range[0], min(page_range[1] + 1, len(pdf.pages) + 1)):
                    t = pdf.pages[pg - 1].extract_text()
                    if t:
                        texts.append(f"=== Page {pg} ===\n{t}")
                text = "\n".join(texts)[:max_chars]
                return {
                    "section": section, "year": year,
                    "text": text, "page_range": page_range,
                    "char_count": len(text), "source": "page_map",
                }
        except Exception as exc:
            pass  # 回退到 full scan

    # 4) 无 page_map → 全扫 PDF 并搜索关键词定位
    try:
        import pdfplumber
    except ImportError:
        return {"section": section, "year": year, "text": "", "error": "pdfplumber 未安装"}

    section_keywords = {
        "MDA": ["管理层讨论", "Management Discussion", "经营回顾", "業務回顧"],
        "RISK": ["风险", "風險", "Risk Factors"],
        "GOV": ["企业管治", "企業管治", "董事", "Corporate Governance"],
        "AUDIT": ["审计", "審計", "独立核数师", "Auditor"],
        "STMT": ["财务报表", "財務報表", "Financial Statements", "综合损益"],
        "NOTES": ["附注", "Notes to the"],
        "SEG": ["分部", "Segment"],
    }
    keywords = section_keywords.get(section.upper(), [section])

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # 先扫前 50 页找章节起始
            found_page = 0
            for pg_num in range(1, min(51, len(pdf.pages) + 1)):
                preview = pdf.pages[pg_num - 1].extract_text() or ""
                if any(kw.lower() in preview.lower() for kw in keywords):
                    found_page = pg_num
                    break
            if not found_page:
                # 回退：返回前 20 页
                found_page = 1

            # 读该章节（起始页 + 后续 10 页）
            texts = []
            end_page = min(found_page + 10, len(pdf.pages))
            for pg in range(found_page, end_page + 1):
                t = pdf.pages[pg - 1].extract_text()
                if t:
                    texts.append(f"=== Page {pg} ===\n{t}")
            text = "\n".join(texts)[:max_chars]

            return {
                "section": section, "year": year,
                "text": text,
                "page_range": [found_page, end_page],
                "char_count": len(text),
                "source": "pdf_scan",
            }
    except Exception as exc:
        return {"section": section, "year": year, "text": "", "error": str(exc)}


def search_report(
    output_dir: str = ".",
    query: str = "",
    year: int | None = None,
) -> dict[str, Any]:
    """在年报全文中搜索关键词。

    返回包含关键词的段落及其上下文。

    Args:
        output_dir: 股票输出目录。
        query: 搜索关键词。
        year: 可选财年过滤。

    Returns:
        ``{query, total_hits, hits: [{snippet, page}]}``。
    """
    ft_pattern = f"{year}_full_text.txt" if year else "_full_text.txt"
    ft_path = os.path.join(output_dir, ft_pattern)
    if not os.path.exists(ft_path):
        # 查找任意年份
        for f in os.listdir(output_dir):
            if f.endswith("_full_text.txt"):
                ft_path = os.path.join(output_dir, f)
                break

    text = _read_text(ft_path) or ""
    if not query or not text:
        return {"query": query, "total_hits": 0, "hits": []}

    # 简单关键词搜索
    lines = text.split("\n")
    hits: list[dict[str, Any]] = []
    q_lower = query.lower()
    for i, line in enumerate(lines):
        if q_lower in line.lower():
            # 取上下文
            ctx_start = max(0, i - 1)
            ctx_end = min(len(lines), i + 2)
            snippet = "\n".join(lines[ctx_start:ctx_end])[:500]
            hits.append({"snippet": snippet, "line": i + 1})

    return {
        "query": query,
        "year": year,
        "total_hits": len(hits),
        "hits": hits[:20],  # 最多返回 20 条
    }


def get_financial_statement(
    output_dir: str = ".",
    statement_type: str = "income",
) -> dict[str, Any]:
    """获取标准化财务报表数据。

    从 ``compute_bundle.json`` 中提取（适配 factor2/3/4 嵌套结构）。

    Args:
        output_dir: 股票输出目录。
        statement_type: 报表类型 (income/balance_sheet/cash_flow/overview)。

    Returns:
        ``{statement_type, metrics: {...}}``。
    """
    cb = _read_json(os.path.join(output_dir, "compute_bundle.json"))
    if not cb:
        return {"statement_type": statement_type, "error": "compute_bundle.json 不存在"}

    f2 = cb.get("factor2", {})
    f3 = cb.get("factor3", {})
    f4 = cb.get("factor4", {})
    p = cb.get("params", {})
    m = cb.get("market", {})
    rej = cb.get("rejection_summary", {})
    trace = cb.get("calculation_trace", {})

    # 财报核心指标
    income_metrics = {
        "np_avg_3y": f2.get("np_avg_3y"),
        "np_avg_5y": f2.get("np_avg_5y"),
        "oe_avg_3y": f2.get("oe_avg_3y"),
        "oe_avg_5y": f2.get("oe_avg_5y"),
        "ocf_np_ratio": f2.get("ocf_np_ratio"),
        "capex_ratio_avg": f2.get("capex_ratio_avg"),
        "M": f2.get("M"),
        "M_source": f2.get("M_source"),
    }
    bs_metrics = {
        "aa": f3.get("aa"),
        "aa_avg": f3.get("aa_avg"),
        "ap_cost_ratio_avg": f3.get("ap_cost_ratio_avg"),
    }
    cf_metrics = {
        "receipt_ratios": f3.get("receipt_ratios"),
        "true_revenue": f3.get("true_revenue"),
    }

    result_map = {
        "income": income_metrics,
        "balance_sheet": bs_metrics,
        "cash_flow": cf_metrics,
        "overview": {
            **income_metrics, **bs_metrics, **cf_metrics,
            "gg": {
                "gg_np": trace.get("factor3_gg_raw", {}).get("result", {}).get("gg_np"),
                "gg_oe": trace.get("factor3_gg_raw", {}).get("result", {}).get("gg_oe"),
                "gg_base": trace.get("factor3_gg", {}).get("result"),
                "scenarios": trace.get("factor3_gg_scenarios", {}),
            },
            "ddm": {
                "fair_value_hkd": f4.get("ddm_v_hkd"),
                "dps_fy": p.get("dps_fy"),
                "dps_ttm": p.get("dps_ttm"),
                "tiers": f4.get("tiers", []),
            },
            "valuation": {
                "II": p.get("II"), "Rf": p.get("Rf"),
                "g_adj": f3.get("g_adj"), "g_base": p.get("g_base"),
                "b_penalty": p.get("b_penalty"),
                "current_price_hkd": m.get("price_hkd"),
                "shares_m": m.get("shares_m"),
                "market_cap_hkd": m.get("mc_hkd"),
            },
            "rejection": rej,
            "position": f4.get("position"),
            "stop_loss": f4.get("stop_loss"),
        },
    }

    return {
        "statement_type": statement_type,
        "metrics": result_map.get(statement_type, result_map["overview"]),
    }


def get_financial_trends(output_dir: str = ".") -> dict[str, Any]:
    """获取财务趋势数据。

    从 ``financial_trends.json`` 或 ``compute_bundle.json`` 中提取关键趋势指标。

    Args:
        output_dir: 股票输出目录。

    Returns:
        趋势数据 dict。
    """
    ft = _read_json(os.path.join(output_dir, "financial_trends.json"))
    if ft:
        return ft

    # 回退：从 compute_bundle 提取完整 overview
    cb = _read_json(os.path.join(output_dir, "compute_bundle.json"))
    if not cb:
        return {"error": "无财务数据"}

    f2 = cb.get("factor2", {})
    f3 = cb.get("factor3", {})
    p = cb.get("params", {})
    m = cb.get("market", {})

    return {
        "np_trend": f3.get("aa"),                    # 归属净利润趋势
        "revenue_trend": f3.get("true_revenue"),       # 真实收入趋势
        "receipt_ratios": f3.get("receipt_ratios"),    # 现金回收率趋势
        "np_avg_3y": f2.get("np_avg_3y"),
        "oe_avg_3y": f2.get("oe_avg_3y"),
        "ocf_np": f2.get("ocf_np_ratio"),
        "gg_scenarios": cb.get("calculation_trace", {}).get("factor3_gg_scenarios", {}),
        "II": p.get("II"),
        "Rf": p.get("Rf"),
        "current_price": m.get("price_hkd"),
        "market_cap": m.get("mc_hkd"),
    }


# 工具元数据（供 auto_discover 使用）
list_documents._tool_meta = {"name": "list_documents", "description": "列出所有可用文档和数据文件", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
read_section._tool_meta = {"name": "read_section", "description": "读取年报特定章节文本(MDA/RISK/GOV/AUDIT/STMT/NOTES等)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "year": {"type": "integer", "description": "财年", "optional": True}, "section": {"type": "string", "description": "章节标签"}}}  # type: ignore[attr-defined]
search_report._tool_meta = {"name": "search_report", "description": "在年报全文中搜索关键词", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "query": {"type": "string", "description": "搜索关键词"}, "year": {"type": "integer", "description": "财年过滤", "optional": True}}}  # type: ignore[attr-defined]
get_financial_statement._tool_meta = {"name": "get_financial_statement", "description": "获取标准化财务报表(income/balance_sheet/cash_flow)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "statement_type": {"type": "string", "description": "income/balance_sheet/cash_flow"}}}  # type: ignore[attr-defined]
def read_zone_data(
    output_dir: str = ".",
    zone: str = "mda",
) -> dict[str, Any]:
    """读取 Zone B 定性分析 JSON 数据（LLM 预提取的结构化洞察）。

    年报 PDF → zone_b_v8.py → mda/segments/risks/governance/audit.json
    这些 JSON 包含**已提炼的关键洞察+证据引用**，比原始 PDF 文本密度高很多。

    Args:
        output_dir: 股票输出目录。
        zone: zone 名称 (mda/segments/risks/governance/audit)。

    Returns:
        对应 Zone JSON 的结构化数据。
    """
    zone_files = {
        "mda": "mda.json",
        "segments": "segments.json",
        "risks": "risks.json",
        "governance": "governance.json",
        "audit": "audit.json",
    }
    filename = zone_files.get(zone.lower(), f"{zone}.json")
    path = os.path.join(output_dir, filename)
    data = _read_json(path)
    if not data:
        return {"zone": zone, "error": f"{filename} 不存在", "data": {}}
    return {"zone": zone, "data": data}


read_zone_data._tool_meta = {"name": "read_zone_data", "description": "读取Zone B定性分析JSON(mda/segments/risks/governance/audit)—LLM预提取的结构化洞察+证据引用", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "zone": {"type": "string", "description": "mda/segments/risks/governance/audit"}}}  # type: ignore[attr-defined]

get_financial_trends._tool_meta = {"name": "get_financial_trends", "description": "获取财务趋势数据", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# V12 新增：同行对比 + 市场数据
# ---------------------------------------------------------------------------


def get_peer_comparison(output_dir: str = ".") -> dict[str, Any]:
    """获取同行对比数据 — 读 industry_context.json 的 comparable_peers + percentiles。

    Agent 在写定性章节（Ch2 行业位置、Ch3 护城河、Ch5 经营表现）前调用，
    用于嵌入同行对比表。
    """
    import json as _json
    path = os.path.join(output_dir, "industry_context.json")
    if not os.path.exists(path):
        return {"ok": False, "error": "industry_context.json 不存在，请先运行 Phase 1"}

    with open(path, encoding="utf-8") as f:
        data = _json.load(f)

    peers = data.get("comparable_peers", [])
    percentiles = data.get("percentiles", {})
    signals = data.get("signals", [])
    meta = data.get("meta", {})

    # 构建同行对比表
    peer_table = []
    for p in peers:
        peer_table.append({
            "ts_code": p.get("ts_code", "?"),
            "name": p.get("name", "?"),
            "market": p.get("market", "?"),
        })

    # 百分位摘要
    pct_summary = {}
    for key, val in percentiles.items():
        if isinstance(val, dict):
            pct_summary[key] = {
                "label": val.get("label", key),
                "value": val.get("value"),
                "industry_median": val.get("industry_median"),
                "percentile": val.get("percentile"),
                "peer_count": val.get("peer_count"),
            }

    return {
        "ok": True,
        "industry": meta.get("industry_l2") or meta.get("industry_group", "未知"),
        "peer_count_total": meta.get("total_industry_peers", 0),
        "comparable_peers": peer_table,
        "percentiles": pct_summary,
        "signals": [
            {"type": s.get("type"), "detail": s.get("detail")}
            for s in signals
        ],
    }


def get_market_data(output_dir: str = ".") -> dict[str, Any]:
    """获取市场数据并标注可信度 — 读 compute_bundle.json。

    特别标注 yfinance 可能的股本数据错误（港股常见：yfinance 取自由流通股而非总股本）。
    """
    import json as _json
    path = os.path.join(output_dir, "compute_bundle.json")
    if not os.path.exists(path):
        return {"ok": False, "error": "compute_bundle.json 不存在"}

    with open(path, encoding="utf-8") as f:
        data = _json.load(f)

    market = data.get("market", {})
    params = data.get("params", {})
    f2 = data.get("factor2", {})
    f4 = data.get("factor4", {})

    warns = []
    shares = market.get("shares_m", 0)
    shares_warning = market.get("shares_warning", False)

    # V12: 尝试从数据库获取正确股本
    db_shares = None
    if shares_warning:
        try:
            import sqlite3
            # output_dir 是 output/01502_金融街物业, 往上两级到框架根目录
            _framework_dir = os.path.abspath(os.path.join(output_dir, "..", ".."))
            db_path = os.path.join(_framework_dir, "stock_analysis.db")
            db = sqlite3.connect(db_path) if os.path.exists(db_path) else None
            if db is None:
                db_path = os.path.join(os.path.dirname(output_dir), "..", "stock_analysis.db")
                db = sqlite3.connect(db_path) if os.path.exists(db_path) else None
            if db:
                row = db.execute("SELECT shares_m FROM stocks WHERE ts_code LIKE ?", (f"%{os.path.basename(output_dir).split('_')[0]}%",)).fetchone()
                if row and row[0]:
                    db_shares = row[0]
                    warns.append(f"⚠️ yfinance 股本={shares}M（❌）。数据库实际总股本={db_shares}M（✅）。GG计算请用数据库股本。")
                db.close()
        except Exception:
            pass

    # 用数据库股本修正市值
    corrected_mc_hkd = None
    corrected_mc_rmb = None
    if db_shares and db_shares > 0:
        price_hkd = market.get("price_hkd", 0) or 0
        fx = market.get("fx", 0.93) or 0.93
        corrected_mc_hkd = round(db_shares * price_hkd, 2)
        corrected_mc_rmb = round(db_shares * price_hkd * fx, 2)

    return {
        "ok": True,
        "market": {
            "price_hkd": market.get("price_hkd"),
            "price_rmb": market.get("price_rmb"),
            "shares_m": shares,
            "shares_m_corrected": db_shares,
            "shares_warning": shares_warning,
            "mc_hkd": market.get("mc_hkd"),
            "mc_hkd_corrected": corrected_mc_hkd,
            "mc_rmb": market.get("mc_rmb"),
            "mc_rmb_corrected": corrected_mc_rmb,
            "mc_rmb": market.get("mc_rmb"),
            "fx": market.get("fx"),
        },
        "params": {
            "II": params.get("II"),
            "Rf": params.get("Rf"),
            "g_base": params.get("g_base"),
            "b_penalty": params.get("b_penalty"),
        },
        "ddm_tiers": f4.get("tiers", []),
        "warnings": warns,
    }


get_peer_comparison._tool_meta = {"name": "get_peer_comparison", "description": "获取同行对比数据(comparable_peers+百分位排名)—用于嵌入同行对比表", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
get_market_data._tool_meta = {"name": "get_market_data", "description": "获取市场数据+数据可信度警告(yfinance股本bug标注)", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]
