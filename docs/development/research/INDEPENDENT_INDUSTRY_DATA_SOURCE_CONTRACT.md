# 独立行业数据 PIT 来源契约

> 状态：`DESIGN_AND_VALIDATOR_READY / NO_LICENSED_RELEASE_ADMITTED`  
> 适用：AVC 一类零售追踪、产业在线（ChinaIOL）一类出货追踪，以及未来具有相同版本纪律的持牌独立行业数据。  
> 不适用：公司现金、返利、经销库存、资本配置、治理、普通股索取权、估值或投资回报的官方事实替代。

## 要解决的问题

当前格力 V1 缺的是同定义的品牌×渠道×产品×分母行业观察，而不是更多公司年报。把厂商线上份额、行业总量或当前网页上的产品介绍拼成全渠道份额，会把 H-A（渠道/价格带重配）和 H-B（广义竞争恶化）错误地裁决为一条机制。

根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`。经济影响是竞争持续期、正常 owner cash 与永久损失判断可能被高估或低估；因此在下面的来源包真正存在前，格力保持 `UNDISCRIMINATED`，不写**冻结的**中心路径、精确概率或价值结论。这个边界不等于停止研究：不完美资料仍可形成明确标注的 `TENTATIVE_WORKING_PATH`，只用于提出反方、决定下一项取证和指定未来应出现的传导顺序，不能升级为结论或投资输入。

## 测量不确定性：把来源当传感器，不当真相投票

历史版本和 query identity 只能证明当时能看到**哪一版**数据，不能证明该版数据准确。每个 release 还必须声明 `measurement_profile`；它不计算“可信度分数”、不为噪声虚构概率，也不允许把多个供应商的数值平均成一个看似精确的答案。

| `permitted_inference` | 可做什么 | 不能做什么 |
|---|---|---|
| `DIRECTIONAL_SENSOR_ONLY` | 发现异常、生成 H-A/H-B 的问题、要求公司官方资料检查后续传导。 | 不能结算数值 FJ、状态分解或公司相对位置。 |
| `WITHIN_PROVIDER_RELATIVE_CHANGE` | 在 provider、dataset、release family、品牌/产品/渠道/分母 mapping 均冻结时，检验同源相对变化和预注册的机制先后顺序。 | 不能把水平值当公司会计事实，不能跨 provider 拼接、平均或把零售端变化直接变成收入/现金。 |
| `LEVEL_WITH_STATED_LIMITS` | 只有供应商给出可定位的方法说明和明确误差边界时，才可在其声明范围内陈述一个非官方水平观察。 | 仍不能替代公司披露、解除现金/资本路径的官方要求，或把边界外推成机制概率。 |

`known_limitations` 必须逐条说明覆盖、抽样、品牌映射、渠道定义、修订或模型口径的已知限制，并给出保守处理。来源相互矛盾时固定动作为 `DO_NOT_AVERAGE_REOPEN_MECHANISM`：保留分歧、检查哪一条因果箭头或测量边界发生变化，再等待同源后续观察和公司官方传导；绝不以平均数选 H-A 或 H-B。

## 可被准入的最小对象

来源包中每个 `source_type=LICENSED_INDUSTRY_DATA` 记录都必须显式为 `official=false`，并带有 `industry_data_contract`（机器契约见 [schema](../../../schemas/phase10_independent_industry_data_source.schema.json)）：

| 层 | 必填内容 | 防止的错误 |
|---|---|---|
| 历史版本 | provider、dataset、release ID、version ID、publication time、data-as-of、原始/历史修订身份与 revision ID | 用今天数据库的回填值假装 cutoff 当时可见。 |
| 查询身份 | 无密钥的 query ID 和完整 query parameters | 事后改产品、地域、期间或渠道筛选。 |
| 指标语义 | `RETAIL_SELL_OUT` 或 `SHIPMENT`、provider 的定义原文定位 | 将零售、出货、金额、台数或线上份额混算。 |
| sell-in 边界 | `SHIPMENT` 只能是 `PROVIDER_DEFINED_SELL_IN`（附 provider 定义定位），否则必须为 `SHIPMENT_SEMANTICS_UNRESOLVED` | 把“内销出货”自动写成渠道 sell-in。 |
| 可比范围 | geography；product/channel/brand mapping；denominator 的 mapping ID 与定义 | 用不同产品、渠道、品牌聚合或分母计算“份额变化”。 |
| 测量边界 | 方法披露/locator、误差是否量化、最大允许推断、已知局限及分歧处理 | 把供应商数字当真值、把多源不一致平均掉，或用一条有噪声数值裁决公司机制。 |

源记录的 `source_version`、`published_at`、`data_as_of` 和（若有）`revision_published_at` 必须与 contract 内 release 完全一致。`ORIGINAL_HISTORICAL` 必须使用 `ORIGINAL_VINTAGE`；`HISTORICAL_REVISION` 只能使用截止日前已发布、身份明确的历史修订版本。`CURRENT_RESTATED_ONLY` 仍不可准入。

### 出货—零售—库存的共同边界

若要核对 flow 与 stock，三个独立 export 必须来自**同一 provider、dataset、release ID 和 version ID**，并分别标记为 `RETAIL_SELL_OUT`、`SHIPMENT`、`INVENTORY_STOCK`。每一份还需保存完全相同的 `stock_flow_boundary`：产品/地域/渠道/品牌/分母 mapping ID、期间、库存归属、边界 ID 与定义 locator。出货轨还必须有 `PROVIDER_DEFINED_SELL_IN`；`SHIPMENT_SEMANTICS_UNRESOLVED` 即使来源本身可读，也不能参与核对。

`validate_stock_flow_reconciliation(...)` 只将这三项分类为 `RECONCILABLE` 或 `NOT_RECONCILABLE`，不在系统内作 `shipment − sell-out` 算术，也不生成任何公司结论。边界不齐、provider/version 不同或任一交易点没有 provider 定义时，三项只能并列为 `MECHANISM_DISCOVERY`；不得由差额推断补库、去库、格力份额、收入、返利、现金或 H-A/H-B verdict。

## AVC 与 ChinaIOL 的预注册用法

| 轨道 | 可解决的问题 | 允许状态 | 不能推出的结论 |
|---|---|---|---|
| AVC 零售轨 | 同一产品、地域、渠道和分母下的品牌销量/销售额、ASP 或价格带；用于 H-A/H-B 的零售端区分信号。 | `RETAIL_SELL_OUT`；只有已取得、版本化的原始历史 release 才能进入 source package。 | 不以其替代公司返利、佣金、库存、回款或资本配置披露。 |
| ChinaIOL 出货轨 | 品牌内销出货的早期方向信号，可提示需要检查公司披露与零售轨的背离。 | 默认 `SHIPMENT_SEMANTICS_UNRESOLVED`；只有 provider 明示交易定义且该定义保存在 source package 中，才可标为 `PROVIDER_DEFINED_SELL_IN`。 | 单独不能区分 H-A/H-B；不能自动等同 retail sell-out、渠道库存或公司收入。 |

这里没有写入 AVC 或 ChinaIOL 数据、账号、下载文件或任何份额数。官网能力页、新闻稿、公司年报转引和当前页面都只可用于发现或提出 acquisition 问题，不能替代这个 release-level 契约。

## 与 PIT 包和前瞻判断结算的边界

1. `enumerate_independent_industry_sources(...)` 冻结的是一个已声明、已获授权查询结果的完整清单；`enumeration_complete=true` 仅表示该查询结果保留完整，**不**声称已经下载整个供应商数据库。
2. 获得授权的导出文件由操作者放进 source package，并通过既有 PIT allowlist 只读读取；系统不会尝试登录、抓取或自动下载持牌数据库。对真实公司 CJO，使用 `compose_company_manifest_with_independent_industry_sources(...)` 将该 release 追加到完整公司公告 inventory，并以新的 selection policy/reason 与逐源 rationale 重冻 source selection；不得手改 manifest 或拿独立行业 manifest 替换公司包。`acquire_source_package(...)` 对该类型只确认本地 export 已存在。CSV 等 `LICENSED_DATA_EXPORT` 可作为其自身的 reader view 投影到 PIT 工作区，但 document manifest 必须标记 `licensed_industry_data / industry_data`，不能标作 company filing，也不能用 `verify_official_fact` 升格为公司 VERIFIED observation。
3. `COMPANY_JUDGMENT_ONLY` 的数值 FJ 可在其预冻结 `allowed_source_types` 明示 `LICENSED_INDUSTRY_DATA`，且其 `industry_measurement_inference` 与实际 source 的 `measurement_profile.permitted_inference` 完全一致并至少为 `WITHIN_PROVIDER_RELATIVE_CHANGE` 时，以该来源结算零售/出货指标。`DIRECTIONAL_SENSOR_ONLY` 只生成问题，不能进入数值结算或状态分解。settlement 仍要求正文已读、发布时间晚于报告 cutoff、版本身份完整、measurement basis/period/unit 相同，及 operating-source timeline 完整。
4. 独立行业数据不得标为官方来源，也不得进入公司现金、分红、资本事项、治理或 market-return 的官方证据路径。冻结适配器还要求其 FJ 的全部 driver 都是 `COMPETITION_DEMAND` 或 `UNIT_ECONOMICS`，并与相应 `FDBMON` allowlist 相交；其 metric、unit、measurement basis、period 和 observation window 必须与 FDBMON 完全一致。`CASH_CONVERSION`、`CAPITAL_ALLOCATION` 与所有 `FDBREAL` 均拒绝该类型。投资回报和价格仍须 `OFFICIAL_MARKET_DATA`；公司财务/资本事实仍须法定公司披露或其他允许的官方类型。

## 最小接纳条件

一个可用于格力竞争 FJ 的真实 release 必须同时满足：

1. 原始历史版本及本地导出文件均已取得，且 release/query/revision identity 可审阅；
2. 品牌、产品、地域、渠道和分母与被冻结的 FJ measurement rule 完全相同，或已预注册可转换规则；
3. `measurement_profile` 明确其最多只能做方向、同源相对变化还是带边界水平值；数值 FJ 至少为同源相对变化，ChinaIOL 若无 provider 定义仍保持 shipment 未解析；
4. 该观察与同窗口公司披露的量价费用/现金事实分层，不拿行业轨填补公司专有字段；
5. 结算结果只能支持或反驳预注册 FJ，不能事后升级为“官方公司事实”或自动生成投资动作。

未满足时的处理是 `UNKNOWN` / `NOT_EVALUATED`，而不是以报告数量、线上份额、单期毛利或 OCF 代替。

## 真实格力 CJO 的接入顺序

在操作者已合法取得原始历史 export 后，使用以下入口；`release.json` 只描述已取得的 release，不能以网页、新闻转述或虚构占位记录替代：

```bash
python scripts/phase10_acquisition.py enumerate-industry \
  --input release.json --output industry_manifest.json \
  --company-code 000651.SZ --cutoff-at 2026-08-03T18:00:00+08:00

python scripts/phase10_acquisition.py compose-industry \
  --input output/research/gree_v1_candidate_20260803/source_manifest.package.json \
  --industry-input industry_manifest.json \
  --selection-input composition_selection.json --output composite.json

python scripts/phase10_acquisition.py download-package \
  --input composite.json --output data/phase10/000651/<new_package> \
  --manifest-output composite.package.json
```

`enumerate-industry` 验证 release/query/metric/scope 契约；`compose-industry` 拒绝公司代码或 cutoff 不同的清单，并要求行业 source 的选择理由；最后一个命令只登记本地授权 export，不会登录或下载供应商数据库。随后才可在同一 source package 中完成 CJO 的 FDB、H-A/H-B pair、FJ、completion/snapshot、独立审阅和无价格 Phase10 case。当前真实格力没有这份 release，故本节是执行程序而不是结论。
