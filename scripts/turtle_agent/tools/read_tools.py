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
import re
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


def _evidence_document_for_year(
    output_dir: str, year: int, source_filename: str = ""
) -> dict[str, Any] | None:
    manifest = _read_json(os.path.join(output_dir, "document_manifest.json")) or {}
    matches: list[dict[str, Any]] = []
    for document in manifest.get("documents") or []:
        if not isinstance(document, dict):
            continue
        if str(document.get("period_end") or "")[:4] != str(int(year)):
            continue
        if document.get("doc_type") not in {"annual_report", "interim_report"}:
            continue
        if source_filename and source_filename not in {
            str(document.get("local_path") or ""), str(document.get("derived_text_path") or "")
        }:
            continue
        matches.append(document)
    if not matches and source_filename:
        return _evidence_document_for_year(output_dir, year)
    annual = [item for item in matches if item.get("doc_type") == "annual_report"]
    return (annual or matches or [None])[0]


def _attach_evidence_identity(
    result: dict[str, Any], output_dir: str, year: int, source_filename: str = ""
) -> dict[str, Any]:
    document = _evidence_document_for_year(output_dir, year, source_filename)
    enriched = dict(result)
    enriched["document_id"] = document.get("doc_id") if document else None
    enriched["document_authority"] = document.get("authority") if document else None
    enriched["verification_eligible"] = bool(
        document and document.get("authority") in {"audited_filing", "company_filing", "official_statistics", "other_official"}
    )
    return enriched


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
        elif f.endswith(".md") and f.startswith("_"):
            docs.append({"file": f, "type": "appendix"})

    # 检查 page_map
    for f in os.listdir(output_dir):
        if f.startswith("page_map") and f.endswith(".json"):
            docs.append({"file": f, "type": "page_map"})

    manifest = _read_json(os.path.join(output_dir, "document_manifest.json")) or {}
    return {
        "documents": docs,
        "data_files": data_files,
        "official_evidence": {
            "state": (manifest.get("validation") or {}).get("state", "UNAVAILABLE"),
            "manifest_hash": manifest.get("manifest_hash"),
            "documents": manifest.get("documents") or [],
        },
    }


_CHAPTER_TEMPLATE_TITLES = {
    0: "投资要点概览",
    1: "公司做的是什么生意",
    2: "行业吸引力与公司位置",
    3: "商业模式机制、护城河与关键约束",
    4: "最近一年关键变化与当前阶段",
    5: "经营表现与核心驱动",
    6: "财务表现与资本配置",
    7: "股东回报路径",
    8: "管理层、治理与激励",
    9: "核心风险与否决项",
    10: "增长质量与参数校准",
    11: "穿透回报率 GG",
    12: "内在价值合成与裁决",
    13: "DDM 估值与仓位执行",
    14: "综合决策",
}

_DECISIVE_QUESTION_CHAPTERS = {
    "owner_return_hurdle": {0, 6, 10, 11, 12, 13, 14},
    "valuation_model_applicability": {0, 10, 12, 13, 14},
    "cash_value_realization": {0, 6, 7, 8, 9, 12, 14},
    "operating_transition": {0, 1, 2, 3, 4, 5, 9, 10, 12, 14},
    "market_implied_path": {0, 3, 10, 12, 13, 14},
    "critical_evidence_gap": set(range(15)),
}


def read_decisive_question_plan(
    output_dir: str = ".", chapter_index: int | None = None
) -> dict[str, Any]:
    """读取写作前已选中的决定性问题、区分信号和研究任务。"""
    plan = _read_json(os.path.join(output_dir, "decisive_question_plan.json")) or {}
    if not plan:
        return {"ok": False, "error": "decisive_question_plan.json 不存在"}
    selected = [item for item in plan.get("selected_questions") or [] if isinstance(item, dict)]
    if chapter_index is not None:
        idx = int(chapter_index)
        selected = [
            item for item in selected
            if idx in _DECISIVE_QUESTION_CHAPTERS.get(str(item.get("topic_family")), set())
        ]
    findings_validation = _read_json(
        os.path.join(output_dir, "decisive_question_findings_validation.json")
    ) or {}
    findings = (
        _read_json(os.path.join(output_dir, "decisive_question_findings.json")) or {}
        if findings_validation.get("state") in {"DECISION_READY", "MONITORING"}
        else {}
    )
    base_rate_context = _read_json(os.path.join(output_dir, "base_rate_context.json")) or {}
    finding_by_question = {
        str(item.get("question_id")): item for item in findings.get("findings") or []
        if isinstance(item, dict)
    }
    selected = [
        {**item, "research_finding": finding_by_question.get(str(item.get("question_id")))}
        for item in selected
    ]
    return {
        "ok": True,
        "state": (plan.get("validation") or {}).get("state"),
        "input_fingerprint": plan.get("input_fingerprint"),
        "chapter_index": chapter_index,
        "selected_questions": selected,
        "rejected_candidates": plan.get("rejected_candidates") or [],
        "base_rate_context": {
            "context_fingerprint": base_rate_context.get("context_fingerprint"),
            "library_fingerprint": base_rate_context.get("library_fingerprint"),
            "policy": base_rate_context.get("policy") or {},
            "queries": base_rate_context.get("queries") or {},
            "warnings": base_rate_context.get("warnings") or [],
        },
        "findings_state": (
            findings_validation.get("state")
            or ("NOT_STARTED" if not findings else "UNVALIDATED")
        ),
        "instruction": "只研究能区分竞争解释并改变估值/动作的问题；每个入选问题都须用write_decisive_question_findings闭环，不得另造未入选问题。基准率只可引用同机制查询中的ELIGIBLE CASE；样本少于5时不得输出经验概率，也不得把公司事实或130家估值模型冒充历史案例。",
    }


def read_industry_knowledge_context(output_dir: str = ".") -> dict[str, Any]:
    """Read matched industry mechanisms as a company-verification agenda.

    This intentionally returns the plan-bound, minimal projection rather than
    treating an industry card as a source of issuer facts. Every new match is
    NOT_EVIDENCED until the analyst verifies the listed issuer fields.
    """
    plan = _read_json(os.path.join(output_dir, "decisive_question_plan.json")) or {}
    context = plan.get("industry_knowledge_context")
    if not isinstance(context, dict):
        return {
            "ok": False,
            "error": "industry_knowledge_context_not_available_for_this_plan",
            "instruction": "历史计划可以没有行业知识上下文；不得用行业常识替代本公司官方证据。",
        }
    return {
        "ok": True,
        **context,
        "instruction": (
            "行业知识只能提供问题、反例和本公司取证清单。每个匹配机制当前默认"
            "NOT_EVIDENCED；只有本公司VERIFIED官方证据支持后才能在研究结论中"
            "写为SUPPORTED或CONTRADICTED。不得把机制卡作为claim/evidence、估值参数、"
            "概率、价格或行动依据。"
        ),
    }


def read_valuation_route(output_dir: str = ".") -> dict[str, Any]:
    """Read the canonical archetype and model route before valuation work."""
    archetype = _read_json(os.path.join(output_dir, "company_archetype.json")) or {}
    route = _read_json(os.path.join(output_dir, "valuation_route.json")) or {}
    if not archetype or not route:
        return {"ok": False, "error": "company_archetype.json或valuation_route.json不存在"}
    return {
        "ok": True,
        "archetype": archetype,
        "valuation_route": route,
        "instruction": "估值账本必须服从route_id、模型角色和口径；禁用模型要显式拒绝，多模型分歧不得无依据加权平均。",
    }


def read_chapter_contract(
    output_dir: str = ".",
    chapter_index: int = 0,
    template_path: str = "templates/report_template_v12.md",
) -> dict[str, Any]:
    """按需读取单章完整模板合同，避免每次 LLM 调用重复携带全部 15 章模板。"""
    del output_dir  # 接口统一；模板属于框架，不属于股票目录。
    idx = int(chapter_index)
    title = _CHAPTER_TEMPLATE_TITLES.get(idx)
    if title is None:
        return {"ok": False, "error": f"无效章节: Ch{idx}"}
    path = template_path
    if not os.path.isabs(path):
        path = os.path.abspath(os.path.join(_scripts_dir, "..", path))
    text = _read_text(path)
    if not text:
        return {"ok": False, "error": f"模板不存在: {path}"}
    match = re.search(rf"^## {re.escape(title)}\s*$", text, re.MULTILINE)
    if not match:
        return {"ok": False, "error": f"模板缺少 Ch{idx} {title}"}
    next_heading = re.search(r"^## ", text[match.end():], re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    content = text[match.start():end].strip()
    return {
        "ok": True,
        "chapter_index": idx,
        "title": title,
        "template": os.path.basename(path),
        "content": content,
        "char_count": len(content),
    }


def read_report_contract_pack(
    output_dir: str = ".",
    chapter_indexes: list[int] | None = None,
    template_path: str = "templates/report_template_v12.md",
) -> dict[str, Any]:
    """一次读取本轮所有章节合同与研究计划，避免逐章增加 LLM 往返。"""
    indexes = [int(item) for item in (chapter_indexes or sorted(_CHAPTER_TEMPLATE_TITLES))]
    chapters: dict[str, Any] = {}
    for idx in indexes:
        result = read_chapter_contract(
            output_dir=output_dir,
            chapter_index=idx,
            template_path=template_path,
        )
        if not result.get("ok"):
            return {"ok": False, "error": result.get("error"), "chapter_index": idx}
        chapters[str(idx)] = {
            "title": result["title"],
            "content": result["content"],
            "char_count": result["char_count"],
        }
    try:
        from scripts.research_plan import build_research_plan
    except ModuleNotFoundError:
        from research_plan import build_research_plan
    research_plan = build_research_plan(output_dir, indexes)
    try:
        from scripts.insight_research import build_insight_research_brief
    except ModuleNotFoundError:
        from insight_research import build_insight_research_brief
    insight_brief = build_insight_research_brief(output_dir, persist=True)
    decisive_plan = read_decisive_question_plan(output_dir)
    industry_knowledge_context = read_industry_knowledge_context(output_dir)
    valuation_route = read_valuation_route(output_dir)
    for idx in indexes:
        chapters[str(idx)]["research_plan"] = research_plan["chapters"][str(idx)]
        chapter_questions = read_decisive_question_plan(output_dir, idx)
        chapters[str(idx)]["decisive_questions"] = chapter_questions.get("selected_questions") or []
    evidence_context = _read_json(os.path.join(output_dir, "report_context.json")) or {}
    return {
        "ok": True,
        "template": os.path.basename(template_path),
        "chapter_indexes": indexes,
        "chapters": chapters,
        "research_plan_version": research_plan["version"],
        "available_annual_years": research_plan["available_annual_years"],
        "insight_research_brief": insight_brief,
        "decisive_question_plan": decisive_plan,
        "industry_knowledge_context": industry_knowledge_context,
        "valuation_route": valuation_route,
        "official_evidence": {
            "state": (evidence_context.get("validation") or {}).get("state", "UNAVAILABLE"),
            "coverage": evidence_context.get("coverage") or {},
            "unresolved_gaps": evidence_context.get("unresolved_gaps") or [],
            "instruction": "重大主张优先引用VERIFIED observation_id；CANDIDATE只能指导继续回读，不得直接支持结论。",
        },
        "char_count": sum(item["char_count"] for item in chapters.values()),
    }


read_report_contract_pack._tool_meta = {
    "name": "read_report_contract_pack",
    "description": "本轮开始时一次读取全部目标章节的完整合同包及问题导向研究计划。每章须回答计划问题、给出支持证据与反证并形成事实→机制→财务→估值闭环；章节通过后框架逐项压缩。不要逐章重复读取合同。",
    "parameters": {
        "chapter_indexes": {"type": "array", "items": {"type": "integer"}, "description": "本轮目标章节；首轮省略即0-14", "optional": True},
        "template_path": {"type": "string", "description": "模板路径，由框架自动注入", "optional": True},
    },
}
read_decisive_question_plan._tool_meta = {
    "name": "read_decisive_question_plan",
    "description": "读取框架在写作前按价值敏感性选出的1-3个决定性问题、竞争解释、区分信号、有界研究任务及已提交研究结论。",
    "parameters": {
        "output_dir": {"type": "string", "description": "股票输出目录"},
        "chapter_index": {"type": "integer", "description": "可选；只返回与该章相关的问题", "optional": True}
    },
}
read_industry_knowledge_context._tool_meta = {
    "name": "read_industry_knowledge_context",
    "description": "读取行业机制匹配及本公司必须验证字段。它只提供研究问题和反例，不能替代公司官方证据或直接支持估值、价格和动作。",
    "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}},
}
read_valuation_route._tool_meta = {
    "name": "read_valuation_route",
    "description": "读取框架写作前确定的公司主/次原型、适用/压力/禁用估值模型、口径和脆弱性规则。",
    "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}},
}


_MARKDOWN_SECTION_PATTERNS: dict[str, tuple[str, ...]] = {
    "MDA": (
        r"^第三节\s+管理层讨论与分析\s*$",
        r"^第三节\s+经营情况讨论与分析\s*$",
        r"^(?:管理层讨论与分析|管理層討論與分析)\s*$",
    ),
    "GOV": (
        r"^第四节\s+公司治理(?:、环境和社会(?:责任)?)?\s*$",
        r"^公司治理\s*$",
    ),
    "AUDIT": (
        r"^(?:獨立核數師報告|独立核数师报告|獨立審計師報告|独立审计师报告)\s*$",
        r"^审计报告正文\s*$",
        r"^一、\s*审计报告\s*$",
    ),
    "STMT": (r"^合并资产负债表\s*$",),
    "NOTES": (r"^20\d{2}\s*年度财务报表附注\s*$", r"^财务报表附注\s*$"),
    "SEG": (r"占公司营业收入或营业利润\s*10%\s*以上", r"分部信息"),
    "RISK": (r"未来发展面临的主要风险", r"可能面对的风险", r"公司面临的主要风险"),
}

_MARKDOWN_SECTION_PAGE_WINDOWS = {
    "MDA": 29,
    "GOV": 15,
    "AUDIT": 5,
    "STMT": 9,
    "NOTES": 40,
    "SEG": 5,
    "RISK": 4,
}


def _read_markdown_section(
    output_dir: str,
    year: int,
    section: str,
    max_chars: int,
    start_char: int,
) -> dict[str, Any] | None:
    """Read an exact annual-report section from page-marked Markdown.

    PDF scans used to stop at the table of contents because it was the first
    occurrence of every section title.  The preprocessed Markdown has explicit
    ``## 第 N 页`` markers, so anchor on the real section heading and preserve
    page identity without rescanning a 200-page PDF.
    """
    path = os.path.join(output_dir, f"{int(year)}_年报.md")
    text = _read_text(path)
    patterns = _MARKDOWN_SECTION_PATTERNS.get(section.upper())
    if not text or not patterns:
        return None
    start_match = None
    for pattern in patterns:
        candidate = re.search(pattern, text, re.MULTILINE)
        if candidate:
            # Patterns are ordered by specificity.  Do not let an earlier
            # generic governance heading beat the actual auditor report.
            start_match = candidate
            break
    if start_match is None:
        return None

    page_headers = [
        (match.start(), int(match.group(1)))
        for match in re.finditer(r"^##\s+第\s*(\d+)\s*页\s*$", text, re.MULTILINE)
    ]
    if not page_headers:
        return None
    start_header_index = max(
        (idx for idx, (position, _) in enumerate(page_headers) if position <= start_match.start()),
        default=0,
    )
    start_position, start_page = page_headers[start_header_index]
    end_page = start_page + _MARKDOWN_SECTION_PAGE_WINDOWS.get(section.upper(), 10)
    end_position = len(text)
    actual_end_page = page_headers[-1][1]
    for position, page in page_headers[start_header_index + 1:]:
        if page > end_page:
            end_position = position
            actual_end_page = page - 1
            break
    full_text = text[start_position:end_position].strip()
    safe_start = max(0, int(start_char or 0))
    safe_max = max(500, int(max_chars or 30000))
    sliced = full_text[safe_start:safe_start + safe_max]
    next_cursor = safe_start + len(sliced)
    has_more = next_cursor < len(full_text)
    return {
        "section": section.upper(),
        "year": int(year),
        "text": sliced,
        "page_range": [start_page, min(end_page, actual_end_page)],
        "char_count": len(sliced),
        "source": os.path.basename(path),
        "source_type": "annual_markdown",
        "original_char_count": len(full_text),
        "returned_char_count": len(sliced),
        "start_char": safe_start,
        "end_char": next_cursor,
        "truncated": has_more,
        "has_more": has_more,
        "next_cursor": next_cursor if has_more else None,
    }


def read_section(
    output_dir: str = ".",
    year: int = 2024,
    section: str = "MDA",
    max_chars: int = 30000,
    start_char: int = 0,
    research_for_chapters: list[int] | None = None,
) -> dict[str, Any]:
    """读取年报特定章节的文本内容。

    优先使用 pre-built page_map.json（页级随机访问，快）；
    无 page_map 时直接扫 PDF 提取文本（无需预生成）。

    Args:
        output_dir: 股票输出目录。
        year: 财年。
        section: 章节标签（MDA, SEG, STMT, GOV, AUDIT, NOTES, RISK, P2, P3, P4, SUB）。
        max_chars: 最大返回字符数（默认30000）。
        research_for_chapters: 本次原文读取明确服务的报告章节；仅用于审计归因。

    Returns:
        ``{section, year, text, page_range, char_count, source}``。
    """
    # 0) 优先使用带页码的年报 Markdown。它能避开目录页误命中，且无需
    # 每次重新扫描 200+ 页 PDF。
    markdown_result = _read_markdown_section(
        output_dir, year, section, max_chars, start_char
    )
    if markdown_result is not None:
        return _attach_evidence_identity(
            markdown_result, output_dir, year, str(markdown_result.get("source") or "")
        )

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

    # 2) 找 PDF 文件（按匹配优先级：精确年_年报 → 模糊年+年报 → 任意年报）
    pdf_path = ""
    pdf_candidates = [
        os.path.join(output_dir, f"{year}_年报.pdf"),           # 2024_年报.pdf
    ]
    # Also try glob-style matching in the directory listing
    if os.path.isdir(output_dir):
        for f in sorted(os.listdir(output_dir)):
            if not f.endswith(".pdf") or "年报" not in f:
                continue
            # Prefer filename with the exact year
            if str(year) in f:
                pdf_candidates.append(os.path.join(output_dir, f))
        # Fallback: any 年报 PDF
        for f in sorted(os.listdir(output_dir)):
            if f.endswith(".pdf") and "年报" in f:
                pdf_candidates.append(os.path.join(output_dir, f))
                break
    for candidate in pdf_candidates:
        if os.path.exists(candidate):
            pdf_path = candidate
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
                full_text = "\n".join(texts)
                sliced = full_text[start_char:start_char + max_chars]
                next_cursor = start_char + len(sliced)
                return _attach_evidence_identity({
                    "section": section, "year": year,
                    "text": sliced, "page_range": page_range,
                    "char_count": len(sliced), "source": "page_map",
                    "original_char_count": len(full_text),
                    "returned_char_count": len(sliced),
                    "start_char": start_char,
                    "end_char": start_char + len(sliced),
                    "truncated": len(full_text) > start_char + len(sliced),
                    "has_more": len(full_text) > start_char + len(sliced),
                    "next_cursor": next_cursor if len(full_text) > start_char + len(sliced) else None,
                }, output_dir, year, os.path.basename(pdf_path))
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
            full_text = "\n".join(texts)
            sliced = full_text[start_char:start_char + max_chars]
            next_cursor = start_char + len(sliced)

            return _attach_evidence_identity({
                "section": section, "year": year,
                "text": sliced,
                "page_range": [found_page, end_page],
                "char_count": len(sliced),
                "source": "pdf_scan",
                "original_char_count": len(full_text),
                "returned_char_count": len(sliced),
                "start_char": start_char,
                "end_char": start_char + len(sliced),
                "truncated": len(full_text) > start_char + len(sliced),
                "has_more": len(full_text) > start_char + len(sliced),
                "next_cursor": next_cursor if len(full_text) > start_char + len(sliced) else None,
            }, output_dir, year, os.path.basename(pdf_path))
    except Exception as exc:
        return {"section": section, "year": year, "text": "", "error": str(exc)}


def search_report(
    output_dir: str = ".",
    query: str = "",
    year: int | None = None,
    offset: int = 0,
    limit: int = 20,
    research_for_chapters: list[int] | None = None,
) -> dict[str, Any]:
    """在年报全文中搜索关键词。

    返回包含关键词的段落及其上下文。

    Args:
        output_dir: 股票输出目录。
        query: 搜索关键词。
        year: 可选财年过滤。
        research_for_chapters: 本次年报检索明确服务的报告章节；仅用于审计归因。

    Returns:
        ``{query, total_hits, hits: [{snippet, page}]}``。
    """
    # 数据源优先级：{year}_full_text.txt → 任意 _full_text.txt → {year}_年报.md → 任意 _年报.md（取最新年）
    # 注：历史上只找 _full_text.txt，但流水线产出的是 <year>_年报.md，导致 search_report 恒空（0 命中）。
    ft_path = ""
    candidates: list[str] = []
    if year:
        candidates.append(os.path.join(output_dir, f"{year}_full_text.txt"))
    listing = sorted(os.listdir(output_dir)) if os.path.isdir(output_dir) else []
    candidates += [os.path.join(output_dir, f) for f in listing if f.endswith("_full_text.txt")]
    if year:
        candidates.append(os.path.join(output_dir, f"{year}_年报.md"))
        candidates += [os.path.join(output_dir, f) for f in listing
                       if f.endswith("_年报.md") and str(year) in f]
    # 任意年报 .md，最新年优先（文件名以年份打头，倒序取最新）
    candidates += [os.path.join(output_dir, f) for f in sorted(
        (f for f in listing if f.endswith("_年报.md")), reverse=True)]
    for cand in candidates:
        if cand and os.path.exists(cand):
            ft_path = cand
            break

    text = _read_text(ft_path) or ""
    if not query or not text:
        return {"query": query, "total_hits": 0, "hits": [], "source": os.path.basename(ft_path)}

    # 多词查询按 OR 语义：空白分词，任一词命中即算命中（原先整串字面匹配，
    # 令 "货币资金 应收账款 存货" 这类多科目查询永远无命中）。
    tokens = [t.lower() for t in query.split() if t.strip()] or [query.lower()]
    lines = text.split("\n")
    hits: list[dict[str, Any]] = []
    current_page: int | None = None
    for i, line in enumerate(lines):
        marker = re.match(r"^##\s+第\s*(\d+)\s*页\s*$", line)
        if marker:
            current_page = int(marker.group(1))
        low = line.lower()
        matched = [t for t in tokens if t in low]
        if matched:
            ctx_start = max(0, i - 1)
            ctx_end = min(len(lines), i + 2)
            snippet = "\n".join(lines[ctx_start:ctx_end])[:500]
            hits.append({
                "snippet": snippet,
                "line": i + 1,
                "page": current_page,
                "matched": matched,
                "locator": {"page": current_page, "line": i + 1},
                "status": "CANDIDATE",
            })

    window = hits[offset:offset + max(1, limit)]
    next_cursor = offset + len(window)
    document = _evidence_document_for_year(output_dir, int(year), os.path.basename(ft_path)) if year else None
    if document is None and ft_path:
        match = re.search(r"(20\d{2})", os.path.basename(ft_path))
        if match:
            document = _evidence_document_for_year(output_dir, int(match.group(1)), os.path.basename(ft_path))
    return {
        "query": query,
        "year": year,
        "source": os.path.basename(ft_path),
        "document_id": document.get("doc_id") if document else None,
        "document_authority": document.get("authority") if document else None,
        "verification_eligible": bool(document and document.get("authority") != "derived"),
        "total_hits": len(hits),
        "hits": window,
        "offset": offset,
        "limit": max(1, limit),
        "has_more": next_cursor < len(hits),
        "next_cursor": next_cursor if next_cursor < len(hits) else None,
    }


def read_evidence_context(
    output_dir: str = ".", domain: str = "", status: str = "VERIFIED"
) -> dict[str, Any]:
    """读取官方证据上下文；默认只返回可支持重大主张的VERIFIED事实。"""
    context = _read_json(os.path.join(output_dir, "report_context.json")) or {}
    observations = _read_json(os.path.join(output_dir, "fact_observations.json")) or {}
    if not context:
        return {"ok": False, "error": "report_context.json 不存在"}
    requested = str(status or "VERIFIED").upper()
    if requested == "VERIFIED":
        domains = context.get("domains") or {}
        selected = domains.get(domain, []) if domain else [item for values in domains.values() for item in values]
    else:
        selected = [
            item for item in observations.get("observations") or []
            if isinstance(item, dict)
            and str(item.get("status") or "").upper() == requested
            and (not domain or item.get("domain") == domain)
        ]
    return {
        "ok": True,
        "state": (context.get("validation") or {}).get("state"),
        "context_fingerprint": (context.get("meta") or {}).get("context_fingerprint"),
        "domain": domain or None,
        "status": requested,
        "facts": selected,
        "count": len(selected),
        "unresolved_gaps": context.get("unresolved_gaps") or [],
        "conflicts": context.get("conflicts") or [],
        "citable": requested == "VERIFIED",
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
read_section._tool_meta = {"name": "read_section", "description": "读取年报特定章节文本(MDA/RISK/GOV/AUDIT/STMT/NOTES等)，返回截断状态与续读 cursor", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "year": {"type": "integer", "description": "财年", "optional": True}, "section": {"type": "string", "description": "章节标签"}, "max_chars": {"type": "integer", "description": "本次最多读取字符数", "optional": True}, "start_char": {"type": "integer", "description": "续读起始字符，使用上次 next_cursor", "optional": True}, "research_for_chapters": {"type": "array", "items": {"type": "integer"}, "description": "本次原文读取服务的章节编号，如 [6] 或 [6,7]；来源深化时必填", "optional": True}}}  # type: ignore[attr-defined]
search_report._tool_meta = {"name": "search_report", "description": "在年报全文中搜索关键词，返回命中行与分页 cursor", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "query": {"type": "string", "description": "搜索关键词"}, "year": {"type": "integer", "description": "财年过滤", "optional": True}, "offset": {"type": "integer", "description": "命中结果续读 offset", "optional": True}, "limit": {"type": "integer", "description": "本次最多返回命中数", "optional": True}, "research_for_chapters": {"type": "array", "items": {"type": "integer"}, "description": "本次年报检索服务的章节编号，如 [4] 或 [4,9]；来源深化时必填", "optional": True}}}  # type: ignore[attr-defined]
read_evidence_context._tool_meta = {"name": "read_evidence_context", "description": "读取结构化官方证据。默认只返回VERIFIED事实及observation_id；CANDIDATE仅用于安排回读，不能支持重大主张。", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}, "domain": {"type": "string", "description": "可选事实域，如audit/financial/operations/governance", "optional": True}, "status": {"type": "string", "description": "VERIFIED/CANDIDATE/CONFLICT，默认VERIFIED", "optional": True}}}  # type: ignore[attr-defined]
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
    """获取同行对比数据 — 读 industry_context.json，返回完整同业财务数据 + 百分位排名。

    Agent 在写定性章节（Ch2 行业位置、Ch3 护城河、Ch5 经营表现）前调用，
    用于嵌入同行对比表。返回的 comparable_peers 包含完整财务指标，
    Agent 可直接用来构建 ≥4家同行 × ≥8项指标的对比表。

    V12.17: 保留完整同行财务数据（不再剥离），新增行业集中度信息。
    """
    import json as _json
    from pathlib import Path
    path = os.path.join(output_dir, "industry_context.json")
    if not os.path.exists(path):
        return {"ok": False, "error": "industry_context.json 不存在，请先运行 Phase 1"}

    with open(path, encoding="utf-8") as f:
        data = _json.load(f)

    peers = data.get("comparable_peers", [])
    percentiles = data.get("percentiles", {})
    signals = data.get("signals", [])
    meta = data.get("meta", {})
    target = data.get("target_metrics", {})

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
        "industry_l1": meta.get("industry_l1", ""),
        "peer_count_total": meta.get("total_industry_peers", 0),
        "fiscal_year": meta.get("fiscal_year", ""),
        "target_metrics": target,
        "comparable_peers": peers,
        "percentiles": pct_summary,
        "signals": [
            {"type": s.get("type"), "detail": s.get("detail")}
            for s in signals
        ],
        "usage_hint": (
            "同行财务数据已包含在 comparable_peers 中。"
            "Agent 应在 Ch2/Ch3/Ch5 中构建对比表（≥4家同行 × 各指标），"
            "关键是解释公司与行业中位数的差异来源（商业模式差异/竞争优势/生命周期阶段），"
            "而非仅罗列排名数字。"
        ),
    }


def get_global_benchmarks(output_dir: str = ".") -> dict[str, Any]:
    """获取国际对标指引 — 基于行业标签自动生成国际对标搜索方案。

    1. 从 industry_context.json / analysis_contract.json 获取行业分类
    2. 用行业名直接构造 web_search 查询（无需手动维护对标名单）
    3. 若 config/global_benchmarks.json 中有该行业的精选对标公司，则额外返回

    Agent 在写 Ch2 前调用：先用本工具获取搜索方案，再用 web_search 获取实时财务数据。
    """
    import json as _json
    import os as _os

    # 1. 获取行业分类
    industry = ""
    peer_group = ""

    industry_path = _os.path.join(output_dir, "industry_context.json")
    if _os.path.exists(industry_path):
        with open(industry_path, encoding="utf-8") as f:
            ind = _json.load(f)
        meta = ind.get("meta", {})
        industry = meta.get("industry_l2") or meta.get("industry_group", "")
        if not peer_group:
            peer_group = meta.get("industry_group", "")

    contract_path = _os.path.join(output_dir, "analysis_contract.json")
    if _os.path.exists(contract_path):
        with open(contract_path, encoding="utf-8") as f:
            contract = _json.load(f)
        ic = contract.get("industry_classification", {})
        if not peer_group:
            peer_group = ic.get("peer_group", "")
        if not industry:
            industry = ic.get("l2", "")

    search_label = peer_group or industry
    if not search_label:
        return {"ok": True, "matched": False, "note": "无法确定行业分类", "peers": [], "search_queries": []}

    # 2. 自动生成搜索查询（覆盖所有行业）
    search_queries = [
        f"{search_label} 行业 全球 龙头 上市公司 毛利率 净利率 ROE",
        f"{search_label} 国际 对标 公司 派息率 估值 对比",
    ]

    # 3. 检查是否有精选对标公司（可选，JSON 不存在也不影响）
    framework_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))))
    benchmarks_path = _os.path.join(framework_root, "config", "global_benchmarks.json")
    curated_peers = []
    business_note = ""
    if _os.path.exists(benchmarks_path):
        with open(benchmarks_path, encoding="utf-8") as f:
            benchmarks_db = _json.load(f)
        keywords_lower = {industry.lower(), peer_group.lower(), search_label.lower()}
        for entry in benchmarks_db.get("benchmarks", []):
            entry_kw = set(k.lower() for k in entry.get("keywords", []))
            if entry_kw & keywords_lower:
                curated_peers = [p["name"] for p in entry.get("peers", [])]
                business_note = entry.get("business_model_note", "")
                # 有精选名单时，额外添加针对性搜索
                for p in entry.get("peers", [])[:3]:
                    search_queries.insert(0, f"{p['name']} {p.get('ticker','')} FY2024 revenue margin dividend")
                break

    return {
        "ok": True,
        "matched": True,
        "industry": industry,
        "peer_group": peer_group,
        "curated_peers": curated_peers,
        "business_model_note": business_note,
        "search_queries": search_queries,
        "note": (
            f"行业={search_label}。search_queries 为自动生成的 web 搜索语句，适用于任何行业。"
            + (f" 另有 {len(curated_peers)} 家精选对标公司。" if curated_peers else "")
            + " Agent 须用 web_search 获取实时财务数据，标注 [source: web_search → {域名} {日期}]。"
        ),
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
get_global_benchmarks._tool_meta = {"name": "get_global_benchmarks", "description": "获取国际对标公司数据(毛利率/净利率/派息率/Capex等)—与全球可比同行对比", "parameters": {"output_dir": {"type": "string", "description": "股票输出目录"}}}  # type: ignore[attr-defined]


def read_structured_ledger_contract(
    output_dir: str = ".", ledger: str = "valuation"
) -> dict[str, Any]:
    """Return the exact nested types expected by a V3 ledger validator.

    Tool schemas prevent gross type errors, while this on-demand contract keeps
    the permanent prompt small and gives the model the IDs created by earlier
    gates in the same run.
    """
    import json as _json
    from pathlib import Path

    def load(name: str) -> dict[str, Any]:
        try:
            value = _json.loads(Path(output_dir, name).read_text(encoding="utf-8"))
        except (OSError, _json.JSONDecodeError):
            return {}
        return value if isinstance(value, dict) else {}

    decisions = [
        str(item.get("entry_id"))
        for item in load("decision_ledger.json").get("entries") or []
        if isinstance(item, dict) and item.get("status") == "active"
    ]
    claims = load("claim_evidence.json").get("claims") or []
    claim_ids = [str(item.get("claim_id")) for item in claims if isinstance(item, dict)]
    evidence_ids = [
        str(raw.get("evidence_id"))
        for item in claims if isinstance(item, dict)
        for raw in item.get("raw_facts") or [] if isinstance(raw, dict)
    ]
    canonical_valuation = load("valuation_model.json")
    valuation_proposal = load("valuation_decision_revision_proposal.json")
    internal_valuation = (
        valuation_proposal.get("candidate")
        if valuation_proposal.get("state") == "INTERNAL_SYNTHESIS_REQUIRED"
        and isinstance(valuation_proposal.get("candidate"), dict)
        else {}
    )
    if internal_valuation:
        try:
            from scripts.valuation_model_gate import valuation_fingerprint
        except ModuleNotFoundError:
            from valuation_model_gate import valuation_fingerprint
        if valuation_fingerprint(internal_valuation) != valuation_proposal.get("candidate_fingerprint"):
            internal_valuation = {}
    model_ids = [
        str(item.get("model_id"))
        for item in (internal_valuation or canonical_valuation).get("models") or []
        if isinstance(item, dict)
    ]
    observations = load("fact_observations.json").get("observations") or []
    verified_observation_ids = [
        str(item.get("observation_id")) for item in observations
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
        and item.get("observation_id")
    ]
    calculation_payload = load("calculation_observations.json")
    verified_calculations = [
        {key: item.get(key) for key in ("calculation_id", "tool", "metric_path", "value", "unit", "status")}
        for item in calculation_payload.get("calculations") or []
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    ]
    verified_observations = [
        {key: item.get(key) for key in (
            "observation_id", "fact_name", "domain", "normalized_value",
            "unit", "as_of", "doc_id", "status",
        )}
        for item in observations
        if isinstance(item, dict) and item.get("status") == "VERIFIED"
    ]
    decisive_plan = load("decisive_question_plan.json")
    gate_files = {
        "decision": load("decision_ledger.json"),
        "claim": load("claim_evidence.json"),
        "valuation": load("valuation_model.json"),
        "thesis": load("thesis_test.json"),
        "decisive": load("decisive_question_findings.json"),
        "insight": load("insight_ledger.json"),
        "judgment": load("judgment_review.json"),
    }
    gate_states = {
        name: "frozen" if bool((value.get("freeze") or {}).get("frozen"))
        else "reviewable" if value else "missing"
        for name, value in gate_files.items()
    }
    common = {
        "sequence": ["decision", "claim", "valuation", "thesis", "decisive", "insight", "judgment"],
        "active_decision_entry_ids": decisions,
        "claim_ids": claim_ids,
        "evidence_ids": evidence_ids,
        "valuation_model_ids": model_ids,
        "verified_observation_ids": verified_observation_ids,
        "gate_states": gate_states,
        "company_archetype": load("company_archetype.json"),
        "valuation_route": load("valuation_route.json"),
        "skip_rule": "Do not rewrite a frozen earlier gate; continue with the first missing/reviewable gate.",
        "staging": "submit complete structure with freeze=false; repair returned findings; freeze=true only when clean",
    }
    if internal_valuation and ledger in {"thesis", "decisive", "insight", "judgment"}:
        common["internal_full_report_synthesis"] = {
            "status": "INTERNAL_HYPOTHESIS_NOT_FINAL_ACTION",
            "valuation_candidate_fingerprint": valuation_proposal.get("candidate_fingerprint"),
            "valuation": internal_valuation,
            "current_canonical_manifest": valuation_proposal.get("current_manifest") or {},
            "rules": [
                "Use this valuation candidate as context for thesis, insight, falsification and chapter synthesis.",
                "Do not describe its action or position as approved, final, published or executable.",
                "Do not force downstream reasoning to agree with it; preserve contradictory evidence and revise the final action only after the full report closes.",
                "Canonical valuation, decision ledger and manifest remain unchanged until one full-report transaction passes every machine gate.",
            ],
        }
    if ledger == "claim":
        migration_candidate = load("claim_evidence_migration_candidate.json")
        migration_report = load("claim_evidence_migration_report.json")
        if migration_candidate and migration_report:
            referenced_calculation_ids = {
                str(evidence.get("calculation_id"))
                for claim in migration_candidate.get("claims") or [] if isinstance(claim, dict)
                for evidence in claim.get("raw_facts") or [] if isinstance(evidence, dict)
                if evidence.get("calculation_id")
            }
            common["deterministic_migration"] = {
                "canonical_ledger_unchanged": bool(migration_report.get("canonical_ledger_unchanged")),
                "source_ledger_fingerprint": migration_report.get("source_ledger_fingerprint"),
                "candidate_validation": migration_report.get("candidate_validation"),
                "unresolved_frontier": migration_report.get("unresolved_frontier") or [],
                "candidate_claims": migration_candidate.get("claims") or [],
                "instruction": (
                    "Use candidate_claims as the repair base. Preserve claim text, reasoning, confidence, "
                    "decision impact and already-bound atomic OBS rows. Resolve only unresolved_frontier; "
                    "never reconstruct the ledger from IDs alone."
                ),
            }
        else:
            # A writer must see the structure it is repairing.  The former
            # ID-only response forced a fresh model to reconstruct conclusions
            # and was a direct cause of context-loss regressions.
            common["current_claims"] = claims
            referenced_calculation_ids = {
                str(item.get("calculation_id")) for item in verified_calculations
            }
        common["verified_calculations"] = [
            item for item in verified_calculations
            if str(item.get("calculation_id")) in referenced_calculation_ids
        ]
        common["verified_calculation_ids"] = sorted(referenced_calculation_ids)
    if ledger == "valuation":
        migration_candidate = load("valuation_model_migration_candidate.json")
        migration_report = load("valuation_model_migration_report.json")
        if migration_candidate and migration_report:
            semantic_observation_names = {
                "dividend_payout_ratio_pct", "dividend_per_share",
                "net_profit_parent_rmb_m", "cash_and_cash_equivalents_rmb_m",
                "restricted_bank_deposits_rmb_m", "restricted_bank_deposits_fy2025",
            }
            semantic_observations = [
                item for item in verified_observations
                if item.get("fact_name") in semantic_observation_names
                or item.get("domain") in {"capital_allocation", "governance"}
            ]
            semantic_calculations = [
                item for item in verified_calculations
                if (
                    item.get("tool") == "compute_gg"
                    and (
                        str(item.get("metric_path") or "") in {"II", "Rf", "gg_base", "hh"}
                        or str(item.get("metric_path") or "").startswith((
                            "gg_fcfe.", "gg_normalized.", "gg_raw.",
                            "ingredients.AA_", "ingredients.NP_", "ingredients.OE_",
                            "ingredients.MC.",
                        ))
                    )
                )
                or (
                    item.get("tool") == "compute_aa"
                    and str(item.get("metric_path") or "").startswith("aa_")
                )
            ]
            rejected_resume = load("valuation_semantic_resolution_best_rejected.json")
            if not rejected_resume:
                rejected_resume = load("valuation_semantic_resolution_last_rejected.json")
            expected_frontier_keys = {
                (str(item.get("model_id") or ""), str(item.get("field") or ""))
                for item in migration_report.get("semantic_frontier") or []
                if isinstance(item, dict)
            }
            resume_resolutions = rejected_resume.get("resolutions") or []
            resume_keys = {
                (str(item.get("model_id") or ""), str(item.get("field") or ""))
                for item in resume_resolutions if isinstance(item, dict)
            }
            resume_candidate = rejected_resume.get("candidate")
            if not isinstance(resume_candidate, dict):
                resume_candidate = load("valuation_model_semantic_candidate.json")
            resume_validation = rejected_resume.get("validation")
            resume_source = rejected_resume.get("source_ledger_fingerprint")
            resume_safe = (
                bool(resume_candidate)
                and isinstance(resume_validation, dict)
                and expected_frontier_keys == resume_keys
                and (not resume_source or resume_source == migration_report.get("source_ledger_fingerprint"))
            )
            common["deterministic_migration"] = {
                "canonical_ledger_unchanged": bool(migration_report.get("canonical_ledger_unchanged")),
                "source_ledger_fingerprint": migration_report.get("source_ledger_fingerprint"),
                "route_id": migration_report.get("route_id"),
                "safe_bindings": migration_report.get("safe_bindings") or [],
                "added_route_rejections": migration_report.get("added_route_rejections") or [],
                "semantic_frontier": migration_report.get("semantic_frontier") or [],
                "candidate_validation": migration_report.get("candidate_validation") or {},
                "candidate_company_profile": migration_candidate.get("company_profile") or {},
                "candidate_models": migration_candidate.get("models") or [],
                "candidate_synthesis": migration_candidate.get("synthesis") or {},
                "semantic_research_evidence": {
                    "verified_observations": semantic_observations,
                    "verified_calculations": semantic_calculations,
                    "selection_rule": (
                        "Only VERIFIED official owner-profit/cash/restricted-cash, dividend/capital-allocation/"
                        "governance observations and compute_aa aa_* or compute_gg calculations relevant to "
                        "the declared semantic frontier are included. Cite the exact observation_id or "
                        "calculation_id; these rows provide identity and meaning, not permission to change "
                        "results, assumptions or synthesis outside the frontier."
                    ),
                },
                "discount_rate_completion_rule": (
                    "When semantic_frontier contains assumptions.discount_rate.kind=required_return, "
                    "submit the complete discount_rate object: kind=required_return; value_pct exactly "
                    "equals that model's existing assumptions.required_return_pct; tax_basis exactly "
                    "equals that model's basis.tax_basis; inflation_basis must be nominal or real and "
                    "must be justified in the semantic resolution. Supplying kind alone is invalid."
                ),
                "rejected_research_resume": ({
                    "candidate": resume_candidate,
                    "resolutions": resume_resolutions,
                    "validation": resume_validation,
                    "instruction": (
                        "This is the closest previously rejected, non-canonical draft for the same exact "
                        "frontier. Preserve its candidate and already-valid resolution evidence/text. Repair "
                        "only the listed invalid_findings/incomplete_findings. Call write_valuation_model_ledger "
                        "with resume_best_rejected=true, semantic_resolutions=[], and "
                        "semantic_resolution_patches containing only corrected full resolution rows; do not "
                        "resend company_profile/models/synthesis. The tool deterministically merges the patch "
                        "into this draft and fully revalidates all six rows. The draft has no authority."
                    ),
                } if resume_safe else None),
                "instruction": (
                    "Use the candidate as the repair base. Preserve every active result, assumption, "
                    "synthesis value, action, position and decision reference unless new VERIFIED research "
                    "proves a semantic change. Resolve only semantic_frontier; never rename earnings to "
                    "owner earnings or change a model role merely to pass the route gate. Submit exactly one "
                    "semantic_resolutions row per frontier item with VERIFIED OBS/CALC evidence, research_basis, "
                    "mechanism, valuation_impact and decision_impact. Any undeclared model or synthesis change "
                    "is rejected before canonical persistence."
                ),
            }
        else:
            common["current_valuation"] = load("valuation_model.json")
        common["decision_reliability_validation"] = load(
            "decision_reliability_validation.json"
        )
        rejected_envelope = load("valuation_model_best_rejected.json")
        rejected_valuation = (
            rejected_envelope.get("candidate")
            if isinstance(rejected_envelope.get("candidate"), dict)
            else load("valuation_model_last_rejected.json")
        )
        if rejected_valuation and rejected_valuation.get("models"):
            try:
                from scripts.decision_reliability import validate_decision_reliability
            except ModuleNotFoundError:
                from decision_reliability import validate_decision_reliability
            chapter_dir = Path(output_dir) / "chapters"
            if not chapter_dir.is_dir():
                chapter_dir = Path(output_dir)
            rejected_report_text = "\n\n".join(
                path.read_text(encoding="utf-8")
                for path in sorted(chapter_dir.glob("_ch*.md"))
            )
            rejected_reliability = validate_decision_reliability(
                output_dir,
                report_text=rejected_report_text,
                enforced=True,
                valuation_override=rejected_valuation,
            )
            common["rejected_reliability_resume"] = {
                "candidate_synthesis": rejected_valuation.get("synthesis") or {},
                "candidate_cash_access_bridge": rejected_valuation.get("cash_access_bridge") or {},
                "candidate_parameter_calibrations": rejected_valuation.get("parameter_calibrations") or [],
                "candidate_model_comparisons": rejected_valuation.get("model_comparisons") or [],
                "candidate_joint_stress_tests": rejected_valuation.get("joint_stress_tests") or [],
                "candidate_action_policy": rejected_valuation.get("action_policy") or {},
                "structural_validation": (
                    rejected_envelope.get("structural_validation")
                    if isinstance(rejected_envelope.get("structural_validation"), dict)
                    else load("valuation_model_last_rejected_validation.json")
                ),
                "reliability_validation": rejected_reliability,
                "verified_distribution_evidence": [
                    item for item in verified_observations
                    if str(item.get("fact_name") or "") in {
                        "dividends_total", "dividend_payout_ratio_pct", "dividend_per_share",
                        "parent_distributable_reserves_rmb_m",
                    }
                ],
                "instruction": (
                    "This is a complete non-canonical rejected valuation candidate. If it is closer to "
                    "passing than current_valuation, call write_valuation_model_ledger with "
                    "resume_last_rejected=true and submit only the full top-level reliability section(s) "
                    "named by reliability_validation findings; omitted model/synthesis/sections are "
                    "preserved and the merged candidate is fully revalidated. Never use this route to "
                    "silently force a changed synthesis through the frozen decision ledger. When patching "
                    "models, preserve the exact complete model_id set. A verified parent distributable "
                    "reserve is not parent cash-location evidence: absent a parent-only cash observation, "
                    "all cash components must be 100% haircutted and conservative_accessible_cash_amount=0; "
                    "verified actual_distribution_flow may still support ordinary distributions. For NAV "
                    "or any kind=not_applicable rate, omit discount_rate_difference_pp; never use a sentinel."
                ),
            }
        common["decision_reliability_contract"] = {
            "cash_access_bridge": (
                "Reconcile gross cash to legal-owner components. Each component needs component_id, "
                "amount, access_status, legal_distributability, legal_owner_scope, haircut_pct and "
                "source_ids. Any unverified/restricted/related-party cash receives a 100% haircut in "
                "primary value. A parent distributable-reserve observation is a legal ceiling, never proof "
                "that cash sits at the parent. ordinary_distribution_capacity must distinguish "
                "actual_distribution_flow from legal_reserve_ceiling. Include unresolved and conclusion."
            ),
            "parameter_calibrations": (
                "One row for every retained_value_realization and moat_decay_pct assumption: model_id, "
                "parameter, value, method, range_low/high, basis, source_ids, no market_price_inputs for "
                "intrinsic value, decision_use and two-sided sensitivity.action_at_low/action_at_high."
            ),
            "model_comparisons": (
                "Compare every non-primary active model against a primary model using comparable, "
                "discount_rate_difference_pp, allowed_use and basis_differences. A basis/rate-mismatched "
                "model cannot be labelled corroboration."
            ),
            "joint_stress_tests": (
                "At least one case with simultaneous_inputs covering normalized earnings, payout ratio "
                "and cash access/retained-value realization; include output.value_per_share, output.action "
                "and decision_implication."
            ),
            "action_policy": (
                "Specify current_holders_action, nonholders_action, quantified holder_specific_friction "
                "when they differ, precedence_order, upgrade_requires resolving the decisive cash question, "
                "and joint_stress_action."
            ),
            "repair_rule": (
                "When reliability is the current frontier, preserve the full current_valuation and repair "
                "only listed reliability findings. A changed action/value/position still requires the "
                "ordinary frozen-ledger decision-diff approval; reliability does not bypass it. If a "
                "reliable candidate honestly changes synthesis action, position, or V_final, submit that "
                "candidate unchanged: the writer will create a non-canonical, fingerprint-bound decision "
                "revision proposal instead of forcing agreement with the old manifest."
            ),
        }
    if ledger == "thesis":
        migration_candidate = load("thesis_test_migration_candidate.json")
        migration_report = load("thesis_test_migration_report.json")
        if migration_candidate and migration_report:
            common["deterministic_migration"] = {
                "canonical_ledger_unchanged": bool(migration_report.get("canonical_ledger_unchanged")),
                "source_ledger_fingerprint": migration_report.get("source_ledger_fingerprint"),
                "safe_bindings": migration_report.get("safe_bindings") or [],
                "semantic_frontier": migration_report.get("semantic_frontier") or [],
                "candidate_validation": migration_report.get("candidate_validation") or {},
                "candidate_competitive_tests": migration_candidate.get("competitive_tests") or [],
                "candidate_thresholds": migration_candidate.get("thresholds") or [],
                "candidate_probability_sets": migration_candidate.get("probability_sets") or [],
                "instruction": (
                    "Use the candidate as the complete repair base. Preserve every explanation, evidence "
                    "identity, threshold, probability, valuation, position and action. Deterministically "
                    "inferred resolution_due is safe only when semantic_frontier is empty; otherwise repair "
                    "only the listed frontier and resubmit the complete thesis ledger."
                ),
            }
        else:
            common["current_thesis"] = load("thesis_test.json")
    if ledger == "decision_binding":
        active_entries = [
            {
                "entry_id": str(item.get("entry_id") or ""),
                "metric_id": str(item.get("metric_id") or ""),
                "value": item.get("value"),
                "unit": item.get("unit"),
                "chapters": item.get("chapters") or [],
            }
            for item in load("decision_ledger.json").get("entries") or []
            if isinstance(item, dict) and item.get("status") == "active"
        ]
        return {
            "ok": True,
            "ledger": ledger,
            "active_entries": active_entries,
            "decision_ledger_validation": load("decision_ledger_validation.json"),
            "decision_compiler_validation": load("decision_compiler_validation.json"),
            "rules": [
                "Do not change active entry values, conclusions, parameters, positions or triggers.",
                "A [decision: D-id] may annotate only the exact canonical value/meaning of that entry.",
                "Different scenarios or model outputs require their existing structured identity, not a false D-id.",
                "Make the smallest chapter-only edit and validate through write_chapter.",
            ],
        }
    contracts: dict[str, Any] = {
        "claim": {
            "claim": "{claim_id:str, claim:str copied verbatim into home chapter, chapters:[int], raw_facts:[evidence], reasoning_steps:[str], alternative_explanations:[str], applicability_conditions:[str], confidence:{kind,value 0..1,basis,interval?}, decision_impact:{valuation,position,action}, decision_entry_ids:[existing D-id]}",
            "evidence": "{evidence_id, exactly one of observation_id (official raw fact) or calculation_id (allow-listed deterministic derived result) for direct support; source_id equals observation.doc_id or calculation.tool; source_group_id; fact is atomic and every substantive number occurs in the bound value; authority is verified_calculation for CALC identities, otherwise audited_filing|company_filing|official_statistics|industry_data|media|other; claim_distance raw_data|direct_statement|secondary_summary|analysis|rumor; published_at/data_as_of; direct_support; support_type; basis_match; conflict_of_interest}",
            "anchors": "home chapter contains exact claim text and [claim: claim_id]; every declared chapter contains that anchor",
            "computed_fact_rule": "A compute_gg/compute_aa result is direct only when bound to its exact CALC identity and authority=verified_calculation. Split compound outputs into one row per CALC value; put formulas and inference in reasoning_steps. Never present a derived result as an audited filing observation.",
        },
        "valuation": {
            "company_profile": "object: business_type and asset_intensity exactly from valuation_route.legacy_company_profile; archetype_id, valuation_route_id, registry_version exactly from route; valuation_route and route_reasoning str",
            "model": "{model_id,route_model_id from valuation_route,model_type,role primary|corroborative|stress,status active|rejected,chapters:[int],independence_group_id,shared_assumption_ids:[str],applicability:{business_fit,cash_flow_fit,capital_structure_fit,payout_fit,rationale,disqualifiers:[]},basis:{value_scope and cash_flow_scope exactly from route,currency,as_of,tax_basis pre_tax|post_tax|not_applicable},assumptions:{forecast_years?:number,discount_rate:{value_pct,kind,inflation_basis,tax_basis},terminal_growth:{value_pct,inflation_basis}},result:{value_per_share,currency},terminal_value?:{present_value,total_model_value,share_pct},sensitivity_tests?:[{case_id discount_rate_up_1pp|growth_down_1pp|combined_stress,value_per_share,action buy|hold|avoid}],fragility_mitigation?,source_ids:[resolvable],decision_entry_ids:[existing D-id]}. A rejected route model may contain only identity/status/rejection_reason.",
            "rules": "follow valuation_route model roles and rejected list; perpetuity models need r-g>=3pp, terminal reconciliation and all 3 cases; >=2 genuinely independent groups; each declared chapter contains [valuation: model_id]; never average unresolved model divergence",
            "synthesis": "{action buy|hold|avoid matching manifest,position_pct matching manifest,range_low,range_base,range_high,chosen_value_per_share matching D006,decision_rule,divergence_explanation,decision_entry_id:D006}",
            "semantic_resolution": "For every deterministic_migration.semantic_frontier item submit {model_id,field,evidence_ids:[VERIFIED OBS:/CALC: identities],research_basis,mechanism,valuation_impact,decision_impact}; exact frontier coverage is required and no other active-model/synthesis field may change.",
        },
        "thesis": {
            "probability_set": "{set_id,mutually_exclusive:true,collectively_exhaustive:true,resolution_due:YYYY-MM-DD later than prediction as_of,estimates:[>=2 {scenario_id,label,kind frequency|base_rate|analyst_subjective|scenario_weight,value 0..1,interval:[lo,hi],basis,source_ids:[],as_of}],chapters:[int]}; probabilities sum 1; use wide intervals for subjective. kind=base_rate requires at least 5 same-mechanism ELIGIBLE CASE: IDs from base_rate_context; otherwise use analyst_subjective/scenario_weight and disclose sample shortage",
            "threshold": "{threshold_id,metric,unit,current_value:number,operator >|>=|<|<=|==|changes_to,threshold_value:number,basis_type historical_volatility|peer_benchmark|model_sensitivity|contractual|accounting_regulatory|base_rate|expert_judgment,basis_description,source_ids:[external],observation_frequency,window,aggregation single_period|rolling_average|consecutive_periods|cumulative,seasonal_adjustment adjusted|not_needed|unavailable,accounting_definition,precision:{justified_decimals:int,basis},discrimination_target:test_id|decision_rule,action buy|hold|increase|reduce|avoid|exit|reassess,decision_entry_ids:[D013/D014/D015],chapters:[int]}",
            "competitive_test": "{test_id,thesis_claim_id:existing claim,primary_explanation,strongest_alternative,alternative_evidence_ids:[contradicts/context evidence],discriminating_observations:[{observation_id,metric,availability,primary_prediction,alternative_prediction,update_rule,threshold_id}],probability_set_id,primary_scenario_id,alternative_scenario_id,flip_condition:{threshold_id,basis,window},valuation_after_flip:number,position_after_flip:number,action_after_flip,decision_entry_ids:[D-id],chapters:[int]}",
            "anchors": "declared chapters contain [thesis-test: id], [threshold: id], [probability: id]",
        },
        "decisive": {
            "selected_questions": decisive_plan.get("selected_questions") or [],
            "finding": "{question_id:exact selected DQ id,outcome:RESOLVED|INCONCLUSIVE|PUBLIC_INFO_UNAVAILABLE,evidence_observation_ids:[verified OBS ids],evidence_calculation_ids:[verified CALC ids],attempted_sources:[str],signal_results:[{signal_id:exact id from that question,result:str,supports_explanation_id:exact explanation id or empty string,evidence_ids:[declared OBS/CALC ids that directly support every number in this signal]}],explanation_update:{favored_explanation_id:exact explanation id or empty string,confidence_before:number 0..1,confidence_after:number 0..1,basis:str},decision_update:{valuation_impact:str,position_impact:str,action:str,changed:bool,decision_entry_ids:[existing D-id]},conclusion:str,unresolved:[str],inference_audit:[{inference_id,claim,supporting_evidence_ids,strongest_alternative,discriminating_observation,decision_if_wrong}],resolution_assessment:{net_support:EXPLANATION_A|EXPLANATION_B|MIXED|INSUFFICIENT,decision_consistency,premise_resolution:[{premise_key,plan_value,direction:SUPPORTS_A|SUPPORTS_B|NEUTRAL|UNKNOWN,evidence_ids,assessment}]}}",
            "rules": "submit exactly one finding for every selected question_id; RESOLVED needs verified evidence, a signal result, favored explanation and resolution_assessment covering every exact sensitivity_basis leaf from the selected plan; obey each premise_assessment_policy diagnostic_role, interpretation_rule and allowed_directions; each non-UNKNOWN premise must cite its unique tool=decisive_plan CALC whose metric_path exactly matches question_id.sensitivity_basis.premise_key, while other evidence may explain the direction; each premise must state its copied plan_value, evidence and whether it supports A/B, is neutral or unknown; A+B directions force net_support=MIXED, UNKNOWN or INSUFFICIENT cannot be labeled RESOLVED; every substantive number in each signal must occur in its own evidence_ids, derived numbers require the exact opaque CALC:<hash> copied from verified_calculations, readable CALC aliases are invalid, and a global pile of unrelated OBS cannot support the signal; zero search hits never prove absence; causal or interpretive language not directly stated by bound evidence must use [inference:I001] and have a matching inference_audit row with evidence, strongest alternative, discriminating observation and decision-if-wrong; document non-disclosure must be labeled [negative-evidence]; either label requires a concrete unresolved item; when inference exists confidence_after may rise by at most 0.05; INCONCLUSIVE/PUBLIC_INFO_UNAVAILABLE needs evidence or attempted_sources and confidence_after must not exceed confidence_before",
            "staging": "no freeze parameter; one complete submission must cover every selected question",
        },
        "insight": {
            "question_basis": "{anomaly:str,evidence_ids:[existing evidence],why_it_changes_the_decision:str}",
            "insight": "{insight_id,title,claim_id:existing claim,evidence_ids:[existing evidence],anomaly,mechanism:[>=2 strings],strongest_alternative,discriminating_observation,valuation_impact,action_impact,falsification,company_specific_terms:[>=2 terms appearing in text],decision_entry_ids:[existing D-id],chapters:[int]}",
            "reverse_expectations": "{as_of,current_price,method:reverse model not PE/PB label,implied_operating_path,assumptions,valuation_model_ids:[existing model],conclusion,flip_condition}",
            "value_realization": "{latent_value,controller,access_mechanism,catalyst_required:bool,catalysts:[str],no_catalyst_value,failure_mode,decision_entry_ids:[D-id]}",
            "adversarial_review": "{strongest_case_against,why_it_may_be_right,evidence_ids:[existing],unresolved,decision_if_true}",
            "memo": "{executive_decision,valuation_action,monitoring,price_rule_exception_basis?}; declared chapters contain [insight: id]",
        },
        "judgment": {
            "distinctive_insight": "{insight_id:existing insight,why_it_matters:str,why_not_obvious:str,evidence_ids:[existing evidence],decision_entry_ids:[existing D-id],valuation_model_ids:[existing model]}",
            "fragile_leap": "{claim:str,why_fragile:str,needed_evidence:str,decision_consequence:str}",
            "competitive_explanation_test": "{strongest_alternative:str,evidence_for_alternative:str,discriminator:str,unresolved:str}",
            "decision_dependency": "{without_insight:str,changed_values:str,changed_action:str,conclusion:str}",
            "dimension_assessments": "exactly five keys question_selection/differentiation/evidence_discrimination/valuation_transmission/action_relevance; each value is {state:strong|mixed|weak|not_assessable lowercase,basis:str at least 15 chars}",
            "rules": "ceiling_verdict is INSIGHTFUL|COMPETENT|FRAGILE|NOT_ASSESSABLE uppercase; diagnostic only; use only IDs exposed by this contract; reviewer_limits and missing_information must be non-empty arrays",
        },
    }
    if ledger not in contracts:
        return {"ok": False, "error": f"unknown ledger: {ledger}"}
    if ledger == "decisive":
        decisive_calc_paths = {
            "II", "Rf", "M", "Q", "aa_avg_3y", "net_cash",
            "net_cash_pct_mc", "ocf_np_ratio", "gg_base", "hh",
            "cash_structure.net_cash_broad", "cash_structure.net_cash_narrow",
            "gg_fcfe.base", "gg_fcfe.capex_3y", "gg_fcfe.fcfe_3y",
            "gg_normalized.aa_norm_3y", "gg_normalized.base",
            "gg_normalized.full_capex_3y", "gg_normalized.g_coef",
            "gg_normalized.maintenance_capex", "ingredients.AA_avg_3y.value",
            "ingredients.M.value", "ingredients.MC.value", "ingredients.Q.value",
        }
        common["verified_calculations"] = [
            item for item in verified_calculations
            if str(item.get("metric_path")) in decisive_calc_paths
            or str(item.get("metric_path", "")).startswith("aa_annual.")
            or str(item.get("tool")) == "decisive_plan"
        ]
        common["calculation_identity_rule"] = (
            "Copy calculation_id exactly from verified_calculations; it is an "
            "opaque CALC:<hash>. Never invent readable aliases such as "
            "CALC:compute_gg:gg_base=6.2, never cite a bare CALC:compute_aa, and "
            "never cite compute_ddm because it is not in the verified calculation allow-list."
        )
        attempted = load("decisive_question_findings_best_rejected.json")
        attempted_validation = load(
            "decisive_question_findings_best_rejected_validation.json"
        )
        resume_source = "best_rejected"
        if not attempted or not attempted_validation:
            attempted = load("decisive_question_findings_last_attempt.json")
            attempted_validation = load(
                "decisive_question_findings_last_attempt_validation.json"
            )
            resume_source = "last_attempt"
        if (
            attempted
            and attempted_validation
            and attempted.get("plan_input_fingerprint")
            == decisive_plan.get("input_fingerprint")
        ):
            invalid_rows = [
                str(value) for value in attempted_validation.get("invalid_findings") or []
            ]
            local_patch_markers = (
                "numeric_support_mismatch", "citation_identity_numeric_mismatch",
                "signal_evidence_not_declared_or_verified",
                "unsupported_absolute_assertion", "dimensionally_invalid_comparison",
                "unlabeled_analyst_inference", "negative_search_presented_as_fact",
                "decision_value_missing_binding", "unknown_or_inactive_decision_entry",
                "unknown_inference_tag", "bare_inference_tag_is_ambiguous",
                "inference_confidence_jump_exceeds_0.05",
                "resolution_net_support_invalid", "premise_resolution_not_array",
                "resolved_with_unknown_decision_premise",
                "resolved_with_insufficient_net_support",
                "mixed_premises_require_mixed_net_support",
                "direction_violates_plan_policy",
                "exact_decisive_plan_calculation_missing",
                "decisive_plan_calculation_identity_invalid",
            )
            incomplete_rows = [
                str(value) for value in attempted_validation.get("incomplete_findings") or []
            ]
            local_patch_incomplete_markers = (
                "inference_audit_missing", "disclosed_inference_requires_unresolved",
                "inference_audit[", "resolution_assessment_missing",
                "resolution_decision_consistency_missing", "premise_not_resolved",
                "premise_resolution[",
            )
            local_patch_only = bool(invalid_rows or incomplete_rows) and all(
                any(marker in row for marker in local_patch_markers)
                for row in invalid_rows
            ) and all(
                any(marker in row for marker in local_patch_incomplete_markers)
                for row in incomplete_rows
            )
            common["rejected_research_resume"] = {
                "candidate": attempted,
                "validation": attempted_validation,
                "authority": "non_canonical_failed_attempt",
                "resume_source": resume_source,
                "recommended_mode": (
                    "local_patch_no_new_research" if local_patch_only
                    else "bounded_research_then_patch"
                ),
                "repair_playbook": ({
                    "do_not_call": [
                        "search_report", "read_section", "get_financial_statement",
                        "get_financial_trends", "web_search",
                    ],
                    "first_action": "submit finding_patches immediately from the saved candidate",
                    "numeric": "delete unsupported numbers or bind the exact existing OBS/CALC; never invent a ratio",
                    "negative_evidence": "remove zero-hit absence claims or mark [negative-evidence] and add concrete unresolved",
                    "inference": "rewrite as direct observations or mark [inference:I001], add concrete unresolved and matching inference_audit with evidence, strongest alternative, discriminating observation and decision-if-wrong",
                    "identity": "add an already-declared exact opaque ID to the finding-level list before using it in a signal",
                    "premise": "obey the plan premise_assessment_policy and bind the unique tool=decisive_plan CALC for that exact premise_key; premise assessment and decision_consistency are fully checked for numbers, citation identity, absolute claims, negative evidence and unlabeled inference; add local supporting IDs or reuse a matching audited inference ID, and do not infer cash access from market discount",
                    "dimension": "remove cross-unit comparisons unless a verified calculation produces like-for-like units",
                } if local_patch_only else {}),
                "instruction": (
                    "Reuse only as an editable draft. Preserve supported material, "
                    "remove unsupported claims, add per-signal OBS/CALC evidence_ids, "
                    "never use zero search hits as proof of absence; label causal or "
                    "interpretive claims not stated by a source as [inference], label "
                    "document non-disclosure as [negative-evidence], and keep a concrete "
                    "residual uncertainty in unresolved for either label; "
                    "and prefer write_decisive_question_findings with "
                    "resume_best_rejected=true plus finding_patches. The program "
                    "merges patches by exact question_id and fully revalidates every "
                    "selected question; do not resend unchanged findings."
                ),
            }
    return {"ok": True, "ledger": ledger, **common, "contract": contracts[ledger]}


read_structured_ledger_contract._tool_meta = {
    "name": "read_structured_ledger_contract",
    "description": "写V3结构化账本前读取精确嵌套类型、顺序和当前可用ID；避免把object误写成string/number",
    "parameters": {
        "output_dir": {"type": "string"},
        "ledger": {"type": "string", "enum": ["decision_binding", "claim", "valuation", "thesis", "decisive", "insight", "judgment"]},
    },
}  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# D0：综合派框架执行器细则（渐进式披露）
# ---------------------------------------------------------------------------

# 白名单：短名 → prompts/references/ 下的文件名。只允许读这些框架文档，防任意文件读取。
_FRAMEWORK_REFS = {
    "asset_value": "factor_资产价值重置成本.md",
    "epv": "factor_EPV盈利能力价值.md",
    "routing": "factor1.5_估值路由.md",
    "growth": "factor_VCF成长价值.md",
    "incremental_growth": "factor1C_增量增长检验.md",
    "cost_of_capital": "factor_资本成本与正常化盈利.md",
    "r5_return": "factor_R5回报率分解.md",
}
_FRAMEWORK_DIR = os.path.join(_scripts_dir, "..", "prompts", "references")


def read_framework_reference(name: str = "", **_ignored: Any) -> dict[str, Any]:
    """按需读取综合派估值框架的执行器细则（渐进式披露）。

    lite 主框架只给执行主干；某一步需要细则时（AV 逐项无形重建、EPV 永续推导、
    路由 EPV/AV 分档、成长价值 ROIC 算法等），调本工具拉对应执行器全文。

    Args:
        name: 细则短名，可选值见白名单键。
        **_ignored: 吞掉 Agent 习惯性传入的 output_dir 等无关参数（本工具不需要）。

    Returns:
        ``{ok, name, file, content}`` 或 ``{ok: False, error, available}``。
    """
    if name not in _FRAMEWORK_REFS:
        return {"ok": False, "error": f"未知框架细则 {name!r}", "available": sorted(_FRAMEWORK_REFS.keys())}
    path = os.path.join(_FRAMEWORK_DIR, _FRAMEWORK_REFS[name])
    content = _read_text(path)
    if content is None:
        return {"ok": False, "error": f"细则文件不存在: {_FRAMEWORK_REFS[name]}", "available": sorted(_FRAMEWORK_REFS.keys())}
    return {"ok": True, "name": name, "file": _FRAMEWORK_REFS[name], "content": content}


read_framework_reference._tool_meta = {"name": "read_framework_reference", "description": "读取综合派估值框架执行器细则(渐进式披露)。lite 里遇「细则见 factor_XXX.md」时调此拉全文。name 可选:asset_value(AV逐项重置/无形重建)/epv(盈利能力价值永续推导)/routing(EPV↔AV分档选路由)/growth(成长价值ROIC)/incremental_growth(增量增长检验)/cost_of_capital(r*与正常化盈利)/r5_return(R5回报分解含④b双重税)", "parameters": {"name": {"type": "string", "description": "细则短名:asset_value/epv/routing/growth/incremental_growth/cost_of_capital/r5_return"}}}  # type: ignore[attr-defined]
