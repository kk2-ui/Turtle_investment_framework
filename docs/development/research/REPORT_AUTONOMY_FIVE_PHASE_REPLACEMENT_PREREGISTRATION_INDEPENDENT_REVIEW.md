# Independent review — Appliance Stage-5 interface-v2 replacement preregistration

## Decision

**PASS.** The replacement register is admissible for its first, fresh 32-cell
pre-outcome execution. There is no blocking root cause (`DATA_COVERAGE`,
`ACQUISITION_MODULE`, `REASONING`, `MODEL`, or `WRITING`: **none**), no
identified experimental impact, and no required remediation.

This was a pre-outcome static review only. I did not run a cohort cell,
materialize a cell, invoke the preregistration or outcome-measurement programs,
open a raw response, access an outcome/post-cutoff source, or use web/API
access.

## Scope reviewed

- `REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231_INTERFACE_V2/00_REPLACEMENT_PROTOCOL.md`
- the replacement `00_MULTICOMPANY_PREREGISTRATION.json`
- all eight replacement value-free measurement contracts (`CASE_01.json` through
  `CASE_08.json`)
- the prior preregistration only for cohort, cutoff, source-package, arm, and
  opaque-label continuity comparisons
- `scripts/report_autonomy_appliance_cohort_prereg_generator.py` and
  `scripts/report_autonomy_outcome_measurement.py`

## Findings

The replacement has a new cohort identity:
`REPORT_AUTONOMY:APPLIANCE:20181231:STAGE5:INTERFACE_V2`. All 32 declared
artifact paths, including the unique raw-response targets, are under the new
`...APPLIANCE_20181231_INTERFACE_V2/execution/` root. The root currently
contains only the eight declared pre-outcome measurement contracts; it contains
no arm response, episode, reader, or freeze artifact. All 32 cells are
`NOT_STARTED` with `episode: 0` and `reader_report: 0` attempts.

The replacement carries 32 valid, unique opaque labels. They match the required
opaque-label pattern and are disjoint from the prior cohort's labels. Its new
preregistration ID, artifact root, anonymous custody paths, and outcome
contract IDs therefore prevent a declared replacement artifact from resolving
to a prior-cohort artifact.

The cohort is exactly continuous with the original register: the full
13-candidate universe, eligibility/exclusions, selection policy, selected
eight cases, selection ranks, cutoff (`2018-12-31T23:59:59+08:00`), source
availability, common source-package references, industry-memory asset, and
expert-correction asset match. The eight selected case/company mappings remain
`01/000016`, `02/000404`, `03/002403`, `04/002543`, `05/002614`, `06/002676`,
`07/002705`, and `08/603355`. The common source packages intentionally retain
the original source-package root: they are the fixed shared inputs, not reused
response artifacts.

The 2×2 arm design is unchanged and balanced. Each case has exactly one
`A00`, `A01`, `A10`, and `A11` cell; every arm retains the same one-episode and
one-reader attempt limit, 1,800-second limit for each phase, 3,000-word
episode ceiling, 5,000-word reader ceiling, and `NO_RETRY_OR_REWRITE` policy.
Each arm retains the same source budget as the prior register: pre-cutoff
package only (`A00`), plus industry memory (`A01`), plus expert-correction
memory (`A10`), or both memories (`A11`).

The outcome plane is sealed and value-free. The top-level gate is
`BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN`, authorization is
`false`, and it requires a frozen anonymous-review receipt for each of the
eight cases. Each `CASE_01`–`CASE_08` contract is
`PREOUTCOME_FROZEN`/`SEALED`, permits only value-free field receipts, prohibits
arm output/mapping, price, return, valuation, and investment-action inputs, and
contains no observation values or source locators. Each fixes 30
issuer-consolidated fields, the same three post-cutoff annual-report slots, and
the closed five-domain anchor set; the assessor cannot add a field or
predicate.

Most importantly, every one of the 32 rendered fresh task packets now makes
`driver_sensitivity_spec.responsibility_boundary` a required field, typed as a
non-empty string, and names it in the task instructions. This repairs the
prior task/validator interface mismatch before any replacement cell is run.

## Non-blocking traceability note

The per-arm training-contract identifiers retain the prior `...:V2` strings.
That is not an execution or raw-response reuse path here: the replacement
preregistration ID, artifact root, opaque labels, anonymous custody paths, and
outcome-contract IDs are all distinct, and all replacement cells are fresh at
zero attempts. Including the replacement cohort ID in a future training
contract identifier could improve human traceability, but it is a naming-only
enhancement and does not change this experiment's admissibility or conclusion.
