---
name: turtle-analysis
description: Run the full Turtle Investment Framework downstream strategy workflow in this repository. Use when the user wants `/turtle-analysis`, 龟龟策略, 龟龟分析, or the final strategy report.
---

# Turtle Analysis

Use this skill only inside the `Turtle_investment_framework` repo.

## Read First

1. Read `.claude/commands/turtle-analysis.md`.
2. Confirm business-analysis outputs already exist:
   - `qualitative_report.md`
   - `data_pack_market.md`
3. Read `.claude/commands/turtle-analysis.md` and the current unified report pipeline instructions if report assembly details matter.

## Execution

1. Prefer `python3 scripts/codex_workflow.py turtle-analysis --code {code}` to refresh the deterministic prerequisite data.
2. Reuse `data_pack_report.md` if present.
3. Follow `strategies/turtle/phase3_quantitative.md` and `strategies/turtle/phase3_valuation.md`; the historical preflight reference is archived under `strategies/turtle/legacy/`.

## Deliverables

- `output/{code}_{company}/{company}_{code}_分析报告.md`
