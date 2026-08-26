# R-104 cutoff-before selection candidate

Status at refreeze: `REVISED_REFREEZE_PENDING_FRESH_INDEPENDENT_REVIEW`
Outcome access: `PIT_OUTCOME_SEALED`
Registration: `NOT_REGISTERED`

## Candidate

- Company: 重庆啤酒股份有限公司 (`CN:600132`)
- Historical cutoff: `2016-04-30T23:59:59+08:00`
- Responsibility unit: the whole legal consolidated listed issuer
- Decisive question: whether six implemented brewery-production closures convert realized revenue-mix improvement and working-capital release into enough recurring whole-issuer operating contribution and owner cash to recover the disclosed closure loss over five years, or whether volume deleveraging and route spending overwhelm those savings.

## Selection Logic

`H-A` is selected without probability. Before cutoff, production operations at six breweries had already closed, revenue per annual headline beer-sales kilolitre had risen through two volume contractions, cash working capital/revenue had fallen for three years, and FY2015 owner cash remained positive after stripping the positive working-capital release. These are implemented or realized facts rather than management targets.

`H-B` remains the strongest rival because operating-contribution margin declined from FY2013 to FY2015, FY2015 selling expense rose 16.62%, volume kept contracting, and the six closed plants generated RMB204,449,973.25 of fixed-asset impairment. Working-capital release may also be non-recurring.

The fair baseline mechanically carries FY2015 forward: 989,500 kl, RMB231,478,984.88 whole-issuer operating contribution and RMB196,326,607.01 owner cash after stripping positive working-capital release.

## Refrozen Central Tests

The annual materiality step is RMB40,889,994.65, equal to 20% of the disclosed six-plant fixed-asset impairment. At an illustrative 25% tax rate it corresponds to about RMB30,667,495.99 of after-tax normal profit. The impairment anchors capital at risk; it is not deducted again as cash.

- `D3 H-A`: operating contribution at least RMB272,368,979.53.
- `D3 baseline`: RMB231,478,984.88.
- `D3 H-B`: operating contribution at most RMB190,588,990.23.
- `D4 H-A`: owner cash excluding positive working-capital release at least RMB237,216,601.66.
- `D4 baseline`: RMB196,326,607.01.
- `D4 H-B`: owner cash excluding positive working-capital release at most RMB155,436,612.36.

All D3 or D4 values inside their frozen middle intervals resolve as `MIXED`. A missing or changed recurring identity resolves as `UNKNOWN` or `MEASUREMENT_MISMATCH`. D1 and D2 are context; D5 is continuous and non-voting.

## Measurement Identity

FY2013, FY2014 and FY2015 ordinary annual reports repeat the same legal issuer perimeter and the fields required for both central voters. D3 uses only a whole-issuer RMB amount: consolidated revenue less operating cost, taxes and surcharges, selling expense and administrative expense. It does not divide consolidated activity by beer-only volume. D4 uses consolidated OCF less all cash paid to acquire fixed, intangible and other long-term assets, then subtracts `max(opening cash working capital - ending cash working capital, 0)`. This prevents one-time working-capital release from masquerading as recurring owner cash; a deterioration remains reflected in OCF.

FY2015 moved supply-chain expense from administrative expense into manufacturing cost. The D3 composite includes both accounts and is invariant to that transfer; reported gross margin remains auxiliary.

Whole-issuer production throughput is not a recurring cutoff-before identity. The current product contract requires the five D1-D5 layers and makes `D3_PRODUCT_VOLUME` optional. R-104 therefore keeps production throughput `UNKNOWN`, does not copy D2 sales volume, does not register a product-volume claim, and gives it no vote.

## Prior Rejection And Refreeze

`02a_independent_pre_outcome_review_v1_rejection.json` preserves the prior rejection verbatim. It grants no outcome access and cannot accept this revision. `07_rejection_remediation_and_refreeze.json` maps each material finding to the current product decision or a concrete measurement correction. This refreeze still requires a new independent v2 review recorded after the final freeze timestamp in `02_independent_pre_outcome_review.json`; only that reviewer may write the current receipt.

## Outcome Firewall

The selector queried only CNINFO announcements from `2013-01-01` through `2016-04-30`; the bounded issuer universe contained 301 rows and no row exceeded the cutoff. No post-cutoff title, filename, snippet, body, report availability, security price, valuation or outcome was accessed. The result-period source types and query windows in `03_outcome_acquisition_contract.json` remain unexecuted.

## Files

- `00_cohort_screen_and_source_selection.json`: bounded cohort, official cutoff sources and recurring-disclosure gate
- `01_case_freeze.json`: responsibility unit, cutoff facts, H-A/H-B, baseline, D1-D5 and sealed attestation
- `02a_independent_pre_outcome_review_v1_rejection.json`: immutable verbatim rejection of the prior packet
- `02_independent_pre_outcome_review.json`: current v2 independent review slot; selector must not write it
- `03_outcome_acquisition_contract.json`: unexecuted opaque source types, query windows and release gate
- `04_measurement_contract.json`: exact metrics, non-overlapping thresholds and resolution rules
- `05_pre_cutoff_measurement_workpaper.json`: source values, owner-cash bridge and impairment-based threshold derivation
- `06_pre_cutoff_product_volume_observability.json`: cutoff-only production-throughput audit and optional-layer decision
- `07_rejection_remediation_and_refreeze.json`: v1 rejection remediation map and fresh-review requirement

This is `HISTORICAL_SELF_REPLAY`: the file firewall prevents deliberate result access but cannot erase latent model or researcher memory. The episode cannot prove unknown-outcome deployment skill, accuracy or probability calibration.
