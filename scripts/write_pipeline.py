#!/usr/bin/env python3
"""write_pipeline.py — V11 默认单Agent + V10 遗留多Agent。

Zone C 报告生成的统一入口。默认走 V11 单 Agent + 工具循环（借鉴 Dayu "LLM in the loop"），


流程：
1. 解析模板 → ChapterTask 列表
2. 加载数据上下文
3. 并行写中间章节（ThreadPoolExecutor）
4. 审计每个章节（如果启用）
5. 写决策章（在所有分析章完成后）
6. 写 Executive Summary
7. 生成来源清单
8. 组装最终报告
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Any

from models import (
    ChapterResult,
    ChapterStatus,
    ChapterTask,
    DecisionInput,
)
from template_parser import parse_template, TemplateChapter, TemplateLayout, build_report_markdown
from template_validator import validate_template as _validate_template_layout
from execution_tracker import ExecutionTracker
from evidence_citation import EvidenceRegistry, validate_evidence_coverage
from source_list_builder import build_source_list as _build_source_list_md

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS_DIR)
OUTPUT_DIR = os.path.join(ROOT, "output")
DB_PATH = os.path.join(ROOT, "stock_analysis.db")
DEFAULT_TEMPLATE = os.path.join(ROOT, "templates", "report_template_v10.md")


class WritePipelineRunner:
    """V10 分章节写作管线运行器。

    协调模板解析、数据加载、章节并行写作、决策综合和最终组装。
    """

    def __init__(
        self,
        stock_dir: str,
        ts_code: str,
        template_path: str = "",
        company_name: str = "",
        max_workers: int = 4,
        enable_audit: bool = True,
        max_retries: int = 2,
    ):
        """初始化管线运行器。

        Args:
            stock_dir: 股票输出目录。
            ts_code: 股票代码。
            template_path: 模板文件路径。
            company_name: 公司名称。
            max_workers: 并行写作的最大线程数。
            enable_audit: 是否启用审计循环（Phase 3 完成后才可用）。
            max_retries: 每章最大重试次数。
        """
        self.stock_dir = stock_dir
        self.ts_code = ts_code
        self.template_path = template_path or os.environ.get("TURTLE_TEMPLATE", DEFAULT_TEMPLATE)
        self.company_name = company_name or _get_company_name(ts_code)
        self.max_workers = max_workers
        self.enable_audit = enable_audit
        self.max_retries = max_retries

        self.layout: TemplateLayout | None = None
        self.tasks: list[ChapterTask] = []
        self.context: dict[str, Any] = {}
        self.results: dict[int, ChapterResult] = {}
        self.start_time: float = 0.0
        self.tracker = ExecutionTracker(
            ts_code=ts_code, company_name=self.company_name,
            template=self.template_path, audit_enabled=enable_audit,
            max_workers=max_workers,
        )
        self.evidence_registry = EvidenceRegistry()

    def run(self) -> str:
        """执行完整管线，返回最终报告路径。

        Returns:
            最终报告文件的路径。

        Raises:
            ValueError: 当模板解析或数据加载失败时。
            RuntimeError: 当前置检查（PDF 数量不足）失败时。
        """
        self.start_time = time.time()
        print(f"\n{'='*60}")
        print(f"🐢 V10 写管线启动")
        print(f"   标的: {self.company_name} ({self.ts_code})")
        print(f"   模板: {self.template_path}")
        print(f"   模式: 单Agent顺序写作（Dayu风格）")
        print(f"   审计: {'启用' if self.enable_audit else '关闭'}")
        print(f"{'='*60}\n")

        # Step 0: 前置检查 — PDF 年报数量
        self._check_prerequisites()

        # Step 1: 解析模板
        self._load_template()

        # Step 2: 加载数据上下文
        self._load_context()

        # Step 3: 构建章节任务
        self._build_tasks()

        # Step 4: 单Agent顺序写中间章节（Dayu: 全上下文逐章写+审）
        self._write_middle_chapters()

        # Step 5: 写决策章
        self._write_decision_chapter()

        # Step 6: 写 Executive Summary
        self._write_summary_chapter()

        # Step 7: 构建来源清单
        self._build_source_list()

        # Step 8: 组装最终报告
        report_path = self._assemble_report()

        # Step 9: V10 增强质量门禁
        try:
            from enhanced_quality_gate import enhanced_check
            with open(report_path, encoding="utf-8") as f:
                report_text = f.read()
            audit_dict = {idx: r.audit_results for idx, r in self.results.items() if r.audit_results}
            quality_result = enhanced_check(report_text, audit_dict, self.context.get("compute_bundle"))
            quality_path = os.path.join(self.stock_dir, "enhanced_quality_report.json")
            import json as _json
            with open(quality_path, "w", encoding="utf-8") as f:
                _json.dump(quality_result, f, indent=2, ensure_ascii=False)
            icon = {"PASS": "✅", "WARN": "⚠️", "BLOCKED": "❌"}.get(quality_result["status"], "❓")
            print(f"\n{icon} 增强质量: {quality_result['status']} | {quality_result['metrics']}")
        except Exception as e:
            print(f"\n⚠️ 增强质量门禁跳过: {e}")

        # Step 10: V10 执行追踪
        summary_path = self.tracker.finish(self.stock_dir)
        self.tracker.print_summary()

        # Step 11: 报告渲染（可选）
        render_format = getattr(self, '_render_format', None)
        if render_format:
            try:
                from render_report import render_to_html, render_to_pdf
                if render_format == "html":
                    render_path = render_to_html(report_path)
                elif render_format == "pdf":
                    render_path = render_to_pdf(report_path)
                print(f"🎨 渲染完成: {render_path}")
            except Exception as e:
                print(f"⚠️ 渲染跳过: {e}")

        # 输出摘要
        elapsed = time.time() - self.start_time
        passed = sum(1 for r in self.results.values() if r.status == ChapterStatus.PASSED)
        failed = sum(1 for r in self.results.values() if r.status == ChapterStatus.FAILED)
        print(f"\n{'='*60}")
        print(f"✅ 管线完成: {passed}/{len(self.tasks)} 章节通过" + (f", {failed} 失败" if failed else ""))
        print(f"   ⏱ 耗时: {elapsed:.1f}s")
        print(f"   📄 报告: {report_path}")
        print(f"   📊 追踪: {summary_path}")
        print(f"{'='*60}\n")

        return report_path

    # ------------------------------------------------------------------
    # 内部步骤
    # ------------------------------------------------------------------

    def _check_prerequisites(self):
        """前置检查：确保关键数据就绪后再进入管线。

        检查项：
        1. 年报 PDF 数量 ≥ 3（否则 Zone B 定性提取质量无法保证）
        2. compute_bundle.json 存在
        3. 至少 3 个 Zone B JSON 文件存在（mda/segments/risks/governance/audit）

        Raises:
            RuntimeError: 当前置条件不满足时。
        """
        issues: list[str] = []

        # 1. PDF 年报检查
        pdf_files = [f for f in os.listdir(self.stock_dir) if f.endswith(".pdf") and "年报" in f]
        if len(pdf_files) < 3:
            issues.append(
                f"年报 PDF 不足: {len(pdf_files)} 份（需 ≥3）。"
                f"请先运行 Phase 0.5:\n"
                f"  python3 scripts/download_report.py --hk --stock-code {self.ts_code.replace('.HK','')} "
                f"--report-type 年报 --year YYYY --save-dir {self.stock_dir} --all-years"
            )

        # 2. compute_bundle.json 检查
        cb_path = os.path.join(self.stock_dir, "compute_bundle.json")
        if not os.path.exists(cb_path):
            issues.append(
                f"compute_bundle.json 缺失。请先运行 Phase 1:\n"
                f"  python3 scripts/compute_bundle.py --code {self.ts_code} "
                f"--contract {self.stock_dir}/analysis_contract.json --output {self.stock_dir}"
            )

        # 3. Zone B JSON 检查（至少 3/5）
        zone_b_files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
        zone_b_available = [f for f in zone_b_files if os.path.exists(os.path.join(self.stock_dir, f))]
        if len(zone_b_available) < 3:
            issues.append(
                f"Zone B JSON 不足: {len(zone_b_available)}/5（mda/segments/risks/governance/audit）。"
                f"请先完成 Phase 2 定性提取。"
            )

        if issues:
            print("❌ 前置检查失败:")
            for i, issue in enumerate(issues, 1):
                print(f"  {i}. {issue}")
            raise RuntimeError(f"前置条件不满足 ({len(issues)} 项)。请完成上述 Phase 后再运行 Zone C。")

        print(f"✅ 前置检查通过: {len(pdf_files)} 份年报 PDF, {len(zone_b_available)}/5 Zone B JSON, compute_bundle 就绪")

    def _load_template(self):
        """加载并解析报告模板。"""
        if not os.path.exists(self.template_path):
            raise FileNotFoundError(f"模板不存在: {self.template_path}")
        with open(self.template_path, encoding="utf-8") as f:
            md = f.read()
        self.layout = parse_template(md)
        # V10: 模板验证（有问题直接阻断）
        template_issues = _validate_template_layout(self.layout)
        if template_issues:
            for issue in template_issues:
                print(f"  ❌ 模板问题: {issue}")
            raise RuntimeError(f"模板验证失败 ({len(template_issues)} 项问题)")
        print(f"📋 模板解析+验证: {len(self.layout.chapters)} 个章节")

    def _load_context(self):
        """加载所有可用数据文件到上下文字典。"""
        # 加载所有 Zone A/B/J JSON 文件
        json_files = [
            "analysis_contract.json", "compute_bundle.json", "compute_bundle_precise.json",
            "financial_trends.json", "industry_context.json",
            "mda.json", "segments.json", "risks.json", "governance.json", "audit.json",
            "moat_assessment.json", "capex_classification.json",
            "earnings_quality.json", "data_discount.json",
        ]
        context: dict[str, Any] = {
            "_meta": {"ts_code": self.ts_code, "company_name": self.company_name,
                       "generated_at": datetime.now().isoformat()}
        }
        for fname in json_files:
            key = fname.replace(".json", "")
            path = os.path.join(self.stock_dir, fname)
            if os.path.exists(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        context[key] = json.load(f)
                except (json.JSONDecodeError, IOError):
                    context[key] = {"_missing": True, "_error": "parse_failed"}
            else:
                context[key] = {"_missing": True}

        self.context = context
        available = [k for k, v in context.items() if not k.startswith("_") and not (isinstance(v, dict) and v.get("_missing"))]
        print(f"📦 数据加载: {len(available)} 个文件可用")

    def _build_tasks(self):
        """从模板布局构建 ChapterTask 列表。"""
        special_titles = {"Executive Summary", "投资决策", "来源清单"}
        for ch in self.layout.chapters:
            is_special = ch.title in special_titles
            # 判断是否需要最后写（依赖其他章节完成后才写）
            write_last = ch.title in {"Executive Summary", "投资决策"}
            # 来源清单不需要 LLM 写
            skipped = ch.title == "来源清单"

            contract_dict = ch.chapter_contract.to_dict() if ch.chapter_contract else {}
            rules_dict = [r.to_dict() for r in ch.item_rules]

            task = ChapterTask(
                index=ch.index,
                title=ch.title,
                skeleton=ch.skeleton,
                chapter_goal=ch.chapter_goal,
                chapter_contract=contract_dict,
                item_rules=rules_dict,
                is_special=is_special,
                write_last=write_last,
            )
            self.tasks.append(task)

    def _write_middle_chapters(self):
        """顺序写所有中间章节（Dayu 模式：单 agent 全上下文，逐章写+审）。

        Dayu 的核心设计：一个 agent 拥有全部数据上下文，
        CHAPTER_CONTRACT 约束写什么而非能看什么。
        写完一章→审过→才写下一章。
        """
        middle_tasks = [t for t in self.tasks if not t.write_last and not t.title == "来源清单"]
        final_tasks = [t for t in self.tasks if t.write_last]
        source_task = [t for t in self.tasks if t.title == "来源清单"]

        print(f"✍️  顺序写作+审计: {len(middle_tasks)} 个中间章节 (audit={'启用' if self.enable_audit else '关闭'})")
        print(f"   📦 Agent 拥有全部 {len([k for k,v in self.context.items() if not k.startswith('_') and not (isinstance(v,dict) and v.get('_missing'))])} 个数据文件上下文")

        for task in middle_tasks:
            try:
                result = self._write_single_chapter(task)
            except Exception as e:
                result = ChapterResult(task=task, status=ChapterStatus.FAILED, error=str(e))
            self.results[task.index] = result

        # 记录特殊章节任务（后续步骤处理）
        for task in final_tasks + source_task:
            self.results[task.index] = ChapterResult(task=task)

    def _write_single_chapter(self, task: ChapterTask) -> ChapterResult:
        """写单个章节（含审计修复循环）。

        流程：加载已有输出 → 审计 → 修复/重写 → 重新审计 → 通过/失败。
        与 Dayu 的 chapter_execution_coordinator 一致：write → audit → repair → re-audit。

        Args:
            task: 章节任务。

        Returns:
            ChapterResult 对象。
        """
        from chapter_writer import _build_chapter_prompt, _extract_evidence_items
        from chapter_audit import audit_chapter
        from repair_executor import apply_repair, needs_regeneration

        safe_title = re.sub(r'[^\w]', '_', task.title)[:40]
        prompt_path = os.path.join(self.stock_dir, f"zone_c_ch{task.index:02d}_{safe_title}_prompt.txt")
        output_path = os.path.join(self.stock_dir, f"zone_c_ch{task.index:02d}_{safe_title}_output.md")
        os.makedirs(self.stock_dir, exist_ok=True)

        # 1. 保存 prompt（供协调器 / LLM 使用）
        prompt = _build_chapter_prompt(task, self.context, self.company_name)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        # 2. 加载或标记为等待 LLM
        if os.path.exists(output_path):
            with open(output_path, encoding="utf-8") as f:
                content = f.read().strip()
        else:
            content = ""

        if not content or (content.startswith("<!-- Ch") and "待 LLM 填充" in content[:200]):
            # 尚无 LLM 输出（占位符模式 "<!-- ChXX Title: 待 LLM 填充 -->"）——返回待填充状态
            return ChapterResult(
                task=task,
                content=f"<!-- Ch{task.index:02d} {task.title}: 待 LLM 填充 -->\n<!-- Prompt: {prompt_path} -->",
                status=ChapterStatus.PENDING,
            )

        # 3. 审计循环（V10 核心）：写 → 审 → 修 → 再审
        result = ChapterResult(task=task, content=content, evidence_items=_extract_evidence_items(content))
        audit_enabled = self.enable_audit  # 默认启用

        for attempt in range(self.max_retries + 1):
            result.retry_count = attempt

            if audit_enabled:
                result.status = ChapterStatus.AUDITING
                audit_result = audit_chapter(result)

                if audit_result.verdict.value == "pass":
                    result.status = ChapterStatus.PASSED
                    result.audit_results.append(audit_result)
                    audit_icon = "✅"
                    break

                # 审计未通过——尝试修复
                result.status = ChapterStatus.REPAIRING
                result.audit_results.append(audit_result)

                if needs_regeneration(audit_result):
                    # 问题太多或需LLM修复 — 保存修复prompt，标记需协调器重新生成
                    repair_prompt_path = output_path.replace("_output.md", "_repair_prompt.txt")
                    repair_plan = audit_result.repair_plan or f"{len(audit_result.violations)} 项违规需修复"
                    with open(repair_prompt_path, "w", encoding="utf-8") as f:
                        f.write(f"# 章节修复请求\n\n## 审计发现 ({len(audit_result.violations)} 违规)\n\n{repair_plan}\n\n## 原始内容\n\n{result.content}")
                    result.content = f"<!-- REGENERATE_REQUIRED: {len(audit_result.violations)}项违规, repair_prompt: {os.path.basename(repair_prompt_path)} -->\n{result.content}"
                    result.status = ChapterStatus.FAILED
                    result.error = f"需LLM重新生成 ({len(audit_result.violations)}项违规)"
                    break

                # 尝试 patch 修复
                repaired = apply_repair(result.content, audit_result, task)
                if repaired != result.content:
                    result.content = repaired
                    # 写回修复后的内容
                    with open(output_path, "w", encoding="utf-8") as f:
                        f.write(repaired)
                    continue
                else:
                    # 修复无变化，停止重试
                    result.status = ChapterStatus.FAILED
                    result.error = "修复无效"
                    break
            else:
                # 审计关闭——直接通过
                result.status = ChapterStatus.PASSED
                break
        else:
            # 超过最大重试次数
            result.status = ChapterStatus.FAILED
            result.error = f"审计/修复超过最大重试次数 {self.max_retries}"

        audit_icon = "✅" if result.status == ChapterStatus.PASSED else "❌"
        violation_count = len(result.audit_results[-1].violations) if result.audit_results else 0
        evidence_coverage = 0.0

        # V10: 证据覆盖率检查（审计通过后附加）
        if result.status == ChapterStatus.PASSED and result.content:
            evidence_cov = validate_evidence_coverage(result.content, self.evidence_registry)
            evidence_coverage = evidence_cov["coverage_ratio"]
            if evidence_cov["status"] == "FAIL":
                result.status = ChapterStatus.FAILED
                result.error = f"证据覆盖率不足: {evidence_coverage:.0%}"
                audit_icon = "❌"

        # V10: 记录执行追踪
        self.tracker.record_chapter(
            index=task.index, title=task.title,
            status=result.status, retry_count=result.retry_count,
            audit_passed=(result.status == ChapterStatus.PASSED),
            evidence_count=len(result.evidence_items),
            content_chars=len(result.content),
            error=result.error or "",
        )

        print(f"  {audit_icon} Ch{task.index:02d} {task.title}: {len(result.content):,} chars"
              + (f", 审计{'通过' if result.status == ChapterStatus.PASSED else '未通过'}"
                 f"({violation_count}违规)" if audit_enabled else "")
              + (f", 证据{evidence_coverage:.0%}" if result.status == ChapterStatus.PASSED and evidence_coverage > 0 else ""))

        return result

    def _write_decision_chapter(self):
        """在所有分析章完成后写投资决策章。

        优先使用 LLM 输出（若已有 zone_c_ch08_*_output.md），
        无 LLM 输出时使用基于规则的 fallback。
        """
        decision_task = next((t for t in self.tasks if t.title == "投资决策"), None)
        if not decision_task:
            return

        print(f"\n🎯 决策综合: Ch{decision_task.index:02d} {decision_task.title}")

        try:
            di = self._build_decision_input()
            from chapter_writer import _build_decision_prompt, _fallback_decision, _parse_decision_output
            from models import DecisionOutput

            # 检查是否已有 LLM 输出
            safe_title = "决策"
            output_path = os.path.join(self.stock_dir, f"zone_c_ch{decision_task.index:02d}_{safe_title}_output.md")
            prompt_path = os.path.join(self.stock_dir, f"zone_c_ch{decision_task.index:02d}_{safe_title}_prompt.txt")

            # 保存 prompt（供协调器/LLM 使用）
            prompt = _build_decision_prompt(di)
            with open(prompt_path, "w", encoding="utf-8") as f:
                f.write(prompt)

            if os.path.exists(output_path):
                with open(output_path, encoding="utf-8") as f:
                    content = f.read().strip()
                if content and not content.startswith("<!--"):
                    # 使用 LLM 输出
                    decision = _parse_decision_output(content, di)
                    # 验证一致性
                    from decision_synthesizer import validate_decision
                    issues = validate_decision(decision, di)
                    if issues:
                        print(f"  ⚠️ 一致性警告: {issues}")
                    from chapter_writer import _extract_evidence_items
                    self.results[decision_task.index] = ChapterResult(
                        task=decision_task, content=content,
                        status=ChapterStatus.PASSED,
                        evidence_items=_extract_evidence_items(content),
                    )
                    print(f"  ✅ 决策章: LLM输出 ({len(content):,} chars) → {decision.verdict}/{decision.confidence}")
                    return

            # Fallback
            decision = _fallback_decision(di, "待LLM生成")
            _format_decision_md = globals().get('_format_decision_markdown')
            if _format_decision_md:
                fb_content = _format_decision_md(decision, di)
            else:
                fb_content = f"## 投资决策\n\n**决策: {decision.verdict}** (置信度: {decision.confidence})\n\n_（待 LLM 生成最终决策章，Prompt: {prompt_path}）_"

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(fb_content)
            self.results[decision_task.index] = ChapterResult(
                task=decision_task, content=fb_content, status=ChapterStatus.PASSED
            )
            print(f"  ⚠️ 决策章: fallback → {decision.verdict}/{decision.confidence}（Prompt: {prompt_path}）")
        except Exception as e:
            self.results[decision_task.index] = ChapterResult(
                task=decision_task, status=ChapterStatus.FAILED, error=str(e)
            )
            print(f"  ❌ 决策章失败: {e}")

    def _build_decision_input(self) -> DecisionInput:
        """从各章结果中构建决策输入数据。"""
        cb = self.context.get("compute_bundle", {})
        cb_precise = self.context.get("compute_bundle_precise", {})
        contract = self.context.get("analysis_contract", {})

        # 提取关键参数
        params = cb.get("params", {})
        factor2 = cb.get("factor2", {})
        factor3 = cb_precise.get("factor3", cb.get("factor3", {}))
        factor4 = cb_precise.get("factor4", cb.get("factor4", {}))
        rejection = cb.get("rejection_summary", {})

        ii = params.get("II", 0)
        rf = params.get("Rf", 0)
        gg_base = factor3.get("gg", {}).get("base", 0) if isinstance(factor3.get("gg"), dict) else factor3.get("gg", 0)
        gg_scenarios = {
            "悲观": factor3.get("gg", {}).get("pessimistic", 0) if isinstance(factor3.get("gg"), dict) else 0,
            "乐观": factor3.get("gg", {}).get("optimistic", 0) if isinstance(factor3.get("gg"), dict) else 0,
        }
        ddm_v = factor4.get("ddm_v_hkd", factor4.get("ddm_v", 0))
        current_price = cb.get("market", {}).get("price_hkd", cb.get("market", {}).get("price", 0))
        position_pct = factor4.get("position_pct", factor4.get("position", 0))

        # 从 moat_assessment 提取
        moat = self.context.get("moat_assessment", {})
        moat_rating = moat.get("moat_rating", "Unknown")

        # 从 risks 提取
        risks_data = self.context.get("risks", {})
        key_risks = []
        if isinstance(risks_data, dict):
            risk_items = risks_data.get("risks", risks_data.get("risk_items", []))
            if isinstance(risk_items, list):
                key_risks = [r.get("description", str(r)) if isinstance(r, dict) else str(r) for r in risk_items[:5]]

        return DecisionInput(
            company_name=self.company_name,
            ts_code=self.ts_code,
            factor_1a_summary=f"快筛完成" if not rejection.get("overall") else f"否决门: {rejection.get('overall')}",
            factor_1b_summary=f"护城河评级: {moat_rating}",
            factor_1c_summary=f"增长质量评估完成",
            factor_2_gg=factor2.get("gg", factor2.get("R_NP_tax", 0)),
            factor_3_gg=gg_base,
            factor_3_gg_scenarios=gg_scenarios,
            factor_4_ddm_v=ddm_v,
            factor_4_current_price=current_price,
            factor_4_position_pct=position_pct,
            ii=ii,
            rf=rf,
            key_risks=key_risks,
            rejection_status=rejection.get("overall", "通过") if isinstance(rejection, dict) else str(rejection),
            moat_rating=moat_rating,
        )

    def _write_summary_chapter(self):
        """写 Executive Summary 章（在所有其他章完成后）。"""
        summary_task = next((t for t in self.tasks if t.title == "Executive Summary"), None)
        if not summary_task:
            return

        print(f"\n📝 Executive Summary: Ch{summary_task.index:02d}")

        # 从已完成章节提取关键信息
        summary = self._generate_executive_summary()

        # Dayu-style: collect chapter summaries for LLM to compress
        chapter_summaries = self._collect_chapter_summaries()
        overview_input = self._build_overview_prompt_input()

        safe_title = "Executive_Summary"
        prompt_path = os.path.join(self.stock_dir, f"zone_c_ch{summary_task.index:02d}_{safe_title}_prompt.txt")
        output_path = os.path.join(self.stock_dir, f"zone_c_ch{summary_task.index:02d}_{safe_title}_output.md")

        prompt = f"""# 投资要点概览（买方一页纸封面）

你是买方分析师。以下是已完成章节的结构化摘要。请将其压缩为一页 Executive Summary（300-500 字），格式为 3-4 段连贯叙事。

**核心规则**：
- 禁止引入前文章节中未出现的新事实或新数据
- 禁止编造前文章节未提及的数字
- 必须覆盖：公司定位、核心护城河、关键财务指标、估值结论、主要风险

**已完成章节摘要**：
{overview_input}

**公司**: {self.company_name} ({self.ts_code})
**核心参数**: II={self._p('II')}%, GG base={self._p('gg_base')}%, DDM={self._p('ddm_v_hkd')} HKD, 现价={self._p('price_hkd')} HKD"""

        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(prompt)

        # Fallback: if LLM not available, generate from data context
        es_content = _format_executive_summary(self.company_name, self.ts_code, self.context)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(es_content)

        self.results[summary_task.index] = ChapterResult(
            task=summary_task, content=es_content, status=ChapterStatus.PASSED
        )
        print(f"  ✅ Executive Summary prompt: {len(prompt):,} chars (fallback: {len(es_content):,} chars)")

    def _p(self, key: str) -> str:
        """Shortcut to read a parameter from compute_bundle."""
        cb = self.context.get("compute_bundle", {})
        # Direct keys
        for section in [cb.get("params", {}), cb.get("market", {}), cb.get("factor4", {}),
                         cb.get("factor2", {}), cb.get("factor3", {})]:
            if key in section: return str(section[key])
        # Nested: gg.base
        f3 = cb.get("factor3", {})
        gg = f3.get("gg", {})
        if isinstance(gg, dict) and key in gg:
            return str(gg[key])
        # Nested: aa_avg
        aa = f3.get("aa_avg", {})
        if isinstance(aa, dict) and key in aa:
            return str(aa[key])
        return "?"

    def _collect_chapter_summaries(self) -> dict:
        """Collect key data points from each completed chapter for ES compression."""
        summaries = {}
        for task in self.tasks:
            result = self.results.get(task.index)
            if not result or not result.content:
                continue
            text = result.content
            # Extract key tables (rows with | separator) + first 2 paragraphs
            lines = text.split("\n")
            table_rows = [l for l in lines if l.count("|") >= 3 and "---" not in l][:10]
            text_lines = [l for l in lines if l.strip() and not l.startswith("#") and not l.startswith("|") and len(l) > 20][:3]
            summary = "\n".join(text_lines[:2] + table_rows[:6])
            summaries[task.title] = summary
        return summaries

    def _build_overview_prompt_input(self) -> str:
        """Build a structured summary for the LLM to compress into one-page overview."""
        parts = []
        for task in self.tasks:
            result = self.results.get(task.index)
            if not result or not result.content:
                continue
            text = result.content
            lines = text.split("\n")
            # Extract: heading + first substantive paragraph + key table rows
            extracted = []
            for i, line in enumerate(lines):
                if line.startswith("## "):
                    extracted.append(line)
                    for j in range(i+1, min(i+8, len(lines))):
                        lj = lines[j].strip()
                        if lj and not lj.startswith("#") and not lj.startswith("|"):
                            if len(lj) > 30:
                                extracted.append(lj[:250])
                                break
                    # Also grab first data table
                    for j in range(i+1, min(i+15, len(lines))):
                        if lines[j].count("|") >= 3 and "---" not in lines[j]:
                            extracted.append(lines[j][:200])
                            break
            parts.append(f"### {task.title}\n" + "\n".join(extracted[:8]))
        return "\n\n".join(parts)

    def _generate_executive_summary(self) -> str:
        """从数据上下文生成 Executive Summary 的关键信息摘要。"""
        cb = self.context.get("compute_bundle", {})
        params = cb.get("params", {})
        market = cb.get("market", {})
        factor3 = cb.get("factor3", {})
        factor4 = cb.get("factor4", {})
        rejection = cb.get("rejection_summary", {})

        ii = params.get("II", "?")
        gg_dict = factor3.get("gg", {})
        gg_base = gg_dict.get("base", "?") if isinstance(gg_dict, dict) else gg_dict
        ddm_v = factor4.get("ddm_v_hkd", factor4.get("ddm_v", "?"))
        price = market.get("price_hkd", market.get("price", "?"))
        # moat_rating is stripped by _strip_zone_j_narrative, use moat_evidence instead
        moat_evidence = self.context.get("moat_assessment", {}).get("moat_evidence", [])
        moat_desc = "; ".join(e.get("evidence", "")[:60] for e in moat_evidence[:3]) if moat_evidence else "未评估"
        reject_status = rejection.get("overall", "?")

        return "\n".join([
            f"公司: {self.company_name} ({self.ts_code})",
            f"II: {ii}%",
            f"GG base: {gg_base}%",
            f"DDM公允价: {ddm_v} HKD",
            f"当前价: {price} HKD",
            f"护城河: {moat_desc}",
            f"否决门: {reject_status}",
            f"否决门: {rejection.get('overall', '通过') if isinstance(rejection, dict) else rejection}",
        ])

    def _build_source_list(self):
        """从所有章节中提取证据锚点，用 source_list_builder 生成分类来源清单。"""
        source_task = next((t for t in self.tasks if t.title == "来源清单"), None)
        if not source_task:
            return

        # 收集所有章节内容
        full_text = ""
        for idx, result in sorted(self.results.items()):
            if result.content:
                full_text += result.content + "\n"

        # V10: 使用 source_list_builder（分类 + 来源描述）
        content = _build_source_list_md(full_text, self.evidence_registry)
        unique_count = len(self.evidence_registry.extract_all_sources(full_text))

        safe_title = "来源清单"
        output_path = os.path.join(self.stock_dir, f"zone_c_ch{source_task.index:02d}_{safe_title}_output.md")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content)

        self.results[source_task.index] = ChapterResult(
            task=source_task, content=content, status=ChapterStatus.PASSED,
            evidence_items=self.evidence_registry.extract_all_sources(full_text),
        )
        print(f"\n📚 来源清单: {unique_count} 条去重来源")

    def _assemble_report(self) -> str:
        """组装最终报告。

        Returns:
            最终报告文件路径。
        """
        print(f"\n🔧 组装最终报告...")

        # 按模板顺序拼接章节
        preface = self.layout.preface_skeleton if self.layout else f"# 龟龟投资策略 · 分析报告：{self.company_name}"
        chapter_contents: list[str] = []

        for task in self.tasks:
            result = self.results.get(task.index)
            if result and result.content:
                chapter_contents.append(result.content)
            else:
                chapter_contents.append(f"## {task.title}\n\n_（本章待填充）_\n")

        report_md = build_report_markdown(preface, chapter_contents)

        # 替换模板变量
        report_md = report_md.replace("{company_name}", self.company_name)
        report_md = report_md.replace("{executive_summary}", "")
        report_md = report_md.replace("{source_list}", "")

        # 写入文件
        code_clean = self.ts_code.replace(".", "")
        report_name = f"{self.company_name}_{code_clean}_分析报告_v10.md"
        report_path = os.path.join(self.stock_dir, report_name)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_md)

        print(f"  📄 {report_path}")
        print(f"  📊 {len(report_md.splitlines())} 行 / {len(report_md.encode('utf-8'))/1024:.1f} KB")

        return report_path


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _get_company_name(ts_code: str) -> str:
    """从数据库获取公司中文名。"""
    import sqlite3
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute("SELECT name_cn FROM stocks WHERE ts_code=?", (ts_code,)).fetchone()
        conn.close()
        if row:
            return row[0]
    except Exception:
        pass
    return ts_code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")


def _format_decision_markdown(di_output, di_input: DecisionInput) -> str:
    """将 DecisionOutput 格式化为 Markdown。"""
    return f"""## 投资决策

### 决策摘要
| 项目 | 内容 |
|------|------|
| 标的 | {di_input.company_name}（{di_input.ts_code}） |
| **决策** | **{di_output.verdict}** |
| 置信度 | {di_output.confidence} |
| 决策日期 | {datetime.now().strftime('%Y-%m-%d')} |

### 核心依据
{chr(10).join(f"{i+1}. {r}" for i, r in enumerate(di_output.rationale))}

### 关键假设与脆弱点
| 假设 | 若错误的影响 | 概率 |
|------|------|:--:|
{chr(10).join(f"| {a.get('assumption', '?')} | {a.get('impact_if_wrong', '?')} | {a.get('probability', '?')} |" for a in di_output.assumptions) if di_output.assumptions else "| _待LLM生成_ | _待LLM生成_ | _待LLM生成_ |"}

### 监控触发器（降级条件）
{chr(10).join(f"- {t}" for t in di_output.triggers) if di_output.triggers else "- _待LLM生成_"}

### 退出条件（清仓信号）
{chr(10).join(f"- {e}" for e in di_output.exit_conditions) if di_output.exit_conditions else "- _待LLM生成_"}
"""


def _format_executive_summary(company_name: str, ts_code: str, context: dict) -> str:
    """生成 Executive Summary 的 fallback 内容。"""
    cb = context.get("compute_bundle", {})
    params = cb.get("params", {})
    market = cb.get("market", {})
    factor3 = cb.get("factor3", {})
    factor4 = cb.get("factor4", {})
    rejection = cb.get("rejection_summary", {})

    ii = params.get("II", "?")
    gg = factor3.get("gg", "?")
    ddm_v = factor4.get("ddm_v_hkd", factor4.get("ddm_v", "?"))
    price = market.get("price_hkd", market.get("price", "?"))
    moat = self_ref(context, "moat_assessment", "moat_rating", "?")

    return f"""## Executive Summary

{company_name}（{ts_code}）。本报告基于四因子模型（V10），综合评估该标的的投资价值。

关键参数：II={ii}%，GG={gg}%，DDM公允价={ddm_v}，当前价={price}，护城河评级={moat}。

_（完整 Executive Summary 待各章完成后由 LLM 回填。）_
"""


def self_ref(data: dict, *keys, default="?"):
    """安全地从嵌套字典获取值。"""
    for key in keys:
        if isinstance(data, dict):
            data = data.get(key, default)
        else:
            return default
    return data if data is not None else default


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _run_pipeline(args: argparse.Namespace) -> int:
    """V10 多 Agent 并行模式（遗留）。"""
    # 查找输出目录
    stock_dir = args.output
    if not stock_dir:
        code_base = args.code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        for name in os.listdir(OUTPUT_DIR):
            if name.startswith(code_base) and os.path.isdir(os.path.join(OUTPUT_DIR, name)):
                stock_dir = os.path.join(OUTPUT_DIR, name)
                break
        if not stock_dir:
            print(f"ERROR: 找不到 {args.code} 的输出目录", file=sys.stderr)
            return 1

    # V10.1: Resume — skip chapters with existing output
    if args.resume:
        completed = len(glob.glob(os.path.join(stock_dir, "zone_c_ch*_output.md")))
        if completed > 0:
            print(f"🔄 Resume: {completed} 章已存在，将跳过")

    runner = WritePipelineRunner(
        stock_dir=stock_dir,
        ts_code=args.code,
        template_path=args.template or "",
        max_workers=args.max_workers,
        enable_audit=True,
        max_retries=args.max_retries,
    )
    # Pass resume state to runner
    if args.resume:
        for ch in runner.layout.chapters if runner.layout else []:
            output_path = os.path.join(stock_dir, f"zone_c_ch{ch.index:02d}_{ch.title.replace(' ', '_').replace('/', '_')}_output.md")
            if os.path.exists(output_path):
                ch._completed = True
    if args.render_html:
        runner._render_format = "html"
    elif args.render_pdf:
        runner._render_format = "pdf"

    try:
        report_path = runner.run()
        print(f"📄 报告路径: {report_path}")
        return 0
    except Exception as e:
        print(f"❌ 管线失败: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


def main():
    ap = argparse.ArgumentParser(description="write_pipeline.py — V11 默认单Agent / V10 遗留多Agent")
    ap.add_argument("--code", required=True, help="股票代码")
    ap.add_argument("--output", help="输出目录（自动检测）")
    ap.add_argument("--template", help="模板路径（默认 templates/report_template_v10.md）")
    ap.add_argument("--max-workers", type=int, default=4, help="[V10] 最大并行章节数")
    ap.add_argument("--max-retries", type=int, default=2, help="[V10] 每章最大重试次数")
    ap.add_argument("--save-prompts-only", action="store_true", help="[V10] 仅保存各章 prompt")
    ap.add_argument("--resume", action="store_true", help="[V10] 跳过已有 zone_c_ch*_output.md 的章节")
    ap.add_argument("--render-html", action="store_true", help="组装后渲染为 HTML")
    ap.add_argument("--render-pdf", action="store_true", help="组装后渲染为 PDF")
    # V11 Agent (默认)
    ap.add_argument("--model", default="claude-sonnet-4-20250514", help="Agent 模型")
    ap.add_argument("--provider", default="anthropic", choices=("anthropic", "openai"), help="LLM provider")
    ap.add_argument("--contract", help="分析合约路径")
    ap.add_argument("--max-iter", type=int, default=30, help="Agent 最大迭代次数")
    ap.add_argument("--skip-prepare", action="store_true", help="跳过Phase 0/0.5/1/2")
    ap.add_argument("--dry-run", action="store_true", help="仅Python计算，不调LLM")
    # V10 回退
    ap.add_argument("--legacy-v10", action="store_true", help="回退到 V10 多Agent并行模式")
    args = ap.parse_args()

    # V10 回退模式
    if args.legacy_v10:
        return _run_pipeline(args)

    # V11 默认: 委托给 turtle_agent.run
    from turtle_agent.run import run_full_pipeline
    try:
        report_path = run_full_pipeline(
            code=args.code,
            output_dir=args.output or "",
            skip_prepare=args.skip_prepare,
            dry_run=args.dry_run,
            provider=args.provider,
            model=args.model,
            max_iterations=args.max_iter,
            template_path=args.template or "templates/report_template_v10.md",
        )
        print(f"📄 {report_path}")
        return 0
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
