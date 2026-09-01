# Stage-5 appliance test-cohort source audit C

> Status: `CUTOFF_ONLY / CANDIDATE_ELIGIBILITY_REEVIDENCED / NOT_A_SELECTION_OR_FREEZE`
>
> Cutoff: `2018-12-31T23:59:59+08:00`  
> Permitted material read: the four candidates' cutoff-before CNINFO static annual reports and their official metadata, plus `00_PRE_SELECTION_COHORT_EXPOSURE_LEDGER.json` only.

## Decision

| Candidate | Formal cutoff-period issuer re-evidenced from the three report covers | Three annual-report records | Identity-exposure result | Status |
| --- | --- | --- | --- | --- |
| `CN:000404` | 华意压缩机股份有限公司 (`华意压缩`, `000404`) | FY2015–FY2017 complete | No ledger collision with the specified four Pack identities or any teacher/holdout/campaign identity | `ADMIT_CANDIDATE` |
| `CN:000521` | 合肥美菱股份有限公司 (`美菱电器` / `皖美菱B`, `000521` / `200521`) | FY2015–FY2017 complete | The ledger omits official co-listed security `CN:200521`; it therefore cannot yet prove an issuer-wide exposure clearance | `INCOMPLETE` |
| `CN:002403` | 浙江爱仕达电器股份有限公司 (`爱仕达`, `002403`) | FY2015–FY2017 complete | No ledger collision with the specified four Pack identities or any teacher/holdout/campaign identity | `ADMIT_CANDIDATE` |
| `CN:002676` | 广东顺威精密塑料股份有限公司 (`顺威股份`, `002676`) | FY2015–FY2017 complete | No ledger collision with the specified four Pack identities or any teacher/holdout/campaign identity | `ADMIT_CANDIDATE` |

`ADMIT_CANDIDATE` means only that a separately identified issuer has the required pre-cutoff source continuity, a researchable business carrier, and no *recorded* direct identity collision. It neither allocates a test side nor selects, freezes, or substitutes a company. `INCOMPLETE` is not an exclusion: it localizes the one unresolved issuer-wide identity mapping.

## Scope and identity test

The exposure comparison used the existing candidate ledger, whose applicable appliance identities are the four current Pack records `CN:000333`, `CN:000651`, `CN:600690`, and `CN:000921`, together with its teacher (`CN:000651`, `CN:600690`), holdout (`CN:002242`), and campaign (`CN:002035`, `CN:002508`, `CN:002677`) records. None carries any of the four candidates' `CN:` codes, and none has the cover-established legal issuer names above.

This is a direct identifier test, not a claim that the candidates lack commercial, shareholder, supplier, or industry relationships with those companies. In particular, a group reference in an annual report is not a legal-entity collision. The ledger's `LEGAL_ENTITY_UNCONFIRMED:` placeholders and empty alias fields were not treated as affirmative bridges; the cover evidence below supplies the formal issuer identity for this audit only.

Every row below has a cutoff-before official publication date, one fixed CNINFO announcement ID, and one official CNINFO static-PDF carrier. The report cover was read for legal issuer, report year, and listed security identifier. No 2019-or-later material, price, valuation, return, outcome, existing target report, or model API was read.

## `CN:000404` — 华意压缩机股份有限公司

### Three-report source chain

| Fiscal year | Official source ID | Publication date | Carrier and cover result |
| --- | --- | --- | --- |
| FY2015 | `CNINFO:000404:ANN:20160326:1202081825` | 2016-03-26 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2016-03-26/1202081825.PDF): `华意压缩机股份有限公司 2015年年度报告`; `华意压缩`, `000404`. |
| FY2016 | `CNINFO:000404:ANN:20170331:1203235613` | 2017-03-31 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2017-03-31/1203235613.PDF): `华意压缩机股份有限公司 2016年年度报告`; `华意压缩`, `000404`. |
| FY2017 | `CNINFO:000404:ANN:20180331:1204554761` | 2018-03-31 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2018-03-31/1204554761.PDF): `华意压缩机股份有限公司 2017年年度报告`; `华意压缩`, `000404`. |

The three covers establish one continuous cutoff-period legal issuer and security, rather than relying on the ledger's later short label `长虹华意` as an identity bridge.

- Core-business component suitable for later acquisition: the FY2017 business overview identifies R&D, production, and sales of household-refrigerator and commercial compressors. The candidate component is the refrigerator-compressor manufacturing carrier, not the later-label shorthand or the report's ancillary activities.
- Material cash/capital-responsibility question (not a conclusion): the FY2017 report records materially higher purchasing cash outflow, inventory build, compressor-capacity project investment, and higher short-term borrowings. Across the compressor cycle, does operating cash after working-capital absorption finance the disclosed capacity/technology investment, or does the responsibility boundary require incremental short-term funding? Later work must keep procurement timing, inventories, long-lived-asset cash purchases, and borrowing separate.

**Status and next step:** `ADMIT_CANDIDATE`. Root cause: `NONE` for the stated cutoff-only admission test. The later source pack may record the cover-established legal entity and historical short name, but must not convert this local admission into test acquisition, selection, or a claim about economic control.

## `CN:000521` — 合肥美菱股份有限公司

### Three-report source chain

| Fiscal year | Official source ID | Publication date | Carrier and cover result |
| --- | --- | --- | --- |
| FY2015 | `CNINFO:000521:ANN:20160325:1202077496` | 2016-03-25 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2016-03-25/1202077496.PDF): `合肥美菱股份有限公司 2015年年度报告`; `美菱电器` / `皖美菱B`, `000521` / `200521`. |
| FY2016 | `CNINFO:000521:ANN:20170330:1203226081` | 2017-03-30 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2017-03-30/1203226081.PDF): `合肥美菱股份有限公司 2016年年度报告`; `美菱电器` / `皖美菱B`, `000521` / `200521`. |
| FY2017 | `CNINFO:000521:ANN:20180531:1205017599` | 2018-05-31 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2018-05-31/1205017599.PDF): `合肥美菱股份有限公司 2017年年度报告`; `美菱电器` / `皖美菱B`, `000521` / `200521`; the cited official record is the cutoff-before `更新后` carrier. |

The three covers establish a continuous legal issuer, but also establish that `CN:000521` alone is not the full listed-security identity. The existing ledger lists only `CN:000521` and has neither `CN:200521` nor a confirmed legal-entity bridge.

- Core-business component suitable for later acquisition: the FY2017 report says the company is focused on refrigeration and reports that refrigerator/freezer, air-conditioner, washing-machine, small-appliance, and kitchen/bathroom lines together generated 95.33% of revenue. The component to take forward is the refrigerator/freezer carrier, with the group of other product lines retained as a consolidation-boundary check.
- Material cash/capital-responsibility question (not a conclusion): the FY2017 report attributes the operating-cash-flow change to purchase payments outpacing customer cash receipts, and identifies higher operating receivables and inventory, larger construction-in-progress, and larger short- and long-term borrowings. Can the refrigeration carrier's cash conversion, separated from the other product lines, support its working-capital and long-lived-asset requirements without relying on group-level financing? This is a source-acquisition question, not an owner-cash or funding conclusion.

**Status and next step:** `INCOMPLETE`. Root cause: `DATA_COVERAGE` (and the ledger-side `ACQUISITION_MODULE` update it requires). Economic impact: without recording `CN:200521` as the same issuer's security, the existing ledger cannot rule out a prior role recorded under the B-share code, so a supposedly unseen issuer could be reintroduced. Missing fact: complete issuer-level security mapping in the ledger. Prohibited assumption: that `CN:000521` is the only listed identifier for the legal issuer. Executable remediation: a curator should add the cover-supported `CN:200521` mapping and formal legal issuer to the candidate exposure ledger, then check it against every Pack/teacher/holdout/campaign record. Acceptance criterion: the enriched identity returns no legal-entity, security-identifier, or alias collision. This audit does not make that edit.

## `CN:002403` — 浙江爱仕达电器股份有限公司

### Three-report source chain

| Fiscal year | Official source ID | Publication date | Carrier and cover result |
| --- | --- | --- | --- |
| FY2015 | `CNINFO:002403:ANN:20160430:1202281897` | 2016-04-30 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2016-04-30/1202281897.PDF): `浙江爱仕达电器股份有限公司 2015年年度报告`; `爱仕达`, `002403`. |
| FY2016 | `CNINFO:002403:ANN:20170427:1203405993` | 2017-04-27 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2017-04-27/1203405993.PDF): `浙江爱仕达电器股份有限公司 2016年年度报告`; `爱仕达`, `002403`. |
| FY2017 | `CNINFO:002403:ANN:20180425:1204737564` | 2018-04-25 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2018-04-25/1204737564.PDF): `浙江爱仕达电器股份有限公司 2017年年度报告`; `爱仕达`, `002403`. |

The covers establish one continuous legal issuer and the same listed security across all three fiscal years.

- Core-business component suitable for later acquisition: the FY2017 business overview says the product structure is weighted toward cookware, despite its additional small-appliance, housewares, and industrial-robot activities. The core component is therefore cookware manufacturing and branded/OEM sales; the robot activity remains a distinct responsibility boundary rather than part of the component by default.
- Material cash/capital-responsibility question (not a conclusion): FY2017 reports operating cash flow, a larger investment cash outflow, construction for the Wenling eastern-new-district project, and higher borrowing. Does the cookware carrier generate cash sufficient for its own working-capital and long-lived-asset needs after separating project/robot and financial-investment cash flows, or is financing attributable to another responsibility unit? That is a later evidence question, not a finding about cash quality or capital return.

**Status and next step:** `ADMIT_CANDIDATE`. Root cause: `NONE` for the stated cutoff-only admission test. A subsequent source package should retain the cookware/robot boundary and capture the relevant cash-flow, construction, and borrowing disclosures before any underwriting use; no cohort allocation follows from this status.

## `CN:002676` — 广东顺威精密塑料股份有限公司

### Three-report source chain

| Fiscal year | Official source ID | Publication date | Carrier and cover result |
| --- | --- | --- | --- |
| FY2015 | `CNINFO:002676:ANN:20160205:1201971842` | 2016-02-05 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2016-02-05/1201971842.PDF): `广东顺威精密塑料股份有限公司 2015年年度报告`; `顺威股份`, `002676`. |
| FY2016 | `CNINFO:002676:ANN:20170425:1203374495` | 2017-04-25 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2017-04-25/1203374495.PDF): `广东顺威精密塑料股份有限公司 2016年年度报告`; `顺威股份`, `002676`. |
| FY2017 | `CNINFO:002676:ANN:20180424:1204697602` | 2018-04-24 | [CNINFO static PDF](https://static.cninfo.com.cn/finalpage/2018-04-24/1204697602.PDF): `广东顺威精密塑料股份有限公司 2017年年度报告`; `顺威股份`, `002676`. |

The covers establish one continuous legal issuer and the same listed security across all three fiscal years.

- Core-business component suitable for later acquisition: the FY2017 report identifies plastic air-conditioner fan-blade design, manufacture, sale, and service as the core business, with modified plastics and mould design/manufacture forming the linked production chain. The candidate component is that fan-blade system, not a generic appliance label.
- Material cash/capital-responsibility question (not a conclusion): the FY2017 report describes lower operating cash flow alongside business-expansion purchasing and payroll cash outflow, higher investment cash outflow for refurbishment and long-lived assets, base-expansion equipment including Thai-base preparation, and higher short-term borrowing. Through the seasonal direct-supply fan-blade cycle, does this carrier cover incremental receivable/inventory and plant-capex needs from operating cash, or are they financed externally? The question keeps operating working capital, plant investment, and financing separate and makes no answer here.

**Status and next step:** `ADMIT_CANDIDATE`. Root cause: `NONE` for the stated cutoff-only admission test. Later acquisition should preserve the fan-blade/modified-plastic/mould boundary and separately bind the Thai-base and borrowing facts; this does not authorize selection or freeze.

## Closing boundary

The audit has no `EXCLUDE` decision because the permitted evidence found no recorded direct identity collision. It also does not repair the `CN:000521` ledger gap, register any candidate, alter a source package, or choose a replacement. Its only output is the cutoff-only eligibility result above.
