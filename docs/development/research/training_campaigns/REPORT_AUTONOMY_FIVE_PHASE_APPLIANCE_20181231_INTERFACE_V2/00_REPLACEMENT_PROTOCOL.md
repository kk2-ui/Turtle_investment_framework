# Appliance Stage-5 interface-v2 replacement protocol

## Status

`PREOUTCOME_REPLACEMENT_PENDING_REVIEW`.

This is a separately identified replacement cohort for the protocol-invalid
`REPORT_AUTONOMY:APPLIANCE:20181231:STAGE5` register. It does not amend that
register, retry any of its three frozen invalid cells, reuse their raw
responses, or open any outcome source.

## Why replacement is necessary

The prior frozen task made `responsibility_boundary` optional in each driver
sensitivity's JSON schema, while the v2 binding validator required it. The
three first attempts therefore failed at the same task-interface surface. The
independent finding is recorded in
`docs/development/research/REPORT_AUTONOMY_FIVE_PHASE_EXECUTION_INTERFACE_INDEPENDENT_REVIEW.md`.

The repaired v2 task now requires that field in its delivered execution schema
and task text, consistently with the binding validator. Independent repair
review is recorded in
`docs/development/research/REPORT_AUTONOMY_FIVE_PHASE_EXECUTION_INTERFACE_REPAIR_INDEPENDENT_REVIEW.md`.

## Invariants carried forward

- Same 13-candidate universe, selected eight companies, cutoff, selection
  ranks, exclusions, common source packages, industry-memory asset,
  expert-correction asset, arms, arm source budgets, feedback clocks, and
  outcome measurement design.
- Same prohibition on external model APIs, web access, post-cutoff sources,
  price, return, valuation result, and investment action during pre-outcome
  work.
- One fresh `fork_turns=none` agent response per cell, no retry or rewrite;
  complete Episode first, deterministic reader report second.
- New task, output, anonymous-label, and outcome-contract paths. The new
  cohort begins with all 32 cells `NOT_STARTED` and zero attempts.

## Changed surface

Only the v2 task/validator parity defect is corrected: each driver sensitivity
must carry its own non-empty `responsibility_boundary`, even when its
transmission is `UNKNOWN` or `PRESERVED`.

No outcome access is permitted until all anonymous pre-outcome reviews for the
new cohort are frozen.
