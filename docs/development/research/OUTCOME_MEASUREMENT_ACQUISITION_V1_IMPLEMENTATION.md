# Outcome Measurement Acquisition v1

Status: implemented as a field-acquisition module; it does not settle a
forecast or grant any learning, CJO, valuation, report, or investment right.

## Investor-facing result

One unavailable accounting field no longer invalidates the rest of an annual
report.  The custodian can now return a verified consolidated revenue, cash,
asset, or segment field with its exact PDF page while preserving a separate
`MEASUREMENT_MISMATCH` or `UNKNOWN` for an unmappable field.  This narrows a
real training blocker: a usable operating measurement can continue to
mechanical settlement without pretending that every forecast dimension is
observable.

It does not turn an accounting observation into a view on the company.  The
module receives neither a forecast direction nor a realised label, price,
CJO, valuation, report, or investment object.

## Contract-first input

`scripts/outcome_measurement_acquisition.py` accepts one of the existing
frozen Measurement Contract forms:

- `turtle-pit-forecast-outcome-measurement-contract.v1`, where each frozen
  cell supplies its `source_field_id`, boundary, period and unit; or
- the one-cell Minimal Historical Episode Measurement Contract.

The second input is a closed, contract-bound local-PDF inventory.  Each
document must already exist locally, have an official static SSE or CNINFO PDF
URL, bind the exact issuer and responsibility boundary, declare its reporting
period, and be an original issuer annual report.  The module never discovers a
new URL, web route, issuer, source version, or accounting period.

The first v1 catalogue is deliberately narrow:

- consolidated revenue, total assets and operating cash flow;
- parent-company equivalents (which intentionally mismatch a consolidated
  Measurement Contract rather than silently substituting scope); and
- segment or product revenue declared in the frozen `source_field_id`.

It reads the registered local PDF with `pdftotext -layout`, identifies the
required statement and line item, normalises only the disclosed Chinese RMB
unit, and returns the current and comparative columns.  A financial-statement
note number is not mistaken for an accounting value.

## Per-field outcomes

Every selected frozen cell is independent:

| Status | Meaning | Downstream consequence |
| --- | --- | --- |
| `OBSERVED` | One direct registered statement row has the frozen period, boundary, unit and field identity. | It is available for the existing settlement layer. |
| `MEASUREMENT_MISMATCH` | A local report exists but cannot deterministically satisfy the frozen definition, such as a parent statement requested for a consolidated contract. | This field cannot be scored or inferred from a substitute. |
| `UNKNOWN` | No registered annual report for the period, or the frozen field is outside the v1 catalogue / absent from the registered statement. | This field remains unobserved; it is not a negative company result. |

An `OBSERVED` result records the official PDF identity and URL, physical PDF
page, report period, source field identity, unit/currency, reporting scope,
current and comparative values, and the inventory's consolidation or
restatement note.  A mismatch preserves the relevant document/page when one
was located, so it can be reviewed without reading any forecast object.

## Acceptance evidence

`tests/test_outcome_measurement_acquisition.py` uses two already selected,
local SSE static annual reports for the same issuer:

- the FY2014 report locates consolidated revenue at physical PDF page 54; and
- the FY2015 report locates the same field at physical PDF page 73.

The same test verifies a parent-company revenue field returns
`MEASUREMENT_MISMATCH` against the consolidated frozen boundary, while an
unsupported frozen field returns `UNKNOWN`; both revenue observations remain
available.  The test is local-PDF only and skips rather than replaces the
registered fixture with a web source if that fixture is absent.

## Root-cause handling

An unavailable field must be classified before changing any research claim:

- `DATA_COVERAGE`: no registered annual report or no disclosed direct field.
  Economic effect: that one label cannot be scored.  Required fact: a
  pre-authorised direct field/source.  Remedy: extend a later frozen contract
  and inventory, then run a fresh episode.
- `ACQUISITION_MODULE`: a registered PDF cannot be extracted, its source page
  cannot be identified, or a supported field class is not yet implemented.
  Economic effect: usable disclosure is not yet mechanically accessible.
  Remedy: extend this narrow field catalogue and add a page-level acceptance
  case; do not infer a value from prose.
- `MODEL`: the contract asks a parent, segment or different perimeter question
  while the frozen boundary is consolidated (or the reverse).  Economic
  effect: a substitute could score a different economic entity.  Remedy:
  preserve `MEASUREMENT_MISMATCH` and define a new contract before prediction.
- `REASONING`: a user tries to turn `UNKNOWN` or `MEASUREMENT_MISMATCH` into a
  directional outcome.  Economic effect: false calibration and learning.
  Remedy: retain the status and exclude the cell from scoring.
- `WRITING`: a report omits the page, unit, period or scope needed to reproduce
  an otherwise valid observation.  Economic effect: the fact cannot be
  independently checked.  Remedy: correct the receipt, not the accounting
  value.

No outcome status authorises method transfer, CJO amendment, valuation,
BuyBand, report publication, or investment action.
