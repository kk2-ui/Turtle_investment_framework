# Minimal Historical Episode v1

Status: synthetic, in-memory control coverage only. This is a new isolated
namespace and does not modify or consume V5, V6, H1, training-program,
selection, CJO, valuation, price, report, pairing, or holdout objects.

## Purpose

The lane supplies the smallest auditable historical episode:

```text
one frozen Decision Contract
  -> one matching Measurement Contract
  -> one static official pre-cutoff field
  -> one directional prediction
  -> independent custodian contract-only access
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

The tests use `sqlite3.connect(":memory:")` and `.invalid` URLs. They cover the
Decision Contract-first chain, decision/measurement identity and role drift,
and changed versus exact decision replay. They never open a source, browser,
outcome, or production database, and create no actual forecast or freeze
artifact outside the test process.
