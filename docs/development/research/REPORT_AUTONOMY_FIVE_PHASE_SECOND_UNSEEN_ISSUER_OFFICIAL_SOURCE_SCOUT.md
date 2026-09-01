# Stage 5 appliance / consumer-durables: second official-source reconnaissance

> Date: 2026-09-01  
> Status: `CANDIDATE_RECONNAISSANCE_ONLY / OUTCOME_BLIND / NOT_SELECTED / NOT_FROZEN`  
> Common knowledge cutoff: `2018-12-31T23:59:59+08:00`

## Decision

This second pass identifies **twelve unallocated, provisional issuer leads**
with three CNINFO statutory annual-report records (FY2015--FY2017) published
before the common cutoff.  It also finds three otherwise similar issuer codes
that must be excluded immediately because they already occur in local
appliance-training material.  This makes a later independent acquisition pass
practical; it does **not** establish that any of the twelve is an eligible
test company.

The labels in the table are deliberately broad, provisional search lanes.  A
three-report chain says nothing yet about the issuer's actual product carrier,
consolidation boundary, business quality, normal earnings, owner cash,
permanent-loss risk, value, return, or investment treatment.

## Evidence perimeter and method

- Only the primary CNINFO historical-announcement metadata route was used:
  `https://www.cninfo.com.cn/new/hisAnnouncement/query`, with the resolved
  `stock=<code>,<org-id>`, market column/plate, and
  `category=category_ndbg_szsh;` parameters.  Each row was restricted to its
  financial-year annual-report query and its returned announcement date.
- The links are the CNINFO static-PDF paths returned by that primary query.
  No PDF was downloaded or read.  A link is therefore an acquisition lead,
  not a cover-page-verified issuer identity or a source package.
- No browser automation, price, return, valuation, target report, outcome,
  settlement record, or external model API was used.
- Before querying CNINFO, codes were searched as identifiers in the local
  training/campaign/Pack/teacher/holdout/target metadata inventory.  A hit is
  conservatively an exclusion, not an invitation to inspect the old work.

`CNINFO:<code>:ANN:<YYYYMMDD>:<announcement-id>` is a stable local source
notation constructed directly from the primary query's code, announcement
date, and static-PDF announcement ID.  It is not a new CNINFO record and does
not replace re-querying CNINFO at the later source-curation gate.

## Unallocated provisional source queue

All entries below returned a FY2015, FY2016, and FY2017 *年度报告* record in
the CNINFO annual-report category.  Each announcement date is before
2018-12-31.  Names are the CNINFO stock-map short names at reconnaissance
time, not a verified assertion of the historical legal issuer name; the
later curator must read each PDF cover and company-profile page.

| Provisional issuer code / CNINFO short name | Provisional lane to verify | FY2015 official static annual report | FY2016 official static annual report | FY2017 official static annual report | Immediate local conflict screen |
| --- | --- | --- | --- | --- | --- |
| `CN:000100` / TCL科技 | consumer electronics durable | [CNINFO:000100:ANN:20160329:1202090846](https://static.cninfo.com.cn/finalpage/2016-03-29/1202090846.PDF), 2016-03-29 | [CNINFO:000100:ANN:20170428:1203415745](https://static.cninfo.com.cn/finalpage/2017-04-28/1203415745.PDF), 2017-04-28 | [CNINFO:000100:ANN:20180428:1204827943](https://static.cninfo.com.cn/finalpage/2018-04-28/1204827943.PDF), 2018-04-28 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:000404` / 长虹华意 | refrigeration-appliance supply chain | [CNINFO:000404:ANN:20160326:1202081825](https://static.cninfo.com.cn/finalpage/2016-03-26/1202081825.PDF), 2016-03-26 | [CNINFO:000404:ANN:20170331:1203235613](https://static.cninfo.com.cn/finalpage/2017-03-31/1203235613.PDF), 2017-03-31 | [CNINFO:000404:ANN:20180331:1204554761](https://static.cninfo.com.cn/finalpage/2018-03-31/1204554761.PDF), 2018-03-31 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:000521` / 长虹美菱 | refrigeration appliance | [CNINFO:000521:ANN:20160325:1202077496](https://static.cninfo.com.cn/finalpage/2016-03-25/1202077496.PDF), 2016-03-25 | [CNINFO:000521:ANN:20170330:1203226081](https://static.cninfo.com.cn/finalpage/2017-03-30/1203226081.PDF), 2017-03-30 | [CNINFO:000521:ANN:20180531:1205017599](https://static.cninfo.com.cn/finalpage/2018-05-31/1205017599.PDF), 2018-05-31, `更新后` | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:000541` / 佛山照明 | consumer lighting durable | [CNINFO:000541:ANN:20160328:1202082322](https://static.cninfo.com.cn/finalpage/2016-03-28/1202082322.PDF), 2016-03-28 | [CNINFO:000541:ANN:20170418:1203314953](https://static.cninfo.com.cn/finalpage/2017-04-18/1203314953.PDF), 2017-04-18, `更新后` | [CNINFO:000541:ANN:20180330:1204543857](https://static.cninfo.com.cn/finalpage/2018-03-30/1204543857.PDF), 2018-03-30 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002290` / 禾盛新材 | appliance-material / supply-chain lead | [CNINFO:002290:ANN:20160427:1202248466](https://static.cninfo.com.cn/finalpage/2016-04-27/1202248466.PDF), 2016-04-27, `更新后` | [CNINFO:002290:ANN:20170426:1203390105](https://static.cninfo.com.cn/finalpage/2017-04-26/1203390105.PDF), 2017-04-26 | [CNINFO:002290:ANN:20180607:1205042588](https://static.cninfo.com.cn/finalpage/2018-06-07/1205042588.PDF), 2018-06-07, `更新后` | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002403` / 爱仕达 | kitchen durable | [CNINFO:002403:ANN:20160430:1202281897](https://static.cninfo.com.cn/finalpage/2016-04-30/1202281897.PDF), 2016-04-30 | [CNINFO:002403:ANN:20170427:1203405993](https://static.cninfo.com.cn/finalpage/2017-04-27/1203405993.PDF), 2017-04-27 | [CNINFO:002403:ANN:20180425:1204737564](https://static.cninfo.com.cn/finalpage/2018-04-25/1204737564.PDF), 2018-04-25 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002429` / 兆驰股份 | consumer-electronics durable / supply-chain lead | [CNINFO:002429:ANN:20160625:1202407657](https://static.cninfo.com.cn/finalpage/2016-06-25/1202407657.PDF), 2016-06-25, `更新后` | [CNINFO:002429:ANN:20170421:1203346439](https://static.cninfo.com.cn/finalpage/2017-04-21/1203346439.PDF), 2017-04-21 | [CNINFO:002429:ANN:20180330:1204547146](https://static.cninfo.com.cn/finalpage/2018-03-30/1204547146.PDF), 2018-03-30 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002473` / 圣莱退 | small-appliance lead | [CNINFO:002473:ANN:20160412:1202164360](https://static.cninfo.com.cn/finalpage/2016-04-12/1202164360.PDF), 2016-04-12, `更新后` | [CNINFO:002473:ANN:20170428:1203416237](https://static.cninfo.com.cn/finalpage/2017-04-28/1203416237.PDF), 2017-04-28 | [CNINFO:002473:ANN:20180425:1204742438](https://static.cninfo.com.cn/finalpage/2018-04-25/1204742438.PDF), 2018-04-25 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002519` / 银河电子 | consumer-electronics lead | [CNINFO:002519:ANN:20160422:1202218119](https://static.cninfo.com.cn/finalpage/2016-04-22/1202218119.PDF), 2016-04-22 | [CNINFO:002519:ANN:20170322:1203182882](https://static.cninfo.com.cn/finalpage/2017-03-22/1203182882.PDF), 2017-03-22 | [CNINFO:002519:ANN:20180320:1204490370](https://static.cninfo.com.cn/finalpage/2018-03-20/1204490370.PDF), 2018-03-20 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:002676` / 顺威股份 | HVAC / appliance-component lead | [CNINFO:002676:ANN:20160205:1201971842](https://static.cninfo.com.cn/finalpage/2016-02-05/1201971842.PDF), 2016-02-05 | [CNINFO:002676:ANN:20170425:1203374495](https://static.cninfo.com.cn/finalpage/2017-04-25/1203374495.PDF), 2017-04-25 | [CNINFO:002676:ANN:20180424:1204697602](https://static.cninfo.com.cn/finalpage/2018-04-24/1204697602.PDF), 2018-04-24 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:300217` / 东方电热 | appliance-heating component lead | [CNINFO:300217:ANN:20160331:1202112827](https://static.cninfo.com.cn/finalpage/2016-03-31/1202112827.PDF), 2016-03-31 | [CNINFO:300217:ANN:20170407:1203259013](https://static.cninfo.com.cn/finalpage/2017-04-07/1203259013.PDF), 2017-04-07 | [CNINFO:300217:ANN:20180413:1204623576](https://static.cninfo.com.cn/finalpage/2018-04-13/1204623576.PDF), 2018-04-13 | `NO_OBVIOUS_LOCAL_CODE_HIT` |
| `CN:300247` / 融捷健康 | health-durable lead | [CNINFO:300247:ANN:20160323:1202067822](https://static.cninfo.com.cn/finalpage/2016-03-23/1202067822.PDF), 2016-03-23 | [CNINFO:300247:ANN:20170415:1203300852](https://static.cninfo.com.cn/finalpage/2017-04-15/1203300852.PDF), 2017-04-15 | [CNINFO:300247:ANN:20180425:1204734979](https://static.cninfo.com.cn/finalpage/2018-04-25/1204734979.PDF), 2018-04-25 | `NO_OBVIOUS_LOCAL_CODE_HIT` |

## Immediate exclusions from this queue

These three codes have equally complete primary annual-report metadata, but
the local identity screen found them in existing appliance-training artifacts.
They are excluded from later unseen-company allocation even if an independent
curator could reconstruct their report chain.  The links are retained only to
make the exclusion reproducible, not to reopen them as candidates.

| Code / CNINFO short name | Local conflict causing exclusion | FY2015 | FY2016 | FY2017 |
| --- | --- | --- | --- | --- |
| `CN:002032` / 苏泊尔 | appliance continuous-training frozen input | [1202077930](https://static.cninfo.com.cn/finalpage/2016-03-25/1202077930.PDF), 2016-03-25 | [1203224152](https://static.cninfo.com.cn/finalpage/2017-03-30/1203224152.PDF), 2017-03-30 | [1204552803](https://static.cninfo.com.cn/finalpage/2018-03-31/1204552803.PDF), 2018-03-31 |
| `CN:002242` / 九阳股份 | appliance four-stage training and Course 1 blind-replay/campaign identity | [1202084550](https://static.cninfo.com.cn/finalpage/2016-03-26/1202084550.PDF), 2016-03-26 | [1203301064](https://static.cninfo.com.cn/finalpage/2017-04-15/1203301064.PDF), 2017-04-15 | [1204680243](https://static.cninfo.com.cn/finalpage/2018-04-21/1204680243.PDF), 2018-04-21 |
| `CN:002677` / 浙江美大 | Round 10 appliance pre-outcome / post-outcome training material | [1202185815](https://static.cninfo.com.cn/finalpage/2016-04-18/1202185815.PDF), 2016-04-18 | [1203144486](https://static.cninfo.com.cn/finalpage/2017-03-10/1203144486.PDF), 2017-03-10 | [1204441828](https://static.cninfo.com.cn/finalpage/2018-03-01/1204441828.PDF), 2018-03-01 |

## Required independent re-curation; no candidate passes it yet

The following are material gaps, not defects to paper over with the
reconnaissance labels:

1. **Identity and version.** Every chain needs cover-page confirmation of the
   historical legal issuer, code, report year, publication date, document
   title, and the relation between the CNINFO short name and any earlier
   name.  `CN:000100`, `CN:000521`, `CN:002473`, and `CN:300247` have obvious
   risk that the current short name differs from the 2015--2017 presentation.
   CNINFO's `更新后`/`修订` records in the table need a deliberate controlling
   version decision; no earlier version has been compared here.
2. **Lane and responsibility boundary.** The broad lane labels are not an
   industry classification.  A cutoff-only curator must establish the
   disclosed product/segment carrier, whether it is a finished-durable maker,
   component supplier, or diversified group, and the consolidated entity to
   which cash, debt, minority interests, or working capital belong.
3. **Three-report fact coverage.** None of the PDFs was opened.  The later
   package must take source locators for operating mechanism, cash-flow
   statement, investment/capital-spending carrier, working-capital carrier,
   financing / non-controlling-interest boundary, and the material current
   action or rival explanation.  It may not infer normal earnings, maintenance
   capital, owner cash, or a permanent-loss outcome from the existence of
   these links.
4. **Final unseen-company clearance.** `NO_OBVIOUS_LOCAL_CODE_HIT` is only a
   narrow code search.  Before any freeze, an allocator must run a complete
   identifier-and-alias ledger across every Pack-side identity, teacher,
   holdout, campaign, target, and source package.  It must also exclude all
   issuer identities chosen for Pack construction from the test side.

## Handoff

The only allowed next action is an independent, cutoff-only source curator
selecting none, one, or more leads from the twelve as separate source-package
*leads*.  That curator must remain blind to results and may reject every lead.
Only after source packages and the final cross-artifact unseen-identity ledger
are independently reviewed may a different allocator consider a preregistered
test panel.  This reconnaissance neither creates a Pack nor supplies an
Enhanced-arm input.
