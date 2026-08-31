# 第二批候选池：截止日前官方源包整理回执

> 状态：`CANDIDATE_ONLY / OUTCOME_BLIND / NOT_SELECTED / NOT_FROZEN / FULL_EXPOSURE_LEDGER_PENDING`
>
> 共同知识截止日：`2018-12-31T23:59:59+08:00`。本回执只是把第二轮官方来源侦察中已经登记的
> CNINFO 年报静态链接元数据整理为六份独立复取证草案；不构成样本资格、公司/行业结论、训练输入、
> 合同、实验冻结或结果结算。

## 本次整理的严格边界

- 唯一来源是
  [`REPORT_AUTONOMY_FIVE_PHASE_SECOND_UNSEEN_ISSUER_OFFICIAL_SOURCE_SCOUT.md`](../../../../REPORT_AUTONOMY_FIVE_PHASE_SECOND_UNSEEN_ISSUER_OFFICIAL_SOURCE_SCOUT.md)
  已登记的 FY2015--FY2017 CNINFO 年度报告 `source_id`、公告日和静态 PDF 路径。
- 本整理没有重新查询 CNINFO、下载或阅读 PDF，也没有引入任何 PDF 内容、封面身份、页码、数字、
  价格、回报、估值、结果或后续经营披露。
- `THREE_CONSECUTIVE_REPORTS_METADATA_AVAILABLE` 只表示三份截止日前 CNINFO 年报**元数据**已被
  上述侦察文档列出；控制版本、历史法定发行人、业务承载和合并边界均未确认。
- 每个发行人均为 `FULL_EXPOSURE_LEDGER_PENDING`。侦察中的
  `NO_OBVIOUS_LOCAL_CODE_HIT` 只是窄代码筛查，不能证明未见性；独立 allocator 必须完成跨
  Pack、teacher、holdout、campaign、target、source-package 与别名的全量暴露账本后，才可讨论
  后续准入。

## 来源链目录

| 编号 | 临时代码 / CNINFO 当期短名 | FY2015--FY2017 元数据链 | 当前局部处置 |
| --- | --- | --- | --- |
| 01 | `CN:000100` / TCL科技 | [三份草案](01_CN000100_TCL_TECH_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |
| 02 | `CN:000404` / 长虹华意 | [三份草案](02_CN000404_CHANGHONG_HUAYI_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |
| 03 | `CN:000521` / 长虹美菱 | [三份草案](03_CN000521_CHANGHONG_MEILING_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |
| 04 | `CN:000541` / 佛山照明 | [三份草案](04_CN000541_FOSHAN_LIGHTING_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |
| 05 | `CN:002290` / 禾盛新材 | [三份草案](05_CN002290_HESHENG_MATERIALS_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |
| 06 | `CN:002403` / 爱仕达 | [三份草案](06_CN002403_AISHIDA_PRE_CUTOFF_SOURCE_PACKAGE_DRAFT.md) | `CANDIDATE_ONLY / FULL_EXPOSURE_LEDGER_PENDING` |

## 给下一位独立 source curator 的固定复读顺序

1. 对每一财年先复读封面、公司简介/证券资料页和公告版本，确认历史法定发行人、证券代码、年度、
   公告日、文档标题及 controlling version；CNINFO 当前短名和本回执文件名均不是身份结论。
2. 在同一份控制版本中定位业务/分部承载、合并范围与非控制权益、合并现金流与现金限制、长期
   资产购建/项目附注、营运资本科目以及借款/担保/权益责任边界。保存页码、原始单位、期间、
   合并层级和会计定义。
3. 分别登记每一项披露是否跨期可比；`更新后` 行须先作版本家族与控制版本决定，不能自动把
   现有静态链接当成唯一版本。
4. 身份、来源和事实覆盖复核完成后，仍须由另一角色完成完整暴露账本与独立准入审阅；本回执
   不选择或冻结任何发行人。

本目录中没有正常盈利、维护/增长资本、owner cash、永久损失、价值、回报或行动结论。三份
链接提供的是下一道事实获取的起点，而非这些结论的证据。
