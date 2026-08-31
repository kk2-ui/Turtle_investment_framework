# Phase-5 appliance cohort: outcome-measurement binding final review

## Decision — RETURN

The value-free measurement plane is ready: all eight registered references
resolve before task materialization, their carrier dispositions are closed, and
future field receipts are limited to the declared field, unit, status, period
slot, and nonempty source locator.  The result remains a RETURN for one
material protocol defect: later assessment does not validate the complete
four-label receipt against the frozen Episodes.  It trusts a caller-supplied
manifest and a superficially shaped binding receipt instead.

No outcome source, web page, API, arm output, price, return, valuation, or
investment action was opened or executed in this review.

| Required control | Result | Evidence |
| --- | --- | --- |
| All eight contracts resolve before task materialization | PASS | The static plane returned `REVIEWABLE` for the registered preregistration, and `materialize_fresh_tasks` rejects an invalid plane before it writes a task. |
| Exact carrier dispositions and fallbacks | PASS | Each closed-carrier predicate has exactly one rule for each of `IMPROVES` and `DETERIORATES`; the validator rejects a missing pair. Missing or mismatched observations are `INCONCLUSIVE_DATA`, while not-measurable anchors are `NON_DISCRIMINATING`. |
| Four-label receipt records actual frozen claims/directions without arm mapping | RETURN | The builder takes four manifest/Episode pairs and produces an arm-free receipt, but neither the receipt nor the later assessor resolves a registered frozen Episode or verifies the four registered anonymous labels. |
| Later assessment requires an immutable binding and rejects direction/predicate drift | RETURN | It only checks the binding schema/state plus the current label's embedded claims. It does not invoke `validate_anonymous_case_claim_binding_receipt` or validate the manifest against its Episode at assessment time. |
| Receipts are constrained to declared data | PASS | Receipt entries are closed to declared field IDs, units, statuses, values, matching `source_period_slot`, and a nonempty `source_locator`; no price, return, or action field is admissible. |
| Economic limitations remain local | PASS | Industry and generic route claims remain non-discriminating; issuer-carrier, capex, and permanent-loss limitations remain on their respective anchors. |

Focused validation passed: the eight-contract plane returned `REVIEWABLE`, and
`tests/test_report_autonomy_outcome_measurement.py` plus
`tests/test_report_autonomy_cohort_execution.py` passed (`15 passed`).

## Material blocker

**Root cause — MODEL.** `build_anonymous_outcome_assessment` accepts a binding
when its schema/state look right and one embedded entry matches the supplied
manifest.  It never validates the complete four-label receipt, the receipt
authority, or the manifest against the actual frozen Episode.  The assessment
validator repeats that same construction path.

An outcome-free synthetic tamper check changed the normal-earnings manifest
direction from `IMPROVES` to `DETERIORATES` and made the same edit to its
embedded binding entry (also changing the receipt authority).  The builder
and validator still returned `REVIEWABLE`, classifying the normal-earnings
assessment as `WEAKENED_OR_FALSIFIED`.

**Economic impact.** A post-freeze operator could reverse a frozen arm's
direction and thereby reverse the deterministic disposition of an observed
carrier.  That can change the comparative utility conclusion among the four
report-autonomy arms, so it blocks the Phase-5 outcome comparison.  It does
not imply any conclusion about an issuer, price, return, valuation, or action.

**Missing fact and prohibited assumption.** The assessment entry point lacks
verified access to the four registered `FROZEN` Episodes and their anonymous
labels.  It must not assume that a receipt having the expected schema/state,
or a matching serialized claim list, was previously validated and remains
unchanged.

**Executable remediation.** Make the anonymous assessment accept a resolved
four-label binding context (or resolve it from the preregistration): each
label must be one of that case's registered anonymous labels, refer to its
registered `FROZEN` Episode, and reproduce that Episode's exact claims and
directions.  Have both assessment construction and validation call the
complete binding validator before using any receipt.  Keep the receipt arm-free
while retaining those opaque label-to-Episode checks.

**Acceptance criteria.** The review can PASS when a coordinated edit of a
manifest direction plus the corresponding receipt entry, a changed receipt
authority, a missing/wrong registered Episode, or a substituted fourth label
all prevent assessment construction and validation; the eight real contracts
and focused outcome-free tests must still pass.
