# Turtle EnterpriseJudgmentEpisode J3 Forecast Projection

> Status: `IMPLEMENTED / PURE_OFFLINE_REQUEST_ADAPTER`
>
> Scope: `RESOLVED J2 THREAD VIEWS -> CELL-LEVEL FORECAST REQUESTS`

## Purpose

J3 projects explicitly forecast-eligible mechanism-thread cells into requests
that the existing PIT company-state forecast lane may answer later. It is not
a second forecast engine: it does not generate probabilities or intervals,
freeze a forecast, acquire outcomes, score a settlement, or persist policy.

Implementation:

- adapter: `scripts/enterprise_judgment_forecast_projection.py`;
- closed output schema and serialized source protocol:
  `schemas/enterprise_judgment_forecast_projection.schema.json`;
- focused regression:
  `tests/test_enterprise_judgment_forecast_projection.py`.

## API and dependency boundary

```python
compile_forecast_projection(
    episode_manifest,
    projection_source,
    mechanism_thread_set=serialized_j2_thread_set,
    reconstruction_read_model=j1_reconstruction,
    reconstruction_inputs=j1_compilation_inputs,
    reconstruction_registry=frozen_j1_registry,
)
validate_forecast_projection_source(
    episode_manifest,
    projection_source,
    mechanism_thread_set=serialized_j2_thread_set,
    reconstruction_read_model=j1_reconstruction,
    reconstruction_inputs=j1_compilation_inputs,
    reconstruction_registry=frozen_j1_registry,
)
```

The public adapter accepts the frozen J2 thread set, bound J1 reconstruction,
its complete compilation inputs and the append-only Frozen J1 registry, then internally calls
`compile_mechanism_thread_projection`. It consumes only that compiler's read
model: thread-set/company/issuer/cutoff identity, claim type and IDs,
outcome-cell refs, resolved source refs, local status, evidence ceiling,
resolution, eligibility and unperformed/unauthorized state. A caller-supplied
or hand-built J2 read model is not accepted, and J2 must exactly recompile J1
and match the previously registered reconstruction/input bundle. Therefore a
relative-causal/blocked thread or synchronized forged source cannot be
activated by flipping or copying routing fields.

The separate closed projection source serializes this minimal request
protocol:

```text
projection source
  -> exact episode/company/issuer/cutoff reference
  -> exact J2 thread-set identity
  -> source-packet receipt identities exactly matching compiled J2 lineage
  -> thread_id resolved against serialized J2 `j3_forecast_eligible`
  -> cells[]
       request_id
       outcome_cell_id + explicit forecast_eligible boolean
       forecast dimension + one/three/five-year window
       measurement-contract/version/measurement identity
       cutoff-visible source/field identity plus timezone-aware available_at
       request kind and kind-specific response contract
```

J0 remains the episode identity and thread/cell binding authority. J2 remains
the mechanism-thread compiler and source-lineage authority. The source
protocol does not copy hypotheses, enterprise facts, mechanisms, or outcome
values from J2.

## Selection and request semantics

A cell is selected only when its serialized J2 thread view sets
`j3_forecast_eligible=true`, the cell itself sets `forecast_eligible=true`,
its `thread_id` exists in the J0 manifest, and the J0 thread binds the same
`outcome_cell_id`. J3 confirms the internally compiled J2 view is resolved, active,
non-relative-causal, bound to the same J0 claims/outcome cells and permitted by
the J0 claim matrix. Projection-level source packet receipts must exactly
equal J2's J1-derived lineage. Each evidence `source_id` and timezone-aware
`available_at` instant must exactly match one of that resolved J2 thread's
cutoff-visible source refs, and both publication date and availability instant
must be no later than the episode cutoff. Publication date may precede the
actual availability instant; J3 does not invent a same-day identity that J2
does not own. The J0 outcome
domain must also be economically compatible with the requested Forecast
dimension; for example, a cash cell cannot be relabeled as permanent-loss
risk. The J2 thread must not already have performed a forecast and retains
`forecast_authorization=NOT_AUTHORIZED`.
The measurement-contract ID must exactly match the J0 outcome cell; the
version and measurement ID remain unchanged in output. J2 thread-set,
source-packet, source, publication, field, episode, company, issuer, cutoff,
thread, cell, dimension, and window identities are also preserved.

The adapter emits four response-request forms:

| request kind | existing forecast meaning | J3 output |
|---|---|---|
| `ORDINAL_PROBABILITY` | ordered labels sum to one | label set only; no probabilities |
| `BINARY_PROBABILITY` | one frozen event probability | event statement only; no probability |
| `NUMERIC_INTERVAL` | architecture-level proper interval request | coverage/unit with `REQUEST_ONLY`; no scoring path added |
| `ABSTAIN` | `EVIDENCE_INELIGIBLE` and no fabricated prediction | explicit reason and coverage-only attribution |

Ordinal labels reuse the current engine's
`DETERIORATE/STABLE/IMPROVE` or permanent-loss
`LOW/BASELINE/HIGH` ordering. Binary and ordinal requests require a frozen
baseline reference. Interval requests remain inert until the existing
forecast engine owns interval validation and scoring; J3 does not implement
that engine behavior locally.

## Locality and no-forecast state

Missing J0/J2 thread bindings, J2-ineligible requests, unknown cells, wrong
cell-to-thread bindings, measurement mismatches, duplicate
request/cell-window identities, invalid request contracts, and post-cutoff
evidence become `cell_rejections`. They do not remove valid sibling requests
and do not alter J0 E0/E1 state.

If no eligible cell survives, compilation remains valid and returns:

```text
projection_state = NO_FORECAST_ELIGIBLE_CELLS
forecast_requests = []
preserved_admission.E0_CONTEXT = PRESERVED
preserved_admission.E1_RECONSTRUCTION = PRESERVED
```

Episode/company/cutoff replacement, an invalid J0 manifest, malformed or
invented J1/J2 source-packet lineage, or any price, return, realized-outcome,
settlement, valuation, or investment payload invalidates the projection
source. A source instant after cutoff, including one later on the same calendar
day, is rejected at its cell, so one contaminated cell cannot erase unrelated
cutoff-safe requests.

## Coverage and error attribution

Each request carries cell-local coverage statuses and an activation gate that
requires the existing forecast settlement path. Probability and interval
requests expose the existing direct scopes for calibration, state definition,
uncertainty policy and baseline performance; evidence-priority and rival-
hypothesis changes remain candidates requiring paired holdout. An abstention
exposes only direct `COVERAGE` feedback. `OUTCOME_MEASUREMENT` remains a
separate failure locus.

These are routing permissions, not active method changes. The existing
forecast validator/control plane still owns settlement, proper scoring,
reviewer independence, paired holdout and policy activation.

## Rights boundary

Every projection fixes the following rights to `NOT_AUTHORIZED`:

- causal;
- comparative;
- CJO;
- method freeze;
- report;
- valuation;
- investment.

The only allowed outputs are `FORECAST_REQUESTS_ONLY` and
`RESEARCH_AGENDA`. Forecast output cannot promote a J2 mechanism, create an
E3 comparative claim, amend an episode or reconstruction, or write an
investment input.

## Acceptance coverage

The focused tests cover probability, interval and abstain requests; exact
identity preservation; explicit eligibility; empty no-forecast behavior;
cell-local missing/measurement mismatch; invalid compiled-J2 eligibility,
forged source and economic-dimension mismatch; invented source-packet lineage;
synchronized J1 receipt/source forgery;
same-day post-cutoff evidence; price
contamination; episode identity replacement; input immutability; permissions;
and the closed schema/source protocol.
