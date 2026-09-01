#!/usr/bin/env python3
"""models.py — V12：写管线领域模型。

定义分章节写作管线使用的数据类。
V12 扩展：从 Dayu 移植 CompanyFacetProfile、PreferredLens，扩展 ChapterContract/ItemRule 支持 facets_any。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChapterStatus(str, Enum):
    """章节执行状态。"""
    PENDING = "pending"
    WRITING = "writing"
    AUDITING = "auditing"
    REPAIRING = "repairing"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AuditVerdict(str, Enum):
    """审计结论。"""
    PASS = "pass"
    PATCH = "patch"           # 需要针对性修复
    REGENERATE = "regenerate"  # 需要完整重写
    FAIL = "fail"              # 不可修复


class RepairStrategy(str, Enum):
    """修复策略。"""
    PATCH = "patch"
    REGENERATE = "regenerate"


# ---------------------------------------------------------------------------
# V12 新增：公司 Facet 归因
# ---------------------------------------------------------------------------


@dataclass
class CompanyFacetProfile:
    """公司级视角标签归因结果。

    从 Dayu models.py 移植，去除了 Dayu 特定依赖。

    Args:
        primary_facets: 主业务类型标签（最多3个），从36种商业模式候选中选取。
        cross_cutting_facets: 横切约束标签（最多3个），从25种约束候选中选取。
        confidence_notes: 简短归因说明。
    """

    primary_facets: list[str] = field(default_factory=list)
    cross_cutting_facets: list[str] = field(default_factory=list)
    confidence_notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "primary_facets": list(self.primary_facets),
            "cross_cutting_facets": list(self.cross_cutting_facets),
            "confidence_notes": self.confidence_notes,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CompanyFacetProfile":
        """从字典恢复 facet 归因结果。

        兼容 Dayu 的 business_model_tags/constraint_tags/judgement_notes 旧字段名。
        """
        primary_facets = list(raw.get("primary_facets", raw.get("business_model_tags", [])))
        cross_cutting_facets = list(raw.get("cross_cutting_facets", raw.get("constraint_tags", [])))
        confidence_notes = str(raw.get("confidence_notes", raw.get("judgement_notes", ""))).strip()
        if any(not isinstance(item, str) for item in primary_facets):
            raise TypeError("company_facets.primary_facets 必须为字符串列表")
        if any(not isinstance(item, str) for item in cross_cutting_facets):
            raise TypeError("company_facets.cross_cutting_facets 必须为字符串列表")
        return cls(
            primary_facets=[item.strip() for item in primary_facets if item.strip()],
            cross_cutting_facets=[item.strip() for item in cross_cutting_facets if item.strip()],
            confidence_notes=confidence_notes,
        )

    def all_facets(self) -> list[str]:
        """返回按顺序合并后的全部 facet（去重）。"""
        merged: list[str] = []
        for item in [*self.primary_facets, *self.cross_cutting_facets]:
            if item not in merged:
                merged.append(item)
        return merged


@dataclass
class PreferredLens:
    """章节优先认知口径。

    从 Dayu chapter_contracts.py 移植。

    Args:
        lens: 该条认知口径的具体内容。
        priority: 重要性，支持 ``core`` 与 ``supporting``。
        facets_any: 命中任一 facet 即可保留的 facet 条件列表。
    """

    lens: str
    priority: str = "core"
    facets_any: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "lens": self.lens,
            "priority": self.priority,
            "facets_any": list(self.facets_any),
        }


# ---------------------------------------------------------------------------
# 审计模型
# ---------------------------------------------------------------------------


@dataclass
class Violation:
    """审计违规项。

    Args:
        rule_code: 规则代码（E1/E2/C1/C2/S1/S2）。
        severity: 严重程度（error/warn）。
        description: 违规描述。
        location: 违规位置（章节内行号或段落引用）。
    """

    rule_code: str
    severity: str  # "error" | "warn"
    description: str
    location: str = ""


@dataclass
class AuditResult:
    """单次审计结果。

    Args:
        verdict: 审计结论。
        violations: 违规项列表。
        repair_plan: 若需要修复，提供修复计划文本。
    """

    verdict: AuditVerdict
    violations: list[Violation] = field(default_factory=list)
    repair_plan: str = ""


@dataclass
class ChapterTask:
    """章节写作任务定义。

    Args:
        index: 章节序号（从 1 开始）。
        title: 章节标题。
        skeleton: 章节骨架（模板去注释后的正文）。
        chapter_goal: 本章写作目标。
        chapter_contract: 章节写作合同。
        item_rules: 条件型写作规则列表。
        depends_on: 依赖的章节序号列表（这些章节必须先完成）。
        is_special: 是否为特殊章节（Overview/Decision/SourceList）。
        write_last: 是否在所有其他章节完成后才写。
        part_label: 章节所属分区的标签（如 "Part A: 定性深度分析"），可选。
    """

    index: int
    title: str
    skeleton: str
    chapter_goal: str = ""
    chapter_contract: "ChapterContract" = field(default_factory=lambda: ChapterContract.empty())
    item_rules: list["ItemRule"] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)
    is_special: bool = False
    write_last: bool = False
    part_label: str = ""


# ---------------------------------------------------------------------------
# 章节合同与规则（V12 扩展：preferred_lens + facets_any）
# ---------------------------------------------------------------------------


@dataclass
class ChapterContract:
    """章节级写作合同。

    V12 扩展：添加 preferred_lens 字段，支持 Dayu 的条件化分析透镜。

    Args:
        narrative_mode: 本章叙事组织方式（如"表格填充""结构化分析""简洁叙事"）。
        must_answer: 本章必须回答的问题列表。
        must_not_cover: 本章禁止展开的问题列表。
        required_output_items: 本章最小输出清单。
        preferred_lens: 本章优先采用的认知口径列表（V12 新增）。
    """

    narrative_mode: str = ""
    must_answer: list[str] = field(default_factory=list)
    must_not_cover: list[str] = field(default_factory=list)
    required_output_items: list[str] = field(default_factory=list)
    preferred_lens: list[PreferredLens] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "ChapterContract":
        """构造空合同。"""
        return cls()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典，供 prompt 构建使用。"""
        return {
            "narrative_mode": self.narrative_mode,
            "must_answer": list(self.must_answer),
            "must_not_cover": list(self.must_not_cover),
            "required_output_items": list(self.required_output_items),
            "preferred_lens": [item.to_dict() for item in self.preferred_lens],
        }


@dataclass
class ItemRule:
    """条目级条件写作规则。

    V12 扩展：添加 facets_any 字段，支持按公司 facet 条件触发。

    Args:
        mode: 规则模式（conditional / optional）。
        target_heading: 规则绑定的目标标题。
        item: 需要在目标标题下按条件补充的输出项名称。
        when: 触发条件或适用条件说明。
        facets_any: 命中任一 facet 即可保留的 facet 条件列表（V12 新增）。
    """

    mode: str
    target_heading: str
    item: str
    when: str
    facets_any: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为字典。"""
        return {
            "mode": self.mode,
            "target_heading": self.target_heading,
            "item": self.item,
            "when": self.when,
            "facets_any": list(self.facets_any),
        }


@dataclass
class ChapterResult:
    """章节写作结果。

    Args:
        task: 关联的 ChapterTask。
        content: 章节 Markdown 内容。
        status: 最终状态。
        retry_count: 重试次数。
        audit_results: 审计历史（每次审计的结果）。
        evidence_items: 提取的证据锚点列表。
        error: 若失败，记录错误信息。
    """

    task: ChapterTask
    content: str = ""
    status: ChapterStatus = ChapterStatus.PENDING
    retry_count: int = 0
    audit_results: list[AuditResult] = field(default_factory=list)
    evidence_items: list[str] = field(default_factory=list)
    error: str = ""


@dataclass
class DecisionInput:
    """决策综合的输入数据。

    Args:
        company_name: 公司名称。
        ts_code: 股票代码。
        factor_1a_summary: 因子1A摘要（快筛结果）。
        factor_1b_summary: 因子1B摘要（护城河等定性结论）。
        factor_1c_summary: 因子1C摘要（增长质量）。
        factor_2_gg: 因子2穿透回报率粗算值。
        factor_3_gg: 因子3穿透回报率精算值（基准）。
        factor_3_gg_scenarios: GG三档情景 {悲观, 基准, 乐观}。
        factor_4_ddm_v: DDM公允价。
        factor_4_current_price: 当前股价。
        factor_4_position_pct: 建议仓位百分比。
        ii: 门槛回报率 II。
        rf: 无风险利率 Rf。
        key_risks: 关键风险列表。
        rejection_status: 否决门状态。
        moat_rating: 护城河评级。
    """

    company_name: str
    ts_code: str
    factor_1a_summary: str = ""
    factor_1b_summary: str = ""
    factor_1c_summary: str = ""
    factor_2_gg: float = 0.0
    factor_3_gg: float = 0.0
    factor_3_gg_scenarios: dict[str, float] = field(default_factory=dict)
    factor_4_ddm_v: float = 0.0
    factor_4_current_price: float = 0.0
    factor_4_position_pct: float = 0.0
    ii: float = 0.0
    rf: float = 0.0
    key_risks: list[str] = field(default_factory=list)
    rejection_status: str = ""
    moat_rating: str = ""


@dataclass
class DecisionOutput:
    """决策综合的输出。

    Args:
        verdict: 最终决策（Continue/Hold/Abandon）。
        confidence: 置信度（high/medium/low）。
        rationale: 核心依据列表。
        assumptions: 关键假设及脆弱点。
        triggers: 监控触发器（降级条件）。
        exit_conditions: 退出条件（清仓信号）。
    """

    verdict: str  # "Continue" | "Hold" | "Abandon"
    confidence: str  # "high" | "medium" | "low"
    rationale: list[str] = field(default_factory=list)
    assumptions: list[dict[str, str]] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    exit_conditions: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# V12 Dayu 审计兼容模型（stubs for repair_executor / evidence_rewriter）
# ---------------------------------------------------------------------------


@dataclass
class RepairContract:
    """Dayu 修复合同。"""
    strategy: str = "patch"
    category: str = ""
    violations_count: int = 0
    repair_actions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class EvidenceAnchorFix:
    """证据锚点修正条目。"""
    original_line: str = ""
    fixed_line: str = ""
    fix_type: str = ""


@dataclass
class EvidenceConfirmationEntry:
    """单条证据复核条目。"""
    slot_id: str = ""
    status: str = ""
    original_claim: str = ""
    confirmed_evidence: str = ""


@dataclass
class EvidenceConfirmationResult:
    """证据复核结果。"""
    entries: list[EvidenceConfirmationEntry] = field(default_factory=list)
    summary: str = ""


@dataclass
class MissingEvidenceSlot:
    """缺失证据槽位。"""
    slot_id: str = ""
    claim: str = ""
    required_source_type: str = ""


@dataclass
class OffendingClaimSpan:
    """违规断言片段。"""
    excerpt: str = ""
    location: str = ""
    rule_code: str = ""


@dataclass
class RemediationAction:
    """修复动作。"""
    action: str = ""
    target: str = ""
    replacement: str = ""


@dataclass
class AuditDecision:
    """审计决策结果。"""
    passed: bool = True
    category: str = "ok"
    violations: list[Violation] = field(default_factory=list)
    repair_strategy: str = "none"
    repair_contract: Any | None = None
    confirm_result: Any | None = None


@dataclass
class WriteRunConfig:
    """Dayu 写作运行配置（stub）。"""
    write_max_retries: int = 2
    output_dir: str = ""
    template_path: str = ""


# ---- ArtifactStore stubs ----

@dataclass
class RunManifest:
    """Dayu 运行清单（stub）。"""
    run_id: str = ""
    ticker: str = ""
    template_signature: str = ""
    chapter_results: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceEntry:
    """Dayu 来源条目（stub）。"""
    source: str = ""
    category: str = ""
    date: str = ""
