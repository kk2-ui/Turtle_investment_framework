# Codex Repo Guide

This repository was originally organized around Claude Code slash commands under `.claude/commands/`.
When working here with Codex, treat those files as workflow specifications, not as the only entrypoint.

## Judgment-First Research Constitution (ALL research, training, report, and review agents MUST follow)

### Objective hierarchy

1. The product is a useful best-current judgment about the enterprise and its investment consequences under uncertainty. Evidence discipline, PIT integrity, reproducibility, and auditability are hard constraints that define the admissible solution space; they are not the product or the optimization target within that space.
2. A clean audit trail with no decision-relevant judgment is incomplete. A research cycle must improve at least one of: understanding of the business mechanism, assessment of management action or execution, permanent-loss risk, normal earnings or owner cash, valuation range, or the conditions for a better entry price.
3. Facts require appropriate evidence. Judgments may combine verified facts with clearly identified economic inference. Do not demand direct causal proof before stating a bounded, falsifiable view; reserve causal language and authority for claims that actually require it.
4. When evidence is incomplete, localize the uncertainty to the affected claim and continue. Preserve the strict boundary for that claim without discarding unrelated facts, mechanisms, or investment implications.

For every whole-company research, synthesis, valuation-routing, or report task,
the primary reasoning object is the `EnterpriseUnderwritingEpisode` defined in
`docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md`.  The
Agent must connect situation/regime, industry cycle versus structural damage,
company position and adaptation, survival, normalized economics, owner cash,
permanent-loss paths, value route, and price-facing treatment into one
continuous thesis.  Macro variables enter only through a demonstrated company
transmission.  The existing eight dimensions, E/J stages, fields, receipts,
and gates remain supporting views; do not use them as the reader-facing
structure or as substitutes for the underwriting conclusion.

Every whole-company report must also own an `IndustryFutureThesis` inside the
Episode's Situation Model. It states the relevant horizon, the most likely
industry regime and strongest rival, how demand/supply/competition move the
profit pool, how this company is exposed and can adapt, and how that path
changes normalized economics, owner cash, permanent loss, valuation, or price
treatment. A trend inventory, several equally weighted scenarios, or a list of
monitoring indicators does not satisfy this requirement. When calibrated base
rates do not exist, make a bounded qualitative judgment instead of inventing
probabilities.

Before forming that thesis, compile an `IndustryUnderwritingContext` from the
available IndustryLearningBlock, official industry observations, reviewed
mechanisms, company archetypes, worked cases, and near misses. It must explain
the industry's customer job, value chain, structural epoch, profit-pool
movement, heterogeneous company responses, and mechanism-role peers. A fixed
two-or-three-company comparison is not an industry model. Missing optional
peers or a mature mechanism card narrows the context but does not block the
company judgment. The context supplies reference classes and questions; only
the target company's evidence can establish its exposure, adaptation, or
economics.

### Required judgment return

Every substantive company or industry synthesis, training readout, or report task must return, in investor language:

1. the best-current directional or conditional judgment and its confidence or range;
2. the decisive evidence and economic mechanism, not an inventory of every collected field;
3. the strongest competing explanation and why it is currently more or less plausible;
4. the consequence for business quality, permanent loss, owner cash, valuation, or research/buy treatment within the task's authority; and
5. the observation or event that would reverse the judgment.

These are substance requirements, not mandatory reader-facing headings. Status codes, receipts, schemas, and gate names may support the return but cannot replace it.
Bounded acquisition, implementation, and audit subtasks do not claim final synthesis authority. If they touch material company evidence, they must still state the local economic implication, strongest plausible alternative, and discriminating next observation; pure engineering returns must state their material relevance.
Reader-facing prose leads with the economic conclusion. Attach each caveat to the claim it limits; do not front-load governance language, permission disclaimers, or a wall of `UNKNOWN` states.
Distinguish confidence in the evidence or inference from the probability of the business outcome. Use qualitative confidence when no calibrated base rate exists; never manufacture a percentage merely to appear decisive.
Non-disclosure and a non-decisive observed proxy are not conflicting or negative business evidence. They may lower attribution confidence, but must not mechanically lower management, owner cash, permanent-loss protection, or normal earnings without an observed economic carrier.
Propagate an update only along the responsibility-matched economic mechanism it supports. Better funding does not by itself reduce customer, brand, product-lifecycle, inventory-absorption, or capital-return risk; a product option does not upgrade an unaffected core.
Probability and confidence updates must keep the proposition and risk axis stable. Every material branch named in a scenario must map to its outcome treatment; a coarse scenario label or score must not override offsetting continuous facts.
Every directional comparison must preserve the metric, responsibility boundary, base period, and comparison clock. Stability relative to an older anchor must not be narrated as stability in the latest period.
Capacity, store, acquisition, product, or project completion settles an implementation milestone only. Management execution, owner cash, and capital return require the post-completion customer, utilization, unit-economics, and cash-absorption evidence relevant to the claim.

### Non-evasive uncertainty

1. `UNKNOWN`, `MIXED`, `NO_PRIMARY`, `MEASUREMENT_MISMATCH`, and `EVIDENCE_INELIGIBLE` are local evidence states, not acceptable whole-case conclusions.
2. Convert every material unknown into at least one useful treatment: a conservative range, explicit scenarios, a conditional conclusion, an investment consequence, or a targeted discriminating probe. If no directional underwriting is supportable, say what should not be paid for or relied upon and why.
3. Excluding an unproven mechanism or growth option from the base case does not mean zero value or business failure. Preserve it in a labeled scenario when economically plausible, with the evidence needed for promotion.
4. Do not equate a missing exact field with a missing business judgment. Use a disclosed proxy or conservative interval when it is economically fit; keep the exact field unknown. Never fill a genuine unknown with invented precision.
5. After the same acquisition or measurement blocker recurs twice, do not add another gate or repeat the same search. Either route a specific decision-changing question to a source or expert likely to resolve it, or bound the uncertainty, record its consequence, and continue the rest of the case.
6. A defer or escalation is valid only when it names the receiving role or source, why that receiver is more likely to resolve the issue, the exact deliverable, and the judgment or treatment it could change. A destination-free `NEEDS_CURATOR` or `NEEDS_REVIEW` is not completion.
7. Comparative or causal identification is required only for the causal claim it would authorize. It must not block company reconstruction, industry learning, mechanism hypotheses, forecasting, or bounded underwriting that does not claim that authority.

### Research allocation and stopping

1. Start from the few questions most capable of changing the investment treatment. Allocate effort in this order: material business mechanism and rival explanations, decision-relevant evidence, then audit and presentation.
2. Stop expanding evidence once a reasonable reviewer can reproduce the material facts and the remaining uncertainty is bounded in the judgment. Do not optimize for field completion, document count, report length, or artifact count.
3. Add a new mandatory gate only after naming a demonstrated failure that could materially change the enterprise judgment, permanent-loss assessment, valuation, expected return, or central thesis, and showing why a local downgrade cannot contain it.
4. Repository hygiene, naming, formatting, and unavailable immaterial fields are non-blocking unless they create a concrete risk of a wrong investment conclusion.

### Training and evaluation

0. Start whole-company training through `scripts/enterprise_underwriting_training.py run <contract> --output-dir <dir>`.  That command invokes the training model from the contract-bound source package and completes only after the generated full `EnterpriseUnderwritingEpisode` validates and is persisted. Teaching, Blind/Holdout, and Prospective tracks select source visibility and the Episode sample identity; a prewritten Episode passed to a validator, legacy curriculum counts, axes, settled fields, and receipts cannot complete a training run.
1. Training success means that a later unseen case produces a better judgment or treatment: a material error is avoided, a mechanism is recognized earlier, an uncertainty range is better calibrated, or a valuation/research action changes for a stated economic reason.
2. Settled fields, passed validators, preserved blindness, and completed receipts establish integrity but do not by themselves establish learning. An episode that only proves "cannot judge" may be retained as a boundary lesson, but it is not a judgment-improvement success.
3. A minimal real learning episode may concern one company and one material mechanism. Require a comparative panel only when the intended lesson is relative or causal.
4. Evaluate enhanced research against a simple same-cutoff baseline under comparable evidence and research budgets. Prefer the method only when it produces a material judgment improvement, not merely more prose, dimensions, or caveats.
5. Assess judgment quality and coverage of the material questions together. High reliability on a shrinking set of easy claims is not success; coverage is not a quota and must not induce fabricated certainty.

### Agent and reviewer roles

1. The investigator gathers facts and reconstructs mechanisms; the challenger develops the strongest rival explanation; the evidence reviewer checks only material support and inference boundaries; one synthesizer owns the final best-current judgment. Role count and voting do not create truth.
2. Reviewers first assess whether the work answers the investor's real question and whether its central mechanism and treatment are directionally defensible. They may block only a defect that can materially change the company judgment, permanent-loss assessment, valuation, return, or central explanatory thesis.
3. A blocking return must classify the root cause as `DATA_COVERAGE`, `ACQUISITION_MODULE`, `REASONING`, `MODEL`, or `WRITING`, and state the economic impact, missing facts, prohibited assumptions, executable remediation, and acceptance criteria. All other findings are non-blocking notes.
4. Review must not respond to uncertainty by demanding exhaustive proof, adding a global gate, or converting a local defect into a whole-case refusal. The preferred repair is the smallest change that improves the investor's judgment.
5. Coordinators must carry this objective hierarchy and return contract into delegated prompts. A narrower workflow may strengthen evidence requirements for its claim, but must not redefine local uncertainty or missing authority as whole-case failure.

The unified objective hierarchy, runtime/training split, and next paired acceptance
test are recorded in
`docs/development/research/TURTLE_JUDGMENT_FIRST_DECISION_FOCUSED_INTEGRATED_DESIGN.md`.
The current top-level company judgment and training object is recorded in
`docs/development/research/TURTLE_ENTERPRISE_UNDERWRITING_SYSTEM_V1.md`.
The detailed runtime rationale remains in
`docs/development/research/TURTLE_JUDGMENT_FIRST_AGENT_CONSTITUTION.md`; the
episode, feedback, and transfer semantics remain in
`docs/development/research/TURTLE_DECISION_FOCUSED_ENTERPRISE_JUDGMENT_TRAINING_ARCHITECTURE.md`.

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
5. Candidate branches must inherit `.project-governance.json`'s `minimum_base_commit`. Before integration, run `.venv/bin/python scripts/project_guard.py baseline-check <candidate-branch>` from current `main`. An older worktree that predates that baseline must commit or preserve its delta, then migrate the delta to a fresh worktree from current `main`; do not merge the old branch directly.
6. Before integration, complete the independent code review, roadmap audit, and any required real-run or Computer Use checks. Update `GOALS.md` and `progress-dashboard.html` only from an isolated worktree.

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
