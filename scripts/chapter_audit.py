#!/usr/bin/env python3
"""chapter_audit.py — V10：章节审计协调器。

对单个章节执行审计循环：
1. 运行可编程检查（P 类规则，无需 LLM）
2. 若发现 warn/error，生成修复计划
3. 返回 AuditResult

从 Dayu 的 chapter_audit_coordinator.py 裁剪而来：
- 跳过 evidence confirmation 步骤（Phase 4 再完善）
- 跳过 facet filtering
- 审计结论简化为 pass/patch/regenerate/fail 四态
"""

from __future__ import annotations

from typing import Any

from models import (
    AuditResult,
    AuditVerdict,
    ChapterResult,
    ChapterStatus,
    ChapterTask,
    Violation,
)
from audit_rules import run_programmatic_audit
from scene_config import SceneConfig, get_scene_config


def audit_chapter(
    result: ChapterResult,
    scene: SceneConfig | None = None,
) -> AuditResult:
    """审计单个章节。

    先运行可编程规则，若通过则直接返回 PASS。
    若发现问题，返回 PATCH/REGENERATE 结论及修复计划。

    Args:
        result: 章节写作结果（含内容和任务定义）。
        scene: 场景配置。

    Returns:
        AuditResult 对象。
    """
    if scene is None:
        scene = get_scene_config("audit")

    content = result.content
    task = result.task

    # Step 1: 可编程检查
    prog_result = run_programmatic_audit(content, task)

    if prog_result.verdict == AuditVerdict.PASS:
        # V10: P 类审计通过后附加证据覆盖率检查
        try:
            from evidence_citation import EvidenceRegistry, validate_evidence_coverage
            registry = EvidenceRegistry()
            cov = validate_evidence_coverage(content, registry)
            if cov["status"] == "FAIL":
                prog_result = AuditResult(
                    verdict=AuditVerdict.PATCH,
                    violations=list(prog_result.violations) + [Violation(
                        rule_code="E1", severity="warn",
                        description=f"证据覆盖率过低: {cov['coverage_ratio']:.0%} ({cov['evidence_anchors']}锚点/{cov['number_claims']}数字声明)",
                    )],
                )
                result.status = ChapterStatus.REPAIRING
                return prog_result
        except ImportError:
            pass
        result.status = ChapterStatus.PASSED
        return prog_result

    # Step 2: 生成修复计划（format violations into repair plan）
    repair_plan = _build_repair_plan(prog_result, content)

    # Step 3: 如果可编程检查要求 regenerate，直接返回
    if prog_result.verdict == AuditVerdict.REGENERATE:
        return AuditResult(
            verdict=AuditVerdict.REGENERATE,
            violations=prog_result.violations,
            repair_plan=repair_plan,
        )

    # Step 4: 返回 patch 结论
    return AuditResult(
        verdict=AuditVerdict.PATCH,
        violations=prog_result.violations,
        repair_plan=repair_plan,
    )


def audit_all_chapters(
    results: dict[int, ChapterResult],
    max_retries: int = 2,
) -> dict[int, ChapterResult]:
    """审计所有章节（含修复循环）。

    Args:
        results: 章节序号到 ChapterResult 的映射。
        max_retries: 每章最大修复重试次数。

    Returns:
        更新后的 results 映射。
    """
    for idx, result in list(results.items()):
        if result.status in (ChapterStatus.PASSED, ChapterStatus.SKIPPED, ChapterStatus.FAILED):
            continue

        retry = 0
        while retry <= max_retries:
            audit_result = audit_chapter(result)

            if audit_result.verdict == AuditVerdict.PASS:
                result.status = ChapterStatus.PASSED
                result.audit_results.append(audit_result)
                break

            if audit_result.verdict == AuditVerdict.FAIL:
                result.status = ChapterStatus.FAILED
                result.error = "审计不可修复"
                result.audit_results.append(audit_result)
                break

            # 需要修复
            result.status = ChapterStatus.REPAIRING
            result.audit_results.append(audit_result)

            # 尝试修复
            from repair_executor import apply_repair
            repaired = apply_repair(
                result.content,
                audit_result,
                result.task,
            )
            result.content = repaired
            retry += 1

        if result.status not in (ChapterStatus.PASSED, ChapterStatus.FAILED):
            result.status = ChapterStatus.FAILED
            result.error = f"审计/修复循环超过最大重试次数 {max_retries}"

    return results


def _build_repair_plan(audit_result: AuditResult, content: str) -> str:
    """基于审计违规项构建修复计划文本。

    Args:
        audit_result: 审计结果。
        content: 章节原始内容。

    Returns:
        修复计划描述文本。
    """
    if not audit_result.violations:
        return "无需修复"

    lines = ["# 修复计划\n"]
    lines.append(f"## 审计结论: {audit_result.verdict.value}\n")

    # 按规则代码分组
    by_code: dict[str, list[Violation]] = {}
    for v in audit_result.violations:
        by_code.setdefault(v.rule_code, []).append(v)

    for code, violations in sorted(by_code.items()):
        lines.append(f"### {code} ({len(violations)} 项)\n")
        for v in violations:
            lines.append(f"- [{v.severity}] {v.description}")
            if v.location:
                lines.append(f"  位置: {v.location}")
        lines.append("")

    if audit_result.verdict == AuditVerdict.PATCH:
        lines.append("## 修复策略: patch")
        lines.append("请针对上述每项违规，在原内容中做最小化修改：")
        lines.append("- S1 违规：将 [/?] 替换为具体数值或 ⚠️ 数据不可用")
        lines.append("- E1 违规：在数字声明后添加 [source: 文件名] 锚点")
        lines.append("- C1 违规：补充缺失的必需内容")
        lines.append("- S2 违规：统一不一致的数值")
        lines.append("- 保持其余内容完全不变")
    elif audit_result.verdict == AuditVerdict.REGENERATE:
        lines.append("## 修复策略: regenerate")
        lines.append("问题过多或过于严重，请完整重写本章。重写时注意：")
        lines.append("- 严格遵守写作合同中的所有约束")
        lines.append("- 每个数据声明附带 [source: X] 锚点")
        lines.append("- 不留任何占位符")

    return "\n".join(lines)
