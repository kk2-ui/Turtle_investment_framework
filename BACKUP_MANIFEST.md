# Turtle Framework Backup Manifest

- Backup path: /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841
- Backup time: 2026-07-08 10:49:16 +0800
- Source path: /Users/xiami/workspace/analy/Turtle_investment_framework
- File count: 20526

## Key file SHA256
91db36169e13d4fe12eeaac8ff733c1b142dcbf15fdbc0883ac546ae5013e316  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/CLAUDE.md
02505751a5043bc942da58348e0e89b24db59123f7af8e46b36272a7a88a3261  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/README.md
78359c9712bc21217d184cee5fce494cd0dd26400ea62e052a97a8f80e754cb4  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/.claude/commands/turtle-analysis.md
70ce673f4ec2cf1558d071d8f3e26ff8c8bc9a0c89ab308d5009d5e622b0f16e  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/strategies/turtle/coordinator.md
461ffea7d0beae319a8fb8018934b20e57628ef231f11d0da8e9546f66a4ff58  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/strategies/turtle/phase3_preflight.md
b380d680428a014d99ba034b0f6f13e7cef19c753d67f9dffd6d66891dad8a80  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/strategies/turtle/phase3_quantitative.md
57b6de1ee16ab7b405a84de04385b05ef8857c5fcd5d1201f1e6cc727e8950f4  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/strategies/turtle/phase3_valuation.md
9e25cc4df510b26f38cfd7f2db33f1aeddba6c93194244fca6b50d2f1c6d0928  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/prompts/phase3_分析与报告.md
88fa0eb62bb5b2b2da55fa4215bffefe1e4eebc4e4c0a456075bd05716f0e4da  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/prompts/references/factor3_穿透回报率精算.md
cd1bd42ca9acbdb97c718380f07917df9263544f573d46e16ee0340cbab0ebf8  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/prompts/references/factor4_估值与安全边际.md
f894e9f3606ee9ca6ea3f969116df765b4d6f4519b96d2c23c0446dbaf907e62  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/tests/test_phase3_prompt.py
b294bbf9c567f96e24434ad54e2fccc721140aebf25968ea3c3de7048f888ce8  /Users/xiami/workspace/analy/Turtle_investment_framework_backup_20260708_104841/tests/test_coordinator.py

## Entry chain summary
- /turtle-analysis -> strategies/turtle/coordinator.md
- Runtime phase files -> strategies/turtle/phase3_preflight.md, phase3_quantitative.md, phase3_valuation.md
- Rule references -> prompts/phase3_分析与报告.md and prompts/references/*.md
- Mirror/package tree -> turtle_framework/

## Baseline note
- Path checks passed for required root framework files.
- Syntax check passed: `python3 -m py_compile scripts/tushare_modules/derived_metrics.py`.
- Pytest baseline could not run in this environment: system Python reports `No module named pytest`; project `.venv` was previously observed to point at a stale interpreter path.
- Rule-fragment scan still finds expected compatibility mentions of `CHAIN_NEXT` in historical/compatibility sections and coordinator legacy blocks; new modular rule files are present under `prompts/references/`.
