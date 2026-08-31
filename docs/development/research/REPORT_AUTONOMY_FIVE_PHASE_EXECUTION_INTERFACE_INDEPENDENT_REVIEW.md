# Independent execution-interface review

## Decision: RETURN

The frozen response contract permits the omission that the binding validation
path treats as required.  This is a pre-outcome protocol defect, not an
underwriting judgment failure.

`fresh_task.json` declares `response_contract.episode_json_schema` to be the
authoritative shape and says to honour each *applicable required* field.  In
that schema, `responsibility_boundary` is **not** in
`$defs.driver_sensitivity_spec.required`; it is therefore optional for every
driver sensitivity.  It is required only in the nested
`sensitivity_delta_magnitude_evidence` and
`sensitivity_magnitude_observation` definitions.  The prose likewise ties
the field to non-PRESERVED bounded-delta magnitude evidence, rather than
unambiguously requiring it on each driver sensitivity.

That is incompatible with a binding validator that requires a responsibility
boundary for the driver sensitivity itself.  The training wrapper binds every
fresh response through that validator before persistence, and the cohort
runner freezes an invalid result with no retry.  The three attempted raw
responses (CASE:01/A00, CASE:02/A01, and CASE:03/A10) all omit
`responsibility_boundary` from every `driver_sensitivity_spec`; all three are
recorded as `EPISODE_INVALID`.  Their transmissions are `UNKNOWN`, so no
nested magnitude-evidence object is present to make the otherwise optional
top-level field required by the frozen schema.

Root cause: `ACQUISITION_MODULE` (the task/schema/validator execution
interface), not `DATA_COVERAGE`, `REASONING`, `MODEL`, or `WRITING`.  The
agent behaviour is a predictable consequence of the supplied contract; it is
not a valid basis for comparing underwriting capability.

Economic and experimental impact: no investment, price, return, or outcome
claim has been made, because the outcome gate remains sealed.  But continuing
would spend the remaining 29 one-shot attempts under a known incompatible
contract and can mechanically convert arm/case observations into invalid
episodes.  That would materially corrupt the later autonomy/quality
comparison and leave the cohort unable to support a downstream economic
conclusion.

The remaining 29 `NOT_STARTED` cells must stop.  Do not retry or rewrite the
three frozen invalid attempts, and do not amend the existing 32-cell register
and proceed: either action violates its `NO_RETRY_OR_REWRITE` preregistration.
Treat this cohort as protocol-invalid for comparative/outcome inference.

Remediation is to create a new, separately identified preregistered cohort
after aligning the interface:

1. Make `responsibility_boundary` required in
   `$defs.driver_sensitivity_spec` if the binding validator requires it there;
   state that exact per-sensitivity requirement in the rendered task's
   semantic instructions.  Keep the existing nested requirements unchanged.
2. Add one focused contract-parity test: an otherwise-valid fixture missing
   the driver-sensitivity boundary must fail both the frozen task schema and
   the binding validator; the same fixture with a non-empty boundary must
   clear that requirement in both.  If the validator is instead intended to
   require the field only for bounded magnitude evidence, narrow the validator
   to that same condition rather than imposing an unstated broader rule.
3. Freeze and independently review the new task packet, schema, validator
   parity result, and a fresh preregistration before any new response is
   collected.  The new cohort must begin at zero attempts, retain the sealed
   outcome boundary, and never reuse these raw responses or attempt counts.

Acceptance requires an unambiguous, identical field obligation at the driver
sensitivity level in the task schema, rendered instructions, and binding
validator; a passing targeted parity test; and a new pre-outcome
preregistration accepted before execution.  Only then may a new cohort start.

RETURN
