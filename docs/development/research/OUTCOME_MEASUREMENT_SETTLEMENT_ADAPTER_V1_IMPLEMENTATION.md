# Outcome Measurement Settlement Adapter v1

Status: implemented as a narrow bridge into the existing Forecast V3+
mechanical settlement engine.  It creates no separate scoring, learning, CJO,
valuation, report, or investment path.

## Investor-facing effect

A usable annual-report field can now continue all the way from a frozen
Measurement Contract to a mechanically scored forecast cell.  A different
field in the same annual report may remain `MEASUREMENT_MISMATCH` or `UNKNOWN`
without cancelling the usable result.  This reduces a real training blockage:
an imperfect disclosure package no longer forces the system to discard its
reliably measured operating facts.

It does not make the company better or worse.  It only applies a pre-frozen
measurement formula and threshold to a value already acquired from a
registered official PDF.

## One bridge, not a second engine

`scripts/outcome_measurement_settlement_adapter.py` accepts only:

```text
stored authorized outcome access
  + stored frozen Forecast / Measurement Contract
  + outcome-measurement-acquisition.v1 result
  -> existing outcome-observation receipts
  -> existing register_forecast_settlement()
```

The adapter loads the authorized Forecast and Measurement Contract from the
existing control-plane tables.  A caller does not pass forecast probabilities,
forecast rationale, realised labels, a price, a CJO, a report, or an investment
conclusion.  It validates company, issuer, period, field identity, unit,
responsibility boundary, contract reference, custodian identity and static PDF
source identity before anything is written.

For the supported first v1 case, an acquired direct numeric field must exactly
match the contract's `DIRECT_NUMERIC` `value_field_id`.  The adapter then
derives the ordinal label from the contract's frozen thresholds.  It does not
infer a ratio, a binary event, a trend, an action effect, or a unit conversion
from narrative text.

## Field-level terminal states

- `OBSERVED` creates one immutable existing observation receipt containing the
  exact source/PDF page and numeric source component, then enters existing
  mechanical settlement.
- `MEASUREMENT_MISMATCH` creates the existing value-free mismatch receipt only
  when the acquisition reason is exactly one of the contract's frozen mismatch
  rules.  It receives no value or directional label.
- `UNKNOWN` creates no observation receipt and settles that one Forecast cell
  as unscored.  It is never converted to zero, false, deterioration, or a
  negative company conclusion.

A result package must account for each frozen contract cell once because the
existing settlement engine must account for every dimension/window.  That is
receipt completeness, not a new global admission gate: non-observed cells are
legal terminal entries alongside observed cells.

## Date-only official publication records

Many registered exchange PDFs expose a publication date but not an intraday
timestamp.  The existing V3 observation validator now accepts an explicit
`DATE_ONLY` source availability form alongside legacy exact timestamps.  Its
chronology is conservative:

- the source calendar day must be strictly after the forecast cutoff day; and
- a custodian observation, settlement, or next prequential cutoff must fall
  on a strictly later calendar day.

This preserves ordering without fabricating an intraday source time.  Legacy
timestamp receipts retain their original validation path.

## Local end-to-end evidence

`tests/test_outcome_measurement_settlement_adapter.py` proves:

1. a direct consolidated-revenue field becomes an existing observation and
   mechanically settled cell while unknown fields remain unscored;
2. a parent-company revenue field becomes a value-free
   `MEASUREMENT_MISMATCH` against a consolidated contract without revoking its
   observed neighbour; and
3. the already registered local SSE FY2014 annual-report PDF for CN:600660
   reaches the same existing settlement path, with the source receipt bound to
   physical PDF page 54.

The tests use no browser or network path.  They preserve
`FORECAST_EVALUATION_ONLY` / `RESEARCH_AGENDA` at settlement and create no
method transfer, report, valuation, CJO, BuyBand, or trading authority.

## Honest failure handling

- `DATA_COVERAGE`: the field or comparable prior value is absent from the
  registered report.  The cell remains `UNKNOWN`; a later contract may define
  another measurable field.
- `ACQUISITION_MODULE`: a registered PDF cannot yield an exact page/field,
  scope or unit.  The cell remains `MEASUREMENT_MISMATCH`; add a bounded field
  extractor rather than substituting prose or a different statement.
- `MODEL`: the frozen formula is not a direct numeric mapping (for example a
  ratio or binary outcome) or the source uses a different responsibility
  boundary.  The adapter refuses to invent a label; a new pre-forecast
  Measurement Contract must define the needed mapping.
- `REASONING`: interpreting an unscored field as business deterioration or
  claiming an action caused an observed value.  Preserve the mechanical status
  and keep causal judgement separate.
- `WRITING`: a source receipt omits its page, unit, period or scope.  Correct
  the receipt before settlement; do not fill the missing fact from a report
  narrative.
