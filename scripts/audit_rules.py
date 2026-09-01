#!/usr/bin/env python3
"""audit_rules.py — V12：从 Dayu 移植的完整审计系统。

程序化审计：结构比对与空壳正文；证据支持由 claim-evidence 合同负责。
审计决策逻辑：verdict、repair strategy — 来自 Dayu audit_rules.py。
V13 增强：P2 使用不受 Markdown 排版影响的实质深度契约。

不包含 LLM 审计（E1-E3/C1-C2/S1-S7）—— Agent 自己就是 LLM，在写章节时会自行判断质量。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from scripts.audit_enums import (
    AuditCategory,
    AuditRuleCode,
    RepairStrategy,
    STRUCTURAL_REPAIR_AUDIT_RULE_CODES,
)

MODULE = "APP.WRITE_PIPELINE"  # Dayu 兼容


# ---- Dayu 兼容 dataclass stubs（供 repair_executor 使用）----

@dataclass(slots=True)
class RepairPatchApplyRecord:
    """单个 repair patch 的应用结果。"""
    patch_index: int = 0
    target_excerpt: str = ""
    target_kind: str = ""
    target_section_heading: str = ""
    occurrence_index: int | None = None
    matched_count: int = 0
    status: str = ""
    skip_reason: str = ""


@dataclass(slots=True)
class RepairPlanApplyResult:
    """repair plan 整体应用结果。"""
    patched_markdown: str = ""
    total_patches: int = 0
    applied_count: int = 0
    skipped_count: int = 0
    all_failed: bool = False
    error_message: str = ""
    patch_results: list[RepairPatchApplyRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "patched_markdown": self.patched_markdown,
            "total_patches": self.total_patches,
            "applied_count": self.applied_count,
            "skipped_count": self.skipped_count,
            "all_failed": self.all_failed,
            "error_message": self.error_message,
        }


# ---- 异常类----

class RepairOutputError(RuntimeError):
    """repair 输出异常。"""
    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


class EmptyOutputError(RuntimeError):
    """空输出异常。"""
    def __init__(self, message: str, *, raw_output: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output


class ConfirmOutputError(RuntimeError):
    """confirm 输出异常。"""
    def __init__(self, message: str, *, raw_output: str = "", parse_error: str = "") -> None:
        super().__init__(message)
        self.raw_output = raw_output
        self.parse_error = parse_error


# ---- LLM 审计 stub 函数（供 chapter_audit_coordinator 调用）----
# Turtle 的 Agent 自己就是 LLM，这些 LLM 审计步骤由 Agent 内部完成。
# 这里提供空实现以兼容 Dayu 的导入链。


def _collect_confirmable_evidence_violations(audit_decision: Any) -> list[Any]:
    """收集可确认的证据违规（stub）。"""
    return []


def _drop_resolved_supported_anchor_violations(audit_decision: Any) -> None:
    """丢弃已解决的锚点违规（stub）。"""
    pass


def _merge_confirmed_evidence_results(audit_decision: Any, confirm_result: Any) -> None:
    """合并证据确认结果（stub）。"""
    pass


def _rebuild_anchor_followup_audit_decision(audit_decision: Any) -> None:
    """重建锚点后续审计决策（stub）。"""
    pass


def _log_chapter_audit_start(chapter_index: int) -> None:
    """审计开始日志（stub）。"""
    pass


def _log_chapter_audit_result(chapter_index: int, audit_decision: Any) -> None:
    """审计结果日志（stub）。"""
    pass


def _log_chapter_confirm_start(chapter_index: int) -> None:
    """确认开始日志（stub）。"""
    pass


def _log_chapter_confirm_result(chapter_index: int, confirm_result: Any) -> None:
    """确认结果日志（stub）。"""
    pass

try:
    from scripts.chapter_depth import (
        MIN_QUALITATIVE_LINES,
        MIN_QUANTITATIVE_LINES,
        QUANTITATIVE_CHAPTER_INDEXES,
        analyze_chapter_depth,
        depth_failure_description,
    )
except ModuleNotFoundError:
    from chapter_depth import (  # type: ignore[no-redef]
        MIN_QUALITATIVE_LINES,
        MIN_QUANTITATIVE_LINES,
        QUANTITATIVE_CHAPTER_INDEXES,
        analyze_chapter_depth,
        depth_failure_description,
    )
# ---- 兼容 Turtle models ----
class AuditVerdict(str, Enum):
    PASS = "pass"
    PATCH = "patch"
    REGENERATE = "regenerate"
    FAIL = "fail"


@dataclass
class Violation:
    rule_code: str
    severity: str  # "error" | "warn"
    description: str
    location: str = ""


@dataclass
class AuditResult:
    verdict: AuditVerdict
    violations: list[Violation] = field(default_factory=list)
    repair_plan: str = ""


# ---- Dayu 程序化审计（结构 + 非空壳）----

def _run_programmatic_audits(
    content: str,
    skeleton: str = "",
    chapter_index: int = 0,
) -> list[Violation]:
    """执行结构与非空壳审计，不用格式计数替代判断质量。"""
    violations: list[Violation] = []

    # P1: 结构比对 — 检查内容是否按骨架标题顺序覆盖
    if skeleton:
        from scripts.audit_formatting import _matches_skeleton_structure
        if not _matches_skeleton_structure(content, skeleton):
            violations.append(Violation(
                rule_code=AuditRuleCode.P1.value,
                severity="error",
                description="章节结构与骨架不匹配：缺少必须的子节标题或顺序错乱",
            ))

    # P2 only rejects an empty/template shell.  Numeric, analysis, derivation,
    # heading and citation counts are diagnostics, not publication rewards.
    depth = analyze_chapter_depth(content, chapter_index)
    if depth["status"] == "FAIL":
        violations.append(Violation(
            rule_code=AuditRuleCode.P2.value,
            severity="error",
            description="章节正文为空壳: " + depth_failure_description(depth),
        ))

    return violations


# ---- S1: 占位符检查 ----

_PLACEHOLDER_PATTERNS = [
    (r"\[\?\]", "[?] 占位符"),
    (r"\[missing\]", "[missing] 占位符"),
    (r"\[待填充\]", "[待填充] 占位符"),
    (r"【\s*占位符[^】]*】", "【占位符】残留"),
]


def _check_placeholders(content: str) -> list[Violation]:
    """S1：检查残留占位符。"""
    violations: list[Violation] = []
    lines = content.split("\n")
    for pat, label in _PLACEHOLDER_PATTERNS:
        for i, line in enumerate(lines, 1):
            if re.search(pat, line):
                violations.append(Violation(
                    rule_code="S1",
                    severity="error",
                    description=f"{label}未填充: {line.strip()[:80]}",
                    location=f"行 {i}",
                ))
    return violations


# ---- E1: 证据密度 ----

def _check_evidence_density(content: str) -> list[Violation]:
    """E1：检查 [source:] 锚点密度。"""
    violations: list[Violation] = []
    sources = re.findall(r"\[source:\s*[^\]]+\]", content)
    try:
        from scripts.chapter_depth import analyze_chapter_depth
    except ModuleNotFoundError:
        from chapter_depth import analyze_chapter_depth
    numeric_claims = analyze_chapter_depth(content, 0)["metrics"]["numeric_claim_lines"]
    # A paragraph/table-level anchor can support several related numbers.  The
    # old token/10 rule punished dense tables and encouraged citation spam.
    required_sources = max(3, (numeric_claims + 8) // 9) if numeric_claims > 20 else 0
    if required_sources and len(sources) < required_sources:
        violations.append(Violation(
            rule_code="E1",
            severity="error",
            description=(
                f"证据锚点密度过低: {len(sources)} 个 [source] 对应 "
                f"{numeric_claims} 个数字声明（至少需要 {required_sources} 个段落/表格级合引用）"
            ),
        ))
    # V12.17: 逐句 source 密度过高检测（反模式）
    # Compiler-owned canonical blocks deliberately use one source per machine
    # generated row.  They are immutable registries, not narrative prose, so
    # applying the anti-citation-spam heuristic to them makes a freshly
    # compiled report fail its next audit.  Keep their anchors in the overall
    # coverage count above, but exclude the blocks from prose-style sampling.
    density_content = re.sub(
        r"<!-- TURTLE:DECISION_BLOCK:Ch\d+:BEGIN[^>]*-->.*?"
        r"<!-- TURTLE:DECISION_BLOCK:Ch\d+:END -->",
        "", content, flags=re.DOTALL,
    )
    paragraphs = [p for p in density_content.split("\n\n") if len(p) > 100]
    for p in paragraphs[:5]:  # 抽查前5段
        src_count = len(re.findall(r"\[source:\s*[^\]]+\]", p))
        sentences = len(re.findall(r"[。；;.]", p)) + 1
        if sentences > 2 and src_count > sentences * 0.8:  # ≥80%句子有source
            violations.append(Violation(
                rule_code="E1",
                severity="error",
                description=f"逐句 [source] 密度过高: {src_count} 个 source / ~{sentences} 句。应合并为每段末尾一个合引用。",
            ))
            break  # 一个就够报警了

    return violations


# ---- C2: 禁止内容 ----

def _check_forbidden(content: str, must_not_cover: list[str]) -> list[Violation]:
    """C2：检查是否涉及禁止内容。"""
    violations: list[Violation] = []
    for item in must_not_cover:
        kw = item[:8] if len(item) >= 8 else item
        if kw in content:
            violations.append(Violation(
                rule_code="C2",
                severity="error",
                description=f"涉及禁止内容: {item}",
            ))
    return violations


# ---- S2: 数值一致性 ----

def _check_number_consistency(content: str) -> list[Violation]:
    """S2：检查关键参数（GG/II/Rf）在全文是否一致。"""
    violations: list[Violation] = []
    try:
        from scripts.report_audit import extract_data_points
    except ModuleNotFoundError:
        from report_audit import extract_data_points
    base_gg_values = {
        f"{float(point['reported_value']):.4g}"
        for point in extract_data_points(content)
        if point.get("inferred_field") == "GG"
        and "base" in set(point.get("metric_tags", []))
        and not {"fcfe", "normalized", "discounted", "scenario"}.intersection(point.get("metric_tags", []))
    }
    if len(base_gg_values) > 1:
        violations.append(Violation(
            rule_code="S2",
            severity="error",
            description=f"GG(AA/base口径) 值不一致: {base_gg_values}",
        ))
    for pat, name in [
        (r"II\s*[=＝]\s*([\d.]+)\s*%", "II"),
        (r"Rf\s*[=＝]\s*([\d.]+)\s*%", "Rf"),
    ]:
        vals = set(re.findall(pat, content))
        if len(vals) > 1:
            violations.append(Violation(
                rule_code="S2",
                severity="error",
                description=f"{name} 值不一致: {vals}",
            ))
    return violations


# ---- 审计决策逻辑（来自 Dayu _recompute_audit_result + _derive_repair_strategy）----

def run_audit(
    content: str,
    skeleton: str = "",
    chapter_index: int = 0,
    must_not_cover: list[str] | None = None,
) -> AuditResult:
    """运行完整程序化审计，返回 AuditResult。

    规则优先级：
    1. P1/P2（结构与空壳）→ error 级 → REGENERATE
    2. S1（占位符）→ error 级 → PATCH（≤3）或 REGENERATE（>3）
    3. 数量型证据密度仅作 diagnostics，不参与发布裁决
    4. C2（禁止内容）→ error 级 → PATCH/REGENERATE
    5. S2（数值一致）→ warn 级 → PATCH

    来自 Dayu 的 _recompute_audit_result + _derive_repair_strategy 逻辑。
    """
    all_violations: list[Violation] = []

    # 结构与空壳审计
    all_violations.extend(_run_programmatic_audits(content, skeleton, chapter_index))

    # S1 占位符
    all_violations.extend(_check_placeholders(content))

    # C2 禁止内容
    if must_not_cover:
        all_violations.extend(_check_forbidden(content, must_not_cover))

    # S2 数值一致性
    all_violations.extend(_check_number_consistency(content))

    # ---- 判定 verdict（Dayu 逻辑）----
    errors = [v for v in all_violations if v.severity == "error"]
    warns = [v for v in all_violations if v.severity == "warn"]

    # 检查是否有结构性违规（P1/P2/P3）
    structural_codes = {r.value for r in STRUCTURAL_REPAIR_AUDIT_RULE_CODES}
    has_structural = any(
        v.rule_code in structural_codes and v.severity == "error"
        for v in all_violations
    )

    if has_structural:
        verdict = AuditVerdict.REGENERATE
    elif errors:
        verdict = AuditVerdict.PATCH if len(errors) <= 3 else AuditVerdict.REGENERATE
    elif warns:
        verdict = AuditVerdict.PATCH
    else:
        verdict = AuditVerdict.PASS

    # 构建修复计划文本（供 Agent 参考）
    repair_plan = ""
    if verdict != AuditVerdict.PASS:
        plan_parts = []
        if has_structural:
            plan_parts.append("⚠️ 结构性违规 → 必须整章重写（REGENERATE）：")
            plan_parts.append("  - 补足一个实质正文判断；禁止为过门补数字、公式、标题或引用")
            plan_parts.append("  - 若任务提供了明确骨架，只补缺失的章节身份结构")
        if errors:
            plan_parts.append(f"  - {len(errors)} 个 error 级违规需修复")
        if warns:
            plan_parts.append(f"  - {len(warns)} 个 warn 级违规")
        repair_plan = "\n".join(plan_parts)

    return AuditResult(verdict=verdict, violations=all_violations, repair_plan=repair_plan)


# ---- 兼容旧 API（Turtle V10 chapter_audit.py / write_tools.py 调用）----

def get_programmatic_rules() -> list:
    """兼容旧 API：返回空列表（规则在 run_audit 内部执行）。"""
    return []


def run_programmatic_audit(content: str, task: Any = None) -> AuditResult:
    """兼容旧 API：委托给 run_audit。

    task 可以是 ChapterTask 对象（V12）或 dict（V10）。
    """
    skeleton = ""
    chapter_index = 0
    must_not_cover: list[str] = []

    if task is not None:
        chapter_index = getattr(task, "index", 0)
        skeleton = getattr(task, "skeleton", "")

        # 兼容 dict 和 ChapterContract 对象
        contract = getattr(task, "chapter_contract", None)
        if contract is None:
            pass
        elif hasattr(contract, "must_not_cover"):
            must_not_cover = list(contract.must_not_cover)
        elif isinstance(contract, dict):
            must_not_cover = list(contract.get("must_not_cover", []))

    return run_audit(content, skeleton=skeleton, chapter_index=chapter_index, must_not_cover=must_not_cover)
