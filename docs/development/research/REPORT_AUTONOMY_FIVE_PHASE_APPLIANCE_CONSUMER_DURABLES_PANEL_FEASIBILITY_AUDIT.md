# Appliance / consumer-durables strict-panel feasibility audit

> Date: 2026-09-01
> Scope: local-only and outcome-blind. No web use, market data, existing target reports, outcome material, or sample selection.
> Result: the local material is sufficient to describe a **training-side source inventory**, but insufficient to form a strictly separate multi-company Pack-building panel and an eight-issuer test-acquisition panel.

## Decision

No Pack is proposed, created, or called TRAINING_READY here. No issuer is selected for either side.

The permitted local inventory contains eight appliance training-material issuer identities and one additional consumer-durables discovery issuer. A strict two-sided design needs a multi-company training side plus eight different test issuers. The maximum visible issuer universe is therefore nine, which cannot satisfy even the minimum abstract separation of two training issuers plus eight test issuers. Under the conservative treatment in which all eight appliance identities remain on the training side, only one provisional non-training issuer is visible and the test-acquisition gap is seven.

This is an availability and source-coverage audit only. It states no outcome, price, return, valuation, company-quality, or utility conclusion.

## Separation rule

The two panels must have disjoint issuer identities:

- **Pack-building side:** only cutoff-before official records used to assemble a multi-company, multi-period IndustryLearningBlock input; and
- **test-acquisition side:** at least eight issuer identities that are absent from that input and from existing teacher, Pack, holdout, target, and campaign identities.

A source record is not an assignment. The tables below identify the currently visible inventory and its gaps; they do not freeze a panel, select a target, or give a candidate any experimental status.

## Training-material inventory

These are the locally visible appliance source/material identities. They are the only available starting material for an appliance Pack-building effort, so they must be treated as unavailable to the strictly separate test side if the corresponding record is incorporated into that effort.

| Issuer | Visible cutoff-only material | Separation / readiness limitation |
| --- | --- | --- |
| CN:000651 Gree | National appliance register contains official statutory FY2016 and 2018 H1 static-PDF metadata, eligible for its C1/C2 cutoffs | Existing Course 1 worked-case and later holdout-selection identity; never a fresh test issuer. |
| CN:000333 Midea | National appliance register contains official statutory FY2016 and FY2017 annual-report metadata at C1/C2 | The consumer-durables discovery package records only a stopped action screen; a Pack role/boundary and multi-period completeness audit is still required, and no fresh test authorization exists. |
| CN:600690 Haier | National appliance register contains official statutory FY2016 and FY2017 annual-report metadata at C1/C2 | Existing Course 1 worked-case identity; never a fresh test issuer. |
| CN:000921 Hisense Kelon | National appliance register contains official statutory FY2016 and FY2017 annual-report metadata at C1/C2 | Source-register coverage only; it requires a role, boundary, and multi-period package audit before it could become a Pack input. |
| CN:600839 Sichuan Changhong | National appliance register and an appliance pre-outcome block identify FY2016/FY2017 official cutoff material | Already an appliance-training material identity; cannot be used on both sides. |
| CN:002032 Zhejiang Supor | Appliance continuous-training metadata identifies a cutoff-before FY2017 CNINFO annual-report PDF at the C2 cutoff | Already a continuous-training material identity; the present record is a single-company frozen input, not a multi-company Pack. |
| CN:002242 Joyoung | Appliance four-stage metadata identifies the FY2017 CNINFO annual report published before the C2 cutoff | Existing appliance training material and Course 1 blind-replay/campaign identity; never a fresh test issuer. |
| CN:002677 Zhejiang Meida | Pre-outcome curator metadata identifies a FY2017 official annual-report PDF published before the C2 cutoff | Already a Round 10 appliance-training material identity; the record is single-company and cannot serve both sides. |

The national appliance source register itself is explicitly E0_E1_RESEARCH_ONLY and permits only an IndustryLearningBlock/research agenda. Its two cutoffs also do not by themselves constitute a common, multi-period Pack panel. The single-company appliance materials above have similar limitations. They are usable source seeds, not a pre-existing Pack.

## Potential non-training issuer inventory

| Issuer | Visible local coverage | Why it is only provisional acquisition inventory |
| --- | --- | --- |
| CN:002024 Suning | Consumer-durables static source package records a cutoff-before official CNINFO Q3 2018 disclosure for a 2018-12-31 discovery cutoff, with issuer-identity, implementation, materiality, and responsibility-boundary roles | The package is CANDIDATE_DISCOVERY_ONLY, grants no research rights, and contains only one issuer. It does not certify an unseen identity, fill a test source package, or authorize a test selection. No hit was found in the permitted training-campaign selection-roster scan, but a full cross-artifact identity check is still required before it could count. |

No other non-training appliance/consumer-durables issuer with cutoff-only official source metadata is visible in the permitted inventory. The local source set therefore cannot supply an eight-issuer test-acquisition panel.

## Company-free expert memory

TURTLE_EXPERT_CORRECTION_DISTILLATION_V1.md describes a company-free TRAINING_MEMORY compiler. Its status is IMPLEMENTED / FIRST_TEACHER_PACKAGE_TRAINING_READY / METHOD_NOT_VALIDATED. The compiler removes company evidence and its output cannot enter a target Episode's evidence trace or existing-object references.

This makes the memory potentially reusable as a method-only input after a separate source panel exists. It cannot:

- contribute an issuer identity;
- supply an official cutoff document;
- close a source, boundary, or multi-period coverage gap;
- convert a source registry into an Experience Pack; or
- prove a candidate is unseen.

It therefore changes neither side's issuer count.

## Minimum source-acquisition worklist

1. **Build a single identity-and-role ledger before any allocation.** It must list the eight appliance material issuers, CN:002024, all existing teacher/Pack/holdout/target/campaign identities, the intended cutoff, and a mutually exclusive side field. This is a feasibility control, not sample selection.
2. **Normalize the training-source panel.** For whichever appliance identities are eventually allocated to Pack building, acquire/validate a common cutoff-before, multi-period official panel: issuer identity, control and responsibility boundary, report dates, product/segment carrier, and industry/peer reference records. The current registry mixes C1/C2 snapshots and the single-company material has different evidence shapes.
3. **Retain the current appliance identities as test exclusions once used.** Their existing material must not reappear in any test-acquisition panel, regardless of whether a prior campaign also used the issuer.
4. **Perform a full source-completeness and identity-conflict check for CN:002024.** It is a possible discovery seed only; do not count it as one of eight until this check passes.
5. **Acquire at least seven additional distinct test-issuer source packages conditionally on CN:002024 passing step 4; otherwise acquire eight.** Each package needs cutoff-before official issuer identification, publication date/precision, responsibility boundary, multi-period operating evidence, and the disclosed action/context necessary for a later screening process. None may overlap the Pack-building ledger or campaign exclusion ledger.
6. **Only after the two source panels exist, compile the IndustryLearningBlock and run the existing Pack-readiness derivation.** A source register, company-free memory, or a set of isolated pre-outcome records must not be hand-promoted to TRAINING_READY.

## Evidence perimeter

- docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json
- docs/development/research/TURTLE_COMPARATIVE_NATIONAL_CONSUMER_DURABLES_2018_STATIC_SOURCE_PACKAGE_V1.json
- Appliance IndustryLearningBlock and cutoff-before source metadata for CN:002032, CN:002242, and CN:002677
- Permitted training-campaign selection rosters used only for identity-conflict checks
- docs/development/research/TURTLE_EXPERT_CORRECTION_DISTILLATION_V1.md

Outcome/settlement artifacts, market prices/returns, existing target reports, and web sources are outside this audit and are not cited.
