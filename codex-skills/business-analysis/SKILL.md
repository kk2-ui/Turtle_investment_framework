---
name: business-analysis
description: Run the standalone Business Model and Moat qualitative analysis workflow in this Turtle Investment Framework repository. Use when the user wants `/business-analysis`, 商业分析, 定性分析, 护城河分析, or the prerequisite outputs for valuation and turtle-analysis.
---

# Business Analysis

Use this skill only inside the `Turtle_investment_framework` repo.

## Read First

1. Read `.claude/commands/business-analysis.md` for the workflow contract.
2. Read `scripts/config.py` to normalize stock codes when needed.
3. Reuse existing PDFs and outputs in `output/{code}_{company}/` before recomputing.

## Execution

1. Create or reuse `output/{code}_{company}/`.
2. Prefer `python3 scripts/codex_workflow.py business-analysis --code {code}` to run the deterministic preparation steps.
3. If a suitable annual report PDF already exists in the output directory, use it.
4. If no suitable PDF exists, use `scripts/download_report.py` or direct exchange/disclosure PDF links to fetch one.
5. Use the workflow specs in `shared/qualitative/` and `strategies/turtle/phase2_PDF解析.md` to produce:
   - `data_pack_report.md` when PDF extraction is possible
   - `qualitative_report.md`
6. Only produce HTML when the user explicitly asks for it.

## Deliverables

- `output/{code}_{company}/data_pack_market.md`
- `output/{code}_{company}/data_pack_report.md` when PDF extraction succeeds
- `output/{code}_{company}/qualitative_report.md`
