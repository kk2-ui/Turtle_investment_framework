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

## Stage 5 pre-selection cohort exposure-ledger re-review

### Verdict: PASS

Scope remained limited to the local exposure ledger and its focused regressions;
no outcome, source content, external API, or model was read or called. The two
previous `MODEL` defects are remediated without expanding the ledger's authority:

- `exposures` must now be an array. A mapping-shaped value is `INVALID`, never
  silently treated as no exposure.
- Security identifiers accept only canonical `MARKET:SECURITY` form, normalize
  case and whitespace around `:`, and reject other formats. Case/separator
  variants therefore collide before an issuer can appear on both sides.
- Each of `PACK`, `TEACHER`, `HOLDOUT`, `TARGET`, and `CAMPAIGN` now has an
  explicit TEST-side blocking regression. None is `REVIEWABLE`.

### Targeted verification

`.venv/bin/python -m pytest -q tests/test_report_autonomy_cohort_exposure_ledger.py` completed successfully: **8 passed**. Independent direct checks returned `INVALID` for a mapping-shaped history and for every one of the five prior-exposure roles.

## Candidate-only pre-cutoff source-package re-review

### Verdict: RETURN — `ACQUISITION_MODULE` / `WRITING`

Scope was limited to the ten candidate-only source-package drafts and
`00_CURATORIAL_RECEIPT.md`. No outcome artifact was read, no external source
was fetched, and no cohort was selected.

The packet correctly keeps every two-report issuer out of eligibility:
`CN:603515`, `CN:603579`, `CN:603868`, `CN:002508`, `CN:002035`, and
`CN:002705` are all `INCOMPLETE_TWO_REPORTS` and explicitly prohibited from
three-period admission. The known prior-role issuers are also not mislabelled:
`CN:002508` and `CN:002035` disclose the Round10 conflict, while `CN:002543`
remains `THREE_REPORT_DOCUMENT_CHAIN_RECONCILIATION_PENDING` and discloses its
`RESERVED_NOT_OPENED` conflict. The three-document claims for `CN:002614`,
`CN:000016`, and `CN:603355` name a per-period identity, date, title, and
official-source path; each remains candidate-only rather than ready or
eligible. No post-cutoff operating disclosure, price, return, valuation, or
outcome fact appears. The `20230703` string in the `CN:002543` issuer-archive
URL is expressly treated as a later hosting-path component, not a document
date or source-version identity, and that issuer remains blocked pending
original-version reconciliation.

However, the receipt's working boundary says that it uses *only* CNINFO full
annual-report PDFs, while its own table counts two SSE reports in
`CN:603355` as a `THREE_CONSECUTIVE_REPORTS_AVAILABLE` chain and lists two
issuer-archive reports for `CN:002543`. SSE may well be an acceptable official
exchange source, but the receipt does not say so; an issuer archive is also
explicitly not sufficient to establish the original CNINFO/version identity.
Thus the stated source policy and the meaning of a “three-report available”
chain are inconsistent.

- **Economic impact:** a later curator can treat a chain as source-qualified
  under an unapproved or version-ambiguous provenance rule, altering the
  pre-cutoff input set before identity, version, and contamination gates run.
  That can contaminate the cohort or the facts available to a later investment
  conclusion.
- **Missing fact:** the approved provider policy for a source-document chain,
  and for each non-CNINFO document the proof that it is the controlling
  pre-cutoff version (or the corresponding CNINFO original identity).
- **Prohibited assumption:** that an official SSE host automatically satisfies
  a receipt that says “CNINFO only”, or that a later issuer archive can stand
  in for the original announced version.
- **Executable remediation:** choose and record one policy. Either (a) require
  CNINFO identities and downgrade any chain relying on SSE/issuer-archive
  pointers until those identities and version families are closed, or (b)
  explicitly permit named official exchanges with their required publication
  and controlling-version evidence, while retaining issuer archives as
  non-counting reconciliation pointers. Make the `CN:603355` state conform to
  that policy. State the eligible count explicitly as zero: this packet is
  candidate-only and has no ready/eligible issuer.
- **Acceptance criteria:** the receipt and every row apply the same declared
  provenance rule; no `THREE_CONSECUTIVE_REPORTS_AVAILABLE` state depends on a
  disallowed provider or an unresolved version; `CN:002543` stays noneligible
  until its original identities/version family and exposure gate close; and all
  known exposure issuers remain neither ready nor eligible. The resulting
  documents must remain free of post-cutoff operating, outcome, price, return,
  and valuation facts.

## Candidate-only source-package strict-CNINFO remediation re-review

### Verdict: PASS

The stated provider policy and every source-row state now agree. The receipt
requires CNINFO full-report identities as the controlling version, explicitly
states that the eligible count is **0**, and still states that source-document
availability is not admission.

Only `CN:002614` and `CN:000016` remain
`THREE_CONSECUTIVE_REPORTS_AVAILABLE`; their FY2015--FY2017 rows are each
identified by a pre-cutoff CNINFO static-report identity. `CN:603355` now is
`THREE_REPORT_DOCUMENT_CHAIN_RECONCILIATION_PENDING`: its SSE FY2015/FY2016
documents are precisely labelled as non-counting location clues until the
original CNINFO identities and version families are recovered. `CN:002543`
remains pending on the same basis for its issuer-archive pointers. No issuer is
described as ready or eligible, and the known Round10/reserved-role issuers
remain blocked from admission.

The focused text scan found no outcome, price, return, or valuation fact. The
later date embedded in the `CN:002543` archive URL remains explicitly
non-controlling and cannot establish a document date or version. No outcome
artifact was read.

### Targeted verification

Static status/provenance scan of the receipt and all ten drafts confirmed that
every `THREE_CONSECUTIVE_REPORTS_AVAILABLE` row uses only CNINFO identities,
while every SSE or issuer-archive row is reconciliation-pending. `git diff
--check` passed for this review update.

## Materialized pre-selection cohort exposure-ledger re-review

### Verdict: RETURN — `ACQUISITION_MODULE`

Scope was limited to the materialized 39-issuer ledger, its local audit, and
the exposure-ledger validator. No referenced outcome, price, or source content
was opened or used.

The materialized object itself is correctly conservative: it validates as
`REVIEWABLE` with 39 issuers (`UNASSIGNED` 21, `EXCLUDED` 15,
`PACK_BUILDING` 3, `TEST_ACQUISITION` 0). All 23 exposure references exist as
local paths. Known code conflicts are recorded on the excluded side, including
`CN:002035` and `CN:002508` as Round10 campaigns, appliance Pack/teacher,
target, and holdout records, and the cement Pack/Course conflicts. All issuer
legal-entity IDs are explicitly `LEGAL_ENTITY_UNCONFIRMED:*`; none is currently
mislabelled as a test-acquisition issuer. The audit correctly describes this
as pre-selection, outcome-blind, and not a cohort choice.

The validator does not enforce that last restriction. It only rejects a
`TEST_ACQUISITION` row with a prior exposure; it accepts any non-empty
`legal_entity_id`. An in-memory-only probe changed the existing unexposed
`ISSUER:CN:603515` row from `UNASSIGNED` to `TEST_ACQUISITION`, retaining its
`LEGAL_ENTITY_UNCONFIRMED:CN:603515` identity and all other ledger data. The
validator returned `REVIEWABLE` with zero findings.

- **Economic impact:** an issuer whose code/name has not been bridged to a
  legal entity can pass the test-side gate. A later alias, restructuring, or
  security mapping collision can then contaminate the supposedly fresh test
  case or attribute another entity's evidence to it.
- **Missing fact:** a confirmed legal-entity bridge for every issuer placed on
  `TEST_ACQUISITION`.
- **Prohibited assumption:** that a security code or short issuer name proves
  legal-entity identity merely because it has no recorded prior role.
- **Executable remediation:** make
  `validate_cohort_exposure_ledger` return `INVALID` when a
  `TEST_ACQUISITION` row has a `legal_entity_id` using the documented
  `LEGAL_ENTITY_UNCONFIRMED:` marker. Add a focused regression using an
  otherwise unexposed existing row; do not alter the ledger into a cohort or
  add issuer sources.
- **Acceptance criteria:** that regression is `INVALID`; the unmodified
  39-issuer ledger remains `REVIEWABLE` with exactly 0 test-acquisition
  records; all 23 local references remain resolvable; and known code conflicts
  remain on `EXCLUDED`/`PACK_BUILDING`, never the test side. The audit and
  ledger must remain free of outcome, price, return, and valuation facts.

### Targeted verification

The source validator accepted the unmodified ledger with the counts above.
The in-memory unconfirmed-entity test-side probe incorrectly returned
`REVIEWABLE`; the existing focused validator regression suite otherwise passed
(`8 passed`).

## Materialized exposure-ledger legal-entity remediation re-review

### Verdict: PASS

The validator now rejects a `TEST_ACQUISITION` identity whose
`legal_entity_id` uses the audit's documented
`LEGAL_ENTITY_UNCONFIRMED:` marker. This is a narrow, state-preserving guard:
it does not select an issuer or alter the treatment of `UNASSIGNED`,
`EXCLUDED`, or `PACK_BUILDING` records.

The synthetic regression passes. Repeating the prior in-memory-only probe on
the existing unexposed `ISSUER:CN:603515` now returns `INVALID` with the exact
finding `test_acquisition_legal_entity_unconfirmed:ISSUER:CN:603515`. The
unmodified materialized ledger remains `REVIEWABLE` with no findings and its
unchanged counts: 39 issuers, 21 `UNASSIGNED`, 15 `EXCLUDED`, 3
`PACK_BUILDING`, and 0 `TEST_ACQUISITION`. No reference content, outcome, or
price data was read.

### Targeted verification

`.venv/bin/python -m pytest -q tests/test_report_autonomy_cohort_exposure_ledger.py`
completed successfully: **9 passed**. The focused in-memory probe and the
unmodified source-script invocation produced the states and counts above.
