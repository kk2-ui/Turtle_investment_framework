# 02669 Reader Evidence Binding: Independent Review

> Date: 2026-08-16
> Scope: `RETURN_READER_EVIDENCE_BINDING` only
> Reviewer: independent follow-up review
> Candidate: China Overseas Property Holdings (02669.HK), Q1.1-F V4

## Verdict

**PASS, with existing `DATA_LIMITED` boundaries retained.**

This review verifies the reader-facing evidence repair only. It does not
accept the candidate as a formal Golden Report or upgrade its action status.

## Evidence Binding Review

The current reader Markdown has 31 nearby `[source: ...]` anchors and 31
evidence bindings. The rendered Markdown and HTML preserve those bindings.

Independent first-party page checks against the official 2025 annual report
confirm that the cited page neighborhoods support the adjacent factual claims:

| Reader subject | Checked official support |
|---|---|
| Project mix, third-party orders, urban-space expansion, revenue and margin pressure | printed pp.34-46 |
| Contract assets, receivables, cash conversion and auditor focus | printed pp.121-133 |
| Related-party balances, ageing, unbilled/acceptance-linked contract assets | printed pp.202-205, 218-220 |
| Restricted deposits, group cash, PRC unremitted earnings, statutory reserves and company-only cash | printed pp.205, 210-212, 230-235 |

The reader distinguishes annual-report facts from model judgments. For
example, the 30%/50%/75% cash-recognition cases, the 80% new-cash treatment,
the long-owner range and the XIRR scenarios are explicitly presented as
conditions or research judgments, not as issuer disclosures. The 51-company
percentile comparison is explicitly described as a system peer sample; the
annual-report anchor supports the company financial facts in that paragraph,
not the peer-sample calculation.

## Reader Coverage

The reader-coverage contract was run with explicit `property_service`
archetype routing. It passed all seven topics:

```text
business_mechanism
earnings_route
ordinary_share_cash_access
valuation_return_price
counter_thesis_permanent_loss
monitoring
data_boundaries
```

It reported `source_anchor_count=31`, `evidence_binding_count=31`, and no
blocking finding. The reader HTML contains no unresolved `{{RESULT:...}}`
tokens.

## V4 Identity And Numeric Preservation

An independent recalculation from
`total_return_v4_inputs.candidate.json` exactly matched the active candidate
results for the material route and price fields:

```text
route                  = DUAL_ROUTE
primary_route          = PRIMARY_ROUTE_UNKNOWN
primary action price   = UNKNOWN_NO_EVIDENCE_BACKED_ACTION_PRICE
current 3Y XIRR        = 3.87%
current 5Y XIRR        = 3.92%
business-value 5Y XIRR = 3.49%
no-confirmation 5Y     = 4.35%
P_LONG                 = HKD1.35-HKD1.85 conditional range
fixed-terminal 5Y      = HKD2.64 conditional price
discount-path 5Y       = HKD2.23 pressure price
```

The reader and rendered HTML retain those identities. Neither HKD2.64 nor
HKD2.23 is promoted to an action price, and neither is averaged with
`P_LONG`.

## Verification

```text
.venv/bin/python -m pytest -q \
  tests/test_calculate_q1_02669_total_return_v4.py \
  tests/test_render_q1_02669_revision.py

49 passed, 23 subtests passed
```

## Residual Boundary

The remaining `DATA_COVERAGE + REASONING` limits are unchanged: city/public
service cohort profitability and collection, smart-engineering cash
conversion, entity-level upstream distributability, capital-use returns, and
an independently evidenced terminal catalyst are not closed. These limits
continue to require `PRIMARY_ROUTE_UNKNOWN`, action price `UNKNOWN`, and
candidate-only status.
