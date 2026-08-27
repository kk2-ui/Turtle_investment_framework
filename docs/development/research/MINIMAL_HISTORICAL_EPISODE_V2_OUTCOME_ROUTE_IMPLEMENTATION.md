# Minimal Historical Episode: Outcome Acquisition Route v2

Status: implemented for future Minimal Historical Episodes only.

## Investor-facing purpose

The second minimal episode must not discover, after a prediction is frozen,
that the official annual-report route cannot be identified. A public report
existing somewhere is not enough: the custodian must have one frozen route to
the statutory disclosure inventory, before the forecast is made.

Measurement Contract v2 therefore adds a bounded, value-free acquisition
route before static evidence and prediction:

```text
Decision Contract
  -> Technical Route Identity (official code -> orgId routing only)
  -> Measurement Contract v2 (frozen CNINFO route)
  -> static evidence
  -> prediction
  -> contract-only access
  -> value-free FIELD_READY / MEASUREMENT_MISMATCH inventory
  -> official observation
  -> mechanical settlement
```

This reduces a reusable acquisition failure. It does not make an outcome more
favorable, change a forecast, or grant learning, CJO, valuation, report, or
investment rights. All objects remain
`MECHANICAL_SETTLEMENT_ONLY + NO_METHOD_TRANSFER_RIGHTS`.

## Closed v2 route

`outcome_acquisition_route` is part of the Measurement Contract and freezes:

- `provider = CNINFO_ANNOUNCEMENT_METADATA` and
  `provider_version = phase10-cninfo-announcement-query.v1`;
- six-digit `security_code`, exact `company_id = CN:<code>`, and exact
  `issuer_id = ISSUER:CN:<code>`;
- nonempty CNINFO `organization_id`;
- `tab_name = fulltext`, `announcement_category = ANNUAL_REPORT`, and bounded
  `begin_date`, `end_date`, and `page_size` (1--30);
- `static_pdf_url_policy = CNINFO_STATIC_FINALPAGE_PDF`.

### Annual-report version-family policy

The route may additionally freeze `annual_report_version_policy`.  It is an
acquisition rule, not a selected source: it cannot contain an announcement ID,
title, publication date, PDF URL, page, or any outcome content.

`ORIGINAL_ONLY` is the historical/default behavior.  It permits exactly one
direct original annual-report title and otherwise returns a value-free
`MEASUREMENT_MISMATCH`.  This keeps existing v2 records readable: an older
route that lacks the optional field behaves as `ORIGINAL_ONLY`, and does not
gain a path through a revised family.

`ONE_OFFICIAL_REVISED_VERSION_AFTER_ORIGINAL` is the only opt-in policy.  It
may select a revised report only when the same bounded official metadata
enumeration contains exactly one direct original title and exactly one direct
canonical revised title (`YYYY年年度报告（修订版）`, with either supported
parenthesis form).  The selected revised row must still carry the exact
static-finalpage PDF URL, and its metadata date and later single PDF-page
locator remain in the ordinary source-identity validators.

The adapter never infers a family from announcement ordering, IDs, PDF text,
or a caller choice.  A summary is not a family member.  A cancellation,
withdrawal, revocation, unsupported correction/update label, missing original,
duplicate original/revision, multiple revisions, or policy/family disagreement
remains `MEASUREMENT_MISMATCH`; it cannot fall back to another row.  No other
annual-period title is ignorable: only the exact original, canonical revision,
and exact annual-report summary forms are permitted in the bounded family.

The query dates must form a closed range, and its start must follow the frozen
outcome period end. The contract does not contain an annual-report title,
selected announcement, PDF quote, outcome value, price, or prediction.

### Technical Route Identity

An annual report PDF cannot reliably disclose CNINFO's internal `orgId`.  For
new v2 episodes, the controller therefore freezes one separate
`TECHNICAL_ROUTE_IDENTITY` after the Decision Contract and before the
Measurement Contract or prediction. It comes from CNINFO's official stock-map
resolver and is deliberately *not* a cutoff-era company-evidence claim.

Its closed receipt contains only the exact six-digit code, matching frozen
issuer/company identity, `organization_id`, resolver endpoint/version, and
`observed_at`. It cannot carry an issuer name, announcement title, metadata
row, PDF, body, outcome, price, or return. The resolver is called with the
frozen code alone and must return exactly that code and one `organization_id`;
unavailability, an identity disagreement, or extra response material produces
a value-free pre-outcome `MEASUREMENT_MISMATCH` instead of a guessed route.

The Measurement Contract stores a reference to that receipt and must exactly
match its code and `organization_id`. A caller cannot substitute either field.
This technical routing lookup does not relax the separate cutoff rule for
static evidence: all company facts used for a forecast remain restricted to
cutoff-before official static sources.

The custodian adapter accepts only an authorization ID and derives every route
parameter from the stored contract. The production runner may additionally
receive one page locator from the custodian for the route-selected PDF; it has
no security-code, organization-ID, date-window, source URL/date/identity, or
generic route argument. Thus a caller cannot redirect the post-prediction
inventory toward a more convenient issuer or period.

The supported runner command is
`controller-acquire-and-register-outcome-source-inventory`. The former manual
inventory-JSON command is intentionally absent: an external caller cannot
submit a hand-selected `FIELD_READY` source. The controller first runs the
stored-route adapter, then appends its value-free candidate with its own clock.

## Legacy boundary

The v1 schema stays readable for immutable history, including the existing
CN:600585, CN:600802, CN:600425, and CN:002003 artifacts. It cannot register a
new Minimal episode, authorize new outcome access, or append a new source
inventory. There is no v1-to-v2 upgrade path and no retrofit of existing
episode artifacts or SQLite state.

This addresses the protected terminal forms previously exposed by
`NO_UNIQUE_DIRECT_ANNUAL_REPORT` and
`CNINFO_ORGANIZATION_ROUTE_UNAVAILABLE`: each is an
`ACQUISITION_MODULE` / `DATA_COVERAGE` issue, not evidence of a company’s
operating quality.

## Future curator handoff (strictly pre-outcome)

For a new real episode, the independent pre-outcome curator must deliver these
route facts together with the Decision/Measurement Contract, before the
forecaster reads or freezes a prediction:

1. The exact `CN:<six-digit security code>` and matching
   `ISSUER:CN:<six-digit security code>` identity.
2. Permission for the controller to make the narrowly scoped official CNINFO
   stock-map resolution for that exact code. The resulting technical receipt
   records only the code, org ID, resolver endpoint/version, and observation
   time; it deliberately records no company name, title, announcement, body,
   or outcome. It is current routing provenance, not historical economic
   evidence, and it must exactly bind the frozen `CN:<code>` /
   `ISSUER:CN:<code>` identity.
3. The one bounded annual-report enumeration window following the frozen
   outcome-period end, using the fixed v2 provider, `fulltext` tab,
   `ANNUAL_REPORT` category, page size, static-finalpage policy, and—for new
   routes—an explicit annual-report version-family policy.  The curator may
   choose only `ORIGINAL_ONLY` or the documented exact original-plus-one-
   revised relationship; it may not nominate an announcement or PDF.
4. The already-frozen company/issuer, responsibility boundary, metric, unit,
   outcome period, and direct field definition.

The curator must not enumerate the outcome window, select an outcome annual
report, open an outcome PDF, read a result value, price, return, H2, R-103,
CJO, or report. If the official technical resolver cannot return one exact
code-to-orgId mapping, the correct result is a value-free pre-outcome mismatch
/ new candidate request—not an after-access `MEASUREMENT_MISMATCH` and not a
guessed organization route.

`cohorts/MINIMAL_HISTORICAL_EPISODE_V2_ROUTE_FIXTURE_TEMPLATE.json` is a
non-real, `.invalid` synthetic template that validates this pre-outcome shape.
It is never a production object or a custodian input.

## Verification boundary

Focused synthetic tests prove that v2 registration succeeds, malformed or
mismatched routes are rejected before access, original-only and
original-plus-summary families remain safe, the sole explicit revised-family
policy selects one canonical revised static row only, and cancellation,
withdrawal, policy mismatch, ambiguous versions, source-date, and page-
identity failures remain closed. The adapter derives its exact request only
from the stored contract, v1 records cannot start a new custody flow, and no
observation or settlement can pass without a stored `FIELD_READY` inventory
receipt. They do not query CNINFO or make any claim about a real company.
