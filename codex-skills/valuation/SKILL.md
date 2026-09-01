---
name: valuation
description: Run the valuation workflow in this Turtle Investment Framework repository. Use when the user wants `/valuation`, 估值分析, 估值报告, or `valuation_computed.md`.
---

# Valuation

Use this skill only inside the `Turtle_investment_framework` repo.

## Read First

1. Read `.claude/commands/valuation.md`.
2. Confirm `output/{code}_{company}/qualitative_report.md` and `data_pack_market.md` already exist.
3. Read `strategies/valuation/coordinator.md` if you need the full report structure.

## Execution

1. Prefer `python3 scripts/codex_workflow.py valuation --code {code}` to run the deterministic valuation step.
2. Use `valuation_computed.md` plus the existing qualitative report to assemble the final valuation report when requested.
3. Keep outputs in the existing repo naming convention.

## Deliverables

- `output/{code}_{company}/valuation_computed.md`
- `output/{code}_{company}/{company}_{code}_估值报告.md` when a full report is requested
