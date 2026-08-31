# Five-phase report-autonomy independent engineering re-review

## Verdict: PASS

This re-review covered only the F3 remediation and targeted F1/F2 regression protection. No outcome or history artifact was read.

F3 is now enforced in the final technical-report completion path:

- Every stable `IEA:` identity in technical text is scanned, whether or not it has a display marker.
- Every scanned identity requires a corresponding `claim_evidence.json` raw-fact declaration. The technical-text and declared-ID sets must match exactly.
- Each declaration must match a validated report-admission entry and preserve that entry’s exact `industry_task_id` and `transmission_requirement_id`.
- A report with neither a technical `IEA:` identity nor a declaration remains correctly `SKIP`.

This removes the prior assumption that the writer would voluntarily add `[industry-evidence: ...]`. The tool schema and writer contract now expose the three required declaration fields, while reader prose can remain marker-free.

The required F3 acceptance cases are covered and pass in `tests/test_industry_evidence_source_binding.py`:

1. An unmarked `IEA:` identity without a readable structured claim ledger is `INVALID`, not `SKIP`.
2. An admitted identity with its exact structured record is `DECISION_READY`.
3. An unadmitted record and a mismatched task/transmission requirement are each `INVALID`.

F1/F2 remain intact: the existing targeted bridge suite still verifies pre-writer bridge initialization, first contract-pack delivery, exact Episode derivation, and Frozen-CJO/current-company-admission episode/thesis identity rejection.

## Targeted verification

`.venv/bin/python -m pytest -q tests/test_industry_evidence_source_binding.py tests/test_report_autonomy_bridge.py tests/test_judgment_generation_handoff.py` completed successfully: **38 passed**.

## Stage 5 multi-company preregistration control-plane re-review

### Verdict: PASS

Scope was limited to `scripts/report_autonomy_multicompany_prereg.py`, its
focused regression test, and the design document's implementation appendix.
No outcomes were read.

The control plane enforces the required pre-outcome experiment shape:

- exactly eight unique cases and the complete 8×4 case/arm bijection (32 cells);
- current v2 individual contracts, with each rendered task equal to a fresh
  deterministic rendering of that exact contract;
- identical case-level pre-cutoff sources and every other common contract field
  across arms; the delegated v2 contract validator also rejects a source whose
  `available_at` is after the case cutoff;
- exact A00/A01/A10/A11 `TRAINING_MEMORY` inclusion, with registered
  company-free, target-evidence-prohibited memory declarations;
- frozen cohort selection, no replacements, no retry/rewrite policy, one-attempt
  budgets, and state-consistent attempt counters;
- a 32-row anonymous reviewer manifest that is a case/label bijection and rejects
  treatment-arm identifiers; and
- one identity-matched outcome-measurement contract per case plus a sealed,
  unauthorized pre-outcome access gate requiring every case's reviewer-freeze
  receipt.

The implementation deliberately validates the register rather than inventing
companies, sources, tasks, reports, outcomes, or a qualified cohort. The lack
of a live eligible cohort is therefore not a validator defect or a reason to
block this control-plane implementation.

### Targeted verification

`.venv/bin/python -m pytest -q tests/test_report_autonomy_multicompany_prereg.py` completed successfully: **6 passed**.
