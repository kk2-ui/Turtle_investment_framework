# Forecast Acquisition Scope v1

## Status

Implemented as the mandatory pre-forecast collection gate for the new
`TURTLE_PIT_COMPANY_FORECAST_EPOCH_V5`. It does not amend Forecast V4 or
reopen the 2018 cement pilot.

## Problem fixed

An Outcome Measurement Contract can define all eighteen state cells while a
specific forecast legitimately abstains from some dimensions as
`EVIDENCE_INELIGIBLE`. A custodian who receives only that broad measurement
contract could otherwise collect post-cutoff facts for cells that were never
forecast. Those facts must not later become score, calibration, or learning
inputs.

## Canonical sequence

```text
Decision Contract
  -> Outcome Measurement Contract
  -> independent preforecast field receipt
  -> Forecast Acquisition Scope
  -> Forecast V5 freeze
  -> custodian-only outcome access
  -> scope-bound observation receipts
  -> settlement
```

`Forecast Acquisition Scope` is append-only and custodian-readable. It binds
one Decision Contract and one Measurement Contract, with the same company,
issuer, cutoff, and custodian. Each selected cell must reproduce its frozen
`dimension_id × window_id × measurement_id`; selection is complete for every
included dimension. It contains no forecast probabilities, rationale, price,
outcome source, or realised value.

Forecast V5 must reference a previously frozen matching scope. Its
`MODEL_UNCERTAIN` dimensions must be exactly covered, while each
`EVIDENCE_INELIGIBLE` dimension must be absent. The observation registration
path reapplies the scope check, so a custodian cannot record an extra cell
after access has opened.

V5 uses a separate outcome-access authorization version.  It carries the same
immutable scope reference as the forecast and is rejected if it is absent or
mismatched.  Settlement, paired evaluation, and error attribution reload the
same stored scope before revalidating referenced observations; an observation
that passed an earlier call cannot bypass the scope at a later lifecycle step.
An Outcome Measurement Contract that any forecast has already consumed cannot
gain a scope afterwards, so V4 cannot be upgraded or used as a delayed V5
input.

## Non-goals and immutable legacy

- Existing V1--V4 forecasts remain immutable and do not gain a retroactive
  scope reference.
- This adds no real outcome access, no CJO or valuation input, no report or
  investment authorization, and no new source acquisition.
- The 2018 CN:600585 V4 settlement remains a scope-corrected historical
  coverage case. Its direct coverage policy applies only at a later cutoff;
  it is not an accuracy conclusion.

## Acceptance evidence

The focused forecast/control suite verifies:

1. an acquisition scope must match the frozen Measurement Contract exactly;
2. a V5 forecast cannot freeze before that scope;
3. an `EVIDENCE_INELIGIBLE` dimension cannot be placed in the scope; and
4. access must carry the frozen scope; and
5. after access, an in-scope observation can register and settle while an
   excluded cell is rejected before it is persisted.
