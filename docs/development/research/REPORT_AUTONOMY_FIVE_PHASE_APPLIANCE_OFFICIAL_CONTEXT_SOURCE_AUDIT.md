# 2018 截止日前中国家电官方行业环境源审计

状态：`LOCAL_PACKAGE_ABSENT / THREE_PRE_CUTOFF_OFFICIAL_CANDIDATES_IDENTIFIED / NOT_MATERIALIZED / CONTEXT_ONLY_IF_ADMITTED`

审计日期：2026-09-01；目标 Pack 截止日：`2018-12-31T00:00:00+08:00`。

## 结论

本地目前**没有**能够被 `Industry Experience Pack` 作为
`OFFICIAL_INDUSTRY_OBSERVATION` 读取的中国家电/消费耐用品官方行业观察集。缺口是
`ACQUISITION_MODULE`，不是“公开资料不存在”：三个官方 HTML 当期发布物均可在截止日前
定位，但尚未按 `scripts/industry_context_acquisition.py` 物化为原始响应、source package 和
带 locator 的 observation ledger。因此它们今天不能进入 Pack，更不能成为任何公司事实。

有一个足以覆盖至少两类 driver 的最小候选对：国家统计局 2018 年 11 月零售稿提供
**需求**背景；工信部 2018 年 1--9 月家电运行稿同时提供**供给**和宽口径的
**行业利润池/竞争环境**背景。国家统计局 2017 年统计公报是有价值的上一年供给锚点，但
不是满足“两类 driver”所必需的第三份来源。

候选集只可在完成下文物化和校验后以 `CONTEXT_ONLY` 使用。它能防止把公司变化写成完全
脱离行业环境的故事；它不能判定品牌竞争位置或正常化现金。

## 本地审计发现

| 已检查的位置 | 发现 | 审计结论 |
| --- | --- | --- |
| `scripts/industry_context_acquisition.py` | catalog 必须有 HTTPS 官方 host、`published_at`/`data_as_of` 不晚于 cutoff、原始 HTML/PDF/data export、本地 `package_path`，且 `use_policy=CONTEXT_ONLY`；ledger 还必须指向已物化 source 和具体 locator。 | 仅有 URL 或阅读笔记不能准入。 |
| `scripts/industry_experience_pack.py` | Pack 对 `OFFICIAL_INDUSTRY_OBSERVATION` 重新验证 ledger、嵌套 source package 和本地 raw path；缺少任一项会被排除，并留下 `official_industry_observation_missing`。 | 不可手工把“已定位”升级成 Pack source。 |
| `docs/development/research/CN_APPLIANCE_INDUSTRY_LEARNING_BLOCK_V1_SOURCE_REGISTER.json` | 是中国家电发行人法定静态 PDF 的登记册，而非政府行业 context package。 | 不能把发行人披露或其转述的行业资料替代为独立官方行业观察。 |
| `docs/development/research/TURTLE_COMPARATIVE_NATIONAL_CONSUMER_DURABLES_2018_STATIC_SOURCE_PACKAGE_V1.json` | 为 discovery-only 的发行人静态披露候选，且明确限制 outcome、price、return 等访问。 | 不含可复用的政府 raw context source。 |
| `docs/development/research/industry_learning_blocks/CN_CEMENT_2014_2018/58_official_industry_context_catalog_v1.json`、`59_official_industry_context_source_package_v1.json`、`60_official_industry_context_observations_v1.json` | 唯一已物化且可验证的官方环境范例；其 `industry_id` 是水泥，raw 路径也只对应水泥。 | 可复用工件形状，不能跨行业移植进家电 Pack。 |

审计范围内未发现家电的 `official-industry-context-catalog.v1`、
`official-industry-context-source-package.v1`、`official-industry-context-observation-ledger.v1`，
或与其对应的家电官方 HTML/PDF/data-export raw 文件。因此当前本地可准入集合为 **空集**。

## 截止日前可物化的最小候选集

下表中的“候选状态”不是准入状态。URL 是官方当前归档入口；审计时仅核验了页面题名、
发布者、时间和原文所列指标，未将响应下载或写入仓库。

| 候选 source ID（建议） | driver / 期间 / 可冻结观察 | 官方 URL 与发布日期 | 文档形态及 PIT 判断 | 合法用途与禁止推断 |
| --- | --- | --- | --- | --- |
| `INDDOC:NBS:APPLIANCE:2017:STATISTICAL_BULLETIN` | **supply**；2017-01-01--2017-12-31。国家统计局年度公报的规模以上工业主要产品表：房间空气调节器产量 `17,861.5 万台`、同比 `+24.5%`（冰箱指标可作为同源补充，但不是最低集必需项）。 | [2017 年国民经济和社会发展统计公报](https://www.stats.gov.cn/xxgk/sjfb/tjgb2020/201802/t20180228_1768641.html)，国家统计局，`2018-02-28T09:30:00+08:00`。 | `ORIGINAL_HTML`；发布、数据期间都严格早于 2018-12-31。公报注明数据为初步统计数，故需保留该版本和脚注。 | 2017 年全国规上生产的年度背景/供给锚点。**不得**当作国内 sell-out、品牌销量/份额、某公司产量或库存；不得用相邻年度绝对值重算官方同比。 |
| `INDDOC:MIIT:APPLIANCE:2018Q1_Q3:RUNNING` | **supply**；2018-01-01--2018-09-30。房间空气调节器累计生产 `16,011.4 万台`、同比 `+12.9%`；家电行业产销率 `96.6%`、同比下降 `1.5 pct`，出口交货值 `2,959.2 亿元`、同比 `+5.9%`。**competition**（宽口径行业 profit-pool context，而非品牌竞争）：家电行业主营业务收入 `11,108.2 亿元`、利润总额 `879.5 亿元`，同比 `+11.9%` / `+20.3%`。 | [2018 年 1－9 月家电行业运行情况](https://www.miit.gov.cn/gxsj/tjfx/xfpgy/jd/art/2020/art_0c0f7ef6e8b84620a5222d3cf20e8b1b.html)，工业和信息化部消费品工业司，`2018-11-22T11:21:00+08:00`。 | `ORIGINAL_HTML`；正文说明“根据国家统计局数据整理”。发布、数据期间均严格早于 cutoff。 | 全国生产、产销、出口与总行业收入/利润的同期背景；后者仅可描述行业利润池已披露的变化。**不得**把产销率写成终端需求或渠道库存，不能把出口交货值当国内销量；总收入/利润不得分配给任何发行人，也不是价格、集中度、品牌份额或竞争优势的证据。 |
| `INDDOC:NBS:APPLIANCE_RETAIL:2018M11` | **demand**；2018-11 及 2018-01--11。限额以上单位“家用电器和音像器材类”零售额：当月 `946 亿元`、同比 `+12.5%`；累计 `7,965 亿元`、同比 `+8.3%`。同文还给出实物商品网上零售占社零 `18.2%`，只能作总零售渠道背景。 | [2018 年 11 月份社会消费品零售总额增长 8.1%](https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1900170.html)，国家统计局，`2018-12-14T10:00:00+08:00`。 | `ORIGINAL_HTML`；发布在 cutoff 前，数据截至 `2018-11-30`。页面列明社零定义、限额以上调查对象及基期/环比修订说明，均应随 raw 保留。 | 广义家电消费需求与全国线上化背景。**不得**当作空调台数、空调 ASP、品牌/渠道份额、线上家电占比、公司收入确认或实际 sell-out；不得把总网上零售占比套用到家电类别。 |

### 最小组合与覆盖边界

| Pack 最低 driver 覆盖 | 所需候选 | 为什么足够 | 仍缺什么 |
| --- | --- | --- | --- |
| demand | `INDDOC:NBS:APPLIANCE_RETAIL:2018M11` | 以官方、截止日前的“家用电器和音像器材类”广义零售额刻画当期消费环境。 | 单品零售量、价格、全/线上/线下口径、品牌分母。 |
| supply + broad competition/profit-pool context | `INDDOC:MIIT:APPLIANCE:2018Q1_Q3:RUNNING` | 同一官方发布物给出家电生产、产销率、出口及总行业收入/利润，足以形成供给和行业利润池的并列背景。 | 企业/品牌份额、价格、成本、库存所有权、渠道交易点和同产品竞争比较。 |

因此：若 Pack 合同只要求“需求/供给/竞争三类中至少两类”，上述两份发布物是最小文档集；
若需要年度供给变化锚点，再加入 2017 年统计公报。三份都不形成竞争结论，`competition`
driver 仅指行业整体利润池环境，不能被重命名为品牌竞争力。

## 物化、ledger 与 Pack 准入所需步骤

以下是下一位获取者应完成的最小、可复核操作；本审计**没有**执行这些写入或下载操作。

1. 为目标 Pack 选定与其 `IndustryLearningBlock` 一致的 `industry_id`。若接入已有全国多品类家电块，应使用其现行 `INDUSTRY:CN:APPLIANCE:MULTI_CATEGORY` 身份；不能借用水泥 package 的 identity。
2. 新建一份 `official-industry-context-catalog.v1`，逐条登记上表的 `source_id`、官方 HTTPS URL、严格的 `published_at`、`data_as_of`、`official_host`、`ORIGINAL_HTML`、相对 `package_path`、coverage IDs、`CONTEXT_ONLY` policy、允许与禁止推断。建议将 2018 包放在新的、家电专属目录，例如 `docs/development/research/industry_learning_blocks/CN_APPLIANCE_2018_OFFICIAL_CONTEXT/`；此路径仅为建议，尚未创建。
3. 以 `scripts/industry_context_acquisition.py validate` 校验 catalog 后，调用其 `materialize`，把每个**原始官方 HTML 响应**写至该 package 根目录下的明确路径（例如 `official_context_raw/nbs/2017_statistical_bulletin.html`、`official_context_raw/miit/2018q1_q3_appliance_running.html`、`official_context_raw/nbs/2018m11_retail.html`），并生成 `official-industry-context-source-package.v1`。不得用今天的数据库数值、截屏、搜索摘要或发行人年报替代 response。
4. 只有 source package 为 `RAW_COMPLETE_PENDING_OBSERVATION_REVIEW`、每个条目为 `MATERIALIZED` 或 `ALREADY_MATERIALIZED`、且 package 内 raw 文件非空时，才创建 observation ledger。每一条 observation 需有 `driver_type`、指标定义、期间、原文值、经济解释、`profit_pool_effect`、`permitted_inference`、`prohibited_inference` 和指向 source ID 的正文/table locator。
5. 以 `validate-observations` 得到 `REVIEWABLE_CONTEXT_ONLY` 后，才把 ledger 作为 `OFFICIAL_INDUSTRY_OBSERVATION` 写入 Pack source list。Pack 会再次验证 source package 的本地路径、industry identity 和 cutoff；任一失败均保持缺口，不得手工标为 `TRAINING_READY`。

## 固定的禁止推断与经济影响

这些来源弥补的是“全国环境完全缺席”的局部问题，不是品牌竞争数据。即使三份来源全部
物化，以下结论仍必须保持 `UNKNOWN` 或由公司/获得许可的同口径行业资料另行建立：

- 任一公司的销量、收入、毛利、现金、库存、产能、价格实现或市场份额；
- 空调、冰洗等单品的终端 sell-out、ASP、线上/线下份额和渠道价格战；
- 以产销率、生产或出口与零售额的差额推导补库/去库，或推导经销商库存归属；
- 从行业收入/利润的同比变化推导公司竞争优势、normal owner cash、估值、价格、回报或投资行动；
- 将国家统计局广义“家用电器和音像器材类”零售额与工信部家电生产、出口或各公司会计口径相除、拼接或当作因果归因。

经济上，这意味着 Pack 在物化前应把行业外部观察标为缺失；物化后最多能把“公司的变化
是否发生在广义需求/供给/行业利润池变化中”变成待验证的背景条件。若核心问题是品牌、
渠道或价格带竞争，最强替代解释仍是共同的品类周期、出口和渠道迁移，需另取同定义品牌 ×
渠道 × 量/额/价格带的资料；上述官方宏观观察不能裁决该问题。
