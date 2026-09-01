# Appliance issuer-identity re-curation audit

> Scope: this is a four-issuer identity-evidence checklist for a potential
> `issuer-identity-catalog.v1`. It uses only official CNINFO static annual reports
> for FY2015–FY2017, and only each report's cover plus its company/securities
> information page. It is not a JSON catalog, sample-selection decision, or a
> statement that any Pack is ready.

## Evidence method and reading convention

For every row, the primary source is the linked CNINFO static PDF, retrieved and
read directly for this audit. The cover supplies the exact Chinese legal issuer
name; the designated company-information or stock-profile page independently
ties that name to the security code and the reported short name. `PDF p.` means
the physical page index of the PDF (not a page inferred from a table of
contents). The source ID preserves the existing CNINFO lineage convention:
`CNINFO:<code>:ANN:<publication-date>:<announcement-id>`.

The publication date below is the CNINFO static-filing date in that lineage and
in the linked `finalpage/YYYY-MM-DD` path. The PDFs' embedded creation/modification
timestamps can be one calendar day earlier, so they are not substituted for the
public filing date.

## Four issuer records: direct evidence checklist

| Code | FY source, source ID, and publication date | Exact legal-issuer cover quotation | Code / securities-page cross-check | Aliases explicitly disclosed in the same annual report | Local uncertainty retained |
|---|---|---|---|---|---|
| `CN:000333` | [Midea Group Co., Ltd. 2015 Annual Report](https://static.cninfo.com.cn/finalpage/2016-03-26/1202084987.PDF), FY2015; `CNINFO:000333:ANN:20160326:1202084987`; 2016-03-26. | PDF p.1: `美的集团股份有限公司` (cover title: `美的集团股份有限公司 2015 年年度报告`). | PDF p.8: `股票简称 美的集团`; `股票代码 000333`; `公司的中文名称 美的集团股份有限公司`. | Chinese short name: `美的集团`; English company name: `MIDEA GROUP CO.,LTD.` | The profile provides no separate English-name abbreviation. This check establishes the listed issuer as presented in FY2015 only; it does not infer any later name, perimeter, or continuity claim. |
| `CN:000651` | [Gree Electric Appliances 2016 Annual Report](https://static.cninfo.com.cn/finalpage/2017-04-27/1203403930.PDF), FY2016; `CNINFO:000651:ANN:20170427:1203403930`; 2017-04-27. | PDF p.1: `珠海格力电器股份有限公司` (cover title: `珠海格力电器股份有限公司 2016 年年度报告`). | PDF p.5: `股票简称 格力电器`; `股票代码 000651`; `公司的中文名称 珠海格力电器股份有限公司`. | Chinese short name: `格力电器`; English company name: `GREE ELECTRIC APPLIANCES, INC. OF ZHUHAI`; English short name: `GREE`. | The English strings are reported company-information fields, not a separate registry extraction. No name/perimeter change outside the observed FY2016 document is assumed. |
| `CN:600690` | [Qingdao Haier 2017 Annual Report](https://static.cninfo.com.cn/finalpage/2018-04-26/1204797433.PDF), FY2017; `CNINFO:600690:ANN:20180426:1204797433`; 2018-04-26. | PDF p.1: `青岛海尔股份有限公司` (cover title: `青岛海尔股份有限公司 2017 年年度报告`). | PDF p.1 header: `公司代码：600690`, `公司简称：青岛海尔`; PDF p.6 stock profile: `A股`, `上海证券交易所`, `青岛海尔`, `600690`; and `公司的中文名称 青岛海尔股份有限公司`. | Chinese short name: `青岛海尔`; English company name: `QINGDAO HAIER CO.,LTD.`; English short name: `HAIER`. | FY2017 is the fiscal year; the CNINFO filing date falls in 2018 and is not an FY2018 report. Any later legal-name or ticker evolution is deliberately outside this evidence window and is not added as an alias. |
| `CN:000921` | [Hisense Kelon Electrical Holdings 2016 Annual Report](https://static.cninfo.com.cn/finalpage/2017-03-30/1203223381.PDF), FY2016; `CNINFO:000921:ANN:20170330:1203223381`; 2017-03-30. | PDF p.1: `海信科龙电器股份有限公司` (cover title: `海信科龙电器股份有限公司 2016 年年度报告`). | PDF p.5: `股票简称 海信科龙`; `股票代码 000921`; `公司的中文名称 海信科龙电器股份有限公司`. | Chinese short name: `海信科龙`; English company name: `Hisense Kelon Electrical Holdings Co.,Ltd`; English short name: `Hisense Kelon`. | This is the historic legal name disclosed in the allowed FY2016 source. A later rename or current-brand mapping is outside scope, so it is neither asserted nor silently merged into this issuer record. |

## Catalog-admissibility result, bounded to identity

Each of the four proposed code keys has one direct, primary-source identity
bundle with all required raw elements: a code, an exact cover quotation of the
legal issuer name, a stable source ID, publication date, physical PDF-page
locations, and only aliases actually printed in that report. The code-to-name
binding is therefore evidenced at the issuer-identity layer for the stated
historical fiscal-year window.

What remains intentionally unresolved is not a defect in those four bindings:

- A cross-window legal-name-history bridge has not been researched. In
  particular, no alias from a fiscal year after FY2017 may be supplied from this
  audit.
- The annual reports establish listed-issuer identity and reported securities
  labels, not an economic-cluster, product-arena, subsidiary, control, or
  responsibility-boundary identity.
- This evidence checklist does not construct, validate, or publish an
  `issuer-identity-catalog.v1`; it only makes the minimum source-grounded
  identity inputs explicit for a later, separately authorized catalog step.

