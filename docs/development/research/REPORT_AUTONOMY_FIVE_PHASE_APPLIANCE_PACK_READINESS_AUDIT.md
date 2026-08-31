# Appliance / consumer-durables Industry Experience Pack readiness audit

Date: 2026-09-01  
Scope: local-only, outcome-blind training-side audit. This is neither a Pack
nor a panel selection. It does not use prices, returns, outcome/settlement
records, target reports, or external sources.

## Decision

The local appliance materials are usable **source seeds**, but they cannot yet
compile a valid `TRAINING_READY` Industry Experience Pack. The smallest
honest route is to normalize a cutoff-safe multi-company IndustryLearningBlock
and then add three missing bound objects:

1. an independently sourced issuer-identity catalog;
2. a materialized, locator-backed official industry-observation ledger; and
3. a four-or-more-company shared-shock projection with verified cutoff states.

The resulting Pack may reach `TRAINING_READY` with no transfer review.
It must not be described as having transfer utility. A later test panel is a
separate pre-registration and exclusion-control task: the current Pack
validator does not test Pack/test issuer disjointness.

## Existing local inventory and admissibility gap map

| Local object | What it safely supplies | Why it is not a Pack source object yet | Required normalization or acquisition |
| --- | --- | --- | --- |
| `CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json` | Official-static-PDF metadata for five appliance issuer identities over two historical cutoff snapshots. Its own status is research-only. | Its schema is `turtle-cn-appliance-industry-learning-block-sources.v1`, not `industry-learning-block.v1` or `.v2`; it is a registry, not a multi-company block. | Use it only as the source register for a new standard ILB and for cover-page identity recuration. Preserve cutoff/date precision and page locators. |
| `CN_APPLIANCE_INDUSTRY_J234_V1.json` | Existing multi-company question, boundary, rival, and unresolved-question scaffolding. | Its schema is `turtle-cn-appliance-industry-j234.v1`; `industry_experience_pack.py` will reject it as `INDUSTRY_LEARNING_BLOCK`. | Project only cutoff-safe material into a newly validated standard ILB. Keep unresolved cash, capital-return, and permanent-loss fields unresolved rather than inferring them. |
| `CN_APPLIANCE_TEACHING_PACK_V1.json` | Company-free teaching drills and prohibited-inference rules. | Historical teaching memory is not an ILB, official observation, shared-shock case, or transfer result; it declares itself not evaluation-eligible. | Retain only as `TRAINING_MEMORY`/method material after the Pack is valid. It closes none of the Pack evidence gaps. |
| `CHINA_HOME_APPLIANCE_OFFICIAL_CONTEXT_PACKAGE_DESIGN.md` | A documented definition of allowable external context and forbidden inference. | It is a design document. The referenced appliance catalog, raw package, and observation ledger JSON objects are absent from this worktree; some described observation windows also do not fit a historical Pack cutoff. | Register and materialize a new cutoff-matched official catalog, package, and observation ledger under the existing `industry_context_acquisition.py` contract. |
| Appliance single-company/legacy campaign records | Additional cutoff-before source leads and known exclusion identities. | A single-company record cannot establish the required shared-shock diversity; historical/post-outcome campaign families are not to be repurposed as Pack evidence. | Treat identities already appearing in Pack construction or prior training material as unavailable to the later test panel. Do not read their outcomes to make this determination. |
| Appliance Pack/identity/shared-shock objects | None found in the current local training-side inventory. | There is no appliance `industry-experience-pack.v1`, `issuer-identity-catalog.v1`, `industry-shared-shock-company-projection.v1`, or reviewable official-observation ledger. | Create the three missing JSON object families below; validate before any Pack manifest is written. |

The only checked-in standard appliance `industry-learning-block` file is in a
legacy historical campaign family. This audit does not promote or rely on it:
the proposed Pack needs its own cutoff-safe source chain and must not inherit
historical result material.

## Exact Pack-validator coverage required

The table states the smallest substantive coverage that produces no
`training_readiness_gaps`, rather than merely exploiting the manifest shape.

| Validator requirement | Minimum object/role coverage | Current appliance state |
| --- | --- | --- |
| `INDUSTRY_LEARNING_BLOCK` | One `industry-learning-block.v1` or `.v2` with the Pack `industry_id`; every block cutoff is no later than the Pack cutoff. For useful compilation, include multi-company members, two epochs, mechanism arenas, evidence refs, rivals, and unresolved questions. | Missing standard object. |
| `INDUSTRY_UNDERWRITING_CONTEXT` | One `industry-underwriting-context.v1` that validates as `REVIEWABLE` and has `context_status: READY`; `BOUNDED` creates a readiness gap. It should be compiled from the normalized ILB and official observation ledger, not hand-written from teaching prose. | Missing Pack-eligible context. |
| `OFFICIAL_INDUSTRY_OBSERVATION` | One `official-industry-context-observation-ledger.v1`, a resolvable `official-industry-context-source-package.v1`, and locally materialized original HTML/PDF/data files. Every observation needs a driver type, metric, period, value, statement, economic interpretation, profit-pool effect, permitted/prohibited inference, and a source locator. | Design exists; validated catalog/package/ledger and raw files do not. |
| `ISSUER_IDENTITY_CATALOG` (use Pack v3) | A separately materialized `issuer-identity-catalog.v1` covering every projection company. Each entry binds code, legal issuer name, exact cover quote, CNINFO source ID, publication date, page locator, and non-duplicate short aliases. | Missing. |
| `WORKED_CASE` / shared-shock projection | A `industry-shared-shock-company-projection.v1` with at least four distinct companies. Each must have a non-empty verified cutoff state; each state has a dated pre-cutoff source ID and page/field locator. In v3, every embedded issuer identity must exactly equal the independent catalog entry. | Missing. |
| `role_coverage.company_paths` | At least four distinct Pack-side companies. Across their roles, cover `CENTRAL`, `HETEROGENEOUS`, `FAILURE_OR_NEAR_MISS`, and `SHARED_SHOCK_DIVERGENCE`. Every path references a bound Pack source. | The register has enough identities to investigate, but no Pack-side role assignment or validated source binding. |
| `structural_epochs` | At least two distinct epoch IDs with cutoff timestamps and bound refs. | The registry has two snapshots; no standard epoch objects. |
| `shared_shock_comparisons` | At least one comparison of four-or-more covered Pack companies. Its refs include the official observation ledger and the multi-company worked case; each compared company must be in that worked case. For v3 prose, identity mentions use `[[CN:code|catalog alias]]` and the discriminator token set exactly matches the four-or-more company IDs. | Missing. |
| Current synthesis, settlement and next sample | Nonempty central path, strongest rival, transmission, scope/break conditions and bound source refs; nonempty industry and company-transmission settlement lanes; a nonempty, non-binding next-sampling decision. | No Pack manifest, therefore missing. |
| Transfer state | `transfer_reviews: []` is valid for `TRAINING_READY`. `TRANSFER_CANDIDATE` and `RELEASED` require independent material-utility reviews, but are outside this acquisition stage. | Correctly absent. |

## Acquisition and normalization checklist

1. Freeze one historical Pack cutoff and one shared observation window before
   reading any outcome material. Record the cutoff in an immutable
   Pack-building identity ledger. The ledger is not a test roster.
2. Build the Pack-side exclusion ledger first. It contains each identity used
   by existing appliance training material and each identity proposed for the
   Pack, with source role and cutoff. It has no outcome, price, or quality
   fields. This is the sole input to later test-panel disjointness checking.
3. Recurate official PDF covers for each prospective Pack-side issuer and
   write a single `issuer-identity-catalog.v1`. Match the same seven identity
   fields inside the future shared-shock projection. Do not derive a legal
   name from a self-consistent projection or a short-form alias.
4. Normalize only cutoff-safe register/J2-J4 content into a standard,
   multi-company `industry-learning-block.v2` (or v1 where legacy support is
   required). Preserve source IDs, dates, page locators, responsibility
   boundaries, product/arena scope, company archetypes, two epochs, rival
   explanation, and unresolved questions. Validate it with its native ILB
   validator before placing it in a Pack manifest.
5. Acquire a small official external-industry set for the *same* cutoff and
   industry ID. Its sole role is demand/supply/competition/regulation context:
   it must not contain a target-company conclusion. First write an
   `official-industry-context-catalog.v1`; materialize each original response;
   then write a matching source package and observation ledger. Reject a
   same-day date-only release and any current-revision substitution.
6. Compile an `industry-underwriting-context.v1` from the normalized ILB and
   reviewed official ledger. Resolve the inputs sufficiently for
   `context_status: READY`; a merely `BOUNDED` context is reader-usable but
   cannot make this Pack training-ready.
7. Construct one cutoff-safe multi-company shared-shock projection. Its
   observation must describe a common shock and its company states must
   preserve divergence and responsibility boundaries. It is not a ranking,
   outcome settlement, normal-earnings estimate, valuation, or test selection.
8. Create a v3 Pack manifest whose included source objects are exactly the
   normalized ILB, READY context, official ledger, identity catalog, and
   shared-shock projection. Bind every `source_refs` field to a manifest ref;
   leave transfer reviews empty; keep the non-authoritative Pack boundary
   unchanged.
9. Run `scripts/industry_experience_pack.py` and only call the result
   `TRAINING_READY` if it is `REVIEWABLE`, its derived state is
   `TRAINING_READY`, and `training_readiness_gaps` is empty. Do not
   hand-promote a source register or teaching pack.
10. Only after step 9, pre-register a later test-acquisition panel from the
    exclusion ledger. Require every test issuer to be absent from the Pack
    identity catalog, ILB members, shared-shock projection, teaching/holdout
    identities, and earlier campaigns. The Pack validator does not enforce
    this, so the later experiment contract must. This audit deliberately does
    not name or select any test issuer.

## Non-goals and evidence boundary

This audit does not establish appliance facts, company rankings, industry
outcomes, normal earnings, owner cash, permanent-loss likelihood, value,
returns, or investment treatment. It does not turn either the teaching pack
or the industry source register into a fact store. It only maps the object
interfaces that must be completed before a valid industry training memory can
be compiled and before an independently frozen test panel can be considered.

Inspected local interfaces:

- `scripts/industry_experience_pack.py`
- `scripts/industry_context_acquisition.py`
- `scripts/industry_underwriting_context.py`
- `scripts/enterprise_judgment_v2_training.py`
- `scripts/enterprise_judgment_multidimensional_training.py`
- `docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json`
- `docs/development/research/CN_APPLIANCE_INDUSTRY_J234_V1.json`
- `docs/development/research/CN_APPLIANCE_TEACHING_PACK_V1.json`
- `docs/development/research/CHINA_HOME_APPLIANCE_OFFICIAL_CONTEXT_PACKAGE_DESIGN.md`
