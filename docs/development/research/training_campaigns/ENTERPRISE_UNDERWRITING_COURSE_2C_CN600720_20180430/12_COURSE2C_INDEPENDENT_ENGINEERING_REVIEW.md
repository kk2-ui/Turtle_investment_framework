# Course 2C independent engineering and experiment-integrity review

Date: 2026-08-31 (Asia/Shanghai)
Reviewer: fresh Codex independent reviewer
`FINAL_STATUS: PASS`
`MATERIAL_BLOCKERS: 0`
`EXTERNAL_API: NO`

## Review judgment

The Course 2C experiment itself has a coherent price-before/outcome-after chain: the corrected CN:600425 Pack identity is bound to an independent issuer catalog; the two arms received the same target-company evidence and execution budget; both v2 Episodes are executable; `TRAINING_MEMORY` does not enter the target-company evidence trace; the anonymous first-stage judgment predates outcome and mapping access; and the final utility verdict is supported by differences frozen in that first stage plus later company facts. The closeout also limits the positive result to a company-transmission method at `TRANSFER_CANDIDATE`, not a demonstrated industry-forecasting capability.

Engineering acceptance nevertheless returns. Two supported mutations of the reusable multi-period acquisition contract are accepted as valid and then produce economically contradictory or misidentified consumer inputs. They can materially alter normal earnings, owner cash, and downstream value routes. These defects do not retroactively change the already frozen Course 2C arm comparison, which did not consume either mutated synthetic record. They do invalidate the branch's claim that cross-cell fact identity and unit conversion are safely closed for reuse.

## Material return 1 — a raw `field_id` has no global cross-cell semantic binding

Classification: `ACQUISITION_MODULE`

The contract validator requires raw IDs to be unique only within each atomic cell. It does not bind a repeated raw `field_id` globally to one source, clock, locator, unit, economic role, and component/responsibility identity. Projection then constructs an `observation_id` from contract, source, component, and `field_id`, while duplicate grouping also includes `raw_field_role`. A single ID rebound to a different role therefore escapes conflict detection but produces duplicate evidence identities.

Targeted negative probe: in the existing synthetic FY2020 fixture, the D3 revenue raw input was rebound to the already frozen `OCF_V4` field ID while retaining D3's revenue role and locator, and the D3 formula/conversion references were updated to that ID. Both contract and acquisition validation returned valid. Projection admitted the same observation identity twice, once as `OPERATING_REVENUE=30` and once as `OPERATING_CASH_FLOW=30`; D3 changed from the correct `25` to `-45`. The cross-cell deduplicator did not flag either cell because their roles differ.

- **Economic impact:** one reported cash-flow fact can be admitted as both revenue and OCF. That can reverse D3/normal-earnings direction, contaminate a V4 candidate, and create two consumer facts with one supposedly stable evidence identity. The error is not local `UNKNOWN/MISMATCH`; it is accepted as observed data.
- **Missing facts/invariants:** there is no globally frozen mapping from each raw `field_id` to its source ID, measurement clock, locator, unit, raw role, component ID, component role, responsibility unit, and perimeter. The production field-record path also checks that `custodian_locator` has the right shape but does not require it to equal the frozen locator.
- **Prohibited assumptions:** do not assume naming conventions make `field_id` globally unique; do not assume a later consumer or the role-sensitive duplicate grouper will discover an evidence-ID collision; do not treat a copied frozen locator plus a different custodian locator as the same located fact.
- **Executable remediation:** validate a contract-wide raw-fact identity registry before outcome access. Every occurrence of a repeated `field_id` must have the same frozen source, clock, locator, unit, role, and component/responsibility binding. If the design needs one physical disclosure to support distinct use roles, represent physical fact identity separately from use identity and guarantee unique, stable consumer observation IDs. Make the custodian's actual locator equal the frozen locator, rather than validating shape only. Keep exact legitimate reuse deduplicated and keep genuine conflicts local.
- **Acceptance criteria:** a regression that reuses one `field_id` with a changed role, locator, source, clock, unit, or component binding must be invalid before acquisition; no valid projection may contain duplicate `observation_id` values; the existing exact OCF reuse must still collapse to one observation; a contradictory value for an otherwise identical fact must still produce only local `MEASUREMENT_MISMATCH`.

## Material return 2 — signed unit scale can reverse an operator that already owns arithmetic sign

Classification: `ACQUISITION_MODULE`

The conversion schema accepts any finite non-zero scale. Formula construction applies the signed scale, whereas consumer projection deliberately applies its absolute magnitude. This is valid only if the contract distinguishes a unit multiplier from an arithmetic coefficient and constrains the coefficient for each operator. It currently does neither.

Targeted negative probe: in the synthetic `OWNER_CASH` cell, changing only the maintenance-capex conversion scale from `1` to `-1` left the contract valid. With OCF `100`, maintenance capex `20`, and adjustment `-10`, the intrinsically signed operator computed `100 - (-20) - 10 = 110`, while consumer projection used the absolute scale and emitted maintenance capex `20`. The correct frozen construction is `70`. The same contract therefore produced mutually inconsistent observed economics.

- **Economic impact:** owner cash can be overstated from `70` to `110` without an `UNKNOWN/MISMATCH`. That can materially raise cash earning power and value, or suppress capital-burden deductions. Similar double-sign risk exists wherever the operator already defines subtraction or ratio direction.
- **Missing facts/invariants:** the contract does not separate positive unit conversion magnitude from arithmetic coefficient/sign, and it lacks operator-specific admissible sign/cardinality semantics at validation time.
- **Prohibited assumptions:** do not assume a conversion scale is only a positive unit magnitude when negative values are accepted; do not assume the operator's intrinsic subtraction will cancel an author-supplied sign; do not rely on the consumer's `abs(scale)` behavior to repair the constructed cell.
- **Executable remediation:** make unit scale a strictly positive conversion magnitude and encode arithmetic coefficients separately, or validate an explicit operator-specific coefficient/sign matrix. `OWNER_CASH` must receive positive converted OCF and maintenance-capex amounts and apply its own subtraction; signed `SUM` uses such as D3 and net commitments must express their arithmetic signs explicitly rather than overloading unit conversion. Validate operator input count, unit compatibility, and sign semantics before the contract is frozen.
- **Acceptance criteria:** the negative-maintenance-scale probe must fail contract validation before outcome access; every valid contract must give consistent economic amounts to the constructed cell and its consumer projection; existing RMB/RMB_10K conversions, signed D3/net-commitment formulas, and local mismatch behavior must continue to pass.

## Controls that passed independent review

### CN:600425 identity and Pack V3

The corrected catalog binds `CN:600425 / 600425 / 新疆青松建材化工(集团)股份有限公司` to `CNINFO:600425:ANN:20180421:1204677754`, and keeps CN:000877/新疆天山水泥 separate. Projection V2 and the active Pack V3 token use the corrected identity. For Pack V3, validation requires the separate issuer catalog and compares the projection's company ID, code, legal name, exact quote, source ID, publication date, and page to it; active company-name tokens must also be catalog-bound. The direct Pack validator returned `REVIEWABLE` with derived and declared state `TRAINING_READY`, and mutation tests reject a self-consistent projection-only rename or an unbound active-text name. Within the project's trusted-local workflow, this materially prevents the prior wrong-name/wrong-announcement binding from recurring.

### Multi-period behavior not covered by the two returns

The new multi-source path strictly freezes the source inventory and availability while preserving the legacy single-source unknown-availability behavior. Positive conversion cases reach working-capital and V4 consumers in destination units. Reusing an exactly identical fact with the same semantic identity deduplicates; conflicting values for that same identity become local mismatch. Component IDs are stably bound to component role, responsibility unit, and perimeter. Missing or mismatched raw fields remain local and are not converted to zero. Those behaviors passed both focused positive and negative tests.

### Arm fairness and evidence separation

The Baseline and Enhanced contracts share the same target company, cutoff, common evidence sources, task contract, model/reasoning setting, and task budget. The material contract difference is the Enhanced arm's Context/training-memory allowance. Both generated Episodes bind target-company claims only to the common source packages: neither Enhanced `existing_object_refs` nor its `evidence_trace` contains `TRAINING_MEMORY`, Pack, Context, or training-memory paths. Thus the treatment changes reasoning memory, not the target-company evidence base.

### Fresh v2 execution and executable routes

The execution record identifies one fresh Codex subagent per arm and `run --agent-response` for both, with no `--provider`, API key, or external model API. Episode and bundle artifacts were co-produced per arm. Both v2 contracts and both Episodes validate `REVIEWABLE`; both bundles compile. Required component IDs, required/optional route bindings, allowed uses, and exclusions are executable under the repository validator rather than being prose-only requirements.

### Outcome chronology and final reasoning

The anonymous first-stage artifact was frozen after both Episodes and before either outcome artifact and the sealed mapping were opened. It selected anonymous Arm A based on price-before differences in accounting-boundary separation, lifecycle cohort handling, owner-cash construction, and route-specific component use. The isolated outcome artifacts contain no arm evaluation; the closeout records that their Custodians did not read arms, mapping, or the first-stage verdict. The final review then maps Arm A to Enhanced and tests the same frozen differences against target-company outcomes: Jiuquan's continuing economics versus accounting boundary, Zhangye's control/new-capital/negative-OCF path, and the divergent commissioned/unfinished/terminated cohorts. It treats owner cash as partial support rather than manufacturing a precise maintenance-capital result. That evidence supports the company-transmission verdict without using outcome facts to invent a new first-stage advantage.

### Leakage and closeout scope

No Episode contains a post-cutoff target outcome or post-cutoff report reference, and no target-company `TRAINING_MEMORY` evidence trace exists. Post-cutoff reports appear only in outcome-custody feedback after the anonymous first stage. No external provider/API implementation, key, or call trace was found in the task changes or execution artifacts, and this review used no network access. `11_EXECUTION_AND_METHOD_CLOSEOUT.md` explicitly denies a demonstrated general industry-forecasting advantage, limits transfer to company/component transmission, retains `TRANSFER_CANDIDATE`, and requires another holdout before release.

## Verification record

- Coordinator-level targeted suite covering contract/Episode validation, Pack V3, multi-source and legacy acquisition, settlement, working-capital, V4, and financial-driver consumers: `216 passed, 2 skipped in 30.23s`.
- Direct Pack V3 validation: `state=REVIEWABLE`, `declared_state=TRAINING_READY`, `derived_state=TRAINING_READY`, no findings.
- Both arm contracts: `REVIEWABLE`; both arm Episodes: `REVIEWABLE`; both compile-bundle runs completed.
- Negative identity probe: contract valid, acquisition valid, duplicate observation ID admitted, D3 `-45` instead of `25`.
- Negative sign probe: contract valid, `OWNER_CASH=110` while maintenance-capex consumer input remained `20`; expected owner cash `70`.

The passing suite demonstrates broad compatibility but contains no regression for either accepted invalid contract above. Both material returns must be closed in the reusable acquisition module and tests; prose, outcome rewriting, or a narrower investment conclusion is not an acceptable substitute.

## Post-fix re-review

Date: 2026-08-31 (Asia/Shanghai)
Reviewer: fresh Codex independent reviewer
`FINAL_STATUS: PASS`
`MATERIAL_BLOCKERS: 0`
`EXTERNAL_API: NO`

The two returned defects are closed in the reusable multi-source V3 lane.  This re-review is limited to `scripts/enterprise_judgment_real_mechanism_training.py`, `scripts/outcome_measurement_acquisition.py`, and `tests/test_enterprise_outcome_multi_source_acquisition.py`; the historical `RETURN` above is retained as the pre-fix record.

### Returned identity defect — closed

The V3 multi-source validator now keeps a contract-wide raw-field registry.  A repeated `field_id` must retain the same frozen source, measurement clock, locator, unit, raw role, and full component/responsibility/perimeter binding; a changed binding is rejected before acquisition.  The resulting consumer evidence ID is consequently unique for every valid projection.  Exact reuse of the FY2020 OCF fact still collapses to one verified observation, while a contradictory duplicate value remains a local `MEASUREMENT_MISMATCH` and removes only the affected constructed/V4 use.

Both acquisition entry points now require the custodian locator to equal the frozen locator for multi-source contracts: automatic observation writes the frozen locator into both source locator representations, and page-located custodian records are rejected when either representation differs.  This closes the prior shape-only check without changing legacy single-source V3's dual-locator allowance.

### Returned sign defect — closed

Multi-source conversion scales are now finite and strictly positive.  Arithmetic direction is carried only by ordered `input_coefficients`; coefficients are finite `+1`/`-1`, intrinsically signed operators require `+1`, and the frozen role patterns lock the negative positions for D3, net commitments, and operating-NWC sums.  The deterministic constructor therefore computes `OWNER_CASH = 100 - 20 + (-10) = 70`, while its consumer inputs retain the same amounts (`100`, `20`, `-10`).  The old negative-scale mutation is rejected at contract validation rather than allowing the former constructed/consumer split (`110` versus `70`).

### Compatibility and bounded settlement note

Legacy single-source V3 behavior remains covered: the signed legacy conversion path and its dual custodian-locator representation continue to use their historical semantics.  The multi-source path separately enforces the new positive-scale and exact-locator invariants.

The generic legacy control-plane/settlement route is not a successful multi-source V3 settlement path.  An isolated probe registered the valid multi-source contract and reached the public generic settlement entry, but the old executor rejected `OWNER_CASH` as an unsupported operator and the old single-source receipt registry then failed closed with `enterprise_observation_authorized_source_mismatch`; no settlement persisted and no alternate economic value was emitted.  It also has no `input_coefficients` implementation.  This is a non-blocking compatibility boundary for the new consumer-projection lane, not a material economic-result defect: every valid negative coefficient is confined to `SUM`, which that old executor rejects rather than silently evaluating, while non-`SUM` operators are contract-constrained to `+1`.  A future decision to route multi-source V3 contracts through canonical settlement should upgrade that executor and source-set registry together and add an end-to-end settlement test.

### Verification

- Two former negative probes plus all parameterized invalid-scale cases: `6 passed, 24 deselected`.
- Identity, exact reuse/local mismatch, locator, sign, multi-source acquisition, legacy Enterprise V3 acquisition, settlement adapter, and real-mechanism regressions: `93 passed, 2 skipped`.
- Direct legacy compatibility probe: the frozen single-source V3 contract remains valid with a signed conversion scale, and its legacy dual-locator tests remained green.
- Focused live-path probe (temporary isolated canonical registry): a valid multi-source contract registered successfully; consumer projection retained `OWNER_CASH=70`; the legacy generic settlement path failed closed as described above.
- No external model API, API key, or network access was used.
