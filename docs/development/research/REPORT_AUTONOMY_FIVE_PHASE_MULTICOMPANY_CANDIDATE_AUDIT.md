# Stage 5 multi-company candidate audit

> Date: 2026-09-01
> Scope: outcome-blind, local-only roster reconnaissance
> Result: **no honest eight-company unseen roster is currently constructible.**

## Decision

The eligible count is **zero**, not eight. The only locally visible industry
training-memory asset in `TRAINING_READY` state is the listed-cement Pack
`IEP:CN:CEMENT_LISTED:2014_2018:TRAINING:V3`, with a 2018-04-30 knowledge
cutoff. Every named cement issuer for which the permitted local materials show
both that Pack and cutoff-only official source coverage is already a Pack,
teacher, holdout, or campaign company.

This is a roster-availability finding only. It states no company, industry,
price, return, valuation, outcome, or utility conclusion.

## Eligibility rule applied

A Stage 5 entry needs all of the following:

1. a versioned `TRAINING_READY` Industry Experience Pack that may be supplied
   only as industry training memory;
2. visible local metadata for cutoff-only official issuer coverage; and
3. no identity overlap with a target, teacher, Pack path, holdout, or any
   training-campaign selection.

The audit treated a source register or an IndustryLearningBlock without a
`TRAINING_READY` Experience Pack as useful acquisition inventory, not as a
substitute for criterion 1. It also treated a generic archetype reference as
not a company. This preserves the distinction between a candidate name and a
reusable, admissible industry-memory asset.

## Qualified-intersection ledger

All eight locally named cement candidates that reach the first two criteria
are disqualified by criterion 3. The cited source coverage is metadata or a
source-package inventory; this audit does **not** assert that any PDF was
re-read.

| Company | Eligible industry-memory asset | Visible cutoff-only official source coverage | Reuse conflict | Result |
| --- | --- | --- | --- | --- |
| `CN:600585` Anhui Conch Cement | Cement Pack V3, `TRAINING_READY`; a Pack company path | Issuer identity catalog: `CNINFO:600585:ANN:20180323:1204507132`, published 2018-03-23 | Pack company; also Course 1 worked-case teacher | Exclude |
| `CN:600425` Qingsong Jianhua | Cement Pack V3, `TRAINING_READY`; a Pack company path | `CNINFO:600425:ANN:20180421:1204677754`, published 2018-04-21 | Pack company | Exclude |
| `CN:600802` Fujian Cement | Cement Pack V3, `TRAINING_READY`; a Pack company path | `CNINFO:600802:ANN:20180417:1204639756`, published 2018-04-17 | Pack company; also Course 1 worked-case teacher | Exclude |
| `CN:600801` Huaxin Cement | Cement Pack V3, `TRAINING_READY`; a Pack company path | `CNINFO:600801:ANN:20170324:1203190337`, published 2017-03-24 | Pack company; also Course 1 worked-case teacher | Exclude |
| `CN:000401` Jidong Cement | Cement Pack V3, `TRAINING_READY`; a Pack company path | `CNINFO:000401:ANN:20180323:1204506085`, published 2018-03-23 | Pack company | Exclude |
| `CN:000877` Tianshan Cement | Cement Pack V3 is the only admissible industry-memory asset at this cutoff | Identity catalog records `CNINFO:000877:ANN:20180323:1204507441`; Course 1 source package also inventories cutoff-only FY2017–FY2019 official annual reports | Course 1 frozen blind-replay / campaign company | Exclude |
| `CN:000672` Shangfeng Cement | Cement Pack V3 is the only admissible industry-memory asset at this cutoff | Course 2B source package inventories official CNINFO FY2013–FY2017 annual reports plus 2018 Q1, all on or before 2018-04-30 | Course 2B target / campaign company | Exclude |
| `CN:600720` Qilianshan | Cement Pack V3 explicitly names this as the next company-reference candidate | Course 2C source package is `CUTOFF_ONLY_SOURCE_PACKAGE` and inventories official FY2013–FY2017 annual-report PDFs, latest published 2018-03-22 | Course 2C target / campaign company | Exclude |

The Pack's other next-sampling reference, `CN:CEMENT:UNSEEN_REGIONAL_ARCHETYPE`,
is an archetype placeholder rather than an issuer and has no issuer-level
cutoff-source package. It cannot be used to fill a roster slot.

## Other local inventory does not add a candidate

These records establish why source volume should not be mistaken for an
eligible roster:

| Local asset family | What is locally visible | Why it creates no Stage 5 slot |
| --- | --- | --- |
| National appliance source register | Official statutory-PDF metadata for `CN:000651`, `CN:000333`, `CN:600690`, `CN:000921`, and `CN:600839` at 2017/2018 cutoffs | The register's status is `E0_E1_RESEARCH_ONLY`, not a `TRAINING_READY` Experience Pack. |
| National consumer-durables static source package | Candidate-discovery metadata, including `CN:002024`, `CN:000651`, and `CN:000333`, with cutoff status fields | Package status is `CANDIDATE_DISCOVERY_ONLY`; no admissible industry Pack is visible. |
| Appliance and franchise IndustryLearningBlocks | Issuer packets are marked complete cutoff-only static PDF for the named block companies | No versioned `TRAINING_READY` Experience Pack is locally visible. The franchise issuer set (`CN:002120`, `CN:002468`, `CN:600233`) is also used as Course 1 worked cases. |
| Property-services IndustryLearningBlock | Official issuer and industry source registers for its target and mechanism peers | It is an industry reference block, not a `TRAINING_READY` Experience Pack; it may not be promoted by this audit. |
| Course 1 and later campaign source packages | Numerous cutoff-only official packages exist | Their companies are campaign identities by construction, so they are exclusions, not fresh candidates. |

The repository search found only three Experience Pack artifacts: cement replay
V1 (`DRAFT`) and cement training V2/V3 (`TRAINING_READY`). No second
industry's Pack is available to diversify the roster.

## Required work before a genuine eight-company roster

Do not fill the eight missing slots with source-only issuers or with companies
from the frozen campaign universe. The reusable work needed first is:

1. **Cutoff-only official-source acquisition module:** collect and validate a
   new multi-company issuer panel (issuer identity, annual/interim documents,
   publication date, cutoff status, and responsibility boundary) for companies
   not present in the Pack or campaign exclusion sets.
2. **IndustryLearningBlock-to-Pack build:** derive a versioned, multi-company,
   multi-period Industry Experience Pack from that panel and let the existing
   readiness process establish `TRAINING_READY`; a source register or a
   single-company block must not be hand-promoted.
3. **Roster-conflict compiler/check:** materialize one identity ledger spanning
   Pack paths, teachers, targets, holdouts, and all campaign selection rosters,
   then select only the remaining issuer identities. It should be applied
   before any candidate facts or evaluation materials are assembled.

Once at least eight entries clear all three criteria, a fresh cutoff-only
roster can be frozen. Until then the truthful Stage 5 roster size is zero.

## Permitted local evidence consulted

- `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/67_industry_experience_pack_training_v3.json`
- `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/65a_cement_issuer_identity_catalog_v1.json`
- `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/01_FROZEN_WORKED_CASE_ROSTER.json`
- `docs/development/research/training_campaigns/ENTERPRISE_UNDERWRITING_COURSE_1_20260829/02_FROZEN_BLIND_REPLAY_ROSTER.json`
- Course 2B and 2C cutoff-only company/common source-package metadata
- `docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json`
- `docs/development/research/TURTLE_COMPARATIVE_NATIONAL_CONSUMER_DURABLES_2018_STATIC_SOURCE_PACKAGE_V1.json`
- Local IndustryLearningBlock metadata and training-campaign selection rosters.

Outcome/settlement materials, existing target reports, market prices, returns,
and web sources are outside this audit and are not cited.
