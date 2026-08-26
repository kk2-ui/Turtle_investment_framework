# Turtle Enterprise Judgment V2 Real Training Goal

> Status: `APPROVED_IMPLEMENTATION_GOAL / NOT_STARTED`
>
> Date: 2026-08-26
>
> Scope: `J0 CONTRACT + J1 INDUSTRY BLOCK + J1A RECONSTRUCTION + J2 THREADS`

## 1. Objective

Implement the smallest real training path that teaches Turtle to understand an
industry, a company, management decisions, execution and changing conditions.
Schema and synthetic tests alone do not complete this Goal.

This Goal has two factual milestones:

1. `REAL_SAMPLE_CREATED`: freeze and validate one real, cutoff-safe
   `IndustryLearningBlock` with real `EnterpriseJudgmentEpisode` E0/E1
   reconstructions;
2. `REAL_FEEDBACK_TURN_COMPLETED`: for at least one predeclared company-cutoff
   transition, reveal the next authorized disclosure window, settle material
   operating or decision-consequence cells, and record a concrete change to
   the next cutoff's research agenda.

The first milestone proves that real training has started. Only the second
completes this Goal. Neither proves method transfer or investment usefulness.

The center is:

```text
industry evolution
  -> company state and constraints
  -> feasible alternatives and management decisions
  -> execution and adaptation
  -> customer / operating / competitive / cash / capital consequence cells
  -> conditional insight and next research question
```

This Goal does not require H2, a final comparator panel, a directional
Comparative result, method freeze, R-61/R-103 access, CJO, valuation, report or
investment permission.

## 2. Authoritative Decisions

Read and obey, in order:

1. repository `AGENTS.md`;
2. repository `GOALS.md`;
3. `docs/CURRENT_DOCUMENTS.md`;
4. `TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md`;
5. `TURTLE_HISTORICAL_TRAINING_SYSTEM_REDESIGN.md`;
6. `HISTORICAL_PIT_TRAINING_COHORT_REGISTER.md`.

The 2026-08-26 V2 decision supersedes any older statement that makes
`SELECTION_ADMITTED`, H2 or Comparative a global prerequisite. Those remain
mandatory only for the claim and permission levels that use them.

## 3. Reuse Before Adding

Reuse these existing objects and validators:

- `EnterpriseSystemModel`, `ManagementDecisionLedger`, responsibility units,
  arenas and graph projections in `scripts/enterprise_judgment_v3.py`;
- industry universe, lifecycle and multi-cutoff history in
  `scripts/judgment_historical_training.py`;
- existing H1 source and receipt identities;
- current PIT time, source-role and post-cutoff rejection semantics.

`EnterpriseJudgmentEpisode` and `IndustryLearningBlock` are composite read
models. Do not create a fourth graph, second fact store, duplicate CJO,
parallel decision ledger, hash inventory or compatibility framework.

## 4. Required Runtime Objects

### 4.1 EnterpriseJudgmentEpisode manifest

The manifest references, rather than copies, current economic objects. It must
bind:

- `episode_id`, `company_id`, `issuer_id`, `company_cluster_id` and `cutoff_at`;
- industry block, risk-set snapshot and source-package identities;
- enterprise context and responsibility boundary;
- EnterpriseSystemModel and ManagementDecisionLedger slice references;
- one primary and two to four supporting judgment questions;
- an evidence coverage matrix with cell-level observation states;
- zero or more mechanism threads, each with its own H-A/H-B, evidence ceiling,
  observation clock and permitted conclusion;
- customer, operating, competition, cash, capital return, leverage and
  permanent-loss outcome cells, using `NOT_APPLICABLE` where appropriate;
- lifecycle, resolution and allowed-output permissions.

One missing or mismatched cell may block only claims that depend on that cell.
It must not invalidate unrelated context, questions or mechanism threads.

### 4.2 IndustryLearningBlock manifest

The block must bind:

- industry and mechanism-defined arena;
- a strictly increasing cutoff sequence;
- current multi-cutoff risk-set/lifecycle series;
- an `IndustryEpochMap` whose claims carry source refs or explicit unknowns;
- a `CompanyArchetypeMap` based on material economic differences rather than
  geography or labels alone;
- the episode roster and company-cluster identities;
- a `DecisionHeterogeneityMatrix` separating company conditions, alternatives,
  decisions, execution, adaptation and external conditions;
- a `ConditionalMechanismSynthesis` with moderators, break conditions,
  counterexamples and evidence ceiling;
- unresolved questions, next-sampling decision and allowed outputs.

The block may output only `INDUSTRY_CONTEXT`, `TEACHING_ONLY`,
`MECHANISM_CANDIDATE` and `RESEARCH_AGENDA` as warranted by its cells. It may
not output empirical probabilities, method freeze, report use or investment
input.

## 5. First Real Block

Use the registered China listed-cement material:

- H1 receipt: `H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1@1`;
- package:
  `docs/development/research/cohorts/COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json`;
- companies: `CN:600585`, `CN:600801`, `CN:000401`, `CN:600425`, `CN:600802`;
- existing six-cutoff history runner and current lifecycle receipts.

All five companies remain in E0 context/risk-set reconstruction. Scope or
control breaks remain useful archetype and lifecycle observations; they are
not silently removed and do not become comparator eligibility.

Before reading any later outcome window, freeze the E1 deep-reconstruction
selection rule. It must select focal/contrast episodes by materiality,
different company state and cutoff-visible field coverage, not by later
results or ease of passing. There is no fixed global company count; however,
the first block must contain enough longitudinal and cross-company variation
to exercise both dimensions. A single-company or single-cutoff block is not
acceptable.

Also freeze an ordered transition roster before outcome access. The roster
must name the first company-cutoff transition and fallback transitions using
only cutoff-visible materiality and measurement readiness. A mismatch may
advance to the next frozen transition; later results may not reorder the
roster.

For each selected E1 episode:

1. reconstruct how the company makes money and consumes capital;
2. record customer, product/channel, operating system, competition, financing
   and ordinary-share cash boundaries;
3. record feasible alternatives, including no action, when cutoff-visible;
4. separate management decision quality, execution, adaptation, external
   shock and eventual outcome;
5. freeze one primary and two to four supporting questions;
6. freeze two to three material feedback loops, not an exhaustive diagram;
7. preserve `UNKNOWN`, `INFERRED`, `EVIDENCE_INELIGIBLE` and
   `NOT_APPLICABLE` at cell level.

If the static package does not reveal a company-wide implemented action, E1
still proceeds. A narrower disclosed decision may become a Teaching or E2
thread with a narrow responsibility boundary. It must not be enlarged into a
company-wide intervention.

## 6. Prequential Training Sequence

The runner must support this order without reading future windows early:

```text
freeze industry/company state at cutoff t
  -> freeze questions and optional mechanism expectations
  -> authorize next disclosure window
  -> settle only contract-matched outcome cells
  -> preserve mismatch/censoring/unknown separately
  -> update the next cutoff research agenda
```

Multiple cutoffs for one company share a `company_cluster_id` and do not count
as independent companies. Post-cutoff facts cannot change the original E0/E1
snapshot, question wording, evidence ceiling or prediction.

The implementation Agent is authorized to create a bounded, outcome-only
custodian subtask after the pre-outcome artifacts and standalone measurement
contract are frozen. The custodian must not receive forecasts, hypotheses or
comparative identities. Absence of a pre-created curator/custodian package is
not an external blocker and must not send the system back to H2 or action
search.

If one transition ends in `MEASUREMENT_MISMATCH`, preserve it and proceed to
the next transition in the frozen roster. The Goal may be returned incomplete
only if every predeclared transition lacks a material contract-matched outcome;
that return must identify the reusable acquisition or measurement defect. It
must not respond by adding a stricter global gate.

## 7. Conditional Industry Learning

Industry synthesis must use this grammar:

```text
WHEN <industry epoch + company state + constraints>
DECISION <action or no-action>
MAY OPERATE THROUGH <mechanism>
OBSERVED AS <specific outcome cells>
UNLESS <moderators and break conditions>
EVIDENCE CEILING <context / teaching / mechanism / comparative / transferred>
```

The implementation must reject:

- universal slogans such as "capacity expansion works";
- a single company score or industry champion;
- treating peers as untreated controls without an E3 contract;
- inferring management quality from one outcome;
- turning shared macro or industry effects into company execution;
- using price, return or later survival as an operating result;
- promoting a synthesis above the weakest evidence needed for its claim.

## 8. Required Deliverables

1. A closed schema or equivalent typed validator for both composite manifests.
2. Pure/offline validation and projection APIs integrated with the existing
   V3 and historical-training modules.
3. Positive and negative synthetic fixtures for permissions, cutoff order,
   cell-local mismatch, company-cluster identity and non-causal references.
4. A real cement IndustryLearningBlock manifest and real E0/E1 episode
   artifacts using only authorized cutoff-visible sources.
5. A separate outcome-settlement artifact for at least one predeclared
   company-cutoff transition, plus the resulting next-cutoff research-agenda
   delta.
6. A human-readable review explaining the industry periods, company
   differences, decision questions, unknowns and why no permission was
   overclaimed.
7. Update `HISTORICAL_PIT_TRAINING_COHORT_REGISTER.md`,
   `docs/CURRENT_DOCUMENTS.md` and `GOALS.md` only for facts actually completed.

Prefer extending existing modules where ownership is clear. A small new
orchestration module is acceptable when it holds the composite semantics; it
must not duplicate current validators or canonical facts.

## 9. Acceptance Tests

The implementation is accepted only if tests prove:

1. all five cement companies remain in the appropriate cutoff risk sets;
2. delayed entry, scope/control breaks, censoring and exits remain distinct;
3. a company can complete E0/E1 without action, H2 or comparator;
4. one `MEASUREMENT_MISMATCH` affects only dependent cells and claims;
5. later sources cannot backfill an earlier epoch, episode or question;
6. one company across multiple cutoffs keeps one company cluster identity;
7. archetypes and relative references cannot gain causal permissions;
8. E2 may settle a narrow mechanism without upgrading the company or block;
9. E3/V5 remains strict and independent, and its absence does not block E0-E2;
10. ConditionalMechanismSynthesis retains moderators, counterexamples,
    break conditions and evidence ceiling;
11. Teaching/Industry outputs cannot unlock method freeze, holdout, CJO,
    valuation, report or investment input;
12. the real pre-outcome cement artifacts pass their validators and contain no
    price, return, post-cutoff outcome or final peer-panel claim;
13. post-cutoff observations exist only in the separately authorized
    settlement artifact, and at least one material observation changes the
    next-cutoff research agenda without rewriting the frozen episode.

Run focused tests, adjacent historical/V3/forecast regressions and the
repository's required merge gate. Do not chase unrelated cosmetic or identity
audits.

## 10. Completion and Return Rules

Do not mark complete for:

- schema and synthetic tests without a real frozen block;
- a real pre-outcome block without one settled feedback turn;
- another Minimal Historical Episode;
- an action-screen receipt without E0/E1 reconstruction;
- a narrative industry memo without typed source/permission boundaries;
- a Comparative candidate, H2 or peer panel alone.

If work is returned, classify the material root cause as `DATA_COVERAGE`,
`ACQUISITION_MODULE`, `REASONING`, `MODEL` or `WRITING`, then state economic
impact, missing facts, prohibited assumptions, executable remediation and
acceptance criteria. Missing E3 evidence is not a blocker for this Goal.

The completion statement must tell the investor:

- what the block learned about the industry and company differences;
- what it learned about management decisions and execution;
- what remains unknown;
- what changed in the next cutoff's research behavior;
- what permissions remain explicitly unavailable.
