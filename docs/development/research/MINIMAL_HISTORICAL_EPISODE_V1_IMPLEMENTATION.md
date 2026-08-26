# Minimal Historical Episode v1

Status:

- synthetic control acceptance: `PASSED`;
- first real-data episode: `MECHANICALLY_SETTLED / PENDING_FINAL_INDEPENDENT_REVIEW`;
- method-transfer authorization: `NONE`.

This remains an isolated namespace and does not modify or consume V5, V6, H1,
training-program, selection, CJO, valuation, price, report, pairing, or holdout
objects.

## Purpose

The lane supplies the smallest auditable historical episode:

```text
one Measurement Contract
  -> one static official pre-cutoff field
  -> one directional prediction
  -> independent custodian contract-only access
  -> one official outcome observation
  -> one mechanical MATCH / MISS settlement
```

Every object is closed and carries the fixed values:

- `allowed_outputs = ["MECHANICAL_SETTLEMENT_ONLY"]`
- `method_transfer_rights = "NO_METHOD_TRANSFER_RIGHTS"`

The contract names precisely one company, issuer, cutoff, metric, and window.
It also freezes the issuer responsibility boundary, unit, outcome-period end,
tolerance, forecaster, and custodian. The static evidence receipt must be an
official HTTPS PDF, published strictly before cutoff, with the same issuer,
metric, boundary, unit and a page reference. Its curator must differ from both
the forecaster and custodian. The outcome source carries the same closed
source-level metric identity and measurement-period end, both of which must
match the contract exactly.
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

The tests use `sqlite3.connect(":memory:")` and `.invalid` URLs. They never
open a source, browser, outcome, or production database, and create no actual
forecast or freeze artifact outside the test process.

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

The first episode fixes one issuer and metric:

```text
CN:600585
FY2017 consolidated cement-and-clinker sales volume: 295,000,000 tonnes
  -> FY2018 directional prediction frozen
  -> independent contract-only custodian
FY2018 consolidated cement-and-clinker sales volume: 368,000,000 tonnes
  -> mechanical MATCH
```

The pre-outcome objects were committed at
`cbd0aa03c715c49d6e97a2df657088c3b41af3e3` before the independent custodian
task received its allowed inputs. That commit is the anti-backfill checkpoint
for this first execution. The original v1 SQLite timestamps were supplied to
the controller immediately around those actions; after review, the reusable
runner was tightened so future persistent executions accept no caller-authored
chronology.

Official source receipts:

- `cohorts/CN600585_FY2017_MINIMAL_HISTORICAL_EPISODE_OFFICIAL_SOURCE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_OFFICIAL_SOURCE_RECEIPT.json`.

Runtime and acceptance receipts:

- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_PREOUTCOME_FREEZE_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_RUNTIME_RECEIPT.json`;
- `cohorts/CN600585_FY2018_MINIMAL_HISTORICAL_EPISODE_ACCEPTANCE.json`.

`MATCH` is visible to the post-settlement reviewer. The prediction was sealed
from the custodian until the observation had been returned; it is not treated
as permanently secret after settlement. Neither the result nor its source
receipts grant learning, method release, V6, pairing, holdout, CJO, valuation,
report, or trading rights.
