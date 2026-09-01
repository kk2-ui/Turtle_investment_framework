# Turtle Enterprise Judgment V2 Real Training Goal

> Status: `COMPLETED_REAL_SAMPLE_AND_ROUND8_CROSS_INDUSTRY_FEEDBACK / EIGHT_DIMENSION_SKELETON_ADOPTED / ARCHITECTURE_REVISION_REQUIRED / TRANSFER_NOT_VALIDATED`
>
> Date: 2026-08-27
>
> Scope: `J0 CONTRACT + J1 INDUSTRY BLOCK + J1A RECONSTRUCTION + J2 THREADS + ROUNDS 5-8 FEEDBACK`

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

## 11. 2026-08-26 Completion Record

The first real implementation is frozen at
[`industry_learning_blocks/CN_CEMENT_2014_2018`](industry_learning_blocks/CN_CEMENT_2014_2018/):

- `04_industry_learning_block.json` retains all five H1 companies, all six
  cutoff snapshots and a sealed 20-row company-cutoff roster; the separate
  `04_pre_outcome_roster_freeze.json` binds its ordered projection to the
  pre-outcome commit before custody may settle a row;
- `01_e0_context_episodes.json` and `03_enterprise_judgment_episodes.json`
  provide real E0/E1 reconstructions; scope breaks and missing action evidence
  remain localized rather than excluding firms or fabricating management facts;
- `06_mechanism_probe.json` is a J2 state-transmission teaching probe with a
  bound H-A/H-B diagnostic; it has `action_effect_authority = NONE`;
- independent outcome custody first preserved a Huaxin perimeter
  `MEASUREMENT_MISMATCH`, then continued the frozen queue and observed the
  contract-matched Conch consolidated operating-cash cell.  Both agenda deltas
  are recorded without rewriting their original episodes;
- [`08_investor_readout.md`](industry_learning_blocks/CN_CEMENT_2014_2018/08_investor_readout.md)
  is the human-readable handoff.

This completes the two Goal milestones (`REAL_SAMPLE_CREATED` and
`REAL_FEEDBACK_TURN_COMPLETED`). It does not complete `TRANSFER_VALIDATED` and
does not grant any E3, method-freeze, CJO, valuation, report or investment
permission.

## 12. 2026-08-26 Mechanism-Training Correction And Next Freeze

Section 11 remains the record of the first block and feedback turn. Subsequent
work validated only the narrow `PERIMETER_FIRST_MEASUREMENT_METHOD`; it did not
validate enterprise judgment or action-effect learning.

The first CN:600802 mechanism settlement attempt is not an accepted training
turn. The FY2014 outcome was read after commit `2cb242b`, but independent review
found that the package used a caller-owned in-memory J1 registry, private J2/J3
compilers, self-reported completed companies and non-mechanical composite
measurement cells. `25_round4_contract_insufficiency_adjudication.json`
therefore permanently supersedes the attempted settlement as
`CONTRACT_INVALID_POST_OUTCOME_TEACHING_ONLY`. Raw official values may be used
only for `POST_OUTCOME_TEACHING`, `DATA_COVERAGE` and `RESEARCH_AGENDA`.

The non-retrospective repair is now implemented:

- `enterprise_judgment_real_mechanism_training.py` derives selection only from
  formal completion/settlement/adjudication receipts plus the immutable roster;
- the production builder has no caller database connection and registers the
  complete J1 bundle through the canonical control layer;
- J2 and J3 are called only through their public Frozen-J1 APIs;
- Outcome Measurement Contract v3 separates cutoff from `FLOW_PERIOD`,
  `BALANCE_AS_OF` and `EVENT_WINDOW`, and freezes every raw input, conversion,
  formula, threshold/event rule and local UNKNOWN/MISMATCH propagation;
- the existing public acquisition and settlement adapters now accept Enterprise
  V3 without constructing Forecast objects. The supported production boundary
  is custodian-located field records, not automatic PDF extraction: a strict
  14-cell synthetic preflight covers 31 raw-field records, all five formula
  operators, exact submission coverage, canonical persistence/replay,
  idempotency, PIT clocks and sibling-local mismatch.

Formal receipts mechanically selected rank 18, CN:600802
`2015-04-15 -> 2016-04-27`. `28_round5_v2_preoutcome_superseding_adjudication.json`
marks `26/27` as superseded historical artifacts. The active chain is now
`29_round5_v3_preoutcome_mechanism_package.json`,
`30_round5_v3_value_free_custody_projection.json`,
`31_round5_v3_preoutcome_control_plane_receipt.json` and
`32_round5_v3_adapter_acceptance_receipt.json`. The synthetic field-record
preflight
does not authorize or read the real FY2015 source. Real outcome authorization,
content read, custodian start and settlement all remain false; no directional-
learning, enterprise-learning, Comparative, CJO, valuation, report or investment
permission is granted.

## 13. 2026-08-27 Round 5 Real Cell-Level Feedback

The sealed Round 5 V3 route has now completed one real outcome turn without
rewriting its pre-outcome package. An independent custodian read only the
value-free projection and the authorized FY2015 static official PDF. The
corrected custody records are `33_round5_custodian_field_records.json`; the
first over-broad mismatch submission remains as the rejected historical
`33a` artifact. The canonical settlement in `34` covers all 14 cells and 31
raw inputs: eight cells are `OBSERVED`, six remain `UNKNOWN`, and no local
missing field became a negative label or stopped a sibling cell.

The independent post-outcome review in `35` accepts one material local change.
Furun remained formally launched, but by FY2015 year-end it had not become an
issuer-controlled, issuer-product-bearing or attributable operating lever for
CN:600802. This removes execution credit for that mechanism; it does not prove
that the action never existed, that management quality was poor, or that Furun
caused the issuer's weaker margin and cash state. Customer response, action
effect, overall management quality, capital return and permanent loss remain
`UNKNOWN`.

`36_round5_real_feedback_completion_receipt.json` records
`REAL_FEEDBACK_TURN_5_COMPLETED` with an evidence ceiling of
`LOCAL_ISSUER_CONTROLLED_EXECUTION_SCOPE`. It authorizes only a research-agenda
change: future joint-arrangement episodes must freeze legal launch, decision
control, issuer-product participation and customer response separately. It
does not grant Comparative, directional or enterprise learning, method
transfer, CJO, valuation, report or investment rights.

Final control-plane acceptance also projects the exact fixed `29 -> 31 -> 32
-> measurement-contract` route during pre-outcome adapter acceptance. Outcome
settlement can only read that route; it cannot create it or supply replacement
artifact identities. Before a Round 5 settlement can be stored, the canonical
control independently re-executes the five frozen formula operators from the
exact ordered `cell_id x field_id` receipts and verifies cell status, value,
label, coverage, rights and allowed outputs. Caller-supplied route IDs, labels
or permissions therefore cannot turn the local feedback into a broader
training or investment claim.

## 14. 2026-08-27 Round 6 Cross-Company Transfer Utility

Round 6 applies the local control-and-product-participation lesson from
CN:600802 to a mechanically selected different company and cutoff. The frozen
roster selects rank 1, CN:600801 `2016-04-27 -> 2017-04-12`; no outcome,
lifecycle label or source convenience participates in selection. Commit
`1ae29ea` freezes `37--39` before the FY2016 outcome PDF is opened.

The Baseline and Enhanced views use exactly the same FY2015 source packet and
fact set. Baseline retains one aggregate action-progress question. Enhanced
separates formal progress, issuer decision control, issuer-product
participation, consolidation and customer response. The outcome contract also
keeps issuer volume, gross margin, operating cash, cash capex, short-term
borrowings and direct loss as separate cells. H2 and Comparative are not
admission gates for this turn.

After the pre-outcome commit, the predeclared FY2016 CNINFO annual report was
read through the existing Enterprise V3 field-record acquisition and generic
settlement adapter. The committed artifacts are `40--44`. Six of eleven cells
are observed and five remain local UNKNOWN: formal acquisition progress is
YES, while issuer control and consolidation are NO; issuer-product
participation and transaction-specific customer response remain UNKNOWN.
Operating cash increases, cash capex decreases and short-term borrowings
decrease, but all three remain issuer state and are not attributed to the
unclosed acquisition. Missing absolute FY2015 volume and margin fields do not
stop the six observable sibling cells.

The paired review concludes `ENHANCED_IMPROVED_KEY_UNKNOWN`. This is a material
research-utility result, not an enterprise-quality score: the Enhanced method
prevents approval and fee-based support from being mistaken for issuer-owned,
consolidated operating capacity, while identifying the exact next evidence
needed. Because later Huaxin summaries already exist in repository history,
the turn is explicitly `MODEL_MEMORY_MITIGATED / DEVELOPMENT_TRANSFER_UTILITY_ONLY`
with `score_authority = NONE`. It does not authorize method transfer,
Comparative, CJO, valuation, report or investment use.

## 15. 2026-08-27 Round 7 Multidimensional Enterprise Judgment

Round 7 tests the larger architecture question left open by the earlier local
mechanism turns: whether the training method can reason across the full
enterprise instead of reducing a company to one action or one accounting
field. The frozen roster mechanically selects rank 3, CN:600585
`2014-04-16 -> 2015-04-15`. Baseline and Enhanced use the same FY2013 official
report, fact set and outcome contract. The Enhanced method must cover initial
conditions, implemented action, execution, customer and competitive response,
unit economics, working capital and cash-capital, adaptation and permanent
loss, and the strongest alternative explanation.

The independent custodian records 33 raw fields from the authorized FY2014
official report. Mechanical settlement covers all 17 cells: nine are
`OBSERVED`, seven remain `UNKNOWN`, and one is a local
`MEASUREMENT_MISMATCH`. The issuer outgrows national cement output by about
7.49 percentage points; operating cash and OCF-to-cash-capex rise, cash capex
falls and net debt ratio declines. Inventory also rises 18.5%. The FY2013
gross-margin baseline includes aggregates and stone, so it cannot be compared
with the frozen cement-and-clinker scope. That mismatch does not stop any
unrelated cell.

The independent paired review finds the Enhanced method materially better in
four of eight dimensions: initial-condition attribution, execution,
customer/competition response and unit economics. It finds no material
difference for implemented action, cash-capital or the strongest rival, and
the one-year evidence is not diagnostic for adaptation/permanent loss. The
useful result is therefore narrower than a company-quality score: the method
prevents industry tailwinds, acquired/new capacity and aggregate accounting
cash from becoming unsupported management, moat, durable-economics or owner-
cash credit.

Artifacts `45--53` preserve the pre-outcome freeze, access authorization,
field records, canonical settlement, independent review and completion
receipt. The round remains `MODEL_MEMORY_MITIGATED` with `score_authority =
NONE`; it does not authorize method transfer, Comparative, CJO, valuation,
report or investment use. The next real turn must test the same chain on a
different company and period while freezing an organic-versus-acquired volume
bridge, direct customer evidence, same-scope unit economics and a conservative
owner-cash bridge before outcome access.

## 16. 2026-08-27 Round 8 Cross-Industry Eight-Dimension Feedback

Round 8 moves from cement to Chinese franchised express delivery. The real
industry block contains Yunda, STO and YTO at the same 2019-05-01 cutoff. A
predeclared rule selects the lowest company ID with a complete cutoff-before
static-PDF packet, CN:002120, independently of outcomes and source convenience.
Commit `5613b36` freezes the Decision Contract, a fair issuer-scale Baseline,
the cumulative eight-dimension Enhanced Episode and a 15-cell Measurement
Contract before the predeclared FY2019 report is opened.

The authorized field-level settlement preserves six observable cells, six
local `MEASUREMENT_MISMATCH` cells and three `UNKNOWN` cells. Volume, share,
operating cash, cash capex and leverage remain usable. Express revenue per
parcel, parcel cost and gross margin do not: the FY2019 report adds dispatch-fee
revenue and corresponding service cost, so the presentation is not
definitionally comparable with the frozen FY2018 baseline. The complaint field
is also mismatched because the report discloses complaints per million parcels
while the frozen contract used a generic ratio. Dated network, automation and
franchise-loss events remain unknown rather than being inferred from annual
narrative.

Independent pre-outcome review found two material contract-design failures.
First, FY2019 annual flows include January-April before the cutoff and may only
serve as mixed-clock context with zero causal credit. Second, the national
industry-growth field was frozen under Yunda's issuer-consolidated
responsibility boundary. Outcome custody therefore locally mismatches the
industry and issuer-minus-industry cells; it does not repair the frozen
contract after seeing results. A scope/clock adjudication mechanically assigns
`causal_credit = NONE` to every Round 8 result cell.

The eight dimensions are adopted as the standard EnterpriseJudgmentEpisode
question skeleton because they prevent scale from silently becoming customer
loyalty, action from becoming execution, headquarters cash from becoming owner
cash, or a one-year result from becoming permanent-loss resilience. They are
not a scorecard and not eight global gates: each dimension may remain
`UNKNOWN`, `EVIDENCE_INELIGIBLE` or `NOT_APPLICABLE`, and only dependent claims
lose permission.

The outcome-side independent reviewer also found that the Baseline already
shared the eight-dimensional question set, owner-cash boundary and principal
rival explanations. Round 8 therefore cannot attribute the shared caution to
Enhanced. It also cannot grant execution error avoidance: the Baseline called
scale a provisional signal but neither method froze a distinct outcome
resolution rule before result access. Both execution assessments are therefore
`NOT_DIAGNOSTIC`.

Round 8 closes as `REAL_FEEDBACK_COMPLETED /
NO_MATERIAL_METHOD_ADVANTAGE_PROVED / ARCHITECTURE_REVISION_REQUIRED`.
The eight dimensions remain the adopted no-score question skeleton, but this
A/B does not validate their aggregate method advantage. The next unseen episode
must freeze a genuinely simple independent Baseline, independent industry and
issuer boundaries, exact complaint units, machine-readable
measurement-use/causal eligibility, same-definition unit-economics bridges and
finding-to-cell support before outcome access. Exact outcome source identity
remains predeclared to prevent result-based source selection; content isolation
is a recorded procedural role boundary, not a claim of adversarial secrecy. No
method, Comparative, CJO, valuation, report or investment permission is granted.

Post-review hardening adds a page-level extraction receipt for every scored raw
value, canonical settlement replay for evaluation, explicit supporting cell IDs
for all eight findings, and mandatory independent acceptance for completion.
Changing a raw value or unit without changing the official PDF page now fails
before settlement; synchronized settlement/adjudication edits, unrelated
evaluation text, missing acceptance and reviewer-role drift all block completion.
