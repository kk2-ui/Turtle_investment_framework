# Minimal Historical Episode v1

Status:

- synthetic control acceptance: `PASSED`;
- V1 real-data run: `LEGACY_MECHANICAL_RUN / POST_SETTLEMENT_SOURCE_REVIEW`;
- V2 real-data episode: `MECHANICALLY_SETTLED / ACCEPTED_FOR_PIPELINE_COVERAGE`;
- method-transfer authorization: `NONE`.

This remains an isolated namespace and does not modify or consume V5, V6, H1,
training-program, selection, CJO, valuation, price, report, pairing, or holdout
objects.

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
outcome-period `ANNUAL_REPORT` with an exact static-finalpage URL, and otherwise
emits the value-free mismatch candidate. Any PDF/page-reader work remains
custodian-temporary; the runner's post-inventory verifier continues to be the
only numeric/quote gate. This is additive for new minimal objects and does not
rewrite existing episodes.

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
fixtures, opens the cited `static.cninfo.com.cn/finalpage` PDF, reconciles the
exact disclosed quote to the numeric tonnes value, and emits an official-source
receipt. The sealed SQLite database belongs only to the controller. A custodian
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
