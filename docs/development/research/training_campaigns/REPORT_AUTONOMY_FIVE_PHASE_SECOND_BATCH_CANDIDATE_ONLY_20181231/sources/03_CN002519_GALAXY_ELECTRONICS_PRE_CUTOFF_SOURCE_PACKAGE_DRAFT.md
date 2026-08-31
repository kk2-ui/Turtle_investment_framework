# `CN:002519`：2018-12-31 截止日前官方源包草案

> reconnaissance short name：`银河电子`（**未作历史法定发行人确认**）
>
> 状态：`CANDIDATE_ONLY / CUTOFF_ONLY / THREE_RECORDED_CNINFO_LEADS / IDENTITY_VERSION_REREAD_REQUIRED`
>
> 本文仅保留既有 reconnaissance 已记录的 CNINFO 静态年报元数据。没有下载、阅读或从 PDF
> 取得任何数值、业务或结果信息。

## 时间边界与记录的主来源

| 财年 | Source ID | 公告日 | 记录的公告标题 | 官方静态 PDF | 版本提示 |
| --- | --- | --- | --- | --- | --- |
| FY2015 | `CNINFO:002519:ANN:20160422:1202218119` | 2016-04-22 | `2015年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2016-04-22/1202218119.PDF) | controlling version 待复读。 |
| FY2016 | `CNINFO:002519:ANN:20170322:1203182882` | 2017-03-22 | `2016年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2017-03-22/1203182882.PDF) | controlling version 待复读。 |
| FY2017 | `CNINFO:002519:ANN:20180320:1204490370` | 2018-03-20 | `2017年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2018-03-20/1204490370.PDF) | controlling version 待复读。 |

三条公告均在 `2018-12-31T23:59:59+08:00` 前，且年份连续。其唯一作用是使独立 curator
可以开始 document-level identity/coverage 复读，不能据此作任何公司或行业判断。

## 事实中性的复取证覆盖图

| 后续必须核对的事实类别 | 三份年报内的优先定位面 | 本草案允许的处置 |
| --- | --- | --- |
| 发行人、证券、年度与版本身份 | 封面、公司简介/证券资料、备查文件 | 逐年确认 code、法定发行人、年度、公告日、标题与 controlling version；不将 short name 视作历史 identity。 |
| 合并与责任边界 | 合并范围变动、子公司、非控制权益、企业合并/处置、借款、担保及权益附注 | 建立合并主体和责任范围；不能由合并报表总额推定单一产品或普通股独占。 |
| 业务 carrier | 业务概要、管理层讨论、营业收入/成本、产品/地区/分部及子公司附注 | 以实际披露确定 business carrier 与可比性；`consumer-electronics lead` 只是 provenance 标签。 |
| OCF 与现金 | 合并现金流量表、货币资金/受限资金、现金流补充资料 | 保存单位、币种、期间、受限条件和合并口径；不承认任何现金可得性。 |
| 资本支出 | 购建长期资产现金流、固定资产、在建工程、无形资产、投资/处置附注 | 将购建、处置、资产存量和项目叙述独立记录；禁止在这个阶段区分维持或扩张。 |
| NWC 与融资 | 应收、预付、存货、应付、预收/合同性项目、借款、债券、担保、权益附注 | 逐项固定会计定义、期间和实体；不由静态 metadata 或简单增减推导经济方向。 |

## 仍待独立复核的限制

- 链接记录未闭合 version family；若后续发现更正/修订或同日多个版本，须按预注册规则选定
  controlling version，不能随内容选择。
- 业务、合并边界、OCF、capex、NWC 和融资均未读，故不能把 source existence 转为正常盈利、
  owner cash 或资本回报的证据。
- full exposure ledger、Pack-side identity exclusion 与未见性检查还未执行；本草案无资格选择
  或冻结 `CN:002519`。
