# CN Cement H1 Static Package Provenance

## Receipt

- Package: `COHORT_CN_CEMENT_LISTED_20180430_h1_static_package.json`
- Schema: `judgment-selection-stage0-static-package.v1`
- Cohort cutoff: `2018-04-30T23:59:59+08:00`
- Curator: `CURATOR:INDEPENDENT:CEMENT-H1-20180430`
- Source basis: only the 25 source IDs already present in the legacy cement feasibility record, five annual reports for each of five issuers.
- Static PDF URL form: `https://static.cninfo.com.cn/finalpage/YYYY-MM-DD/<announcement-id>.PDF`

## Verification

- 25 of 25 declared static PDF URLs returned a PDF and were parsed locally.
- All 25 source identities are retained in the new package; no issuer or source was added.
- 105 declared page references were checked against the corresponding extracted PDF page and contained text.
- The package validator returned `STAGE0_FEASIBILITY_REVIEWABLE` with an empty findings list.
- The targeted discovery regression returned `56 passed`.

The package uses the report year for `period_end`, rather than the announcement publication year. Two legacy page references were corrected after page-level inspection: Jidong FY2016 cement/clinker sales uses PDF p12, and Fujian Cement FY2017 control evidence uses PDF p35.

## Admission Boundary

`600801` and `000401` remain `KNOWN_MATERIAL_SCOPE_OR_CONTROL_BREAK`. Their cutoff-before evidence is retained for disclosure intake, but they are disclosure-only and do not count as final peers. The other three issuers remain `PENDING_ACTION_WINDOW_REVIEW`.

The arena is expressed as a mechanism-defined multi-region delivered cement market. Province equality is not an H1 gate. Transport radius, delivered price, plant/terminal reach, customer end-market overlap, action implementation, and perimeter continuity remain action-specific H2/V5 questions.

## Open H2/V5 Gaps

The H1 package intentionally does not contain:

- an action or action implementation screen;
- a target, final peer panel, winner, outcome, or directional learning;
- action-specific transport/delivered-price/customer overlap evidence;
- final control/perimeter continuity after the action window;
- the final comparator capacity decision.

These are DATA_COVERAGE / ACQUISITION_MODULE inputs for the next closed H2 action-screen package. Their absence is not an H1 rejection and does not authorize episode creation or report use.

## G2 Registration

- Isolated development namespace receipt: `H1:COHORT:CN:CEMENT_LISTED:20180430:STATIC:V1@1`.
- Registered at: `2026-08-24T18:56:41+00:00`.
- The receipt stores this exact H1 package as an immutable source input. It created no selection freeze, H2 screen, outcome access, event, learning permission or report-use right.
- A future H2 receipt must name this H1 receipt/version; V5 seal rejects a root whose provenance, cohort/member identity, source identity or source lane does not match its registered H1/H2 receipts.

The first static URL construction attempt used the compact date embedded in the source ID and returned 404 for all 25 attempts. The successful receipt uses the required dashed `YYYY-MM-DD` path; the 25 failed compact-date attempts contributed no evidence and are not present in the package.
