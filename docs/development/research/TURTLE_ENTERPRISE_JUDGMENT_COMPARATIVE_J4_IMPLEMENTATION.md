# Turtle Enterprise Judgment Comparative J4 Implementation

> Status: `IMPLEMENTED / READ_ONLY_CANONICAL_J1_RESOLVER / SYNTHETIC_REGRESSION_VERIFIED`
>
> Date: 2026-08-26
>
> Architecture: `TURTLE_TRAINING_SYSTEM_TOP_LEVEL_ARCHITECTURE.md` sections 3.2, 8.1 and 10.1

## 1. Purpose

J4 is the narrow bridge from one EnterpriseJudgmentEpisode mechanism thread to
the existing V5 Comparative admission contract. It is not a second Comparative
engine and does not create a candidate from episode prose, industry references,
or partial evidence. Its public resolver reads Frozen J1 from the canonical
local control database; the projection compiler itself remains deterministic
and write-free.

The public J4 entry point requires:

1. the J0 episode manifest and one Frozen J1 identity resolved by the canonical control registry;
2. the complete serialized J2 thread set and selected `thread_id`;
3. six thread-local target-trial bindings; and
4. one complete, unchanged `judgment-selection-admission-v5.v1` bundle.

The J2-to-V5 semantic bridge is not a J4 caller argument. An explicit
`RELATIVE_CAUSAL / E3` thread must already contain its frozen
`comparative_projection_contract`; the J2 compiler validates and carries that
contract into its read model.

`scripts/enterprise_judgment_comparative_projection.py` first calls
`enterprise_judgment_mechanism.compile_mechanism_thread_projection` and uses
only its generated read model. It then checks that the selected thread
explicitly has `claim_type=RELATIVE_CAUSAL` and
`e3_comparative_requested=true`, binds that thread to the V5 identities, and
calls `judgment_selection_v5.validate_v5_candidate`. V5 remains the sole
economic admission authority.

The standalone request protocol is an internal normalization shape. It is not
a public route around J2. J4 does not modify the J0/J2 manifest.

`compile_serialized_j2_thread_projection` accepts no caller-supplied J1
payload, registry connection or J2 read model. It resolves J1 by formal object
identity from the control-plane-owned registry, internally compiles the
J0/J1/J2 sources, then requires exactly one
`RESOLVED`/J4-eligible view and consumes its role, claim type/IDs, H-A/H-B,
responsibility boundary, outcome cells, source refs, local status, evidence
ceiling, E3 request and frozen Comparative contract. This prevents a hand-built J2-shaped object, failed
thread, cross-thread-set splice or post-J2 identity change from entering V5.
A synchronized forged J1 object also fails because J2 first replays its bound
SourcePacketReceipt, source package, model, ledger, spec and DecisionContract,
then compares the entire reconstruction/input bundle with the previously
registered Frozen J1 object. The registry-injectable compiler is private and
exists only for isolated regression tests.
A normal J2 thread therefore maps to
`NOT_REQUESTED`; only `claim_type=RELATIVE_CAUSAL` together with
`e3_comparative_requested=true` maps to the E3 request. Its responsibility unit
and arena must match the V5 target member and competitive arena. The normalizer
also preserves the pre-outcome boundary by rejecting J2 price/return narrative
leakage and source availability later than the episode cutoff before any field
is reduced to the minimal protocol.

## 2. Activation and statuses

| Condition | J4 status | Comparative payload |
|---|---|---|
| Thread does not explicitly request the exact `RELATIVE_CAUSAL/E3` pair | `NOT_REQUESTED` | none |
| The request, local bindings, pre-outcome boundary, or V5 candidate fails | `NOT_ADMITTED` | none |
| All local bindings match and V5 returns `SELECTION_ADMITTED` | `ADMISSION_CANDIDATE` | unchanged deep copy of the V5 bundle |

`ADMISSION_CANDIDATE` means only that the existing pure V5 pre-outcome contract
accepted the supplied bundle. It does not seal a freeze, authorize outcome
access, or create a control-plane record.

Every result names exactly one `thread_id` and fixes these locality statements
to true:

- E0--E2 remain unaffected;
- other mechanism threads remain unaffected;
- the IndustryLearningBlock remains unaffected.

Missing Comparative data therefore cannot become a global episode or industry
gate.

## 3. Local target-trial bindings

The request must bind six groups to exact identities already present in the
supplied V5 bundle:

| Binding | Required V5 identity |
|---|---|
| `action_exposure` | action, focal issuer, exposure start, economic carriers and scope bridges |
| `eligibility_time_zero` | cohort snapshot, eligibility time, action time zero and decision-observable time |
| `comparator_roles` | frozen panel and ordered comparator/witness/falsifier issuer roles |
| `outcome_follow_up` | D3/D4 metric IDs, economic periods, outcome window and minimum exposure rule |
| `censoring_interference` | no-replacement rule plus each member's parallel-action and spillover assumptions |
| `estimand` | target, action, `EXTERNAL_SHOCK_COMPARATOR`, D3/D4 metrics, outcome window and the fixed V5 relative contrast |

The bindings are identity checks, not duplicate estimators or measurement
rules. D3/D4 formulas, panel eligibility, source timing, scope bridges,
materiality, raw matrix completeness and independent pre-outcome review remain
entirely governed by V5.

The J2-owned `comparative_projection_contract` prevents a valid V5 bundle from
silently answering a different question. It is frozen before J4 and stores
three mappings:

1. J2 H-A/H-B IDs and statements to V5 hypothesis IDs and mechanism text;
2. every J2 outcome cell and J0 measurement-contract ref to the exact V5
   measurement-contract objects;
3. J1 source-packet refs and J2 source refs to the exact V5 provenance and
   source manifest.

J4 does not judge approximate prose equivalence or invent the mapping. J2
requires one exact mechanism identity: hypothesis ID and mechanism text must be
identical on both sides. Each J0 outcome cell maps to exactly one full V5
measurement contract whose `metric_id` equals the frozen J0 measurement ref.
J4 then requires the V5 bundle to reproduce the full frozen measurement and
source objects. Replacing mechanism text, metric semantics or source package
after that freeze returns `NOT_ADMITTED` even when the replacement V5 bundle
would independently pass. A caller-supplied bridge field is rejected rather
than used as an override.

A missing or invalid Comparative contract closes only that thread's J4 route.
It does not change its J2 mechanism resolution, sibling threads, E0--E2 or the
IndustryLearningBlock.

Relative references and CompanyArchetypeMap entries are not untreated controls.
J4 rejects them when they are presented as comparator fields, typed comparator
issuer identities, or causal roles. A peer must already be a V5 cohort issuer
with one of V5's causal roles; J4 never recruits or reclassifies it.

## 4. Information and authority boundary

The projection rejects price, return, actual/settlement values, explicit
post-cutoff payload fields, and post-cutoff observation timestamps. V5 still
owns the authoritative cutoff checks for its source manifest and candidate
contract. A later source therefore appears as a V5 finding rather than being
reinterpreted by J4.

The result schema fixes all of the following authority to false:

- database writes and selection sealing;
- outcome reads;
- peer recruitment or H2 fabrication;
- method freeze;
- CJO, report, valuation or investment use.

No function in the J4 module imports a database, reads an outcome artifact,
accesses the network, or writes a file.

## 5. Files and verification

- adapter: `scripts/enterprise_judgment_comparative_projection.py`;
- result schema: `schemas/enterprise_judgment_comparative_projection.schema.json`;
- focused tests: `tests/test_enterprise_judgment_comparative_projection.py`.

The synthetic tests cover the exact activation pair, exact J1 replay,
resolved J2/thread-set binding, post-J2 hypothesis/boundary/outcome/source
changes, J2-to-V5 mechanism/measurement/source replacement, all six missing-binding failures,
caller-supplied bridge override rejection,
thread/candidate identity drift, non-causal reference rejection,
price/return/post-cutoff rejection, V5 source-time rejection, invalid panel
roles, missing H2 provenance, immutability, and thread-local non-blocking
semantics. They establish adapter behavior only; they do not admit a real
company episode or grant any downstream permission.
