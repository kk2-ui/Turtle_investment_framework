# 激成投资 local contingency：选择与结果隔离

> campaign：`JUDGMENT_FIRST_12H_20260828`
>
> roster：`training_campaigns/JUDGMENT_FIRST_12H_20260828/24_FROZEN_LOCAL_CONTINGENCY_ROSTER.json`
>
> 状态：`PREOUTCOME_CURATED / FY2022_OUTCOME_SEALED`

## 固定选择依据

候选顺序在读取任何目标结果前按以下规则冻结：

1. 排除本 campaign 已使用，或仓库已经存在 episode、settlement、价格或回报暴露的公司；
2. cutoff 前至少有两份完整的发行人官方年报；
3. 下一期完整官方年报已经在本地存在，但只允许用路径和 PDF 元数据确认存在；
4. 优先选择与已完成样本商业模式差异最大的公司；
5. cutoff 前必须存在能沿客户、经营、现金和永久损失结算的材料经营矛盾。

激成投资是固定名单第一名。其酒店拥有及运营、物业投资、开发和管理的跨地域重资产模式，区别于
本 campaign 已完成的制造、软件、零售药房、白酒、游戏、保险及餐饮等案例。选择时没有使用
FY2022 结果方向、价格、回报、预期得分、预期学习效用或写作便利性。

## Episode 身份

- company：`HK:00184 / 激成投资`
- cutoff：`2022-05-01T00:00:00+08:00`
- outcome period：`FY2022`
- archetype：`CROSS_GEOGRAPHY_HOTEL_OWNERSHIP_AND_OPERATIONS_WITH_PROPERTY_INVESTMENT_DEVELOPMENT_AND_MANAGEMENT`
- 中心经营矛盾：酒店重新开放和入住率回升，能否同时穿过 ADR/RevPAR、固定成本、维护资本开支、
  少数股权和资产减值，最终形成母公司股东可取得的 owner cash；还是仅改善营业状态或会计表象。

## Cutoff 前白名单原件

| 年度 | 来源类别 | 绝对路径 | 访问状态 |
| --- | --- | --- | --- |
| FY2020 | 发行人官方完整年报 | `/Users/xiami/workspace/analy/Turtle_investment_framework/output/00184_激成投资/00184_2020_年报.pdf` | `PREOUTCOME_CURATOR_ALLOWED` |
| FY2021 | 发行人官方完整年报 | `/Users/xiami/workspace/analy/Turtle_investment_framework/output/00184_激成投资/00184_2021_年报.pdf` | `PREOUTCOME_CURATOR_ALLOWED` |

FY2021 年报署期为 2022-03-25。本 episode 的 cutoff 取 2022-05-01，只把上述两份完整年报作为
结果前企业证据。

## 封存结果原件

- 绝对路径：`/Users/xiami/workspace/analy/Turtle_investment_framework/output/00184_激成投资/00184_2022_年报.pdf`
- 结果期：`FY2022`
- 本轮确认方式：`PATH_AND_PDF_METADATA_ONLY`
- 内容访问：`SEALED`

本文件及同目录其他结果前工件均未打开、搜索、摘录或引用 FY2022 年报正文，也未读取 settlement、价格
或回报。

## 污染检查与运行隔离

- `HK:00184` 不在本 campaign 已使用的 company roster 中；
- 仓库的 `docs/`、`config/`、`scripts/` 和 `tests/` 对 `00184` 或“激成投资”没有既有 episode、
  settlement 或训练命中；
- 原始 `output/00184_激成投资/` 目录存在旧派生报告和 cutoff 后材料，因此正式 forecaster 不得读取、
  列举或搜索该目录；
- forecaster 只能接收复制出来的 FY2020、FY2021 两份白名单 PDF；
- FY2022 PDF 只能在本目录结果前合同冻结、独立审阅和访问许可完成后交给独立 outcome custodian；
- 任一局部口径不匹配只把对应 cell 标为 `MEASUREMENT_MISMATCH`，不取消其他可结算企业判断。

## 当前权限

本轮只冻结结果前企业判断和结果合同。`outcome_access=SEALED`。transfer validation、method freeze、
Comparative、CJO、正式估值、BuyBand、报告和投资行动权限均为 `NONE / NOT_GRANTED`。
