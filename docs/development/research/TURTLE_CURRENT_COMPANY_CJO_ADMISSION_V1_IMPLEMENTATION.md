# Current-company CJO admission v1

Status: `SYNTHETIC_ACCEPTED / REAL_COMPANY_PRE_FREEZE`.

This is the narrow pre-freeze admission layer for a current-company,
directional `PRIMARY` CJO. It consumes the generic Enterprise Judgment Core;
it does not change its schema, invent source facts, or turn a generic CJO into
an investment authorization.

```text
EnterpriseSystemModel + ManagementDecisionLedger + source package
  -> Core CJO candidate
  + Financial Driver Bridge + two-sided Thesis Test
  -> current-company admission review binding
  -> independently reviewed Frozen CJO + immutable admission receipt
  -> synthetic Overlay / INVESTMENT_ENRICHMENT read
```

## Admission boundary

`PRIMARY_ADMITTED` requires exact company, cutoff, method and source-package
identity; all central traces, CJO forward judgments, operating variables and
financial transmissions must be explicitly bound. The selected thesis side and
its mechanism chains must match each CJO forward judgment binding.

Every material driver is observed and monitored, cash conversion is
`NORMALIZED`, and any material allocation event is resolved with its early and
terminal realization contracts. The selected rival-hypothesis side cannot have
an unknown critical assumption or causal trace. A `NO_PRIMARY` or `MIXED` CJO
may still be independently frozen as `REVIEWED_NOT_PRIMARY`, preserving its
unknowns and report-read boundary, but cannot enter Overlay.

The independent Core review is supplemented by a current-company review
binding. It exactly records the compiled candidate time, admission ID, source
package and primary binding. A valid recompile with a changed `compiled_at` or
binding needs a new independent review; a reused candidate ID is insufficient.

## Downstream enforcement

`freeze_admitted_current_company_cjo` returns a separate immutable admission
receipt bound to the frozen CJO ID, full identity, Core review receipt and
admission context. The dedicated quantitative Overlay requires this receipt
and `overlay_read_allowed=true`; a bare generic Frozen CJO is rejected.

For contract-bound `INVESTMENT_ENRICHMENT`, `analysis_contract.json` now has:

```json
{
  "canonical_judgment_refs": {
    "frozen_cjo_ref": "canonical/frozen_cjo.json",
    "current_company_cjo_admission_ref": "canonical/current_company_cjo_admission.json",
    "investment_overlay_ref": "canonical/investment_overlay.json"
  }
}
```

The handoff verifies the admission receipt, Frozen CJO and Overlay exact
identity before producing the read-only report projection. `JUDGMENT_SYNTHESIS`
may still present an independently reviewed non-directional CJO, but it cannot
be paired with an Overlay.

## Explicit non-results

This implementation does not freeze a real company CJO or produce a real
BuyBand. The current Gree package remains `PRE_FREEZE / NO_PRIMARY`: it still
needs a licensed same-definition industry release plus a complete frozen
financial-driver and rival-thesis package. No price, outcome, Forecast,
Measurement Contract or training object is read by this gate.

Focused synthetic acceptance covers closed driver/owner-cash/event bindings,
unknown preservation, selected-side compatibility, immutable review binding,
bare-Core Overlay rejection, non-directional Overlay closure and report-handoff
identity matching.
