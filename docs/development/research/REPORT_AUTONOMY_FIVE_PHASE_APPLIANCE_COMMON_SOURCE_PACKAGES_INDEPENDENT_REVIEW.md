# Appliance common-source packages — independent review

**Decision: PASS** — limited to admitting the eight listed packages as the common, cutoff-only factual input for the subsequent two-arm contracts. This is not an authorization to turn a group-level fact into a component-level fact, or to derive a later-stage conclusion from these packages.

## Scope and method

This is an independent, read-only review of the following eight files only:

- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN000016_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN000404_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN002403_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN002543_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN002614_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN002676_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN002705_PRE_CUTOFF_SOURCE_PACKAGE.md`
- `training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_APPLIANCE_20181231/sources/01_CN603355_PRE_CUTOFF_SOURCE_PACKAGE.md`

No 2019-or-later material, price, valuation, return, outcome, target report, or external model API was read or used. I inspected each package's cited-source, boundary, fact, and UNKNOWN surfaces. I also performed a read-only availability check of the 24 unique `static.cninfo.com.cn` annual-report URLs: all returned HTTP 200. Their embedded disclosure dates run from 2016-02-05 to 2018-04-27, hence all precede the 2018-12-31 cutoff.

## Admission checks

| Package | Three dated static CNINFO annual reports | Formal identity and consolidation boundary | Common-input sufficiency | Gap treatment |
| --- | --- | --- | --- | --- |
| CN:000016 | PASS — FY2015–FY2017, IDs `1202150039` / `1203237063` / `1204553590` | PASS — same issuer, code, control-based consolidation and FY2017 inclusion changes stated | PASS at group level — business, three-period operating facts, CFO/capex cash, receivables, inventory, borrowing, disposals/projects and financing facts | PASS — component-level cash, capital, working-capital and funding allocation explicitly `UNKNOWN` |
| CN:000404 | PASS — `1202081825` / `1203235613` / `1204554761` | PASS — same issuer/code; group perimeter and the Shanghai Weile addition stated | PASS at group level — operating components, CFO/capex cash, working capital, debt, encumbered assets, acquisitions/projects and loan flows | PASS — ice-compressor component allocations and customer-contract fields explicitly `UNKNOWN` |
| CN:002403 | PASS — `1202281897` / `1203405993` / `1204737564` | PASS — same issuer/code; consolidated subsidiaries and perimeter references stated | PASS at group level — operations, CFO/capex cash, working capital, debt, restricted assets, projects/placements and financing flows | PASS — component allocation and FY2015/FY2016 long-term-borrowing values explicitly `UNKNOWN`, not zero-filled |
| CN:002543 | PASS — `1202113827` / `1203333837` / `1204648529` | PASS — same issuer/code; consolidated group and boundary-change references stated | PASS at group level — business/channel facts, CFO/capex cash, working capital, debt, restricted assets, projects/joint ventures and loan facts | PASS — product/entity project cash and funding allocation explicitly `UNKNOWN` |
| CN:002614 | PASS — `1202216781` / `1203378240` / `1204793945` | PASS — the pre-cutoff name change is bound to one code and explicitly described; consolidated subsidiaries and acquisitions are stated | PASS at group level — operating facts, three-period CFO/capex cash, working capital, debt, restricted cash, acquisition/new-base and placement facts, plus accounting changes | PASS — brand/ODM/new-base profit and cash allocation, and brand-level receivables, explicitly `UNKNOWN` |
| CN:002676 | PASS — `1201971842` / `1203374495` / `1204697602` | PASS — same issuer/code; consolidated group and annual perimeter changes stated | PASS at group level — operating facts, CFO/capex cash, working capital, debt reclassification, project/funding facts and accounting presentation breaks | PASS — FY2015 restricted-cash amount and non-core component economics explicitly `UNKNOWN`; missing values are not converted to zero |
| CN:002705 | PASS — `1202241491` / `1203402114` / `1204799583` | PASS — same issuer/code; consolidated financial basis and annual scope changes stated | PASS at group level — business/customer facts, CFO/capex cash, working capital, debt, restricted cash, placement/project/acquisition facts and presentation change | PASS — untranscribed customer fields and all component/customer cash and collection terms explicitly `UNKNOWN` |
| CN:603355 | PASS — `1202243180` / `1203379379` / `1204791498` | PASS — same issuer/code; consolidated subsidiaries and annual boundary changes stated | PASS at group level — operations, CFO/capex cash, working capital, debt classification, restricted-cash statement, IPO/funding and accounting-presentation facts | PASS — customer identity and brand/ODM/component cash, profit and receivable allocation explicitly `UNKNOWN`; blank borrowing disclosure is not interpreted as zero |

## Fact-layer boundary

The packages retain a factual layer. Each contains official-source citations with pages, group-level operating and financial observations, named project/acquisition/funding facts, and accounting or reporting-perimeter breaks where disclosed. The review found no base-case, conditional-case, excluded-route, maintenance-versus-growth capital, normalized economics, owner-cash, permanent-loss, valuation, price, return, outcome, or target-report conclusion embedded as a package conclusion. Statements that a particular field cannot be allocated, or that an unlisted balance must not be treated as zero, are evidence-boundary instructions rather than a later-stage conclusion.

## Two-arm symmetry and localized limitations

The data surface is sufficient for symmetric use because both arms can receive the same eight package files, the same three annual-report vintages per issuer, the same group-level operating/cash/working-capital/debt/project/funding facts, and the same named reporting-perimeter breaks plus accounting-presentation breaks where the package discloses them. No package grants one arm a separate source, hidden reconstruction, or future observation.

The material limits are localized rather than concealed: all eight packages identify missing component-, brand-, ODM-, product-, or customer-level cash and capital allocation; several also mark a particular restricted-cash or borrowing field as `UNKNOWN`/unlisted and forbid a zero assumption. The subsequent contract must preserve those local states for both arms. It may use the disclosed group-level facts, but may not attribute them to a business component, customer, project, or financing source without a cited allocation inside the shared source set.

No blocking defect was found, so no RETURN remediation is required.
