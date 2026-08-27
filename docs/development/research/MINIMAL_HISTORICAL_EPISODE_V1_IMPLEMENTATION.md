# Minimal Historical Episode v1

Status:

- synthetic control acceptance: `PASSED`;
- V1 real-data run: `LEGACY_MECHANICAL_RUN / POST_SETTLEMENT_SOURCE_REVIEW`;
- V2 real-data episode: `ONE_INDEPENDENT_MECHANICAL_SETTLEMENT / ACCEPTED_FOR_PIPELINE_COVERAGE`;
- protective terminals: `CN600802 / CN600425 / CN002003 / CN002404 = MEASUREMENT_MISMATCH`;
- bounded lane state: `CLOSED_AT_CURRENT_ACCEPTANCE_POINT / NO_SECOND_FIELD_READY`;
- method-transfer authorization: `NONE`.

This remains an isolated namespace and does not modify or consume V5, V6, H1,
training-program, selection, CJO, valuation, price, report, pairing, or holdout
objects.

## Bounded acceptance and next production lane

From an investor's perspective, this lane has proved one narrow thing: Turtle
can freeze a single historical operating claim before the result is read, let a
separate custodian observe the permitted official disclosure, and settle the
claim mechanically. It has not proved that a forecasting method improves
enterprise judgment, explains an operating mechanism, or supports a valuation
or a buy decision.

The lane is therefore closed at its current acceptance point. One independent
mechanical settlement proves the chain capability. `CN600802`, `CN600425`,
`CN002003`, and `CN002404` each ended in a value-free
`MEASUREMENT_MISMATCH`; together they show that the acquisition gates refuse
to manufacture a label when an official result cannot be mapped uniquely. None
reached a second `FIELD_READY` observation.

Do not add another schema, control-plane rule, adapter capability, or Minimal
candidate merely to pursue a second settlement. Reopen this lane only when a
newly identified **reusable acquisition-contract deficiency** would otherwise
make a uniquely mappable official field unavailable. The remediation must be
bounded to that reusable contract deficiency; a candidate-specific source
substitution, outcome search, or relaxed mapping is not a reason to reopen.

The next production lane is action-first `Comparative`: independently freeze
an implemented, falsifiable operating action, then the comparator eligibility
predicate and result contract before a directional settlement. The Minimal lane
does not gate that work and cannot substitute for it.

## Purpose

The lane supplies the smallest auditable historical episode:

```text
one frozen Decision Contract
  -> one matching Measurement Contract
  -> one static official pre-cutoff field
  -> one directional prediction
  -> independent custodian contract-only access
  -> value-free OutcomeSourceInventoryReceipt
  -> one official outcome observation
  -> one mechanical MATCH / MISS settlement
```

Every object is closed and carries the fixed values:

- `allowed_outputs = ["MECHANICAL_SETTLEMENT_ONLY"]`
- `method_transfer_rights = "NO_METHOD_TRANSFER_RIGHTS"`

The Decision Contract is the first closed object. It names precisely one
company, issuer, cutoff, metric, window, and
`decision_purpose = "ONE_METRIC_DIRECTIONAL_PREDICTION"`, then freezes distinct
forecaster and custodian identities. It is append-only: an exact replay is
idempotent, while a changed replay and direct update/delete are rejected.

The Measurement Contract references an already frozen Decision Contract and
must match its company, issuer, cutoff, metric, window, and roles exactly. The
controller rejects a Measurement Contract submitted before its Decision
Contract, or at the same time. It then freezes the issuer responsibility
boundary, unit, outcome-period end, and tolerance. The static evidence receipt
must be an official HTTPS PDF, published strictly before cutoff, with the same
issuer, metric, boundary, unit and a page reference. Its curator must differ
from both the forecaster and custodian. The outcome source carries the same
closed source-level metric identity and measurement-period end, both of which
must match the Measurement Contract exactly.
Baseline and outcome numeric values must be finite before the controller can
serialize or persist either receipt.

## Custody boundary

The access payload is contract-only: its closed shape cannot name a prediction,
predicted direction, evidence field, realised value, price, valuation, report,
or method. The controller only checks that one stored prediction exists before
opening access; it returns no prediction content. Observation and settlement
requests likewise contain no prediction content. Settlement resolves the stored
baseline/evidence/prediction/observation internally and emits only a bound
`MATCH` or `MISS` result with technical object identities.

The persistent outcome runner requires the already-stored
`outcome_access_authorization_id` before it opens any outcome-candidate,
observation JSON, or source-verification input. After that authorization, an
independent custodian must append one closed, value-free
`OutcomeSourceInventoryReceipt`. `FIELD_READY` names exactly one direct
official `static.cninfo.com.cn/finalpage` annual-report PDF, its declared
availability precision and one physical page locator; it contains no numeric
value, quote, label, prediction, price, CJO, report, or learning payload.
`MEASUREMENT_MISMATCH` records only the applicable mapping rule and detail and
blocks observation and settlement. The receipt is append-only, contract- and
custodian-bound, and controller-timed. An observation must reproduce every
frozen source identity field and page locator before the later official PDF
verifier is allowed to inspect its numeric field.

`scripts/minimal_historical_outcome_acquisition.py` is the corresponding
custodian-only metadata adapter for future objects. It uses the existing
bounded Phase10 CNINFO enumerator after stored access, accepts only one direct
outcome-period original annual-report title with an exact static-finalpage URL.
Any same-period revised, corrected, updated, cancelled, withdrawn, or revoked
annual-report disclosure instead makes the field value-free
`MEASUREMENT_MISMATCH`. Any PDF/page-reader work remains
custodian-temporary; the runner's post-inventory verifier continues to be the
only numeric/quote gate. This is additive for new minimal objects and does not
rewrite existing episodes.

New Minimal episodes now require the separate
[Outcome Acquisition Route v2](MINIMAL_HISTORICAL_EPISODE_V2_OUTCOME_ROUTE_IMPLEMENTATION.md):
the Measurement Contract freezes the contract-bound CNINFO security code,
organization ID, bounded query dates, annual-report category, and static-PDF
policy before prediction. A preceding, closed `TECHNICAL_ROUTE_IDENTITY`
obtains only the official stock-map code-to-orgId routing mapping and resolver
provenance; it is not company evidence and cannot include names, announcements,
PDFs, outcomes, or prices. The adapter derives the final route only from the
stored v2 contract. Existing v1 artifacts stay readable historical records and
cannot be retrofitted or used to start a new custody flow.

Official static CNINFO source verification is page-bound. `source.field_ref`
must declare exactly one positive physical PDF page (for example `PDF p. 21`
or `page_21`). The runner invokes `pdftotext` with that page as both its first
and last page and matches the frozen exact quote only in that extraction. A
missing, ambiguous, or unparseable page reference—and a quote found only on a
different page—fails verification before an observation can be persisted.

## Mechanical result

The static and observed numeric values are compared with the frozen tolerance:

- difference above tolerance → `INCREASE`;
- difference below negative tolerance → `DECREASE`;
- otherwise → `STABLE`.

The controller compares that derived direction to the single stored prediction.
No probability, peer comparison, action attribution, D3/D4 chain, method
baseline, holdout, transfer, CJO, valuation, price, BuyBand, release, or report
claim is produced.

## Entry points

- Shape validators: `scripts/minimal_historical_episode.py`
- Append-only controller: `scripts/minimal_historical_episode_control_plane.py`
- JSON schema: `schemas/minimal_historical_episode.schema.json`
- Synthetic acceptance tests: `tests/test_minimal_historical_episode.py`
- Controller-owned persistent runner: `scripts/minimal_historical_episode_runner.py`
- Custodian-only bounded source metadata adapter: `scripts/minimal_historical_outcome_acquisition.py`

Synthetic tests use in-memory and temporary on-disk SQLite plus `.invalid`
URLs. They cover the Decision Contract-first identity/role/replay controls
without opening real sources, and create no committed production artifact.

The persistent runner is a separate real-data entrypoint. It rejects `.invalid`
fixtures, opens the cited `static.cninfo.com.cn/finalpage` PDF, and reconciles
the exact disclosed quote to the contract-bound finite numeric value before
emitting an official-source receipt. It has deterministic quote rules for the
existing `tonnes` disclosure form and for
`ISSUER_CONSOLIDATED_OPERATING_REVENUE_RMB`: the latter requires the declared
consolidated income-statement revenue field and maps only the first numeric
column immediately following `营业收入` (commas permitted). Other units remain
unverifiable until a similarly explicit rule exists; the runner never guesses a
scale or selects a comparative column. The sealed SQLite database belongs only to the controller. A custodian
receives the Measurement Contract plus contract-only outcome authorization and
returns one observation; the custodian does not run the database commands.
Freeze, authorization, observation receipt, and settlement persistence times
are generated from the runner execution clock rather than accepted from CLI
arguments.

## First real-data episode

The V1 run is retained as a legacy mechanical record only. Its official-source
verification was performed after settlement, so it cannot prove the real
runner's source-before-persistence property.

The accepted V2 episode fixes the same issuer and metric:

```text
CN:600585
FY2017 consolidated cement-and-clinker sales volume: 295,000,000 tonnes
  -> FY2018 directional prediction frozen
  -> independent contract-only custodian
FY2018 consolidated cement-and-clinker sales volume: 368,000,000 tonnes
  -> mechanical MISS
```

The V2 pre-outcome objects and source-before-freeze receipt were committed at
`d503bc3` before the independent V2 custodian task received its allowed inputs.
The controller then verified the outcome source before writing the observation,
and generated observation/settlement chronology from its own execution clock.

Official source receipts:

- `cohorts/CN600585_FY2017_MINIMAL_HISTORICAL_EPISODE_OFFICIAL_SOURCE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_OFFICIAL_SOURCE_RECEIPT.json`.

V2 source and execution receipts:

- `cohorts/CN600585_FY2017_MINIMAL_HISTORICAL_EPISODE_V2_OFFICIAL_SOURCE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_V2_OUTCOME_OFFICIAL_SOURCE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_V2_RUNTIME_RECEIPT.json`.

Runtime and acceptance receipts:

- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_PREOUTCOME_FREEZE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_RUNTIME_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_ACCEPTANCE.json`.

The V2 `MISS` is visible to the post-settlement reviewer. The prediction was sealed
from the custodian until the observation had been returned; it is not treated
as permanently secret after settlement. Neither the result nor its source
receipts grant learning, method release, V6, pairing, holdout, CJO, valuation,
report, or trading rights.
