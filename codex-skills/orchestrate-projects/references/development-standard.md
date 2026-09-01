# Development governance reference

## Required artifacts

- `GOALS.md`: coordination truth for milestones, decisions, blockers, and evidence.
- Domain roadmap: product/technical truth; do not duplicate it into GOALS.
- `progress-dashboard.html`: compact status surface for the active goal, milestones, evidence, blockers, and recent decisions.
- `.project-governance.json`: branches, prefixes, worktree root, and verification profiles.
- Project guard plus `.githooks/`: local enforcement.
- `.project/evidence/latest.json`: ignored verification record bound to branch and commit.

## Milestone lifecycle

Use `PLANNED → IN_PROGRESS → VALIDATING → COMPLETE`, with `BLOCKED` only for a real impasse. One active Goal must correspond to one active milestone. New evidence may change scope or completion evidence, but the decision must be recorded.

Before completing a milestone, require implementation evidence, roadmap audit, code review, relevant local/device verification, and updated project state.

## Isolation and merging

Treat `main/master` as integration-only. Require a linked worktree, a fresh branch using an allowed prefix, and a single coherent objective. Run verification after committing from a clean tree. Store the tested branch and HEAD commit in evidence; invalidate evidence after any new commit.

When the root repository has an ignored `.venv/`, `start` links that environment into the new worktree and adds `.venv` to the repository-local Git `info/exclude`; the environment stays out of commits and does not make the worktree dirty.

`merge-check` is readiness evidence, not permission to merge. Remote repositories should additionally require PRs, independent review, required checks, and disabled force pushes.

Existing dirty protected worktrees are a migration state. Inventory, test, review, snapshot, and obtain the user's baseline decision. Never hide the problem with automatic reset/stash or by creating a worktree from a HEAD that omits uncommitted work.

## Verification profiles

- `docs`: configuration and documentation validation only.
- `fast`: focused tests for iteration.
- `full`: complete merge gate.

The project owns the commands. Database changes, backups, permissions, browser flows, device behavior, external integrations, and expensive real runs may require evidence beyond automated tests.

## Coordination

Keep the coordinator focused on objectives, constraints, decisions, state, and evidence. Workers return conclusions, changes, evidence, and next action. Use separate visible threads for durable audits/reviews and local Computer Use testing; use subagents only for authorized bounded tasks.

Report state as 已完成 / 下一步 / 阻断项. Do not convert normal intermediate findings into user approval steps.
