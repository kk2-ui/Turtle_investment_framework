#!/usr/bin/env python3
"""V12 Agent Loop 一键运行 — 使用 DeepSeek API。

用法:
    export ANTHROPIC_API_KEY="sk-xxx"
    python3 scripts/run_v12_agent.py
"""

import os, sys, time

_scripts_dir = os.path.join(os.path.dirname(__file__), "turtle_agent")
sys.path.insert(0, _scripts_dir)

from llm_client import LlmClient
from tool_registry import ToolRegistry
from agent_loop import TurtleAgent, AgentConfig

# Config
CODE = "01502"
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output", "01502_金融街物业")
CONTRACT_PATH = os.path.join(OUTPUT_DIR, "analysis_contract.json")
TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "..", "templates", "report_template_v12.md")
MAX_ITERATIONS = 40  # 15 chapters × ~2-3 rounds each

# Check API key
key = os.environ.get("ANTHROPIC_API_KEY", "")
if not key:
    print("❌ 请设置 ANTHROPIC_API_KEY 环境变量")
    sys.exit(1)

print(f"API Key: {key[:10]}...")
print(f"Output: {OUTPUT_DIR}")
print(f"Template: {TEMPLATE_PATH}")
print(f"Max iterations: {MAX_ITERATIONS}")
print()

# LLM client
llm = LlmClient(provider="deepseek", model="deepseek-chat")
print(f"LLM: {llm._provider} / {llm._model}")

# Tools
tools = ToolRegistry()
for mod in [
    "turtle_agent.tools.read_tools",
    "turtle_agent.tools.calc_tools",
    "turtle_agent.tools.write_tools",
    "turtle_agent.tools.phase_tools",
]:
    n = tools.auto_discover(mod)
    print(f"  {mod}: {n} tools")

# Agent
config = AgentConfig(
    code=CODE,
    contract_path=CONTRACT_PATH,
    output_dir=OUTPUT_DIR,
    max_iterations=MAX_ITERATIONS,
    template_path=TEMPLATE_PATH,
)

agent = TurtleAgent(llm=llm, tools=tools, config=config)

start = time.time()
try:
    report_path = agent.analyze()
    elapsed = time.time() - start
    print(f"\n{'='*60}")
    print(f"✅ 分析完成 ({elapsed:.0f}s)")
    print(f"📄 {report_path}")
    print(f"{'='*60}")
except Exception as e:
    elapsed = time.time() - start
    print(f"\n❌ 失败 ({elapsed:.0f}s): {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
