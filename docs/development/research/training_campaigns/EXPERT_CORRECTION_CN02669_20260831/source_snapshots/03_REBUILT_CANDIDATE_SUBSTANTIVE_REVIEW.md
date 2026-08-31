# 02669 rebuilt candidate independent substantive review

```text
reviewer = /root/q1_02669_rebuilt_candidate_substantive_reviewer
review_date = 2026-08-16
review_type = INDEPENDENT_SUBSTANTIVE_REVIEW
verdict = ACCEPT_WITH_DATA_LIMITED
candidate_status_after_review = PENDING_REVIEW
```

## 1. Scope and authority

This review covers the current operating-driver candidate only:

- `research/02669/q1_1_f_revision_20260811/total_return_v4_inputs.candidate.json`
- `research/02669/q1_1_f_revision_20260811/total_return_v4_results.candidate.json`
- `scripts/calculate_q1_02669_total_return_v4.py`
- `research/02669/q1_1_f_revision_20260811/reader.md`
- `research/02669/q1_1_f_revision_20260811/technical_appendix.md`
- the two generated `revision-20260811.candidate.html` files

The author, model, schema, renderer and prior reviewers' PASS labels were not treated as acceptance evidence. I independently reconstructed the main numeric chain, ran new perturbations against in-memory copies, checked the primary-source support for the central operating thesis, and did not modify any reviewed candidate input or output.

## 2. Verdict

**ACCEPT_WITH_DATA_LIMITED.** The operating drivers genuinely generate normal common-owner profit; owner cash is conserved; retained capital changes future business value; and the chain through current value, fifth-year value, terminal price, five-year XIRR and the 10% reverse price is arithmetically and economically live. The reader case also supports the parent-pipeline, business-engine, industry and management claims without treating land acquisition, managed area or a peer margin as company profit.

The two remaining limitations are material uncertainties rather than concealed model defects. Public disclosure does not close project/cohort economics by engine or the legal-entity ownership of consolidated cash. The candidate exposes both limits, uses ranges, and reaches a current-price conclusion that survives the disclosed operating-driver and cash-access ranges. This review does not authorize any later workflow state.

## 3. Independent reconstruction

I rebuilt the base case from revenue, gross margin, common expense, impairment, maintenance, tax, NCI and recurring collection absorption without calling the candidate's calculation functions. I then reconstructed yearly owner-cash allocation, machine earnings, operating EPV, recognized cash, terminal pricing, dated HKD cash flows, XIRR and reverse price.

| Output | Independent result | Stored result | Difference |
|---|---:|---:|---:|
| normal common-owner earnings | RMB896.979630m | RMB896.979630m | 0 |
| `V0` | HKD3.300450800/share | HKD3.300450800/share | 0 |
| `V5` | HKD3.600988662/share | HKD3.600988662/share | 0 |
| five-year terminal price | HKD3.682572210/share | HKD3.682572210/share | 0 |
| five-year XIRR | 3.922864006% | 3.922864006% | below `4e-13` percentage points |
| `P_XIRR_5` at 10% | HKD2.231347447/share | HKD2.231347447/share | 0 |

The underlying machine owner earnings are RMB809.433011m for mature base property, RMB62.685809m for city/public service and RMB24.860810m for smart engineering/project work. The first-year gross distribution is RMB313.942871m; tax, receipt friction and fixed fees reduce it to RMB278.416977m, or HKD0.094201/share. The fifth-year bridge contains RMB7,420.647005m of operating value and RMB816.022941m of recognized new cash. The allocation rows conserve owner earnings in every year.

The terminal identity is correctly implemented as:

```text
m0 = P0 / V0
P5 = V5 * [m0 + alpha5 * (1 - m0)]
```

with `alpha5=1/2`. Thus `alpha=0` still transmits `V5/V0`; ordinary market confirmation changes only the terminal transaction price; and dividends, retained principal, recognized new cash and market confirmation are not added twice.

## 4. New perturbations

These are new isolated shocks, not rows copied from the candidate's stored sensitivity outputs. Each used a deep in-memory copy of the input and called the full scenario projection. No product path was overwritten.

| Perturbation | Owner earnings RMBm | `V0` HKD | `V5` HKD | terminal HKD | XIRR 5y | `P_XIRR_5` HKD |
|---|---:|---:|---:|---:|---:|---:|
| Base | 896.980 | 3.3005 | 3.6010 | 3.6826 | 3.9229% | 2.2313 |
| Price/volume: mature revenue +5% | 944.441 | 3.4323 | 3.7525 | 3.7622 | 4.4799% | 2.3337 |
| Direct cost: mature gross margin -100 bp | 827.238 | 3.1038 | 3.3736 | 3.5618 | 3.0665% | 2.0781 |
| Expense: selling/admin expense +10% | 870.692 | 3.2292 | 3.5203 | 3.6406 | 3.6226% | 2.1767 |
| Capital intensity: identified reinvestment +10% | 896.980 | 3.3005 | 3.5864 | 3.6677 | 3.8480% | 2.2206 |

The capital-intensity shock correctly leaves current normal profit and `V0` unchanged but lowers `V5`, terminal value, XIRR and the reverse price because more retained cash is committed at the observed low incremental return. The other three shocks propagate immediately through normal profit and every downstream decision output.

## 5. Substantive assessment

### Operating engines

The model no longer imports normal profit as a fixed scalar. It starts with RMB14,959.871m of disclosed revenue and calculates mature property, resident value-added, city/public, smart/project and parking components. Resident value-added is separately generated before being grouped with the mature-base valuation machine; non-resident engineering/project work has a separate 16% required return and decay path. Common expense, maintenance adjustment and NCI are allocated once, while the already-after-tax city margin and PBT-level parking result avoid a second common-cost charge.

The engine mapping is economically usable but data-limited. In particular, managed GFA is diagnostic only because fee-bearing area, same-project price, collection and direct labor/subcontracting are not disclosed. City margin is bounded from mechanism-matched peers and procurement contracts, not presented as a company fact. Smart/project recovery is conditional rather than embedded in the main case.

### Parent developer

The report distinguishes China Overseas Holdings, ultimate controller CSCEC and fellow developer China Overseas Land. The cited 2025 developer filing supports 35 acquired parcels, 4.99m sqm gross/4.45m sqm attributable GFA and RMB92.42bn attributable land cost, concentrated in core cities. The developer's official 2026 July update independently confirms seven-month sales of RMB149.47bn, up 13.2%, sales area down 12.6%, and five July parcels with 663,163 sqm attributable GFA and RMB13.942bn attributable land cost. The report appropriately discounts this evidence for development lag, appointment uncertainty and scale: 2025 acquired GFA was only about 1% of the property manager's year-end managed area.

### Cash, NCI and owner return

The model keeps RMB6,270.725m consolidated cash and bank balances separate from the RMB27.854m listed-company cash memo, restricted cash, the operating floor and unremitted-profit memo. It removes normalized NCI earnings from operating profit and does not add listed-company or subsidiary balances to consolidated cash. Public evidence also shows RMB75.868m of NCI equity and RMB10.730m of 2025 NCI profit, but not an entity-level allocation of cash. The 50% excess-cash realization factor is therefore a valuation judgment, not proof of legal availability.

### Industry and management

The industry section is a five-year transmission analysis: falling new-home completions affect future related-party supply; existing communities preserve service demand; price regulation and wage/subcontract costs constrain mature margins; local fiscal pressure affects public-project price and collection; engineering contracts add procurement, construction, acceptance and warranty cash needs. Management analysis names responsibility lines, separates operating ability from capital allocation, dates the current chair/CEO record, examines project exits, compensation, ownership and the aborted related acquisition, and ties improvement to margins, collections, distributions and return on retained capital. This supports the central thesis rather than merely describing the sector or biographies.

## 6. Acceptance-limiting findings

### DL-1: engine-level cohort economics remain unobserved

- **Root cause:** `DATA_COVERAGE`, `ACQUISITION_MODULE`
- **Economic impact:** The main normal earnings point is RMB896.980m, but the disclosed 27-cell driver range is RMB637.327m-RMB1,182.732m. Across that range, five-year XIRR is 1.15%-6.81% and `P_XIRR_5` is HKD1.73-HKD2.79. The current no-entry conclusion survives at HKD3.45, but the size and source of permanent loss cannot be made project-specific.
- **Missing facts:** Fee-bearing area, same-project price and collection, direct labor and subcontracting by business, project startup capital, city-project cohort profit/cash, resident value-added cohort persistence, and a standalone smart/project revenue-to-cash bridge.
- **Prohibited assumptions:** Do not multiply managed area by an invented fee; treat a peer margin as a company fact; assume reported 34.0% resident or 13.1% project margin persists; or infer project profit from contract value, awards or revenue growth.
- **Executable remediation:** Extend the reusable deep-financial acquisition request/schema and validator first to capture engine, cohort, contract start, revenue, direct cost, working capital, capex and cumulative collection. Populate it from later issuer disclosures and project records; only then revise judgments and rerun the model.
- **Acceptance criteria:** Either obtain a reconciled company/cohort bridge covering the material revenue and capital pools, or retain explicit `UNKNOWN` fields and demonstrate that bounded residuals cannot change the investment conclusion, permanent-loss route or 10% price range.

### DL-2: consolidated cash cannot be assigned exactly to listed common shareholders

- **Root cause:** `DATA_COVERAGE`, `ACQUISITION_MODULE`
- **Economic impact:** The main case recognizes RMB2,552.220m of existing excess cash, 26.2% of `V0` common value. Holding payout at 35%, moving cash realization from 30% to 75% changes five-year XIRR from 2.44% to 5.60% and `P_XIRR_5` from HKD1.99 to HKD2.53. It does not reverse the current-price conclusion, but it materially affects valuation and downside.
- **Missing facts:** Cash by material subsidiary, NCI rights in those entities, statutory/distributable reserves, subsidiary operating floors, upstream approvals/timing, withholding tax and cash held in group finance arrangements.
- **Prohibited assumptions:** Do not equate consolidated cash with immediately distributable listed-company cash; call the 50% factor a legal entitlement; infer cash ownership solely from the small NCI profit line; or add company-level receivables/cash to consolidated cash.
- **Executable remediation:** Add a legal-entity cash/upstreaming table to the reusable acquisition schema and validator, then acquire issuer disclosure for material cash-holding subsidiaries, NCI ownership, reserves, taxes and actual upstream distributions. Keep 30%/50%/75% as explicit economic-realization scenarios until that module produces evidence.
- **Acceptance criteria:** Reconcile the material cash-holding entities and NCI claims to consolidated cash and show the ordinary-shareholder upstream path, or preserve an explicit conservative range whose endpoints are carried through `V0`, `V5`, XIRR and `P_XIRR`.

Neither finding requires prose to hide unavailable facts or a model assumption to impersonate disclosure. Both justify `ACCEPT_WITH_DATA_LIMITED`; neither supports unrestricted acceptance.

## 7. Verification record

- Independent formula reconstruction of owner earnings, `V0`, yearly retained-capital propagation, `V5`, terminal price, dated HKD cash flows, XIRR and reverse price.
- Four new in-memory perturbations covering price/volume, direct cost, expense and capital intensity.
- Pinned-runtime deterministic rebuild with schema validation; rebuilt JSON and both CSV outputs matched the reviewed candidate structurally and cell-for-cell.
- `/Users/xiami/workspace/analy/runtime/turtle-q1-02669-revision-py314/bin/python -m unittest -v tests.test_calculate_q1_02669_total_return_v4`: 35 tests passed.
- Official China Overseas Land July 2026 developer update inspected directly for sales and land-acquisition facts.

No model, Markdown, HTML, input, result, CSV, test or prior review artifact was changed by this review.
