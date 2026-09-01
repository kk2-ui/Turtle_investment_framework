# REPORT_AUTONOMY_FIVE_PHASE Independent Engineering Review

## Verdict: BLOCKED

The new bridge compiler is a clean read-only derivation and the focused unit
suite passes.  However, three material production bindings remain incomplete.
They can let the first-pass writer omit the component economics, mix two
different same-cutoff Episodes, or use an unadmitted external industry claim.
Each can change the normal-earnings, owner-cash, permanent-loss, or valuation
route judgment, so these are not presentation-only issues.

## Scope and evidence

Reviewed only the uncommitted five-phase changes in:

- `scripts/industry_evidence_report_admission.py`
- `scripts/judgment_generation_handoff.py`
- `scripts/report_autonomy_bridge.py`
- `scripts/report_completion.py`
- `scripts/turtle_agent/tools/read_tools.py`
- `scripts/turtle_agent/tools/write_tools.py`
- their changed/new tests and five-phase design/audit documents.

No History or outcome material was read, and no network/API call was made.
The focused regression run passed: `35 passed` for
`test_report_autonomy_bridge.py`, `test_judgment_generation_handoff.py`, and
`test_industry_evidence_source_binding.py`.

An isolated temporary-output reproduction then called
`write_enterprise_underwriting_component_reader_bridge` with a valid Episode
and investment contract.  The write returned `ok: true`, while the first
`read_report_contract_pack` returned no `writer_underwriting_handoff`.

## Findings

### F1 — A successfully bound component bridge is not reliably delivered to the first-pass writer

**Classification:** `ACQUISITION_MODULE`

`write_enterprise_underwriting_component_reader_bridge` records a bridge ref
after checking only the supplied Episode and report identity
([write_tools.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/turtle_agent/tools/write_tools.py:460)).
But `read_report_contract_pack` decides whether to read and expose
`JUDGMENT_SYNTHESIS` from only `frozen_cjo_ref` or
`current_company_cjo_admission_ref`; it ignores the bridge ref
([read_tools.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/turtle_agent/tools/read_tools.py:464)).
The bridge is therefore omitted from the contract pack for the valid public
tool outcome above.  More generally, the changed implementation provides only
a writer tool; it does not establish the bridge before the ordinary writer's
first contract-pack read.

The consequence is not merely a late validation inconvenience.  The writer
can draft all chapters without the required component, normal-earnings, and
sensitivity anchors.  It will either fail only at assembly after wasting the
run, or—when no bridge was created at all—continue down the old report path
without the promised constraint.  That can omit or alter the component route
that determines normalized earnings, realizable owner cash, permanent-loss
exposure, and valuation use.

There is no missing company fact.  The prohibited assumption is that a
successful tool write, or an optional tool being visible to an agent, implies
the existing first-pass writer received the binding.

**Executable remediation:** establish the bridge during the normal
Episode-bound report initialization, before the first `read_report_contract_pack`.
Use one activation predicate across the writer tool, contract pack, handoff,
and completion.  Either expose a valid bridge whenever its ref is bound, or
reject a bridge-only binding with a precise prerequisite error if the intended
contract requires Frozen CJO/admission bindings.  Do not let a successful
write create a contract shape that the writer pack silently ignores.

**Acceptance criteria:**

1. A normal Episode-bound initialization persists the bridge ref before the
   first writer pack is read.
2. A successful bridge bind is followed by a first
   `read_report_contract_pack` containing a `READY` bridge in
   `writer_underwriting_handoff`; a deliberately unsupported bridge-only
   contract instead fails at the write/preflight point with a named reason.
3. An assembly test omitting one bridge anchor is `BLOCKED`, while the same
   initialized report containing each anchor reaches the existing downstream
   completion gates.

### F2 — The bridge can originate from a different Episode than the bound Frozen CJO/admission

**Classification:** `REASONING`

The component bridge carries `episode_id` and `underwriting_thesis_id`, but
the newly added checks compare only company and cutoff.  This is true in the
writer tool ([write_tools.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/turtle_agent/tools/write_tools.py:489)),
handoff projection ([judgment_generation_handoff.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/judgment_generation_handoff.py:927)),
and completion ([report_completion.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/report_completion.py:339)).
The Frozen CJO already exposes a thesis projection with those identities, but
the new bridge code never compares them.

Consequently, two reviewable Episodes for the same company and cutoff but with
different component decisions or thesis can both pass their local validation;
one can supply the Frozen CJO/admission while the other supplies the component
anchors.  The writer then receives incompatible economic authorities with no
finding.  This can directly replace the CJO's treatment of normal earnings,
owner cash, permanent loss, or valuation route.

The missing fact is the formal relationship between the bridge Episode and the
Frozen CJO/admission Episode.  The prohibited assumption is that equal company
and calendar-date identities imply equal Episode and underwriting thesis.

**Executable remediation:** when the investment contract binds a Frozen CJO
or current-company admission, resolve its underwriting-thesis projection and
require its `episode_id` and `underwriting_thesis_id` to equal the bridge
identity.  Enforce this at bridge binding/preflight and repeat it in the
handoff/completion validator so a manually written artifact cannot bypass the
check.  Keep a legacy no-CJO route explicit rather than treating it as a
same-Episode match.

**Acceptance criteria:**

1. A bridge from the exact Episode underlying the Frozen CJO/admission is
   `READY` and completes anchor validation.
2. A second reviewable Episode with the same company and cutoff but different
   `episode_id` or `underwriting_thesis_id` is rejected with named
   episode/thesis-mismatch findings.
3. The regression covers writer-tool binding, `JUDGMENT_SYNTHESIS`, and
   `evaluate_report_completion`, not just the bridge's self-derivation.

### F3 — Report admission remains a writer instruction, not an enforced external-evidence boundary

**Classification:** `ACQUISITION_MODULE` + `REASONING`

The new admission projection correctly adds task and transmission identities,
then tells the writer that only its observations may be used
([judgment_generation_handoff.py](/Users/xiami/workspace/analy/worktrees/Turtle_investment_framework/feat-report-autonomy-five-phase/scripts/judgment_generation_handoff.py:1070)).
But no changed completion or assembly logic reads the admission list or checks
the report's external-industry evidence uses.  `report_completion.py` adds
only component-anchor validation; it has no report-admission validator.
Thus a writer can place an unadmitted external industry observation in report
prose and pass the new gate, provided the component anchors are present.

This leaves open precisely the material error the admission layer was intended
to prevent: an unbound industry statistic, customer disclosure, or industry
claim can be narrated as evidence of the target company's transmission.  It
can change the industry-future thesis and its effects on normal economics,
cash conversion, permanent-loss conditions, and valuation treatment.

The missing fact is a report-local identity for each external industry claim
used in the technical narrative and its membership in the admission list.  The
prohibited assumption is that the writer's natural-language instruction alone
constrains all later report evidence use.

**Executable remediation:** use the existing technical evidence-binding path
to require a stable external-industry observation reference for each such
claim, and have completion compare those references with
`report_admitted_industry_evidence.observations`.  Reader-surface projection
may remove the control marker while retaining the prose; no admission should
force a report to invent an industry fact.

**Acceptance criteria:**

1. A technical report use of an unadmitted `IEA` observation is `BLOCKED`
   before publication, with the observation id in the finding.
2. An admitted observation with its paired target-company transmission passes.
3. A report with no external industry observation, or a valid
   `UNKNOWN`/`PUBLIC_INFO_UNAVAILABLE` research outcome, remains eligible for
   the unrelated report gates.

