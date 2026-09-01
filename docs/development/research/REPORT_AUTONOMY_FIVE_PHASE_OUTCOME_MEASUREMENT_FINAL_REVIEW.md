# Phase-5 appliance cohort: final outcome-measurement review

## Decision — RETURN

The eight outcome-measurement contracts and the pre-task contract gate are now
substantively ready, including the explicit predicate-direction closure added
in the final revision. The outcome-assessment interface is also locally
deterministic given a manifest. The result remains a RETURN because no
manifest is bound to the actual frozen Episode artifact used by the cohort, and
the assessor can therefore accept a direction-altered manifest without ever
reading that artifact. This is a narrow outcome-custody defect; it makes no
company, industry, price, return, valuation, or investment-action conclusion.

No outcome source, web page, API, or arm output was opened during this review.

## Verified controls

| Required control | Result | Evidence |
| --- | --- | --- |
| Closed predicates and fallbacks | PASS | Each of the eight generated contracts has one rule for every `predicate_id × {IMPROVES, DETERIORATES}` pair. The validator requires exact coverage. `UNKNOWN`/`MEASUREMENT_MISMATCH` map to `INCONCLUSIVE_DATA`; the industry-regime and generic-value-route anchors are explicitly `NOT_MEASURABLE_BY_DESIGN` / `NON_DISCRIMINATING`. |
| Declared future receipts only | PASS | Receipts must cover every declared field exactly once, use a declared field ID and matching unit, and use only `OBSERVED`, `UNKNOWN`, or `MEASUREMENT_MISMATCH`. Extra receipt fields, metrics, statuses, duplicate identities, and unit drift are rejected. |
| Deterministic anonymous assessment | PASS, conditional on a valid manifest | The assessment object must exactly equal the deterministic result of contract, receipts, and manifest. It cannot append a claim, metric, predicate, receipt ID, direction, or discretionary status. |
| Dangling contracts block task materialization | PASS | `materialize_fresh_tasks` now calls the eight-contract plane validator before writing any task. The focused negative test covers a missing contract reference. |
| Local economic limits and value freedom | PASS | All contracts keep an issuer carrier from settling an industry-regime claim; preserve the owner-cash/total-capex/maintenance-capital limitation; prohibit price, return, valuation, and investment-action inputs; and do not embed an arm identity, outcome, price, return, or action result. Every declared field now explicitly has `source_role = OFFICIAL_AUDITED_ANNUAL_REPORT`. |

The current static plane validates `REVIEWABLE` for all eight referenced
contracts. The focused suite passed: `15 passed` in
`tests/test_report_autonomy_outcome_measurement.py` and
`tests/test_report_autonomy_cohort_execution.py`.

## Blocking defect

**ACQUISITION_MODULE / MODEL — the manifest is not tied to the actual frozen
Episode.** `frozen_episode_ref` is an unchecked string: it is neither resolved
nor required to name the registered `FROZEN` cell artifact. The cohort
finalizer neither writes nor validates a manifest. The assessment builder then
reconstructs a synthetic Episode from the manifest's own directions instead of
receiving and validating the declared frozen Episode.

With synthetic, outcome-free inputs, a manifest whose `frozen_episode_ref`
does not exist validates as `REVIEWABLE`. Altering its normal-earnings
direction is correctly invalid when tested against the genuine synthetic
Episode, yet a new assessment built from that altered manifest validates as
`REVIEWABLE`, because assessment does not receive the genuine Episode. This
demonstrates the missing custody link without accessing any actual report or
arm artifact.

### Economic-protocol impact

A post-freeze operator could substitute a direction-bearing manifest while
retaining the expected opaque label and case contract. The deterministic
assessor would score the substituted direction rather than the frozen arm's
structured direction. That can change the comparison among report-generation
arms, so it blocks a Phase-5 autonomy conclusion even though it says nothing
about any investment outcome.

### Missing facts and prohibited assumption

What is missing is a registered, immutable-in-workflow manifest artifact linked
to a specific `FROZEN` episode path and cell. The prohibited assumption is that
an arbitrary reference string, or a manifest previously validated against an
in-memory Episode, is evidence that the assessor received the exact frozen
Episode from the cohort.

### Executable remediation

1. Add a declared anonymous-manifest artifact/reference to the execution
   register and materialize it only from the registered `episode_ref` after
   that cell is `FROZEN`.
2. Make manifest validation resolve that registered artifact, check the frozen
   cell/case/opaque-label association, and compare every directional claim
   directly with the Episode's structured economic directions and its fixed
   anchor.
3. Require the assessment entry point to receive that resolved validation
   context (rather than reconstructing an Episode from the manifest). Reject a
   missing reference, a non-frozen cell, or any manifest-direction drift before
   receipt settlement.
4. Add focused negative tests for a nonexistent or wrong episode reference and
   for an altered manifest direction that must make assessment construction and
   validation fail. Add the cohort-level positive test proving every frozen
   cell's manifest is generated at its declared location.

## Acceptance criteria for PASS

This review becomes PASS when the eight current contracts still validate and:

- each anonymous manifest is generated from, stored with, and validated against
  its registered `FROZEN` Episode;
- no missing/wrong `frozen_episode_ref` or altered structured direction can
  reach a reviewable assessment; and
- the focused tests above pass without reading post-cutoff outcomes or
  revealing arm mappings to the custodian or assessor.
