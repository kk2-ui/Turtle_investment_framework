#!/usr/bin/env python3
"""Reader-facing coverage contract for Golden reports.

This is intentionally a semantic gate, not a length or formatting score.  It
checks that the document explains the economic chain a reader needs in order
to use the conclusion.  A topic can be closed with an explicit UNKNOWN when
the evidence is unavailable; a link to a technical appendix alone is never a
closure.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "reader-coverage.v1"
READY_STATES = {"PASS", "SKIP"}
ANALYSIS_PURPOSES = {"INVESTMENT_DECISION", "COMPANY_JUDGMENT_ONLY"}

_SOURCE_ANCHOR_RE = re.compile(r"\[(?:table-)?source:\s*[^\]]+\]", re.I)
_FOOTNOTE_RE = re.compile(r"^\[\^\d+\]:\s*\S+", re.M)
_FOOTNOTE_MARKER_RE = re.compile(r"\[\^\d+\]")
_EVIDENCE_BINDING_RE = re.compile(
    r"(?:证据|来源|事实|绑定|evidence|source)\s*(?:绑定|锚点|ids?|:|：)?\s*"
    r"[A-Za-z0-9_.:@/-]{2,}", re.I,
)
_UNKNOWN_RE = re.compile(
    r"未知|未披露|未能确认|证据不足|资料不足|无法计算|无法判断|不可得|不确定|"
    r"unknown|not available|insufficient evidence|undisclosed",
    re.I,
)
_CAUSAL_RE = re.compile(
    r"因为|由于|因此|所以|意味着|取决于|导致|反映|如果|但|然而|区别|"
    r"路径|机制|传导|支持|限制|whether|because|therefore|depends|if|but",
    re.I,
)

# Reader reports explain the economic judgment in ordinary language.  These
# machine identities remain available in structured ledgers and technical
# appendices, but exposing them in the reader body turns the report into an
# internal control-plane panel rather than an investor-facing explanation.
_INTERNAL_CONTROL_TOKEN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "workflow_status",
        re.compile(
            r"\b(?:MECHANISM_READY|NOT_EVIDENCED|LEARNING_APPLIED|"
            r"READY_WITH_NO_PRIOR|G1J_COMPLETE|LEGACY_PARTIAL|NO_PRIMARY|"
            r"SELECTION_ADMITTED|NOT_SELECTION_ELIGIBLE|BINDING_PENDING|"
            r"REVIEWABLE|DECISION_READY|PIT_EVIDENCE_ONLY|"
            r"NO_DECISIVE_PLAN_EVIDENCE_ONLY|NO_MATCHING_MECHANISM_READY|"
            r"NO_EXPLICIT_LEARNING_REFS|NOT_APPLICABLE_TO_VIEW)\b",
            re.I,
        ),
    ),
    (
        "workflow_object_id",
        re.compile(
            r"(?<![A-Za-z0-9_])"
            r"(?:JAX(?:REPORT|UNIT)?|FJ|RHP(?:ASM|EDGE|SIG)?|FDB(?:DRV|EV|MON|REAL)?)"
            r":[A-Za-z0-9_.:@/-]+",
            re.I,
        ),
    ),
)
_INTERNAL_CONTROL_PANEL_RE = re.compile(
    r"^\s*(?:[-*]\s*)?"
    r"(?:[a-z][a-z0-9_.-]*_)?(?:ledger|gate|status|validator|validation)"
    r"\s*(?:[:=]|\|)",
    re.I | re.M,
)
_INTERNAL_CONTROL_TABLE_RE = re.compile(
    r"^\s*\|[^\n|]*(?:ledger|gate|validator|validation)[^\n]*\|"
    r"[^\n|]*(?:status|state|verdict)[^\n]*\|",
    re.I | re.M,
)


def _load(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _normalise(value: str) -> str:
    return re.sub(r"\s+", "", value or "").lower()


def _paragraphs(text: str) -> list[str]:
    """Keep prose blocks while ignoring headings and table-only boilerplate."""
    result: list[str] = []
    for raw in re.split(r"\n\s*\n", text):
        block = raw.strip()
        if not block or block.startswith("#"):
            continue
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or all(line.startswith("|") for line in lines):
            continue
        prose = " ".join(lines)
        prose = re.sub(r"[`*_]", "", prose)
        prose = re.sub(r"\s+", " ", prose).strip()
        # A source list or an appendix link is not reader-facing explanation.
        if len(re.sub(r"\[[^\]]+\]", "", prose)) < 50:
            continue
        result.append(prose)
    return result


def _context(output_dir: str | Path | None, archetype: str | None) -> tuple[str, str]:
    if archetype:
        return archetype, "argument"
    if output_dir is None:
        return "general_operating", "default"
    output = Path(output_dir)
    routed = _load(output / "company_archetype.json")
    primary = routed.get("primary_archetype") or {}
    if isinstance(primary, dict) and primary.get("archetype_id"):
        return str(primary["archetype_id"]), "company_archetype.json"
    valuation = _load(output / "valuation_model.json")
    profile = valuation.get("company_profile") or {}
    if profile.get("archetype_id"):
        return str(profile["archetype_id"]), "valuation_model.json"
    legacy = str(profile.get("business_type") or "")
    aliases = {
        "property_service": "property_service",
        "mature_consumer_manufacturing": "mature_consumer_manufacturing",
        "heavy_asset_cyclical": "heavy_asset_cyclical",
        "utility_infrastructure": "utility_infrastructure",
        "property_developer": "property_developer_asset_holding",
        "bank": "regulated_financial",
    }
    return aliases.get(legacy, "general_operating"), "valuation_model.json" if legacy else "default"


def _topic_specs(
    archetype: str,
    *,
    analysis_purpose: str = "INVESTMENT_DECISION",
) -> dict[str, dict[str, Any]]:
    # Each cue group expresses a different part of the economic question.  A
    # paragraph must connect multiple groups; a keyword list by itself is not
    # sufficient evidence of an explanation.
    earnings_groups = [
        ("earnings", ("收入", "利润", "毛利", "经营", "收益", "earnings", "profit")),
        ("cash", ("现金流", "自由现金", "owner", "fcf", "可分配", "cash")),
        ("normal", ("正常化", "维护", "资本开支", "周期", "跨周期", "常态", "normal", "maintenance")),
    ]
    if archetype in {"heavy_asset_cyclical", "mature_consumer_manufacturing"}:
        earnings_groups = [
            ("cycle", ("周期", "利用率", "价格", "高峰", "低谷", "cycle")),
            *earnings_groups,
        ]
    elif archetype in {"utility_infrastructure", "property_developer_asset_holding"}:
        earnings_groups = [
            ("asset_cash", ("租金", "收费", "npi", "特许", "项目", "出租率", "资产")),
            ("cash", ("现金流", "可分配", "回款", "现金", "cash")),
            ("term_cost", ("期限", "维护", "资本开支", "债务", "利息", "term")),
        ]
    elif archetype == "regulated_financial":
        earnings_groups = [
            ("income", ("收入", "利润", "净息差", "保费", "手续费", "income")),
            ("capital", ("资本充足", "监管资本", "偿付能力", "拨备", "capital")),
            ("distribution", ("可分配", "分红", "派息", "现金", "distribution")),
        ]
    elif archetype == "pre_revenue_biotech":
        earnings_groups = [
            ("pipeline", ("管线", "临床", "适应症", "项目", "pipeline", "clinical")),
            ("runway", ("现金跑道", "现金", "融资", "稀释", "runway", "dilution")),
            ("milestone", ("里程碑", "成功率", "上市", "销售", "milestone")),
        ]

    specs: dict[str, dict[str, Any]] = {
        "business_mechanism": {
            "label": "业务机制",
            "groups": [
                ("offer", ("产品", "服务", "平台", "资产", "收费", "product", "service")),
                ("customer", ("客户", "用户", "支付方", "租户", "买方", "customer", "payer")),
                ("monetise", ("收入", "定价", "销售", "佣金", "租金", "怎么赚钱", "revenue", "monet")),
            ],
            "minimum_groups": 2,
        },
        "earnings_route": {
            "label": "正常盈利或现金路线",
            "groups": earnings_groups,
            "minimum_groups": 2,
            "required_any_groups": ["cash", "normal", "asset_cash", "capital", "runway"],
        },
        "ordinary_share_cash_access": {
            "label": "普通股现金可达性",
            "groups": [
                ("cash", ("现金", "现金流", "分配", "股息", "可分配", "cash")),
                ("ownership", ("普通股", "归母", "上游", "控制", "实体", "上市主体", "ordinary")),
                ("claims", ("少数股东", "nci", "债务", "受限", "法定储备", "索取", "minority", "restricted")),
            ],
            "minimum_groups": 2,
        },
        "valuation_return_price": {
            "label": "估值、回报与价格身份",
            "groups": [
                ("method", ("估值", "epv", "nav", "sotp", "ddm", "dcf", "现金流", "模型", "价值")),
                ("return", ("回报", "xirr", "irr", "收益率", "股息率", "经济回报", "return")),
                ("price", ("当前价", "买入价", "研究价格", "每股", "期末", "卖出", "p_long", "p_xirr", "价格")),
                ("identity", ("今天", "未来", "条件", "业务价值", "市场价格", "不依赖", "身份")),
            ],
            "minimum_groups": 3,
        },
        "counter_thesis_permanent_loss": {
            "label": "反方论点与永久损失",
            "groups": [
                ("downside", ("风险", "反方", "压力", "悲观", "下行", "失败", "against", "downside")),
                ("permanent", ("永久", "不可逆", "资本毁灭", "清算", "债务失控", "牌照", "permanent")),
                ("alternative", ("替代解释", "为什么市场可能", "正方", "翻转", "证伪", "如果成立", "alternative")),
            ],
            "minimum_groups": 2,
            "required_group": "permanent",
        },
        "monitoring": {
            "label": "监控与触发条件",
            "groups": [
                ("track", ("跟踪", "监控", "观察", "以后", "后续", "monitor", "track")),
                ("metric", ("指标", "利润", "现金", "回款", "出租率", "毛利率", "订单", "metric")),
                ("trigger", ("阈值", "触发", "升级", "降级", "终止", "如果", "低于", "高于", "trigger")),
            ],
            "minimum_groups": 2,
        },
        "data_boundaries": {
            "label": "数据边界与未知项",
            "groups": [
                ("evidence", ("来源", "年报", "公告", "披露", "证据", "原文", "source", "evidence")),
                ("limits", ("未知", "未披露", "证据不足", "缺口", "不确定", "无法", "区间", "unknown", "limited")),
                ("assumption", ("假设", "判断", "估计", "敏感性", "条件", "保守", "assumption", "sensitivity")),
            ],
            "minimum_groups": 2,
            "required_group": "limits",
        },
    }
    if analysis_purpose == "COMPANY_JUDGMENT_ONLY":
        # A company-judgment release freezes causal mechanisms and their
        # observable settlement.  It must not borrow the shareholder-access,
        # valuation, return or market-price questions from an investment
        # report merely to make the prose look complete.
        specs.pop("ordinary_share_cash_access", None)
        specs.pop("valuation_return_price", None)
        specs["rival_mechanisms"] = {
            "label": "竞争性机制与反方解释",
            "groups": [
                ("primary", ("主路径", "主要机制", "核心解释", "primary", "mechanism")),
                ("rival", ("竞争解释", "替代解释", "反方", "相反", "rival", "alternative")),
                ("split", ("区分", "判别", "不同", "分歧", "证伪", "discriminat", "falsif")),
            ],
            "minimum_groups": 2,
            "required_group": "rival",
        }
        specs["forward_settlement"] = {
            "label": "前瞻信号与结算",
            "groups": [
                ("forward", ("未来", "前瞻", "之后", "horizon", "forward")),
                ("signal", ("信号", "指标", "阈值", "观察", "metric", "signal", "threshold")),
                ("settle", ("结算", "验证", "到期", "确认", "settle", "resolve", "confirm")),
            ],
            "minimum_groups": 2,
            "required_any_groups": ["signal", "settle"],
        }
    return specs


def _group_hits(text: str, groups: list[tuple[str, tuple[str, ...]]]) -> set[str]:
    lowered = text.lower()
    return {name for name, cues in groups if any(cue.lower() in lowered for cue in cues)}


def _windows(paragraphs: list[str]) -> list[str]:
    """Allow a reader explanation to span adjacent prose blocks."""
    windows = list(paragraphs)
    windows.extend(
        f"{left} {right}"
        for left, right in zip(paragraphs, paragraphs[1:])
    )
    return windows


def _topic_result(
    text: str, spec: dict[str, Any], paragraphs: list[str], *, source_available: bool
) -> dict[str, Any]:
    hits: list[dict[str, Any]] = []
    for paragraph in _windows(paragraphs):
        groups = _group_hits(paragraph, spec["groups"])
        unknown = bool(_UNKNOWN_RE.search(paragraph))
        causal = bool(_CAUSAL_RE.search(paragraph))
        prose_chars = len(re.sub(r"\[[^\]]+\]", "", paragraph))
        # The paragraph must connect multiple economic cues and contain an
        # explanation or an explicit evidence boundary.  This prevents a
        # table of labels and a technical-link line from closing a topic.
        # This floor only filters source-list/link fragments.  It is not a
        # report-length target; the semantic cue and explanation tests above
        # remain the actual closure criteria.
        if len(groups) >= int(spec.get("minimum_groups", 2)) and prose_chars >= 45 and (causal or unknown or len(paragraph.split("。")) >= 2):
            hits.append({
                "groups": sorted(groups),
                "unknown": unknown,
                "source": bool(
                    _SOURCE_ANCHOR_RE.search(paragraph)
                    or _FOOTNOTE_MARKER_RE.search(paragraph)
                    or _EVIDENCE_BINDING_RE.search(paragraph)
                ),
                "preview": paragraph[:180],
            })
    required_group = spec.get("required_group")
    if required_group and hits and not any(required_group in hit["groups"] or hit["unknown"] for hit in hits):
        hits = []
    required_any = set(spec.get("required_any_groups") or [])
    if required_any and hits and not any(required_any.intersection(hit["groups"]) or hit["unknown"] for hit in hits):
        hits = []
    if not hits:
        return {
            "status": "FAIL",
            "label": spec["label"],
            "reason": "missing_reader_explanation",
            "matched_groups": [],
            "reader_explanation": False,
            "source_anchor_nearby": False,
        }
    if not any(hit["source"] or hit["unknown"] for hit in hits):
        return {
            "status": "FAIL",
            "label": spec["label"],
            "reason": "reader_source_anchor_missing_for_topic",
            "matched_groups": sorted({group for hit in hits for group in hit["groups"]}),
            "reader_explanation": True,
            "source_anchor_nearby": False,
            "evidence": hits[:3],
        }
    return {
        "status": "PASS",
        "label": spec["label"],
        "reason": "reader_explanation_present",
        "matched_groups": sorted({group for hit in hits for group in hit["groups"]}),
        "reader_explanation": True,
        "source_anchor_nearby": any(hit["source"] for hit in hits) or source_available,
        "evidence": hits[:3],
    }


def _identity_findings(text: str, output_dir: str | Path | None) -> list[str]:
    if output_dir is None:
        return []
    output = Path(output_dir)
    manifest = _load(output / "decision_manifest.json")
    ledger = _load(output / "decision_ledger.json")
    decision = ledger.get("decision") or {}
    label = str(manifest.get("display_label") or decision.get("display_label") or "").strip()
    findings: list[str] = []
    if label and len(_normalise(label)) >= 2 and _normalise(label) not in _normalise(text):
        findings.append("decision_display_label_missing_from_reader")
    unified = str(manifest.get("unified_decision") or decision.get("unified_decision") or "").strip()
    if unified and len(_normalise(unified)) >= 3 and _normalise(unified) not in _normalise(text):
        findings.append("unified_decision_missing_from_reader")
    return findings


def _internal_control_findings(text: str) -> list[str]:
    """Detect machine control identities in the reader body, without broad prose keywords."""
    findings = [
        "reader_internal_control_leak:" + category
        for category, pattern in _INTERNAL_CONTROL_TOKEN_PATTERNS
        if pattern.search(text or "")
    ]
    if _INTERNAL_CONTROL_PANEL_RE.search(text or "") or _INTERNAL_CONTROL_TABLE_RE.search(text or ""):
        findings.append("reader_internal_control_leak:workflow_panel")
    return findings


def _analysis_purpose(output_dir: str | Path | None, declared: str | None) -> str:
    """Resolve purpose without making a missing legacy contract invalid."""
    if declared:
        purpose = str(declared)
    elif output_dir is not None:
        purpose = str(_load(Path(output_dir) / "analysis_contract.json").get(
            "analysis_purpose"
        ) or "INVESTMENT_DECISION")
    else:
        purpose = "INVESTMENT_DECISION"
    return purpose if purpose in ANALYSIS_PURPOSES else "INVALID"


def evaluate_reader_coverage(
    report_text: str,
    output_dir: str | Path | None = None,
    *,
    archetype: str | None = None,
    analysis_purpose: str | None = None,
    enforced: bool = True,
    persist: bool = False,
) -> dict[str, Any]:
    """Evaluate reader coverage without using byte counts, hashes or grades."""
    if not enforced:
        result = {"schema_version": SCHEMA_VERSION, "status": "SKIP", "reason": "not_enforced"}
        return result
    if not str(report_text or '').strip():
        result = {"schema_version": SCHEMA_VERSION, "status": "BLOCKED", "blocking_findings": ["reader_report_empty"]}
        return result
    purpose = _analysis_purpose(output_dir, analysis_purpose)
    if purpose == "INVALID":
        return {
            "schema_version": SCHEMA_VERSION,
            "status": "BLOCKED",
            "analysis_purpose": purpose,
            "blocking_findings": ["reader_analysis_purpose_invalid"],
        }
    archetype_id, source = _context(output_dir, archetype)
    paragraphs = _paragraphs(report_text)
    source_count = len(_SOURCE_ANCHOR_RE.findall(report_text)) + len(_FOOTNOTE_RE.findall(report_text))
    binding_count = len(_EVIDENCE_BINDING_RE.findall(report_text))
    source_available = bool(source_count or binding_count)
    topics = {
        name: _topic_result(report_text, spec, paragraphs, source_available=source_available)
        for name, spec in _topic_specs(
            archetype_id, analysis_purpose=purpose
        ).items()
    }
    blocking = [
        f"topic_missing:{name}" for name, item in topics.items() if item.get("status") != "PASS"
    ]
    if not source_available:
        blocking.append("reader_source_anchor_missing")
    if purpose == "INVESTMENT_DECISION":
        blocking.extend(_identity_findings(report_text, output_dir))
    blocking.extend(_internal_control_findings(report_text))
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "BLOCKED" if blocking else "PASS",
        "analysis_purpose": purpose,
        "archetype": archetype_id,
        "archetype_source": source,
        "paragraph_count": len(paragraphs),
        "source_anchor_count": source_count,
        "evidence_binding_count": binding_count,
        "topics": topics,
        "blocking_findings": list(dict.fromkeys(blocking)),
        "warnings": [],
        "policy": "semantic_topics_with_explicit_unknown; no length_or_hash_gate",
    }
    if persist and output_dir is not None:
        path = Path(output_dir) / "reader_coverage_validation.json"
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        result["path"] = str(path)
    return result


def reader_coverage_prompt(
    *,
    archetype: str = "general_operating",
    analysis_purpose: str = "INVESTMENT_DECISION",
) -> str:
    """Prompt hook used by report synthesis and repair contexts."""
    labels = ", ".join(
        spec["label"]
        for spec in _topic_specs(
            archetype, analysis_purpose=analysis_purpose
        ).values()
    )
    scope = (
        "公司判断稿只解释经营机制、竞争解释、前瞻信号与证据边界；不得写证券价格、估值、回报、仓位或交易动作。"
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else
        ""
    )
    implication = (
        "公司判断含义"
        if analysis_purpose == "COMPANY_JUDGMENT_ONLY" else "投资含义"
    )
    return (
        "读者层覆盖契约：在技术附录或ledger之外，正文必须用普通语言解释 "
        f"{labels}。每一项都要连接事实、机制与{implication}；证据不足时明确写UNKNOWN/未披露及其影响。"
        "不得用附录链接、来源清单、字段名或数字表格代替解释；内部对象ID、工作流状态码和"
        "ledger/gate/status面板只能留在结构化工件或技术附录。" + scope
    )


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="Validate reader-facing Golden report coverage")
    parser.add_argument("report")
    parser.add_argument("--output-dir")
    args = parser.parse_args()
    text = Path(args.report).read_text(encoding="utf-8")
    print(json.dumps(evaluate_reader_coverage(text, args.output_dir), ensure_ascii=False, indent=2))
