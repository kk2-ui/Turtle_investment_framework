# Blind 10 CN:600036 independent post-outcome review

## Decision: ACCEPT

This review used only the permitted pre-outcome judgment, pre-outcome independent review, outcome-access authorization, and custodian settlement. It did not open an outcome report or use any external, browser, prior-case, curriculum, Method Pack, or other outcome material.

## Contract and source-boundary validation

The source-identity record is internally consistent. The authorization fixes one original FY2024 report for CN:600036 / 招商银行股份有限公司, including the 2025-03-26 disclosure date, announcement ID `1222895154`, and the exact authorized static-PDF URL. The settlement repeats those authorized identity fields, records matching cover legal name and ticker, and declares `MATCHED`. Its contents-title qualifier `（A股）` is recorded as the PDF contents label; it is not a substitute source, and the settlement continues to identify the same authorized report, announcement, and URL.

The four-cell contract is unchanged and complete in the authorization and settlement: `CMB24_01_RETAIL_AUM_AND_WEALTH_INCOME`, `CMB24_02_GROUP_NIM_STABILITY`, `CMB24_03_COMPONENT_CREDIT_RECOGNITION`, and `CMB24_04_RISK_CAPITAL_TRACTION`. The settlement applies the frozen scopes, definitions, thresholds, and pass/fail/mixed resolutions rather than adding a field or replacing a required metric with a proxy. In particular, it preserves the bank-level real-estate and group-level credit-card scopes, and retains the advanced-approach CET1/RWA treatment for the capital cell.

The settlement's firewall attestations limit access to the authorized PDF and four frozen cells, attest that no outside outcome source or non-frozen outcome fact was used, and attest that no pre-outcome artifact or enterprise/investment judgment was produced. This is consistent with the authorization's forecaster and pre-outcome-reviewer boundary.

## Permitted cell use and local mismatch

- `CMB24_01_RETAIL_AUM_AND_WEALTH_INCOME` is a `LOCAL_MISMATCH` and may not be resolved or used to trigger a J1 pass, fail, or mixed action. The contract requires group retail AUM, whereas the settlement found the available AUM field at company scope. Its separately recorded fee component does not cure that scope break. This mismatch is local to the J1 cell: it neither becomes adverse evidence nor blocks the independently resolved J2/J3 cells; no substitute AUM measure or pre-outcome revision is authorized.
- `CMB24_02_GROUP_NIM_STABILITY` is a usable `FAIL` for J2 under its frozen group-NIM definition and thresholds.
- `CMB24_03_COMPONENT_CREDIT_RECOGNITION` is a usable `PASS` for J3 under its frozen bank-real-estate and group-credit-card definitions and thresholds.
- `CMB24_04_RISK_CAPITAL_TRACTION` is a usable `PASS` only for its frozen risk-capital capacity treatment supporting J2/J3. It does not erase the separate J2 margin-cell failure, and it is not owner-cash, total-credit-quality, or whole-enterprise evidence.

## Unmodified post-reveal consequences

No J1 outcome action is called: the local scope mismatch leaves its frozen pass/fail/mixed actions unapplied.

For the J2 margin cell, the unmodified `FAIL` consequence is: “Weaken J2 and move the next-cutoff agenda to deposit pricing, terming, loan yields and asset-allocation limits before relying on the earnings engine.” The concurrent risk-capital `PASS` consequence remains separately: “Retain risk-capital capacity as support for J2/J3 and focus the next cutoff on quality of RWA and loss absorption, not on a claim of owner-cash availability.”

For J3, the unmodified component-credit `PASS` consequence is: “Retain J3 as conditionally supported and focus the next-cutoff agenda on loss-recognition coverage and recoveries by component.” The same separately scoped risk-capital `PASS` consequence above also applies to J3. Neither action permits a broader enterprise conclusion.

Any later outcome-derived synthesis must apply only these resolved-cell consequences and must not modify the pre-outcome text in `131_CN600036_PREOUTCOME_JUDGMENT.json` or `132_CN600036_PREOUTCOME_INDEPENDENT_REVIEW.md`.

## Validation

- The frozen-cell IDs and their order agree across the pre-outcome contract, authorization, and settlement.
- The reported settlement states are exactly one local mismatch, one fail, and two passes; each is localized to the judgment links frozen before reveal.
- No source substitution, fifth cell, threshold change, resolution rewrite, backward pre-outcome edit, or outcome-aware investment conclusion is recorded.
