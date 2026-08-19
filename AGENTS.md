# Codex Repo Guide

This repository was originally organized around Claude Code slash commands under `.claude/commands/`.
When working here with Codex, treat those files as workflow specifications, not as the only entrypoint.

## Primary Workflows

- `/business-analysis`
  - Source spec: `.claude/commands/business-analysis.md`
  - Codex wrapper: `scripts/codex_workflow.py business-analysis --code <code>`
  - Main deterministic entrypoint: `scripts/tushare_collector.py`
  - Typical outputs: `output/{code}_{company}/data_pack_market.md`, `qualitative_report.md`
- `/valuation`
  - Source spec: `.claude/commands/valuation.md`
  - Codex wrapper: `scripts/codex_workflow.py valuation --code <code>`
  - Main deterministic entrypoint: `scripts/valuation_engine.py`
  - Typical outputs: `output/{code}_{company}/valuation_computed.md`, valuation report
- `/turtle-analysis`
  - Source spec: `.claude/commands/turtle-analysis.md`
  - Codex wrapper: `scripts/codex_workflow.py turtle-analysis --code <code>`
  - Depends on prior business-analysis outputs
  - Typical outputs: final strategy report in `output/{code}_{company}/`
- `/download-annual-report`
  - Source spec: `.claude/commands/download-annual-report.md`
  - Main deterministic entrypoint: `scripts/download_report.py`

## Agent Execution Rules

### Report Generation (ALL agents MUST follow)

1. Full reports use the current automatic unified pipeline in `scripts/turtle_agent/run.py`. The historical fixed four-agent chain and 600-line minimum are obsolete; length is not a quality proxy.
2. Publication requires the completion contract and V3 decision/data/model gates. Clear prose cannot offset a critical fact, identity, model, or decision inconsistency.
3. Ordinary repair passes may edit only their target chapters. They must not mutate structured ledgers, synthesis findings, review decisions, or assembly state.
4. A synthesis-only pass may update structured synthesis artifacts but must not rewrite already-passed chapters.
5. Sources are chapter-attributed. Low-authority relay/search/social pages cannot be the sole support for a material claim; return to annual reports, filings, regulators, official statistics, industry bodies, or other directly reviewable sources.

### Real-run resource discipline

1. Treat a real LLM run as acceptance of an offline-tested framework change, never as an iterative live-debugging loop.
2. Before a long run, report the preflight call/time upper bound and stop conditions. Pass `--approve-expensive-run` only after explicit one-time or standing operator approval. The standing authorization recorded in `docs/RUNTIME_OPERATIONS.md` satisfies this requirement without asking before every bounded run.
3. Run at most one long real baseline per development stage without one-time or standing operator authorization. Standing authorization does not relax resource discipline: once a framework defect is found, stop the run, fix it offline, and pass local regression before retrying.
4. Two consecutive repair passes with an unchanged blocker set must trip the no-progress circuit breaker. Do not bypass it by increasing pass counts.
5. Background runs are checked at phase/pass milestones. Do not poll every few seconds or repeatedly reread large logs.
6. Never reduce evidence, reasoning, valuation consistency, or decision gates merely to save tokens. Reduce replay, duplicate context, redundant prose, and unnecessary reruns instead.

### Codex Execution Rules

1. Prefer real Python scripts over paraphrasing command docs.
2. Use `.venv/bin/python` when `.venv/` exists.
3. Reuse existing files in `output/{code}_{company}/` before recomputing.
4. If a Claude workflow step assumes agent-only WebSearch behavior, adapt pragmatically:
   - run deterministic script steps directly
   - use existing PDFs and markdown outputs
   - write the missing markdown deliverable in the repo's expected format
5. Keep output filenames and directories consistent with existing repo conventions.
6. Prefer emitting scaffold and handoff files when a workflow still requires non-deterministic report writing.
7. If `--write-report` is available in `scripts/codex_workflow.py`, prefer it when the user wants Codex to continue writing the real report files directly.
8. For Tushare broker/proxy setups, the repo accepts `TUSHARE_API_URL`, `TUSHARE_HTTP_URL`, or `API_URL`.
9. For `business-analysis`, prefer reusing the latest 5 annual-report PDFs already present in `output/{code}_{company}/` and use them as multi-year primary sources.

### Session Bootstrap And Isolation

When a new Codex session is asked to continue, improve, or repair this project, restore project state before editing:

1. Read `GOALS.md`, `docs/CURRENT_DOCUMENTS.md`, `progress-dashboard.html`, the current domain roadmap, and this file. Treat the active milestone and recorded blockers as the starting state; do not silently activate a later milestone. Never restore current state from `docs/History/`.
2. Run `git status --short --branch`. `main` and `master` are integration-only. If the protected worktree is dirty, stop and record the baseline blocker; never reset, stash, or edit it to begin a task.
3. For any write, start a fresh linked worktree and branch from clean `main` with `.venv/bin/python scripts/project_guard.py start <kind> <slug>`. Do not modify files in the primary worktree before `start` succeeds.
4. Keep one coherent objective per worktree. Commit from that worktree, then run `.venv/bin/python scripts/project_guard.py verify full` and `merge-check`; verification evidence must match the current branch and commit.
5. Before integration, complete the independent code review, roadmap audit, and any required real-run or Computer Use checks. Update `GOALS.md` and `progress-dashboard.html` only from an isolated worktree.

Current-state document searches should exclude `docs/History/` by default. Search History only when the task explicitly needs design provenance, an old failure, or audit reconstruction.

Read-only investigation may remain in the primary worktree, but any generated report, configuration, documentation, or source change follows the same isolation and verification gates. When the `orchestrate-projects` skill is available, activate it for long-running coordination rather than relying on conversation history alone.

## Important Paths

- `.claude/commands/` — original command specs
- `strategies/` — workflow coordination and report instructions
- `shared/qualitative/` — qualitative framework
- `scripts/` — deterministic entrypoints and helpers
- `output/` — generated analysis artifacts

## For Future Codex Users

If you want reusable Codex-native workflow definitions from inside the repo, check `codex-skills/`.
