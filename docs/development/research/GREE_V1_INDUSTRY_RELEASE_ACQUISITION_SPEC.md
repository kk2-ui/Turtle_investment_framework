# 格力 V1：独立行业 release 最小交付单

状态：`READY_TO_REQUEST / NO_RELEASE_ACQUIRED`  
适用 cutoff：`2026-08-03T18:00:00+08:00`  
用途：只为 `COMPANY_JUDGMENT_ONLY` 的 H-A/H-B 竞争和单位经济 FJ 提供可结算行业观察；不形成公司事实、normal owner cash、估值、回报或动作。

## 要解决的判断

格力 2023–25 的线上零售额份额下降、2025 内销收入走弱而消费电器毛利未塌陷，同时符合两条机制：

- **H-A**：低价线上让位，但线下/全渠道/较高价格带的相对位置及利润池仍稳；
- **H-B**：线上弱势扩展为全渠道的量、价或贡献恶化，毛利暂由组合或费用列报掩盖。

因此需要同定义的品牌×渠道×量/额×价格带 retail 轨，以及品牌×出货/库存 shipment 轨，才能**结算**竞争 FJ。单一线上份额、全行业总量、年报转引、新闻摘录或当前数据库回填均不足以判别。根因是 `DATA_COVERAGE + ACQUISITION_MODULE + REASONING`；若混同零售和出货，会材料性误判竞争持续期、normal owner cash 与永久损失。

数据缺口或供应商误差是研究常态，不是暂停理由。没有 P0 release 时可维护一个 `TENTATIVE_WORKING_PATH`：它只记录 H-A/H-B 各自还需解释什么、下一项要取什么证、以及随后公司收入/费用/营运资本应以何种顺序分叉；它没有中心路径、概率、估值、动作或结算胜负。P0 是把该工作路径升级为可冻结、可结算公司判断的资料，不是“没有它就不研究”的前提。

## 优先数据交付

| 优先级 | 供应方候选与官方能力证据 | 请求的原始历史 export | 允许解决的问题 | 不允许的推断 |
|---|---|---|---|---|
| P0 | [奥维云网家电零售数据产品](https://www.avc-mr.com/product/content?type=data) 明示覆盖线上、线下、抖音和下沉等渠道，并可按品牌、价格、产品属性、渠道、区域和竞品比较。 | 家用空调的**零售 sell-out**，按月（至少 2023-01 至 cutoff 前最后可得月）、品牌/品牌组、渠道、产品类型、冷量/匹数和 provider 定义的价格带；每行销量、销额、ASP、行业分母、品牌映射和渠道覆盖。交付对应的 release/version、历史取得/发布时间、data-as-of、query 参数、字段字典和修订说明。若同时交付库存或 shipment，必须另给共同 product/region/channel/brand/period/transaction-point/inventory-ownership boundary 与定义 locator；否则这些流量不能相减。 | H-A/H-B 的全渠道/线下/价格带相对位置、量价方向及其早期 FJ。 | 返利、经销库存、回款、公司收入确认、格力 ASP 或公司现金。 |
| P0 | [产业在线《中国家用空调行业产销月度研究报告》](https://www.chinaiol.com/Report/202005/9_797.html) 的官方目录明确列有企业产销存、品牌按内销量格局、重点企业（含格力）及其内外销对比；报告为按月提供的 Excel。 | 同期家用空调**出货/生产/库存** export，按月、企业或品牌、总量/内销/出口/库存；交付 report/release ID、版本、发布时间、data-as-of、查询范围、字段定义、企业/品牌映射和修订策略。必须保存供应方对“内销”的交易点定义；若要将出货、零售和库存做一致性核对，还必须明确共同 product/region/channel/brand/period/transaction-point/inventory-ownership boundary 及三个定义 locator。 | H-B 的早期出货/库存方向，与 P0 retail 形成动态交叉验证；公司披露任务的触发器。 | 自动标作 sell-in；零售 sell-out、终端份额、公司收入、经销库存或 owner cash。 |
| P1 | 产业在线公开说明其 `中国家用空调行业C端细分品牌季度报告` 在内销出货基础上增加细分品牌、OEM/OBM 拆分；公开文章亦仅为产品能力提示。 | 如可得，按季度的细分品牌、价格带和 OEM/OBM 历史 export，以及相同 release/query/字段定义。 | 检查低价带扩张是否改变品牌/子品牌相对位置；为 H-A/H-B 提供补充 shipment 信号。 | 代替 AVC retail 轨或用细分品牌和公司合并口径直接计算全渠道零售份额。 |

产业在线另有公开的[《中国家用空调行业生产计划及规模预测月度研究报告》](https://www.chinaiol.com/Report/202005/9_875.html)产品页，明确其为月度 Excel，并列出行业/品牌库存推算、格力等企业产销、生产计划及预测吻合追踪。这使 P0 的库存/企业轨请求可精确指向两类历史产品（`产销月度` 与 `生产计划及规模预测月度`），而非笼统索要新闻观点；接收时仍必须取得**当时版本的原始 Excel、release/query 身份、指标定义和修订政策**。该目录页本身既非历史 export，也没有可锁定的版本、品牌映射或交易点定义，故只用于收窄请求，不能直接进入 source package 或与 AVC 零售轨核对。

P0 的两条轨必须并行取得，才可能把竞争机制提升为可结算结论；没有 AVC retail 轨时，产业在线只可产生 `SHIPMENT_SEMANTICS_UNRESOLVED` 或供应方定义后的 shipment/sell-in 信号，不能裁决 H-A/H-B，但仍可作为要求公司后续披露检查的方向传感器。

### 可直接发送的 P0 请求正文（草稿，未发送）

**给 AVC：**

> 为一项截至 `2026-08-03T18:00:00+08:00` 的中国家用空调竞争研究，请提供在该日期前已发布的、可保留历史版本的月度零售 sell-out 导出。范围为 2023-01 至该日可得的最后一个月，字段需包含品牌/品牌组、线上/线下及可获得的新渠道、产品类型、冷量/匹数、您定义的价格带、地区、销量、销额、ASP、行业分母与品牌映射。请同时提供每个 release 的发布时点、data-as-of、version/revision ID、查询参数、字段字典及 sell-out 定义。研究只将该文件用于品牌×渠道×价格带的经营机制检验；不会要求或使用账户、Cookie、数据库连接，也不会把零售导出当作公司会计收入、现金或投资建议。

**给产业在线：**

> 为同一日期边界的中国家用空调竞争研究，请提供 `中国家用空调行业产销月度研究报告` 及（如库存/企业轨在其中单列）`中国家用空调行业生产计划及规模预测月度研究报告` 在 2023-01 至该日可得最后月份的**历史原始 Excel**。字段需覆盖企业或品牌、生产、内销、出口、库存及定义；请随文件给出 report/release ID、发布时点、data-as-of、version/revision、查询范围、品牌映射和修订政策。请特别说明“内销”位于何种交易点（shipment、sell-in 或其他），以及库存的所有权与覆盖边界。该数据只用于与零售轨并列地判断订单/库存机制，未经同一 release 的共同边界不会与零售数据相减或被当成终端需求、公司收入、渠道库存或 owner cash。

接收方只需交付许可允许保存的原始 export 与定义页；Turtle 接收后按本文件的 source contract、历史版本和同口径验收处理。任何仅有截图、新闻链接、当前网页摘要、没有 release/query/version 身份的回复都保留为 `MECHANISM_DISCOVERY_ONLY`，不会进入 CJO 结算。

### 已发现、但尚不能准入的公开 AVC 线索

[奥维云网 2025-08-15 的公开文章](https://m.cheaa.com/n_detail/w_648808.html)称其“2025 年 7 月全渠道（涵盖线上与线下）空调销售数据”中，格力市场占有率为 17%，同比下降 2 个百分点。这说明 provider 确实能形成品牌×全渠道的查询结果，因而可把 P0 请求进一步收敛为该数据背后的历史 release/查询，而不是笼统索要“行业观点”。

但该网页没有说明份额是销量还是销额，也没有原始 export、指标/交易点定义、release/version、data-as-of、revision、query 参数、品牌/子品牌映射、分母或可复算的月度面板。故它只能标为 `MECHANISM_DISCOVERY_ONLY`：提示 H-B 值得用同口径轨道检验，却不能作为 `LICENSED_INDUSTRY_DATA`、当前格力公司事实、H-A/H-B 结论、前瞻判断结算或参考类样本。若以后取得对应 release，但方法/误差边界仍不充分，只能标为 `DIRECTIONAL_SENSOR_ONLY`；若冻结了同一 provider 的范围和 mapping，最多升级为 `WITHIN_PROVIDER_RELATIVE_CHANGE`。尤其不得把其 17% 与格力年报中线上零售**额**份额 24.31% 相比，也不得将单月同比变动扩展为长期全渠道趋势。

### AVC retail 到位后的描述性状态分解

只有 P0 AVC 同一 release/query 的完整 `RETAIL_SELL_OUT` 面板到位、其测量 profile 至少允许 `WITHIN_PROVIDER_RELATIVE_CHANGE` 后，才运行 `scripts/industry_retail_state_decomposition.py`。输入锁定两个预注册期间，并要求每个 `channel × product_type × capacity_band × price_band × region`（实际采用的维度可为其子集）category cell 在两期都存在、品牌组与行业分母映射不变。模块以对称 Shapley 恒等式分别拆分格力零售量和零售额的变动：行业规模、category mix、以及格内格力份额；它消除选择先变规模还是先变份额造成的记账顺序差异，不能消除供应商覆盖或映射误差。

输出只能作为 `FJ:GREE:competitive_position` 的竞争诊断：若线上/低价带变弱而线下或较高价格带的格内份额稳定，可支持继续检验 H-A；若同口径格内份额在更广泛 channel/price-band 同步变弱，可支持继续检验 H-B。两者都不是因果裁决，必须同已冻结的其他 FJ 和公司官方披露共同结算。禁止把这一分解用于 ChinaIOL shipment、缺失 cell 回填、公司收入确认、返利/渠道库存、owner cash、资本配置、估值、股价、回报或投资动作；无真实授权 release 时不得生成数值或改写当前 `UNDISCRIMINATED`。

每个拟进入该 FJ 的份额、零售量、零售额和 ASP 都须从同一 release 的 `market × Gree` cells 共同派生，并满足 `Gree units/value ≤ market units/value`、`share = Gree ÷ market` 与 `ASP = value ÷ units` 的层级恒等式；不得把另一张份额图、行业 shipment 或公司会计收入拼接进来。恒等式只保证测量对象一致，不构成渠道竞争、收入确认或 owner-cash 的因果证明。

在读入 release 前，还须冻结有限的 `PANEL_SPECIFICATION` 视图清单，例如全渠道、线上/线下、可由供应方字典稳定定义的价格带和产品/冷量切分，以及品牌组合映射；每个视图必须是同一 source contract 下理论合理、可复算且不冗余的切分。报告逐视图呈现状态分解，明确“方向稳定”或“由哪一口径边界改变”，绝不挑一个最有利的分组，也不以小样本做 joint inference、综合分数或机制概率。缺 cell 或映射变化的视图必须剔除并说明，不能补齐。

## 历史版本与交付纪律

1. 每条 export 必须保留在当时已发布的版本。对 2026-08-03 cutoff，不能使用该日以后才发布的 2026 年 7 月数据；请求方须随文件给出每个 release 的 `published_at`、`data_as_of`、`revision_id` 和 original/revision 身份。
2. 每个数据集按 [独立行业数据 PIT 来源契约](INDEPENDENT_INDUSTRY_DATA_SOURCE_CONTRACT.md) 建立 `LICENSED_INDUSTRY_DATA` source record：`official=false`、provider/dataset/release/query/metric/scope/measurement profile contract 完整；不得将授权 export 放入公司官方事实账本，也不得把历史版本身份误写成测量准确性。
3. AVC 轨必须为 `RETAIL_SELL_OUT`。产业在线轨在供应方交易点定义随 release 保存前，保持 `SHIPMENT_SEMANTICS_UNRESOLVED`；两轨不得相除、拼接或以一方补另一方缺字段。
4. 交付原文件及其字典/定义页，不交账号、Cookie、数据库连接或截图。系统只读取已放入 source package 的文件，绝不登录或拉取供应方页面。
5. 格力、美的、海尔、奥克斯、小米、TCL、海信及其他分母内品牌的集团/子品牌映射必须写明，不能把 `GREE`、`晶弘`、OEM 或企业口径静默合并。
6. 出货、零售与库存只有共同 `stock_flow_boundary` 才可核对：必须是同一 provider release、共同 product/region/channel/brand/denominator/period/transaction point/inventory ownership，且三个定义均有保存的 locator。没有它们，结果一律 `NOT_RECONCILABLE`，可用于提出取证任务但不得由差额反推补库、去库、格力需求、份额、现金或 H-A/H-B。

## 接收后先做什么

先用 `enumerate-industry → compose-industry → download-package` 将 release 与既有 41 源公司公告包合成；再冻结以下同口径、无价格 FJ，而非先写中心路径：

| FJ | H-A 预期 | H-B 预期 | 最低结算要求 |
|---|---|---|---|
| `FJ:GREE:competitive_position` | 线上可弱，但线下/全渠道或较高价格带的格力相对位置稳定。 | 弱势扩展至同口径全渠道/线下/价格带。 | AVC 同一 metric/unit/region/channel/denominator 的 t0/t1 面板。 |
| `FJ:GREE:revenue_margin_transmission` | 较高价格带/组合稳定，且费用、官方公司收入/毛利没有共同恶化。 | 出货和/或零售相对位置走弱，随后公司费用、收入或利润传导恶化。 | AVC 或 ChinaIOL 的明确定义行业观察与公司同期间披露分层比较；不可把 shipment 与公司收入直接相除。 |
| `FJ:GREE:normalized_cash_conversion` | 无持续渠道资金占用迹象。 | 渠道压力最终通过官方应收、存货、合同负债及调整后 OCF 变现。 | **只**由官方公司披露及已闭合 adjustment bridge 结算；行业 release 只能触发取证任务。 |

接纳条件是：合成 manifest `REVIEWABLE`、本地 source package 完整、`measurement_profile` 允许该 FJ 所声称的推断、FDBMON 与 FJ 的 metric/unit/basis/period/window 一致、独立审阅通过，且尚未到期 FJ 保持 `PARTIAL`。任一条件缺失，正式 CJO 结论只能为 `UNKNOWN / UNDISCRIMINATED`；但研究工作路径仍继续保留为明确标注的暂定机制和下一项取证任务。
