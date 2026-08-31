# Phase-5 appliance cohort: outcome-measurement re-review

## Decision — RETURN

This outcome-blind re-review confirms that the eight referenced contracts now exist and that the new static plane resolves all eight.  That is meaningful progress, but it is not yet sufficient to PASS the prior protocol return: the contracts name predicates without freezing how a predicate result becomes `SUPPORTED`, `WEAKENED_OR_FALSIFIED`, or the fallback assessment state, and there is no anonymous arm-claim binding or custody/assessor validation path.

No FY2018+ outcome material, prices, returns, valuations, action data, arm output, or external source was opened; no arm was executed.

## Confirmed controls

- `CASE_01.json` through `CASE_08.json` exist at their frozen preregistration references.  `report_autonomy_outcome_measurement.py validate ...00_MULTICOMPANY_PREREGISTRATION.json --project-root .` returned `REVIEWABLE` with no findings.
- Every contract is value-free and has 30 declared direct fields (ten named carriers across fixed `P1`/`P2`/`P3`, FY2018–FY2020), units, source line identities, and the listed-issuer-consolidated boundary.
- `UNKNOWN` and `MEASUREMENT_MISMATCH` map to `INCONCLUSIVE_DATA`; explicit industry-regime and generic value-route anchors map to `NOT_MEASURABLE_BY_DESIGN` / `NON_DISCRIMINATING`.
- The fixed limitations prevent total long-lived-asset cash from becoming maintenance capex, prevent survival/no-event reasoning for permanent-loss safety, and prevent issuer carriers from settling an industry regime.  Contracts prohibit and reject price, return, valuation, investment-action, and arm-mapping fields.
- The targeted suite passed: `4 passed` in `tests/test_report_autonomy_outcome_measurement.py`.

## Blocking gaps

1. **MODEL — predicate results have no closed assessment disposition.**  An anchor only carries an unlabelled list of predicates.  It has no `supports_when`, `weakens_or_falsifies_when`, `otherwise_status`, or equivalent mapping.  For example, the three permanent-loss predicates do not say whether one, all, or which combination yields which assessment state.  The allowed-state list and the ban on added predicates do not remove this later assessor discretion.

2. **ACQUISITION_MODULE / MODEL — no implementation binds anonymous arm claims to anchors or enforces the later custodian/assessor handoff.**  The new module has no arm-claim-manifest schema/validator, receipt schema, anonymous assessment record, or integration into the cohort's execution gate.  Its only consumers are its direct tests.  Therefore, after arm production an assessor could still select an anchor, claim direction, or disposition rule per arm after seeing the reports; the contract's prohibition on embedding an arm mapping does not supply the required separate frozen binding.

These gaps can change the comparative conclusion about the four arms by letting a later evaluator choose the rule or carrier most favorable to a report.  They do not support any company, industry, valuation, price, return, or investment conclusion.

## Required remediation and acceptance

Add a closed per-anchor disposition grammar that maps declared predicate IDs and the unknown/mismatch fallback to exactly one assessment status; validate exhaustive, non-overlapping treatment.  Add a value-free anonymous arm-claim manifest and validator that, after all four arms are frozen but before outcome access, binds each material eligible claim and direction to exactly one compatible anchor.  Add the custodian receipt and anonymous assessor record validation so only declared fields, predicate IDs, and receipt IDs can reach settlement, and disclose mapping only after that record freezes.  Wire the plane and manifest checks into the cohort gate and add positive/negative value-free tests for these paths.

This re-review can become a PASS only when the actual eight-contract plane and those new arm-binding/custody tests pass without outcome access.  Until then, keep outcome sources sealed and do not treat the static `REVIEWABLE` result as authorization for outcome assessment or a Phase-5 autonomy conclusion.
