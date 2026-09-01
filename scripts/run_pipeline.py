#!/usr/bin/env python3
"""run_pipeline.py — V10 全管道协调器（状态机 + 门禁检查）

Phase 0 → 0.5 → 1 → 2 → 3 → 4 → 5
与 coordinator_v10.md 步骤一一对应，本文件为可执行真源。

Usage:
  python3 scripts/run_pipeline.py --code 03990.HK              # 自动推进到下一个未完成步骤
  python3 scripts/run_pipeline.py --code 03990.HK --status      # 查看进度
  python3 scripts/run_pipeline.py --code 03990.HK --resume      # 从断点继续
  python3 scripts/run_pipeline.py --code 03990.HK --step 0      # 只运行指定步骤
"""

import argparse, json, os, sqlite3, subprocess, sys
from datetime import datetime

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPTS)
OUTPUT_DIR = os.path.join(ROOT, "output")
DB_PATH = os.path.join(ROOT, "stock_analysis.db")
VENV_PYTHON = os.path.join(ROOT, ".venv", "bin", "python3")

def _py(): return VENV_PYTHON if os.path.exists(VENV_PYTHON) else sys.executable

# ── Pipeline State Machine (与 coordinator_v10.md 步骤同步) ──
PIPELINE = [
    # Phase 0: 前置诊断
    {"step": 0,   "phase": 0,   "zone": "pre",        "name": "Phase 0 前置诊断",           "requires": [],                                       "produces": ["analysis_contract.json"]},
    # Phase 0.5: 年报下载（阻断门：<3年阻断后续）
    {"step": 0.5, "phase": 0.5, "zone": "download",   "name": "Phase 0.5 年报批量下载",     "requires": ["analysis_contract.json"],                "produces": ["*_年报.pdf"]},
    # Phase 1: Zone A 定量计算
    {"step": 1,   "phase": 1,   "zone": "A",          "name": "Phase 1 Zone A 基础计算",     "requires": [],                                       "produces": ["compute_bundle.json", "financial_trends.json"]},
    {"step": 1.5, "phase": 1,   "zone": "D",          "name": "Phase 1 Zone D 行业数据",     "requires": [],                                       "produces": ["industry_context.json"]},
    # Phase 2: Zone B 定性提取（手动门：需协调器调度 LLM sub-agent）
    {"step": 2,   "phase": 2,   "zone": "B_prompts",  "name": "Phase 2 Zone B prompt生成",   "requires": ["compute_bundle.json"],                   "produces": ["zone_b_prompt_*.txt"]},
    {"step": 2.5, "phase": 2,   "zone": "B_llm",      "name": "Phase 2 Zone B LLM提取 ⚡手动","requires": ["zone_b_prompt_mda.txt"],                 "produces": ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]},
    # Phase 3: Zone J 判断参数化（手动门：需协调器调度 LLM sub-agent）
    {"step": 3,   "phase": 3,   "zone": "J_prompts",  "name": "Phase 3 Zone J prompt生成",   "requires": ["mda.json"],                              "produces": ["zone_j_prompt_*.txt"]},
    {"step": 3.5, "phase": 3,   "zone": "J_llm",      "name": "Phase 3 Zone J LLM处理 ⚡手动","requires": ["zone_j_prompt_moat.txt"],                "produces": ["moat_assessment.json", "capex_classification.json", "earnings_quality.json", "data_discount.json"]},
    {"step": 4,   "phase": 3,   "zone": "A_precise",  "name": "Phase 3 Zone A 精算(消费ZoneJ)","requires": ["moat_assessment.json"],                "produces": ["compute_bundle_precise.json"]},
    {"step": 4.5, "phase": 3,   "zone": "rules",      "name": "Phase 3 规则引擎",            "requires": ["financial_trends.json"],                  "produces": ["rule_engine_signals.json"]},
    # Phase 4: Zone C V10 写管线（自动：模板→写作→审计→决策→来源→组装）
    {"step": 5,   "phase": 4,   "zone": "C_pipeline", "name": "Phase 4 Zone C V10写管线",    "requires": ["compute_bundle.json"],                   "produces": ["分析报告_v10.md", "run_summary.json"]},
    # Phase 5: 验证
    {"step": 6,   "phase": 5,   "zone": "quality",    "name": "Phase 5 质量门禁+增强",       "requires": ["分析报告_v10.md"],                        "produces": ["quality_gate_report.json", "enhanced_quality_report.json"]},
    {"step": 6.5, "phase": 5,   "zone": "verify",     "name": "Phase 5 数字溯源+证据验证",   "requires": ["分析报告_v10.md"],                        "produces": ["verification_report.json"]},
]

def find_stock_dir(code):
    for e in os.listdir(OUTPUT_DIR):
        if (e.startswith(code.replace(".","_")) or e.startswith(code.split(".")[0]+"_")) and os.path.isdir(os.path.join(OUTPUT_DIR, e)):
            return os.path.join(OUTPUT_DIR, e)
    return None

def state_path(code): return os.path.join(find_stock_dir(code) or OUTPUT_DIR, f".pipeline_state.json")

def load_state(code):
    sp = state_path(code)
    if os.path.exists(sp):
        with open(sp) as f: return json.load(f)
    return {"code": code, "completed_steps": [], "started_at": datetime.now().isoformat()}

def save_state(code, state):
    state["updated_at"] = datetime.now().isoformat()
    d = find_stock_dir(code)
    if not d: d = OUTPUT_DIR
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, ".pipeline_state.json"), "w") as f:
        json.dump(state, f, indent=2, default=str)

def check_requirements(code, step_def):
    """Check if all required files exist for this step."""
    d = find_stock_dir(code)
    if not d:
        return False, [f"output dir not found for {code}"]
    missing = []
    for f in step_def["requires"]:
        if not os.path.exists(os.path.join(d, f)):
            missing.append(f)
    return len(missing) == 0, missing

def check_produced(code, step_def):
    """Check which produced files already exist."""
    d = find_stock_dir(code)
    if not d:
        return False, []
    existing = [f for f in step_def["produces"] if os.path.exists(os.path.join(d, f))]
    all_exist = len(existing) == len(step_def["produces"])
    return all_exist, existing

def run(cmd, desc):
    print(f"  🏃 {desc}...", flush=True)
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if r.returncode != 0:
        print(f"  ❌ FAILED: {r.stderr.strip()[-200:]}", flush=True)
        return False, r.stderr
    print(f"  ✅", flush=True)
    for line in r.stdout.strip().split("\n"):
        if line.strip(): print(f"     {line.strip()}")
    return True, r.stdout

def execute_step(code, step_def, state):
    """Execute a pipeline step."""
    d = find_stock_dir(code)
    if not d:
        return False

    step_num = step_def["step"]
    zone = step_def["zone"]
    print(f"\n── Step {step_num}: {step_def['name']} ──")

    # Check requirements
    ok, missing = check_requirements(code, step_def)
    if not ok:
        print(f"  ⛔ 前置条件不满足，缺少: {missing}")
        print(f"  💡 请先完成前置步骤")
        return False

    # Check if already done
    done, existing = check_produced(code, step_def)
    if done:
        print(f"  ✅ 已完成，跳过")
        state["completed_steps"] = list(set(state.get("completed_steps", []) + [zone]))
        save_state(code, state)
        return True

    if existing:
        print(f"     (已有: {existing})")

    ok = True

    # ── Step execution ──
    if zone == "pre":
        # Phase 0: 前置诊断
        contract_path = os.path.join(d, "analysis_contract.json")
        ok, _ = run([_py(), os.path.join(SCRIPTS, "pre_analysis_phase.py"),
                     "--code", code, "--output", d, "-v"], "pre_analysis_phase.py")

    elif zone == "download":
        # Phase 0.5: 年报批量下载（阻断门：<3年阻断后续）
        ok, _ = run([_py(), os.path.join(SCRIPTS, "download_report.py"),
                     "--hk", "--stock-code", code.replace(".HK", ""),
                     "--report-type", "年报", "--year", "0",
                     "--save-dir", d, "--all-years"], "download_report.py --all-years")
        if ok:
            pdfs = [f for f in os.listdir(d) if f.endswith(".pdf") and "年报" in f]
            print(f"  📄 年报 PDF: {len(pdfs)} 份")
            if len(pdfs) < 3:
                print(f"  ❌ 阻断：仅 {len(pdfs)} 份年报 PDF，需 ≥3 才能继续")
                ok = False

    elif zone == "A":
        # Phase 1: Zone A 基础计算
        contract = os.path.join(d, "analysis_contract.json")
        contract_arg = ["--contract", contract] if os.path.exists(contract) else []
        ok, _ = run([_py(), os.path.join(SCRIPTS, "compute_bundle.py"),
                     "--from-db", "--code", code, "--output", d] + contract_arg,
                    "compute_bundle.py")
        if ok:
            ok, _ = run([_py(), os.path.join(SCRIPTS, "build_financial_trends.py"),
                         "--code", code, "--output", d], "build_financial_trends.py")

    elif zone == "D":
        # Phase 1: 行业数据
        ok, _ = run([_py(), os.path.join(SCRIPTS, "zone_d_industry_context.py"),
                     "--code", code, "--output", d], "zone_d_industry_context.py")

    elif zone == "B_prompts":
        # Phase 2: Zone B prompt 生成（PDF页码定位 + 提取prompt）
        for yr_file in sorted([f for f in os.listdir(d) if f.endswith("_年报.pdf")]):
            yr = yr_file[:4]
            run([_py(), os.path.join(SCRIPTS, "pdf_page_locator.py"),
                 "--pdf", os.path.join(d, yr_file),
                 "--output", os.path.join(d, f"page_map_{yr}.json")],
                f"pdf_page_locator FY{yr}")
        ok = True
        print(f"\n  📋 Zone B: page_map 已生成。下一步需协调器调度 sub-agent 读 PDF 提取。")
        print(f"  💡 提取 mda/segments/risks/governance/audit → 保存为 {d}/ 下 .json 文件")

    elif zone == "B_llm":
        # Phase 2: Zone B LLM 手动门
        b_files = ["mda.json", "segments.json", "risks.json", "governance.json", "audit.json"]
        b_exist = [f for f in b_files if os.path.exists(os.path.join(d, f))]
        if len(b_exist) < 3:
            print(f"  ⚠️  Zone B JSON 不足 ({len(b_exist)}/5)。需协调器调度 sub-agent 提取。")
            return True  # 手动步骤，不标记失败
        ok, _ = run([_py(), os.path.join(SCRIPTS, "boundary_validator.py"),
                     "--code", code, "--boundary", "zone_b"], "boundary_validator (zone_b)")

    elif zone == "J_prompts":
        # Phase 3: Zone J prompt 生成
        if not os.path.exists(os.path.join(d, "mda.json")):
            print(f"  ⚠️  Zone B 未就绪，跳过 Zone J")
            return True
        for agent in ["moat", "capex", "earnings_quality", "data_quality"]:
            run([_py(), os.path.join(SCRIPTS, "zone_j_agent.py"),
                 "--code", code, "--agent", agent,
                 "--save-prompt", os.path.join(d, f"zone_j_prompt_{agent}.txt")],
                f"zone_j_agent.py --agent {agent}")
        ok = True
        print(f"\n  📋 Zone J prompts 已生成。需协调器调度 4 个 sub-agent 并行处理。")

    elif zone == "J_llm":
        # Phase 3: Zone J LLM 手动门
        j_files = ["moat_assessment.json", "capex_classification.json",
                   "earnings_quality.json", "data_discount.json"]
        j_exist = [f for f in j_files if os.path.exists(os.path.join(d, f))]
        if len(j_exist) < 4:
            print(f"  ⚠️  Zone J JSON 不足 ({len(j_exist)}/4)。需协调器调度 sub-agent。")
            return True
        run([_py(), os.path.join(SCRIPTS, "boundary_validator.py"),
             "--code", code, "--boundary", "zone_j"], "boundary_validator (zone_j)")
        ok = True

    elif zone == "A_precise":
        # Phase 3: Zone A 精算（消费 Zone J 参数）
        zone_j_dir = d if os.path.exists(os.path.join(d, "moat_assessment.json")) else None
        cmd = [_py(), os.path.join(SCRIPTS, "compute_bundle.py"),
               "--from-db", "--code", code, "--output", d]
        if os.path.exists(os.path.join(d, "analysis_contract.json")):
            cmd += ["--contract", os.path.join(d, "analysis_contract.json")]
        if zone_j_dir:
            cmd += ["--zone-j", zone_j_dir]
        ok, _ = run(cmd, "compute_bundle.py --zone-j")

    elif zone == "rules":
        ok, _ = run([_py(), os.path.join(SCRIPTS, "rule_engine.py"),
                     "--code", code], "rule_engine.py")

    elif zone == "C_pipeline":
        # Phase 4: Zone C V10 写管线（自动：模板→写作→审计→决策→组装）
        ok, _ = run([_py(), os.path.join(SCRIPTS, "zone_c_chain.py"),
                     "--code", code, "--pipeline"], "zone_c_chain.py --pipeline")

    elif zone == "quality":
        # Phase 5: 质量门禁 + 增强
        ok, _ = run([_py(), os.path.join(SCRIPTS, "quality_gate.py"),
                     "--code", code], "quality_gate.py")
        run([_py(), os.path.join(SCRIPTS, "enhanced_quality_gate.py"),
             "--code", code], "enhanced_quality_gate.py")  # best-effort

    elif zone == "verify":
        # Phase 5: 数字溯源 + 证据验证
        ok, _ = run([_py(), os.path.join(SCRIPTS, "citation_verifier.py"),
                     "--code", code], "citation_verifier.py")
        run([_py(), os.path.join(SCRIPTS, "citation_verifier.py"),
             "--code", code, "--evidence-only"], "citation_verifier.py --evidence-only")

    # Update state
    if ok:
        state["completed_steps"] = list(set(state.get("completed_steps", []) + [zone]))
        save_state(code, state)

    return ok

def show_status(code, state):
    """Display pipeline progress."""
    d = find_stock_dir(code)
    print(f"\n🐢 Pipeline Status: {code}")
    print(f"   Output: {d or 'NOT FOUND'}")
    print(f"   Started: {state.get('started_at', '?')[:19]}")
    print()
    print(f"{'Step':<6} {'Phase':<7} {'Status':<10} {'Description'}")
    print("-" * 65)
    for s in PIPELINE:
        zone = s["zone"]
        phase = f"P{s.get('phase', '?')}"
        if zone in state.get("completed_steps", []):
            status = "✅ DONE"
        elif any(not os.path.exists(os.path.join(d, f)) if d else True for f in s["requires"]):
            status = "⛔ BLOCKED"
        else:
            _, existing = check_produced(code, s) if d else (False, [])
            if existing and len(existing) > 0:
                status = "🔄 PARTIAL"
            else:
                status = "⬜ READY"
        print(f"  {str(s['step']):<5} {phase:<7} {status:<10} {s['name']}")
    print()

def main():
    p = argparse.ArgumentParser(description="run_pipeline.py — V10 Pipeline Coordinator（与coordinator_v10.md同步）")
    p.add_argument("--code", required=True)
    p.add_argument("--status", action="store_true", help="Show pipeline progress")
    p.add_argument("--resume", action="store_true", help="Resume from first incomplete step")
    p.add_argument("--step", type=int, choices=range(1, 12), help="Run specific step")
    args = p.parse_args()

    state = load_state(args.code)

    if args.status:
        show_status(args.code, state)
        return 0

    # Find/create output dir
    conn = sqlite3.connect(DB_PATH); conn.row_factory = sqlite3.Row
    stock = conn.execute("SELECT * FROM stocks WHERE ts_code=?", (args.code,)).fetchone()
    conn.close()
    if not stock:
        print(f"❌ {args.code} not in DB", file=sys.stderr); return 1
    d = find_stock_dir(args.code)
    if not d:
        d = os.path.join(OUTPUT_DIR, f"{args.code.replace('.','_')}_{stock['name_cn']}")
        os.makedirs(d, exist_ok=True)

    print(f"🐢 Turtle V7 Coordinator: {args.code}")
    print(f"   DB: {DB_PATH}")

    if args.step:
        s = PIPELINE[args.step - 1]
        ok = execute_step(args.code, s, state)
        return 0 if ok else 1

    # Resume mode: find first incomplete step
    completed = set(state.get("completed_steps", []))
    for s in PIPELINE:
        if s["zone"] not in completed:
            ok = execute_step(args.code, s, state)
            if not ok:
                print(f"\n❌ Pipeline stopped at Step {s['step']}: {s['name']}")
                print(f"   修复问题后运行: python3 scripts/run_pipeline.py --code {args.code} --resume")
                return 1
            # For manual LLM steps, stop and let user process
            if s["zone"] in ("B_llm", "J_llm", "C_llm"):
                state["completed_steps"] = list(set(state.get("completed_steps", []) + [s["zone"]]))
                save_state(args.code, state)
                show_status(args.code, state)
                print(f"✅ 自动化步骤完成。下一步需要手动 LLM 处理。")
                print(f"  完成后运行: python3 scripts/run_pipeline.py --code {args.code} --resume")
                return 0
        else:
            print(f"  ✅ Step {s['step']}: {s['name']} (已完成，跳过)")

    show_status(args.code, state)
    print(f"✅ 全管道完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())
