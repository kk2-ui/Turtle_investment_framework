# Phase-5 appliance cohort: independent outcome-measurement protocol review

**Scope:** the frozen 8-case × 4-arm preregistration, the Phase-5 design, and the local preregistration validator. This is an outcome-blind protocol review. It did not open any FY2018+ outcome material, prices, returns, valuations, historical arm output, settlement object, web page, external API, or execute an arm.

## Decision — RETURN

The cohort has an outcome gate and eight case-level references, but it does not yet have eight frozen outcome-measurement contracts. The references alone cannot settle an arm's industry/situation, normal-earnings, owner-cash, permanent-loss, or value-route claim without allowing the later observer to choose the metric, clock, responsibility boundary, and interpretation after seeing the report.

This RETURN is limited to Phase-5 outcome-measurement readiness. It makes no company, industry, valuation, price, return, or investment conclusion. Do not open outcome sources or authorize outcome access. Because the Phase-5 design requires each case's matrix before the arms start, do not start the Phase-5 cells until the eight contracts below have been materialized and passed static validation.

### Observed protocol gap

Each outcome_measurements entry currently fixes only the case identity, cutoff, a broad official-source category, a first-complete-report phrase, a listed-issuer-consolidated phrase, generic mismatch/disposition phrases, and a nonempty measurement_contract_ref. The referenced execution/measurements/CASE_*.json objects are not present. The current multicompany preregistration validator checks that the reference is nonempty; it does not resolve it or validate a contract behind it.

Those controls are useful identity and custody controls. They are not a measurement specification. No frozen object currently states:

- which exact issuer or industry observation carries each claim;
- the fiscal periods, baseline, comparison clock, units, or permitted transformations;
- whether a group, parent, segment, joint venture, or ordinary-shareholder boundary is admissible for that claim;
- what a transient reported result can and cannot say about normal economics, owner cash, permanent loss, or a route to value; or
- the finite rule by which an anonymous frozen arm claim receives SUPPORTED, WEAKENED_OR_FALSIFIED, INCONCLUSIVE_DATA, or NON_DISCRIMINATING.

FIRST_COMPLETE_FISCAL_YEAR_AFTER_CUTOFF cannot by itself resolve these questions. A first annual report can be an implementation or operating-carrier observation. It is not, without an already declared multi-period rule and scope, evidence that a normal earnings level persisted, that cash was ordinary-shareholder owner cash, that permanent loss was avoided, or that a value route realized.

## Why this blocks the Phase-5 conclusion

| Claim surface | What an after-the-fact assessor could otherwise choose | Material economic effect |
| --- | --- | --- |
| Industry / situation | An issuer proxy, a segment, a favorable industry narrative, or a different period | A company print could be narrated as a structural industry confirmation even when it only observes one operating carrier. |
| Normal earnings | Reported profit line, one-off exclusion, period, or normalization basis | A cyclical or exceptional result could be scored as proof or disproof of sustainable earning power. |
| Owner cash | Operating cash, total capex, an assumed maintenance capex, parent cash, or consolidated cash | Cash absorption or ordinary-shareholder accessibility could be overstated or silently ignored. |
| Permanent loss | A no-event, a solvency metric, an impairment, dilution, or a price move | A slow erosion path could be missed, or the absence of bankruptcy could be treated as protection. |
| Value route | A price/return, a reported operating number, or a different component/routing assumption | A route could be declared validated even though its required owner-cash or realization condition was never observed. |

The problem can change the causal comparison of the four arms. Different reports can emphasize different components; a post-outcome evaluator could then use the metric most flattering to an arm's prose rather than the common predeclared evidence carrier. This is not an unavailable immaterial field: it can reverse the claimed report-autonomy improvement and misdirect later method adoption.

### Root-cause classification

| Classification | Defect | Prohibited assumption | Executable remediation |
| --- | --- | --- | --- |
| DATA_COVERAGE | The contract has no per-claim field identity, observation window, baseline, unit, or completeness rule. | A later annual report will make the relevant measure self-evident. | Freeze a finite observation-field inventory and an explicit NOT_MEASURABLE_BY_DESIGN treatment for each uncovered domain. |
| ACQUISITION_MODULE | A pointer is accepted without an existing, schema-valid, value-free contract. | A nonempty path means the custodian can acquire an admissible field. | Resolve and validate all eight contract files before any arm; validate later receipts against those files only. |
| MODEL | There is no closed claim-to-measurement and predicate grammar, nor a frozen anonymous-arm claim binding. | A reviewer can consistently infer what “supported” means from prose. | Add assessment anchors, deterministic predicates, and frozen arm binding manifests. |
| REASONING | Generic issuer-consolidated and first-report labels allow a proxy to stand in for normal earnings, owner cash, permanent loss, or value realization. | A convenient disclosed proxy has the same economic responsibility as the claim. | Enforce the boundary, carrier, and limitation rules below; preserve non-comparable outcomes instead of substituting. |

WRITING is not the root cause. Better prose around the present references would not make a later settlement reproducible.

## Reusable, outcome-blind measurement-contract schema

Materialize one closed JSON object per case before any Phase-5 arm. The object contains definitions and identifiers only: no post-cutoff values, outcome pages, outcome narrative, arm identity, anonymous-arm judgment, price, return, valuation, or investment action. A formal implementation may call it report-autonomy-outcome-measurement-contract.v1.

### 1. Identity, custody, and clock

Every contract must include these closed groups.

| Group | Required fields |
| --- | --- |
| identity | schema_version, immutable contract_id, preregistration_id, case_id, company_id, legal listed-issuer identity, cutoff_at, and PREOUTCOME_FROZEN state. |
| custody | outcome_access = SEALED, authorized roles, declared receipt/output paths, and an explicit prohibition on arm mapping, arm output, price, return, valuation, and action inputs to the custodian. |
| source_policy | Allowed source role(s), issuer identity, original-report/version precedence, audited-report requirement where applicable, publication chronology, and a rule for amendments/restatements. A restatement cannot silently replace a previously specified comparison series. |
| observation_calendar | Named, finite period slots with fiscal start/end, read order, base period, and the exact number of reports required for each assessment anchor. P1, P2, etc. must resolve to one fixed fiscal-period rule before observation. |
| outcome_status_policy | Observation states, the allowed mismatch reasons, and the closed mapping to assessment states. |

The source policy may permit an issuer audited annual report and, when an industry-wide claim truly needs it, a specifically defined official industry/regulatory series. If the Phase-5 source restriction remains issuer-annual-reports-only, the contract must label an industry-wide regime claim NOT_MEASURABLE_BY_DESIGN; it may assess only the explicitly named issuer operating carrier. It must not promote that carrier into an industry verdict.

### 2. Responsibility-boundary registry

All measurement fields and assessment anchors reference a registry entry; free-text scope is not enough. A boundary entry declares:

- boundary_id, issuer_id, accounting scope (LISTED_ISSUER_CONSOLIDATED, PARENT_COMPANY_ONLY, or DECLARED_OPERATING_SEGMENT), legal/entity coverage, currency and unit policy, and ordinary-shareholder claim coverage where cash or per-share value is at issue;
- a continuity rule for mergers, disposals, reverse acquisitions, accounting restatements, reporting-currency changes, and segment reorganization; and
- for a segment, immutable segment_id, accepted issuer disclosure label(s), the allowed segment metric, and its relation to the issuer-wide claim.

A parent-company line never substitutes for a consolidated measurement, and a segment line never substitutes for the consolidated issuer. A segment can support a segment-scoped component only. It can support an issuer-wide claim only if the contract separately names the complete segment set, reconciliation rule, and predeclared economic bridge. A renamed, reorganized, or incompletely disclosed segment is MEASUREMENT_MISMATCH, not the “closest” segment selected by an assessor.

### 3. Observation-field registry

The contract has a finite measurement_fields array. Each field contains:

    field_id
    field_group
    source_role + source_field_identity
    boundary_id
    period_slot(s) + comparison_clock
    observation_kind
    unit/currency/per-share basis
    required_for_assessment_ids
    allowed_observation_statuses

field_group is one of the following common groups; a case may have no field in a group only when an affected assessment anchor says NOT_MEASURABLE_BY_DESIGN.

| Group | Minimum contract meaning |
| --- | --- |
| INDUSTRY_SITUATION_CARRIER | A direct named operating carrier—such as a disclosed volume, price/mix, utilization, order/backlog, capacity, or official industry series—and the scope it can represent. It is not an unbounded “industry outcome” field. |
| NORMAL_EARNINGS_CARRIER | A direct reported earnings/operating-profit carrier plus the predeclared reference series, exceptional-item treatment, and persistence window. Without those inputs it assesses reported-period performance only, not normal earnings. |
| OWNER_CASH_CARRIER | Direct operating cash, working-capital, long-lived investment, distributions, and cash-accessibility fields needed by the stated claim. Maintenance capital is usable only when it is directly disclosed or calculated from a frozen formula and frozen inputs; total capex cannot be renamed maintenance capex. |
| PERMANENT_LOSS_CARRIER | A named loss route such as durable earnings erosion, cash absorption, leverage/refinancing pressure, dilution, asset impairment, or capital-return failure, with its required direct carriers. It excludes price and return. |
| VALUE_ROUTE_CONDITION | A route-specific operating, asset-realization, distribution, or incremental-return condition. It assesses whether that named route remains economically available; it never supplies a price, return, or action result. |

observation_kind is limited to DIRECT_NUMERIC, DIRECT_EVENT, or DERIVED_FROM_DECLARED_FIELDS. A derived field declares its complete input set, arithmetic, comparison order, unit conversion, and rounding rule. No narrative extraction, undisclosed adjustment, replacement financial line, or new ratio is permitted during custody.

### 4. Assessment-anchor registry

An observation is not a settlement. Each assessment_anchor freezes the only admissible connection between measured fields and a claim surface:

    assessment_id
    claim_domain
    claim_scope / boundary_id
    eligible_measurement_field_ids
    minimum_observed_period_slots
    comparison_clock and frozen predicates
    supports_when / weakens_or_falsifies_when
    otherwise_status
    limitations

claim_domain is one of INDUSTRY_SITUATION, NORMAL_EARNINGS, OWNER_CASH, PERMANENT_LOSS, or VALUE_ROUTE. Predicate syntax must be machine-closed: direct event, signed/thresholded delta, bounded range, ALL_OF, or ANY_OF over already named fields. It must include an explicit ambiguous band or fallback. Free-text rules such as “materially improved” or “looks sustainable” are invalid.

The limitation is substantive:

- An industry anchor distinguishes an issuer carrier from an industry-regime conclusion.
- A normal-earnings anchor requires its full persistence/exceptional-item rule; otherwise it can settle only a reported-period carrier.
- An owner-cash anchor must keep normal owner cash, total current capital absorption, and growth-return evidence separate.
- A permanent-loss anchor cannot treat a single no-bankruptcy/no-impairment observation as support for safety. It may observe a named loss route, or remain non-discriminating/inconclusive.
- A value-route anchor identifies its route type and required components. A route remains inconclusive if a required owner-cash, realization, or incremental-return condition is unobserved; it cannot be validated from a stock-price or total-return outcome.

### 5. Anonymous-arm claim manifest

Before outcome access, each frozen anonymous arm needs a compact, value-free arm_claim_manifest that binds its material claim to an existing assessment_id. It contains only anonymous label, frozen artifact identity, claim domain, assessment_id, direction/conditionality taken verbatim from the frozen Episode, referenced component or value-route ID where relevant, and OUT_OF_SCOPE/UNKNOWN treatment where no outcome assertion is made.

The renderer should give every arm the case contract. It may not invent an anchor. A deterministic post-freeze validator verifies that a material, outcome-eligible arm claim has exactly one compatible anchor and that the frozen direction is evaluated only by that anchor's predicate. A genuinely nonmeasurable claim remains visible as OUT_OF_SCOPE or UNKNOWN; it is not converted into a favorable outcome. An unbound material claim cannot later be scored and makes the paired case PAIRED_TEST_INVALID, rather than inviting an assessor to bind it after outcomes are visible.

### 6. Legal local uncertainty

The following are legal terminal states, with local—not enterprise-wide—effect:

| Layer | Allowed state | Treatment |
| --- | --- | --- |
| Acquisition | OBSERVED | Only when source field, period, boundary, unit, and source-version rule exactly match. |
| Acquisition | UNKNOWN | The direct permitted field/source is absent or undisclosed. It is not zero, deterioration, or an invitation to find a substitute. |
| Acquisition | MEASUREMENT_MISMATCH | The disclosed material has the wrong issuer, boundary, period, unit, field identity, or a contract-defined continuity failure. |
| Assessment | SUPPORTED / WEAKENED_OR_FALSIFIED | Only a predeclared predicate over eligible OBSERVED fields can reach either state. |
| Assessment | INCONCLUSIVE_DATA | Required field is UNKNOWN or MEASUREMENT_MISMATCH; retain the reason and do not infer a sign. |
| Assessment | NON_DISCRIMINATING | All required observations may exist, but the frozen rule says the specified clock/carrier cannot distinguish the claim. |

The current preregistration's broad PRESERVE_SOURCE_MISMATCH rule should be implemented as an immutable MEASUREMENT_MISMATCH observation with the assessment state INCONCLUSIVE_DATA, unless the preregistration is formally amended before arms to add a distinct top-level state. Creating an unregistered status during settlement is not permitted.

## Required validator behaviour

The reusable validator should validate the preregistration and the eight contracts as one pre-outcome control plane. It need not fetch an outcome source to do so.

1. **Reference existence and identity.** Resolve every referenced contract; require exactly eight unique, closed-schema, PREOUTCOME_FROZEN objects. Require exact preregistration/case/company/cutoff agreement and reject missing files, duplicate contract IDs, mutable/relative escape paths, and any outcome observation or arm result embedded in the contract.

2. **Field and clock completeness.** Every assessment anchor has at least one declared carrier, a boundary, finite periods, unit, source-field identity, comparison clock, and finite fallback. Every referenced field exists; every derived input and formula is closed; no field can be used outside its declared period or scope. A domain without valid fields is accepted only with an explicit NOT_MEASURABLE_BY_DESIGN anchor.

3. **Boundary and segment safety.** Reject a parent field for a consolidated anchor, a segment field for an issuer-wide anchor without its full bridge, mixed scopes in a formula, unregistered segment aliases, or an unspecified restatement/reorganization rule. Reject a cash field that changes the ordinary-shareholder claim boundary without an explicit bridge.

4. **Claim-specific adequacy.** Reject a normal-earnings anchor that lacks a reference/persistence/exceptional-item rule; an owner-cash anchor that conflates operating cash, maintenance capital, total capital absorption, or growth-return evidence; a permanent-loss anchor that scores mere survival or price; and a value-route anchor without required component/realization conditions. Reject an issuer carrier labeled as an industry-regime settlement without a predeclared eligible industry source and scope.

5. **Finite assessor rule.** Reject a free-text threshold, a predicate that references an undeclared field, a missing ambiguous outcome, or a status outside the closed state map. The only allowed result of UNKNOWN or MEASUREMENT_MISMATCH is its predeclared inconclusive treatment.

6. **Arm binding before custody.** Once arms exist but before outcome access, validate the four anonymous manifests per case against the same case contract. The validator rejects altered assessment IDs, post-freeze claim text, a component/route outside the permitted anchor, or an arm-specific measurement rule. It preserves all four attempts and declares the pair invalid rather than permitting a retry or replacement.

7. **Custodian and assessor separation.** The acquisition custodian receives only a valid contract and permitted source request; it cannot read arm output, anonymous mapping, reviewer preference, or price/return. It emits immutable field receipts only. The anonymous outcome assessor receives only contract, receipts, and anonymous frozen claim manifests; it must emit one predeclared status per bound claim with receipt IDs and predicate IDs. It cannot add a field, substitute a boundary, revise a predicate, narrate a new industry conclusion, or aggregate arms. Arm mapping is revealed only after this record freezes.

8. **Synthetic acceptance cases.** Add value-free fixtures that prove rejection of a dangling reference, wrong case/cutoff, a missing period, a free-text threshold, a parent/segment substitution, a mixed-scope derived formula, unregistered restatement, maintenance-capex invention, survival-as-safety, price-as-route-validation, UNKNOWN treated as a sign, unbound arm claim, and assessor-added metric. A positive fixture must contain no actual outcome values and must pass for all eight case slots.

## Acceptance criteria

This RETURN becomes a PASS for outcome-measurement readiness only when all of the following are true without reading a post-cutoff outcome:

1. Eight existing, value-free, closed contracts resolve from the frozen preregistration and pass the reusable validator.
2. Each contract covers every claim domain with either a valid, scoped assessment anchor or an explicit predeclared non-measurable treatment; it does not use issuer annual-report prose as an unbounded industry verdict.
3. Each anchor has fixed fields, periods, units, issuer/segment/ordinary-owner boundary, comparison/predicate logic, and a legal UNKNOWN/mismatch path.
4. The cohort validator rejects a nonempty-but-dangling reference and every material scope, formula, predicate, or claim-binding drift described above.
5. The custody interfaces enforce value-free field acquisition, anonymous assessor settlement, no post-hoc rule addition, and mapping disclosure only after anonymous assessment freeze.
6. A fresh independent outcome-blind review confirms the contracts and validator satisfy these criteria. Only then may the existing reviewer-freeze gate govern subsequent outcome access; neither this design PASS nor a validator pass authorizes an arm, source opening, or investment conclusion.

## Protocol conclusion

The appropriate repair is a small reusable contract layer, not a new score, new report writer, market outcome, or post-hoc reviewer discretion. It lets a later official observation test exactly the operating carrier or route condition the protocol named, while leaving genuinely unobservable claims as local uncertainty. Until that layer exists, the current measurement pointers are insufficient for a defensible Phase-5 autonomy result.
