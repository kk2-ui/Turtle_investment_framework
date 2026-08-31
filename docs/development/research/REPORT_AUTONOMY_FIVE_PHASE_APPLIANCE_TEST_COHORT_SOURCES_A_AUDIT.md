# Appliance test-cohort cutoff-only source audit A

**Audit status:** `COHORT_FEASIBILITY` only  
**Cutoff:** `2018-12-31T23:59:59+08:00`  
**Decision authority:** admission screen only — this audit does not select, freeze, replace, or settle any issuer.

## Scope and method

This audit tests four named candidates against the minimum source and identity
requirements for a fresh appliance test cohort. It used only:

1. CNINFO's official `hisAnnouncement/query` metadata for the named issuer,
   restricted to disclosures published no later than the cutoff; and
2. the corresponding official CNINFO static full-year-report PDFs; and
3. the existing [pre-selection cohort exposure ledger](training_campaigns/REPORT_AUTONOMY_FIVE_PHASE_CANDIDATE_ONLY_20181231/00_PRE_SELECTION_COHORT_EXPOSURE_LEDGER.json).

No 2019-or-later disclosure, price, valuation, return, outcome, target report,
or external-model material was read. `Formal identity confirmed` below means
that the CNINFO metadata has one security code and organization identifier, and
the FY2015--FY2017 report covers carry the same legal issuer. It is a
listed-issuer identity check, not a conclusion about common ownership,
competition, quality, cash generation, or investment merit.

CNINFO's displayed `announcementTime` (China Standard Time) supplies the
publication date. Every `CNINFO:<id>` below is the announcement ID embedded in
the official static `finalpage` carrier URL.

| Issuer | Formal identity | FY2015--FY2017 full-report chain | Component/question available | Ledger-purity result | Admission result |
|---|---|---|---|---|---|
| CN:002508 老板电器 | Confirmed | 3 / 3 | Yes | `CAMPAIGN` exposure | `EXCLUDE` |
| CN:002543 万和电气 | Confirmed | 3 / 3 | Yes | No exact exposure | `ADMIT_CANDIDATE` |
| CN:002035 华帝股份 | Confirmed | 3 / 3 | Yes | `CAMPAIGN` exposure | `EXCLUDE` |
| CN:002705 新宝股份 | Confirmed | 3 / 3 | Yes | No exact exposure | `ADMIT_CANDIDATE` |

## CN:002508 — 杭州老板电器股份有限公司

**Result: `EXCLUDE`**

- **Formal identity:** CNINFO resolves `002508` to organization `9900015938`.
  The FY2015, FY2016, and FY2017 full-report covers each name **杭州老板电器股份有限公司**.
- **Continuous official source chain:**

  | Fiscal year | CNINFO source ID and title | Publish date | Official carrier |
  |---|---|---|---|
  | 2015 | `CNINFO:1202149647`, 2015年年度报告 | 2016-04-08 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2016-04-08/1202149647.PDF) |
  | 2016 | `CNINFO:1203225575`, 2016年年度报告 | 2017-03-30 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2017-03-30/1203225575.PDF) |
  | 2017 | `CNINFO:1204595205`, 2017年年度报告 | 2018-04-10 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2018-04-10/1204595205.PDF) |

- **Admissible component and question (not a conclusion):** The FY2017 report
  describes a kitchen-appliance solution built around range hoods and gas
  stoves, with ovens, steam ovens and dishwashers among the extensions. A
  material cash/capital-responsibility question can therefore be posed: *after
  product, channel and operating-capital needs for that kitchen-appliance
  system, how durable is cash conversion?* The same report makes this a real
  question rather than an inference: operating cash flow was RMB1.256bn,
  18.72% below 2016.
- **Identity-contamination test:** The ledger records the exact issuer ID as
  `EXPOSURE:CN:002508:ROUND10:CAMPAIGN`. It is not one of the Pack-four codes
  (`000333`, `000651`, `600690`, `000921`), but the existing campaign exposure
  is independently disqualifying. The ledger has no need to be supplemented by
  a conclusion about economic similarity.
- **Root cause and next step:** `MODEL` — an already exposed campaign identity
  cannot serve as an unseen test identity. The impact is test-cohort purity,
  not a business or investment conclusion. Keep this issuer excluded from this
  test-cohort screen; do not substitute another issuer or turn this result into
  a freeze.

## CN:002543 — 广东万和新电气股份有限公司

**Result: `ADMIT_CANDIDATE`**

- **Formal identity:** CNINFO resolves `002543` to organization `9900017428`.
  The FY2015, FY2016, and FY2017 full-report covers each name **广东万和新电气股份有限公司**.
- **Continuous official source chain:**

  | Fiscal year | CNINFO source ID and title | Publish date | Official carrier |
  |---|---|---|---|
  | 2015 | `CNINFO:1202113827`, 2015年年度报告 | 2016-03-31 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2016-03-31/1202113827.PDF) |
  | 2016 | `CNINFO:1203333837`, 2016年年度报告 | 2017-04-20 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2017-04-20/1203333837.PDF) |
  | 2017 | `CNINFO:1204648529`, 2017年年度报告 | 2018-04-18 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2018-04-18/1204648529.PDF) |

- **Admissible component and question (not a conclusion):** The FY2017 report
  identifies gas water heaters as the core gas-appliance business, with gas
  stoves and related kitchen products as extensions. It also reports increased
  equipment, materials prepayments, strategic inventory and completed plant
  construction. A material question is therefore available: *can the
  water-heater / related-kitchen-appliance growth system fund its materials,
  inventory and manufacturing-capital responsibilities without impairing owner
  cash?* This is a question for later work, not an answer.
- **Identity-contamination test:** The ledger gives `ISSUER:CN:002543` the
  status `UNASSIGNED`. Its note records `RESERVED_NOT_OPENED`, explicitly not
  actual input exposure, and the ledger's exposure array contains no
  `CN:002543` record. Its formal issuer ID is distinct from the Pack-four
  issuer IDs and from the recorded appliance teachers (`CN:000651`,
  `CN:600690`), holdout (`CN:002242`), and campaigns (`CN:002035`,
  `CN:002508`, `CN:002677`).
- **Root cause and next step:** `NONE` at this admission boundary. The prior
  source/identity gap is now closed by the three official covers and metadata.
  This only permits the issuer to remain a candidate; a separate pre-outcome
  process must decide whether to research, select, or freeze it.

## CN:002035 — 华帝股份有限公司

**Result: `EXCLUDE`**

- **Formal identity:** CNINFO resolves `002035` to organization `gssz0002035`.
  The FY2015, FY2016, and FY2017 full-report covers each name **华帝股份有限公司**.
- **Continuous official source chain:**

  | Fiscal year | CNINFO source ID and title | Publish date | Official carrier |
  |---|---|---|---|
  | 2015 | `CNINFO:1202218805`, 2015年年度报告 | 2016-04-22 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2016-04-22/1202218805.PDF) |
  | 2016 | `CNINFO:1203386598`, 2016年年度报告 | 2017-04-26 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2017-04-26/1203386598.PDF) |
  | 2017 | `CNINFO:1204805433`, 2017年年度报告 | 2018-04-27 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2018-04-27/1204805433.PDF) |

- **Admissible component and question (not a conclusion):** The FY2017 report
  identifies a branded kitchen-appliance system whose products include range
  hoods, cooktops and water heaters, and whose route to market includes a
  nationwide agent/distributor network. A material question can therefore be
  posed: *does channel expansion and the supporting production/supplier cycle
  consume enough working capital to weaken cash conversion?* The report records
  2017 operating cash flow of RMB368.5m, 54.97% below 2016; that is a prompt
  for later attribution, not an attribution here.
- **Identity-contamination test:** The ledger records the exact issuer ID as
  `EXPOSURE:CN:002035:ROUND10:CAMPAIGN`. It is not a Pack-four code, but the
  known campaign exposure is sufficient to fail unseen-test identity purity.
- **Root cause and next step:** `MODEL` — pre-existing campaign exposure
  blocks a fresh-test role. The impact is test validity only; it does not
  characterize the business. Leave it excluded from this cohort and do not
  replace it, select it, or access outcomes.

## CN:002705 — 广东新宝电器股份有限公司

**Result: `ADMIT_CANDIDATE`**

- **Formal identity:** CNINFO resolves `002705` to organization `9900023005`.
  The FY2015, FY2016, and FY2017 full-report covers each name **广东新宝电器股份有限公司**.
- **Continuous official source chain:**

  | Fiscal year | CNINFO source ID and title | Publish date | Official carrier |
  |---|---|---|---|
  | 2015 | `CNINFO:1202241491`, 2015年年度报告 | 2016-04-26 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2016-04-26/1202241491.PDF) |
  | 2016 | `CNINFO:1203402114`, 2016年年度报告 | 2017-04-27 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2017-04-27/1203402114.PDF) |
  | 2017 | `CNINFO:1204799583`, 2017年年度报告 | 2018-04-27 | [static CNINFO PDF](https://static.cninfo.com.cn/finalpage/2018-04-27/1204799583.PDF) |

- **Admissible component and question (not a conclusion):** The FY2017 report
  identifies western-kitchen small appliances (for example, electric coffee
  makers) as the core export-oriented component, supported by an integrated
  design, mould, testing and mass-production service platform. A material
  question is available: *after raw-material purchases, labour, automation and
  manufacturing-capital needs, how much of the export/ODM cash flow remains
  available to the owner?* The report notes both a 25.01% increase in fixed
  assets and operating cash flow of RMB461.9m, 51.68% below 2016. Neither fact
  settles the later answer.
- **Identity-contamination test:** The ledger leaves `ISSUER:CN:002705`
  `UNASSIGNED` and contains no exact `CN:002705` exposure. Its issuer ID is
  distinct from the Pack-four identities and from the recorded appliance
  teacher, holdout, and campaign identities named above.
- **Root cause and next step:** `NONE` at this admission boundary. The stated
  FY2015 cover/identity gap is closed. Keep the issuer only as an admitted
  candidate pending a separate, cutoff-safe decision process; do not infer
  selection, a freeze, or an outcome treatment.

## Cohort-level conclusion

The cutoff-only record supports two source-complete, identity-clear **admitted
candidates** (`CN:002543`, `CN:002705`) and identifies two formally
source-complete but already exposed **exclusions** (`CN:002508`, `CN:002035`).
The exclusions protect unseen-test validity; they are not negative judgments
about either issuer. No company has been selected or replaced, and no test
cohort is frozen by this audit.
