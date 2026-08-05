---
name: orchestrate-projects
description: Set up and coordinate long-running software projects with milestone-based GOALS.md roadmaps, one active Goal at a time, concise status dashboards, independent milestone audits, local Computer Use verification, and mandatory linked-worktree/branch/test gates before main. Use when the user asks to coordinate a long-running project, adopt the Codex collaboration workflow, create GOALS.md or a progress dashboard, enforce worktree development, or bootstrap the same governance in another repository.
---

# Orchestrate Projects

## Establish the project state

1. Read every applicable `AGENTS.md` and existing roadmap before changing files.
2. Identify repository boundaries, protected branches, remotes, test entrypoints, and dirty working trees.
3. Reflect the user's durable objective separately from implementation milestones.
4. Preserve existing domain roadmaps as truth sources; make `GOALS.md` a coordination overlay instead of rewriting product intent.

Read [references/development-standard.md](references/development-standard.md) before defining gates or milestone completion evidence.

## Maintain the roadmap

Create or update `GOALS.md` with:

- the durable project objective;
- milestone outcome, scope, decisions, blockers, and completion evidence;
- exactly one milestone marked as the current Goal;
- a short dated decision log.

Keep only one Goal-mode objective active. Complete it only after its agreed evidence and end-of-milestone audit exist. Do not activate the next objective merely because implementation stopped.

Maintain `progress-dashboard.html` when the project has multiple milestones or workers. Show only the active goal, milestones, evidence, recent decisions, and the three status sections: 已完成、下一步、阻断项.

## Coordinate execution

Keep the main thread at coordination altitude. Workers return conclusions, changes, evidence, and recommended next action—not full transcripts.

Use separate visible threads for work the user may revisit, especially roadmap audits, code reviews, and local Computer Use tests. Use bounded subagents only when delegation is authorized and a persistent visible history is unnecessary.

After every milestone:

1. Audit `GOALS.md` against code and evidence.
2. Run `/review` or an equivalent independent code review.
3. Resolve blocking findings.
4. Run required local/browser/device checks.
5. Update roadmap and dashboard before changing the active Goal.

## Enforce isolated development

Bootstrap reusable files with:

```bash
python3 codex-skills/orchestrate-projects/scripts/bootstrap_project.py \
  --repo /path/to/repo --name "Project Name" --type python
```

Supported types are `python`, `android`, and `generic`. The bootstrapper refuses to overwrite files unless `--force` is explicitly provided.

After adapting `.project-governance.json`:

1. Run the installed guard's `self-test`.
2. Configure `core.hooksPath=.githooks` only after inspecting an existing hooks configuration.
3. Verify that `preflight` fails in the protected primary worktree.
4. Create future work with `project_guard.py start <type> <slug>`.
5. Commit in the linked worktree, run `verify full`, then `merge-check`.

Never reset, stash, relocate, or commit a pre-existing dirty main worktree automatically. Record it as a baseline-migration blocker and require a safe audit/freeze decision.

## Report state

Whenever state changes, report only:

- 已完成
- 下一步
- 阻断项

Attach the shortest useful evidence: commit, test command, artifact hash, screenshot, or device log. Ask for approval only at genuine authority boundaries such as destructive baseline handling, expensive runs, external publication, remote branch settings, or a material change of objective.
