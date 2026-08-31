# `CN:300217`：2018-12-31 截止日前官方源包草案

> reconnaissance short name：`东方电热`（**未作历史法定发行人确认**）
>
> 状态：`CANDIDATE_ONLY / CUTOFF_ONLY / THREE_RECORDED_CNINFO_LEADS / IDENTITY_VERSION_REREAD_REQUIRED`
>
> 本文件保存的只有 already-documented CNINFO 目录 metadata；没有重新查询、下载或阅读年报。
> 因此接下来的覆盖图只是给独立 curator 的事实定位任务，不陈述任何事实答案。

## 时间边界与记录的主来源

| 财年 | Source ID | 公告日 | 记录的公告标题 | 官方静态 PDF | 版本提示 |
| --- | --- | --- | --- | --- | --- |
| FY2015 | `CNINFO:300217:ANN:20160331:1202112827` | 2016-03-31 | `2015年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2016-03-31/1202112827.PDF) | controlling version 待复读。 |
| FY2016 | `CNINFO:300217:ANN:20170407:1203259013` | 2017-04-07 | `2016年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2017-04-07/1203259013.PDF) | controlling version 待复读。 |
| FY2017 | `CNINFO:300217:ANN:20180413:1204623576` | 2018-04-13 | `2017年年度报告` | [PDF](https://static.cninfo.com.cn/finalpage/2018-04-13/1204623576.PDF) | controlling version 待复读。 |

三个公告日期均不晚于共同 cutoff。这不是对 PDF 页面、公司资料、财务报表内容或截至 cutoff
状态的读取；只能作为切断结果信息的 future curation 起点。

## 事实中性的复取证覆盖图

| 后续必须核对的事实类别 | 三份年报内的优先定位面 | 本草案允许的处置 |
| --- | --- | --- |
| 发行人、证券、年度与版本身份 | 封面、公司简介/证券资料、备查文件 | 逐年核对 code、历史 legal issuer、报告年度、公告日、标题、版本及名称桥；不得以 current short name回填。 |
| 合并与责任边界 | 子公司、合并范围变动、非控制权益、企业合并/处置、借款、担保和权益附注 | 区分集团合并层、各子公司和普通股责任，保留每年范围变化；不假定任意 component 是整个公司。 |
| 业务 carrier | 业务概要、管理层讨论、产品/分部/地区收入成本和子公司资料 | 以源文确认实际 carrier 和定义变化；`appliance-heating component lead` 不是已验证分类。 |
| OCF 与现金 | 合并现金流量表、货币资金/受限资金、现金流补充资料 | 捕捉 OCFlow、现金余额、受限条件及单位/币种/合并口径；不将其转化为 cash recognition。 |
| 资本支出 | 购建长期资产现金流、固定资产、在建工程、无形资产、投资和处置附注 | 单独保存资产 stock、购建流量、处置和项目事实，禁止预置维持/扩张资本标签。 |
| NWC 与融资 | 应收、预付、存货、应付、预收/合同性项目、借款、债券、担保、权益附注 | 每项字段须有期间、主体、会计定义，不能只以同比或总额判定营运资本消耗或融资风险。 |

## 仍待独立复核的限制

- source availability 不是身份或版本一致性。独立 curator 必须逐份回读 cover 和 company profile，
  并核验 source-ID 所指版本是否是唯一 controlling version。
- 任何产品、客户、项目、现金、资本、债务或少数股东数据都未从这三份报告读取，不能进入
  business mechanism、component ledger 或 reader report。
- 完整 exposure ledger 和 independent unseen clearance 尚未生成。该文档不创建 cohort、
  training contract 或 `CN:300217` 的任何 allocation。
