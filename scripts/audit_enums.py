"""V12 审计枚举与固定集合 — 从 Dayu enums.py 移植。

去掉 WriteSceneName/WritePhaseName（Dayu 写作流水线概念），
保留核心审计规则码、分类、修复策略、证据复核状态。
"""

from __future__ import annotations

from enum import StrEnum


class RepairStrategy(StrEnum):
    """章节重写策略。"""
    PATCH = "patch"
    REGENERATE = "regenerate"
    NONE = "none"


class RepairResolutionMode(StrEnum):
    """修复合同中单条违规的处置模式。"""
    DELETE_CLAIM = "delete_claim"
    REWRITE_WITH_EXISTING_EVIDENCE = "rewrite_with_existing_evidence"
    ANCHOR_FIX_ONLY = "anchor_fix_only"


class AuditCategory(StrEnum):
    """审计分类。"""
    OK = "ok"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    CONTENT_VIOLATION = "content_violation"
    STYLE_VIOLATION = "style_violation"


class AuditRuleCode(StrEnum):
    """审计规则编号 — 完整 13 条规则。"""
    UNKNOWN = "unknown"
    P1 = "P1"  # 结构不匹配
    P2 = "P2"  # 内容过短
    P3 = "P3"  # 缺少证据小节
    E1 = "E1"  # 关键断言缺证据锚点
    E2 = "E2"  # 证据模糊或无法追溯
    E3 = "E3"  # 证据完全缺失
    C1 = "C1"  # 合同禁止内容/逻辑事实错误
    C2 = "C2"  # 低优先级内容问题
    S1 = "S1"  # audit 输出非法 JSON
    S2 = "S2"  # 语气/措辞不当
    S3 = "S3"  # 不符合合同或规则约束
    S4 = "S4"  # 低优先级风格
    S5 = "S5"  # 低优先级格式
    S6 = "S6"  # 低优先级
    S7 = "S7"  # 证据锚点过粗


class RepairTargetKind(StrEnum):
    """repair patch 的目标粒度。"""
    SUBSTRING = "substring"
    LINE = "line"
    BULLET = "bullet"
    PARAGRAPH = "paragraph"


class EvidenceConfirmationStatus(StrEnum):
    """证据复核结论状态。"""
    CONFIRMED_MISSING = "confirmed_missing"
    SUPPORTED = "supported"
    SUPPORTED_BUT_ANCHOR_TOO_COARSE = "supported_but_anchor_too_coarse"
    SUPPORTED_ELSEWHERE_IN_SAME_FILING = "supported_elsewhere_in_same_filing"


# ---- 规则集合 ----

EVIDENCE_AUDIT_RULE_CODES: tuple[AuditRuleCode, ...] = (
    AuditRuleCode.E1, AuditRuleCode.E2, AuditRuleCode.E3,
)

CONTENT_AUDIT_RULE_CODES: tuple[AuditRuleCode, ...] = (
    AuditRuleCode.C1, AuditRuleCode.C2,
)

STYLE_AUDIT_RULE_CODES: tuple[AuditRuleCode, ...] = (
    AuditRuleCode.S1, AuditRuleCode.S2, AuditRuleCode.S3,
    AuditRuleCode.S4, AuditRuleCode.S5, AuditRuleCode.S6, AuditRuleCode.S7,
)

LOW_PRIORITY_AUDIT_RULE_CODES = frozenset({
    AuditRuleCode.C2, AuditRuleCode.S4, AuditRuleCode.S5,
    AuditRuleCode.S6, AuditRuleCode.S7,
})

BLOCKING_EVIDENCE_AUDIT_RULE_CODES = frozenset(EVIDENCE_AUDIT_RULE_CODES)
BLOCKING_CONTENT_AUDIT_RULE_CODES = frozenset({AuditRuleCode.C1})
REGENERATE_EVIDENCE_AUDIT_RULE_CODES = frozenset({AuditRuleCode.E3})

STRUCTURAL_REPAIR_AUDIT_RULE_CODES = frozenset({
    AuditRuleCode.P1, AuditRuleCode.P2, AuditRuleCode.P3,
})

CONFIRMABLE_EVIDENCE_AUDIT_RULE_CODES = frozenset({
    AuditRuleCode.E1, AuditRuleCode.E2,
})


# ---- 规范化函数 ----

def normalize_repair_resolution_mode(raw_value: object) -> RepairResolutionMode:
    try:
        return RepairResolutionMode(
            str(raw_value or RepairResolutionMode.REWRITE_WITH_EXISTING_EVIDENCE).strip()
            or RepairResolutionMode.REWRITE_WITH_EXISTING_EVIDENCE
        )
    except ValueError:
        return RepairResolutionMode.REWRITE_WITH_EXISTING_EVIDENCE


def normalize_repair_strategy(raw_value: object) -> RepairStrategy:
    try:
        return RepairStrategy(str(raw_value or RepairStrategy.PATCH).strip() or RepairStrategy.PATCH)
    except ValueError:
        return RepairStrategy.PATCH


def normalize_audit_category(raw_value: object) -> AuditCategory:
    try:
        return AuditCategory(str(raw_value or AuditCategory.STYLE_VIOLATION).strip() or AuditCategory.STYLE_VIOLATION)
    except ValueError:
        return AuditCategory.STYLE_VIOLATION


def normalize_audit_rule_code(raw_value: object) -> AuditRuleCode:
    normalized = str(raw_value or "").strip().upper()
    if not normalized:
        return AuditRuleCode.UNKNOWN
    try:
        return AuditRuleCode(normalized)
    except ValueError:
        return AuditRuleCode.UNKNOWN


def normalize_repair_target_kind(raw_value: object) -> RepairTargetKind:
    try:
        return RepairTargetKind(str(raw_value or RepairTargetKind.SUBSTRING).strip() or RepairTargetKind.SUBSTRING)
    except ValueError:
        return RepairTargetKind.SUBSTRING


def normalize_evidence_confirmation_status(raw_value: object) -> EvidenceConfirmationStatus:
    return EvidenceConfirmationStatus(str(raw_value or "").strip())


# ---- Dayu 兼容：阶段名和辅助函数 ----


class WritePhaseName(StrEnum):
    """写作流水线固定 phase 名称。"""
    INITIAL = "initial"


def is_initial_write_phase(phase: str) -> bool:
    """判断当前 phase 是否为初始写作阶段。"""
    return phase == WritePhaseName.INITIAL


def build_rewrite_phase_name(*, strategy: RepairStrategy, retry_count: int) -> str:
    """根据重写策略生成动态 phase 名称。"""
    if strategy == RepairStrategy.REGENERATE:
        return f"regenerate_{retry_count}"
    return f"repair_{retry_count}"


def build_audit_scope_rules_payload() -> dict[str, list[str]]:
    """构建 audit prompt 使用的规则范围摘要。"""
    return {
        "evidence_rules": [r.value for r in EVIDENCE_AUDIT_RULE_CODES],
        "content_rules": [r.value for r in CONTENT_AUDIT_RULE_CODES],
        "style_rules": [r.value for r in STYLE_AUDIT_RULE_CODES],
    }
