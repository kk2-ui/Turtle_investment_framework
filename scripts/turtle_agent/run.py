#!/usr/bin/env python3
"""Turtle V12 统一入口 — 一键全流程。

V12: 单 Agent + 工具循环，Dayu 定性 + Turtle 定量在同一个 Agent Loop 内完成。
V11 兼容模式: --template report_template_v10.md 恢复原有行为。

Usage::
    # V12 统一模式（Dayu 定性 + Turtle 定量 → 15章报告）
    python -m turtle_agent.run --code 06668.HK --unified

    # V11 兼容模式（仅定量）
    python -m turtle_agent.run --code 06668.HK

    # 仅定性分析
    python -m turtle_agent.run --code 06668.HK --qualitative-only

    # 干跑
    python -m turtle_agent.run --code 06668.HK --dry-run
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# 确保 scripts/ 可导入
_scripts_dir = os.path.join(os.path.dirname(__file__), "..")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

_OUTPUT_DIR = os.path.join(_scripts_dir, "..", "output")


# ===================================================================
# 主入口
# ===================================================================


def run_full_pipeline(
    code: str,
    *,
    output_dir: str = "",
    skip_prepare: bool = False,
    dry_run: bool = False,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    max_iterations: int = 30,
    template_path: str = "templates/report_template_v10.md",
    unified: bool = False,
    qualitative_only: bool = False,
) -> str:
    """运行完整分析管线。

    V11: Phase 0 → 0.5 → 1 → 2 → Agent Loop (定量报告)
    V12: Phase 0 → 0.5 → 1 → 2 → Agent Loop (定性+定量统一报告)

    Agent Loop 内全自动：定性写作 Ch1-9 → 摘要提取 → Zone J → 定量估值 Ch10-13 → 统一决策。
    所有 LLM 调用走 Claude Code 内置 API（不受子进程安全策略限制）。
    """
    if not output_dir:
        output_dir = _OUTPUT_DIR
    os.makedirs(output_dir, exist_ok=True)

    # V12: 统一模式自动切换模板
    is_v12 = unified or qualitative_only
    if is_v12 and template_path == "templates/report_template_v10.md":
        template_path = "templates/report_template_v12.md"

    start_time = time.time()

    print(f"\n{'='*60}")
    print(f"🐢 Turtle {'V12' if is_v12 else 'V11'} 全流程分析: {code}")
    print(f"   输出: {output_dir}")
    print(f"   模板: {template_path}")
    if unified:
        print(f"   模式: Dayu定性 + Turtle定量 → 15章统一报告")
    elif qualitative_only:
        print(f"   模式: Dayu定性(Ch1-9) + 摘要提取")
    if dry_run:
        print(f"   ⚠️ 干跑模式 (仅 Python 计算)")
    print(f"{'='*60}\n")

    # ---- Phase 0-2: 数据准备 ----
    contract_path = os.path.join(output_dir, "analysis_contract.json")

    if not skip_prepare:
        print("━" * 40)
        print("📊 Phase 0-2: 数据准备")
        print("━" * 40)

        # Phase 0
        print("\n[Phase 0] 前置诊断...")
        pa = _run_phase("pre_analysis", code, output_dir)
        if not pa.get("ok"):
            raise RuntimeError(f"Phase 0 失败: {pa.get('error')}")
        print(f"  ✅ 有效窗口: {pa.get('effective_years')} ({pa.get('cycle_type')})")

        # Phase 0.5
        print("\n[Phase 0.5] 年报下载...")
        code_short = code.replace(".HK", "").replace(".SH", "").replace(".SZ", "")
        chk = _run_phase("check", code_short, output_dir)
        if not chk.get("complete"):
            print(f"  ⚠️ 缺失: {chk.get('missing')}, 开始下载...")
            dl = _run_phase("download", code_short, output_dir)
            ok = dl.get("ok")
            print(f"  {'✅' if ok else '⚠️'} 下载完成")
        else:
            print("  ✅ 年报完整")

        # Phase 1
        print("\n[Phase 1] 定量计算...")
        cb = _run_phase("compute", code, output_dir)
        if not cb.get("ok"):
            raise RuntimeError(f"Phase 1 失败: {cb.get('error')}")
        gg = cb.get("gg", {})
        print(f"  ✅ GG(base)={gg.get('base', '?')}%, DDM={cb.get('ddm', {}).get('fair_value', '?')}")

        # Phase 2
        print("\n[Phase 2] PDF章节提取...")
        pdfs = [f for f in os.listdir(output_dir) if f.endswith(".pdf") and "年报" in f]
        for pdf_file in pdfs[:3]:
            pdf_path = os.path.join(output_dir, pdf_file)
            try:
                year = int(pdf_file[:4]) if pdf_file[:4].isdigit() else 0
            except (ValueError, IndexError):
                year = 0
            ep = _run_phase("extract_pdf", "", output_dir, pdf_path=pdf_path, year=year)
            if ep.get("ok"):
                print(f"  ✅ {pdf_file}: {ep.get('sections_count', 0)} sections")
            else:
                print(f"  ⚠️ {pdf_file}: {ep.get('error', 'unknown')}")

    # ---- Agent Loop ----
    if dry_run:
        print(f"\n⏭ 干跑模式: 跳过 Agent Loop")
        report_path = os.path.join(output_dir, f"{code}_V12_DRY_RUN.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(f"# {code} {'V12' if is_v12 else 'V11'} 干跑报告\n\nPhase 0-2 数据准备已完成。\n跳过 LLM 分析。\n")
        return report_path

    from turtle_agent.tool_registry import ToolRegistry
    from turtle_agent.agent_loop import TurtleAgent, AgentConfig
    from turtle_agent.llm_client import LlmClient

    # 自动发现工具（每次 run 重新注册，~0.1秒，可接受）
    tools = ToolRegistry()
    for mod in [
        "turtle_agent.tools.read_tools",
        "turtle_agent.tools.calc_tools",
        "turtle_agent.tools.write_tools",
        "turtle_agent.tools.phase_tools",
    ]:
        n = tools.auto_discover(mod)

    # 尝试自动选择 LLM provider
    api_key = os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("DEEPSEEK_API_KEY", "")
    llm = None

    if api_key:
        # 有 API key → 自动检测 provider 并运行完整 Agent Loop
        if api_key.startswith("sk-ant-"):
            provider = "anthropic"
            model_name = model
        else:
            # DeepSeek OpenAI 兼容 API — httpx 直调，零额外依赖
            provider = "deepseek_oa"
            model_name = "deepseek-v4-pro"

        print(f"\n{'━'*40}")
        print(f"🤖 {'V12' if is_v12 else 'V11'} Agent Loop — 全自动模式")
        print(f"   Provider: {provider} / {model_name}")
        print(f"━'*40")

        llm = LlmClient(provider=provider, model=model_name)

        config = AgentConfig(
            code=code,
            contract_path=contract_path,
            output_dir=output_dir,
            max_iterations=max_iterations,
            template_path=template_path,
        )
        agent = TurtleAgent(llm=llm, tools=tools, config=config)

        start_time = time.time()
        try:
            report_path = agent.analyze()
            elapsed = time.time() - start_time
            print(f"\n{'='*60}")
            print(f"✅ 分析完成 ({elapsed:.0f}s)")
            print(f"📄 {report_path}")
            print(f"{'='*60}\n")
            return report_path
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"\n❌ Agent Loop 失败 ({elapsed:.0f}s): {e}")
            import traceback
            traceback.print_exc()
            raise RuntimeError(f"Agent Loop 失败: {e}") from e
    else:
        # 无 API key → Claude Code 模式：生成 prompt 文件
        print(f"\n{'━'*40}")
        print(f"🤖 {'V12' if is_v12 else 'V11'} Agent — Prompt 生成模式")
        print(f"   (设置 ANTHROPIC_API_KEY 环境变量以启用全自动模式)")
        print(f"━'*40")

        config = AgentConfig(
            code=code,
            contract_path=contract_path,
            output_dir=output_dir,
            max_iterations=max_iterations,
            template_path=template_path,
        )
        agent = TurtleAgent(llm=None, tools=tools, config=config)
        agent._load_context()

        qual_info = ""
        if agent._context.get("qualitative_summary"):
            qual_info = " (含定性摘要)"
        print(f"  📖 上下文: {len(agent._context)} 项{qual_info}")

        system_prompt = agent._build_system_prompt()

        fname = "_v12_system_prompt.md" if is_v12 else "_v11_system_prompt.md"
        prompt_path = os.path.join(output_dir, fname)
        with open(prompt_path, "w", encoding="utf-8") as f:
            f.write(system_prompt)

        tool_path = os.path.join(output_dir, "_v12_tools.json" if is_v12 else "_v11_tools.json")
        with open(tool_path, "w", encoding="utf-8") as f:
            json.dump(tools.get_anthropic_schemas(), f, ensure_ascii=False, indent=2)

        print(f"  📄 System Prompt → {prompt_path} ({len(system_prompt):,} chars)")
        print(f"  🔧 Tool Schemas  → {tool_path} ({len(tools)} tools)")

        return prompt_path


# ===================================================================
# Phase 执行器
# ===================================================================


def _run_phase(
    phase: str,
    code: str,
    output_dir: str,
    **kwargs: Any,
) -> dict[str, Any]:
    """执行单个 Phase。"""
    if phase == "pre_analysis":
        from turtle_agent.tools.phase_tools import run_pre_analysis
        return run_pre_analysis(code=code)

    elif phase == "check":
        from turtle_agent.tools.phase_tools import check_report_completeness
        return check_report_completeness(code=code, save_dir=output_dir)

    elif phase == "download":
        from turtle_agent.tools.phase_tools import download_annual_reports
        return download_annual_reports(code=code, save_dir=output_dir)

    elif phase == "compute":
        from turtle_agent.tools.phase_tools import compute_bundle_db
        return compute_bundle_db(code=code, output_dir=output_dir)

    elif phase == "extract_pdf":
        from turtle_agent.tools.phase_tools import extract_pdf_sections
        return extract_pdf_sections(
            pdf_path=kwargs.get("pdf_path", ""),
            output_dir=output_dir,
            year=kwargs.get("year", 0),
        )

    elif phase == "verify":
        from turtle_agent.tools.phase_tools import verify_report
        return verify_report(
            report_path=kwargs.get("report_path", ""),
            output_dir=output_dir,
        )

    return {"ok": False, "error": f"未知 Phase: {phase}"}


# ===================================================================
# CLI
# ===================================================================


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Turtle V12 — 全流程分析 (单Agent)")
    ap.add_argument("--code", required=True, help="股票代码")
    ap.add_argument("--output", default="", help="输出目录")
    ap.add_argument("--skip-prepare", action="store_true", help="跳过Phase 0/0.5/1/2")
    ap.add_argument("--dry-run", action="store_true", help="仅Python计算，不调LLM")
    ap.add_argument("--model", default="claude-sonnet-4-20250514")
    ap.add_argument("--max-iter", type=int, default=30, help="Agent最大迭代次数")
    ap.add_argument("--template", default="templates/report_template_v10.md")
    # V12 flags
    ap.add_argument("--unified", action="store_true", help="V12: Dayu定性+Turtle定量 → 15章统一报告")
    ap.add_argument("--qualitative-only", action="store_true", help="V12: 仅定性分析(Ch1-9)")
    args = ap.parse_args(argv)

    try:
        report_path = run_full_pipeline(
            code=args.code,
            output_dir=args.output or "",
            skip_prepare=args.skip_prepare,
            dry_run=args.dry_run,
            model=args.model,
            max_iterations=args.max_iter,
            template_path=args.template,
            unified=args.unified,
            qualitative_only=args.qualitative_only,
        )
        print(f"\n📄 {report_path}")
        return 0
    except RuntimeError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⏹ 用户中断")
        return 130


if __name__ == "__main__":
    sys.exit(main())
