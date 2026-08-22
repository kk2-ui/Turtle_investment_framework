# 中国家电官方行业环境包：PIT 设计

状态：`OFFICIAL_PILOT_PRE_REGISTERED / NOT_MATERIALIZED / ASSOCIATION_SUPPLEMENT_MATERIALIZED / CONTEXT_ONLY`  
用途：为家电公司研究提供可冻结的外部环境变量；不生成品牌份额、公司销量、ASP、价格战结论、估值输入或独立参考类样本。

## 允许回答与禁止替代

这个包应覆盖 2020–2025 的生产、广义零售、价格环境下限、出口、以旧换新、住房/工程和整体渠道迁移。每条序列均须保存原始当期发布物及其发布日期，不能用统计数据库的当前修订值回填旧时点。

| 主题 | 一手/官方来源与可冻结字段 | 正确用途 | 不可推断 |
|---|---|---|---|
| 空调供给 | 国家统计局规模以上工业“房间空气调节器产量”：当月/累计/同比；工信部消费品工业按月/年归档。 | 供给、产能和出口/库存节奏的外部背景。 | 不能当国内 sell-out、需求或品牌份额。 |
| 广义家电零售与线上化 | 国家统计局限额以上“家用电器和音像器材类”零售额，以及实物商品网上零售额。 | 消费环境、广义渠道迁移。 | 不是空调台数、空调 ASP 或品牌/线上份额。 |
| 价格环境下限 | 国家统计局 CPI“家用器具”；可补家用电力器具制造 PPI。 | 观察宽口径终端/制造价格方向。 | 不等于空调 ASP、促销深度、返利或公司价格实现。 |
| 出口 | 海关总署月度主要出口商品量值及可查询的 HS 8415 数据。 | 外销需求、目的地和量值近似。 | HS 8415 非纯家用分体空调；量值单价不能当国内 ASP 或格力单价。 |
| 以旧换新 | 商务部/发改委政策文件与截至某日的购买人数、件数、带动销售额和高能效占比。 | 政策状态、覆盖强度和时点变化。 | 不是全市场需求；2024 八大类与 2025 十二类不能直接做同比；通常没有空调品牌/渠道拆分。 |
| 房地产与工程 | 国家统计局房地产投资、开工/施工/竣工、住宅销售；建筑业产值/施工面积。 | 住宅交付和工程 HVAC 的宽口径领先/同步变量。 | 不能把平方米机械换算为空调安装、更新需求或品牌订单。 |
| 耐用品存量 | 国家统计局住户调查每百户空调拥有量，年度。 | 更新/渗透背景，且必须接受发布滞后。 | 无机龄、报废、房间数、地区气候、替换周期和品牌，不能推导更新量。 |

## 最小序列契约

每一个 observation/series 必须冻结：

```text
series_id / institution / indicator_definition / geography /
period_end / release_date / source_url / source_version /
value / unit / monthly_or_cumulative / revision_note /
PIT_usable_after / forbidden_inference
```

准入规则：

1. 只读取法定/官方发布物或官方统计查询导出的可保存原始响应；
2. `release_date` 必须早于目标 cutoff；同日只有日期、没有发布时间的，按既有日期精度规则拒绝；
3. 统计库的现值只可作为发现路径，实际 PIT 值必须回到当期的 HTML/PDF/下载响应；
4. 当月、累计、年初合并的 1–2 月、修订版本和全国/省级口径必须显式标记；
5. 不同序列只能在 `indicator_definition`、频率、范围和销售/生产边界可比时相连，否则只能并列为背景。

### 存量—流量核对边界

零售 sell-out、厂家 shipment/sell-in 与渠道 inventory 是三个不同对象。Lee、Padmanabhan 与 Whang 的[原始供应链研究](https://sloanreview.mit.edu/article/the-bullwhip-effect-in-supply-chains/)说明，终端销售、经销订单与上游订单的波动可以逐级放大；因此“行业出货高增长”不能自动等于终端需求强，也不能从零售与出货的简单差额断言某品牌正在去/补库存。

Turtle 只有在同一供应方 release 明示下列共同边界时才允许计算库存变化：产品、地域、渠道、品牌/行业分母、期间、流量交易点以及库存归属范围。每项核对还须保存供应方对三个指标的定义和 locator。少一项即标为 `NOT_RECONCILABLE`：各指标仅能作为并列背景，背离最多生成“需求信号可能被库存、补货、促销或订单节奏扭曲”的 `MECHANISM_DISCOVERY`。它不能生成格力需求、品牌份额、返利、经销库存、现金转换、估值或 H-A/H-B verdict。

当前协会刊物中 AVC 的冷年内销 shipment、全渠道 retail sell-out 与“冷年中期库存超过 5,000 万台”不具共同期间/库存范围/交易点定义，故为 `NOT_RECONCILABLE`；禁止从 1.02 亿台、8,059 万台和该库存下限反算补库或去库。未来 AVC/产业在线 release 也不会因来自同一行业而自动满足此条件。

## 明确的数据缺口

本包不能得到连续、全国且官方公开的：

- 空调内销台数与国内 sell-out；
- 国内 ASP、品牌份额、线上/线下品牌份额或价格战强度；
- 格力/同行的渠道返利、平台佣金、经销商库存与 sell-in 对 sell-out；
- 商用/中央空调项目订单、交付与回款的可比较品牌序列。

这些是 `DATA_COVERAGE + ACQUISITION_MODULE` 缺口。若格力判断依赖它们，正确输出是 `UNKNOWN + conservative_treatment`，不能用新闻摘要、研究机构二手摘要、当前数据库值或卖方报告叙事替代。

## 格力 V1 的最小官方 context pilot（尚未接入判断）

下列八条为截至 `2026-08-03T18:00:00+08:00` 已定位的当期官方发布物。它们是后续逐条下载原始响应、创建 `INDCTX:` identity 的最小 pilot；在原始响应与页/段定位写入 package 前，状态一律为 `MATERIALIZABLE_NOT_YET_REVIEWABLE`，不得成为格力事实或 bridge 的 `OBSERVED` input。

| 拟用 identity | 当期官方发布物（可得日） | 冻结值 | 只服务的背景问题 | 不能替代 |
|---|---|---|---|---|
| `INDCTX:NBS:AC_PRODUCTION:2020` | [国家统计局 2020 国民经济和社会发展统计公报](https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901004.html)（2021-02-28 09:30） | 规上房间空调产量 21,035.3 万台，同比 -3.8%。 | 公司变化是否处于行业生产收缩背景。 | 国内 sell-out、品牌/渠道份额、格力销量或 ASP。 |
| `INDCTX:NBS:AC_PRODUCTION:2024` | [国家统计局 2024 国民经济和社会发展统计公报](https://www.stats.gov.cn/sj/zxfb/202502/t20250228_1958817.html)（2025-02-28 09:30） | 26,598.4 万台，同比 +9.7%。 | 公司渠道/组合变化是否处于生产扩张背景。 | 同上。 |
| `INDCTX:NBS:AC_PRODUCTION:2025` | [国家统计局 2025 国民经济和社会发展统计公报](https://www.stats.gov.cn/sj/zxfbhjd/202602/t20260228_1962662.html)（2026-02-28 09:30） | 26,697.5 万台，同比 +0.7%。 | 产量近停滞是否构成广义背景。 | 0.7% 不是内销需求、价格压力或份额。 |
| `INDCTX:NDRC:TRADE_IN_POLICY:2024_H2` | [发改委、财政部 2024 加力支持以旧换新通知](https://www.ndrc.gov.cn/xwdt/ztzl/tddgmsbgxhxfpyjhx/gzdt/202407/t20240725_1392001.html)（2024-07-25；日精度保守可得日） | 空调属 8 类，二级及以上能效补贴 15%。 | 识别 2024H2 渠道/产品组合的政策断点。 | 格力补贴份额、空调销量、ASP 或利润。 |
| `INDCTX:NDRC:TRADE_IN_POLICY:2025` | [发改委、财政部 2025 加力扩围通知](https://www.ndrc.gov.cn/xwdt/ztzl/tddgmsbgxhxfpyjhx/gzdt/202501/t20250108_1395617.html)（2025-01-08） | 原 8 类延续；空调每人最多 3 件；二级/一级能效 15%/20%，单件上限 2,000 元。 | 识别 2025 政策与能效结构影响。 | 公司、渠道、价格带的实际受益。 |
| `INDCTX:NBS:RETAIL_AND_ONLINE:2025` | [国家统计局 2025 经济发展向新向优](https://www.stats.gov.cn/sj/zxfb/202601/t20260119_1962330.html)（2026-01-19 10:00） | 家电音像零售额 +11.0%；实物网上零售 +5.2%，占社零 26.1%。 | 格力收入下滑与广义消费/线上环境的背离是否值得进一步核查。 | 空调渠道份额、品牌份额或竞争强度。 |
| `INDCTX:NBS:PPI_DURABLE_CONSUMER_GOODS:2025` | 同上（2026-01-19 10:00） | 耐用消费品 PPI -3.3%。 | 要求对“毛利稳=价格权”提出反证要求。 | 空调 ASP、终端价格、促销或格力实现价格。 |
| `INDCTX:NBS:REAL_ESTATE:2025` | 同上（2026-01-19 10:00） | 房地产开发投资 -17.2%、新开工 -20.4%、竣工 -18.1%。 | 将工程/安装需求背景与纯线上渠道机制分开。 | 中央/房间空调需求、格力工程收入或竞争份额。 |

这批**官方** pilot 已在 `official_industry_context_catalog.json` 预注册为 6 个网页发布物及 1 个 2024 政策 PDF 附件；原始响应的 materialization manifest 为 `official_industry_context_manifest.json`。8 条对应观察及其页/段定位存于 `official_industry_context_observations.json`，并已由同一模块验证为 `REVIEWABLE_CONTEXT_ONLY`。这不是“公司事实已验证”：它只意味着每条外部背景可回读，且受 `CONTEXT_ONLY` 禁止推断边界约束。当前已物化的下节协会刊物补充也同样是 `CONTEXT_ONLY`。因此这些材料可以排除把宏观生产、政策或房地产变化遗漏掉的叙事，却不能在 H-A/H-B 之间提供可判别的公司竞争证据。若下一步缺少同口径全渠道、量价费用和调整后现金，正式竞争层应保持 `UNKNOWN`；增加更多宏观项目不会改变这一状态。

## 已物化的协会一手行业量价/库存补充（仍非公司证据）

政府统计无法给出渠道、价格带和库存的联合背景，但协会刊物中存在可审计的带原始归因页面。已将[中国家用电器协会《电器》2025 年第 9 期](https://www.cheaa.org/upload/file/20250928/6389465323530752764793788.pdf)的原 PDF 物化为格力候选目录下的 `industry_context_sources/CHEAA_ELECTRIC_APPLIANCE_2025_09.pdf`，并记录为 [context manifest](../../../output/research/gree_v1_candidate_20260803/industry_context_manifest.json)。封面载明 `2025-09-08` 出版；PDF 第 27–28 页（印刷页 25–26）为奥维云网（AVC）署名的 2025 冷年（2024-08 至 2025-07）材料。

- AVC PSI：内销出货 1.02 亿台、同比 +8.7%，冷年中期行业总库存超过 5,000 万台且渠道库存占比较大；
- AVC 推总：全渠道零售量 8,059 万台（+17.6%）、零售额 2,572 亿元（+17.1%），线上/线下零售额为 1,320.8/1,251.6 亿元；
- 线上主销 1.5HP 挂机均价从 2024Q4 的 2,536 元降至 2025Q2 的 2,101 元（-17.2%），2,200 元以下价格段零售额份额升至 35.2%。

该材料的来源层级是“行业协会刊物中明确归因于 AVC 的推总/PSI 数据”，不是政府官方统计，也不是格力自身事实。冷年、自然年、出货和零售口径不得互相相除或拼接。它只允许作为 H-A/H-B 的 `CONTEXT_ONLY` 反证：行业线上价格/库存压力存在，所以格力单期毛利稳定不能排除组合或渠道机制；反过来，行业零售增长也不能直接推出格力失份额。它仍不能提供格力线下/全渠道品牌份额、品牌 ASP、返利或经销库存，因此不能选择 H-A/H-B、进入估值、FJ outcome、动作或基准率。

## 与格力机制设计的接口

它可为[格力渠道对立机制](GREE_V1_RIVAL_HYPOTHESIS_DESIGN.md)提供背景信号：供给、广义零售、补贴、出口、住房/工程和整体线上化。它不能裁决 H-A/H-B，因为两者的分界需要同口径公司—行业渠道份额、量价、返利/费用和调整后现金。

每条被格力 `COMPETITION_DEMAND` driver 使用的外部观察只可作为范围受限的 `comparison_evidence` / `QUALITATIVE_GUARDRAIL`；不得直接成为格力收入、毛利、owner cash、终值、概率或投资行动的数值输入。

## 预注册来源入口

- [国家统计局国家数据：主要工业产品产量](https://data.stats.gov.cn/easyquery.htm)
- [国家统计局：房间空气调节器产量指标说明](https://www.stats.gov.cn/zs/tjws/jbtjzswd/tjzb/202503/t20250321_1959112.html)
- [工信部：2024 年家电行业生产情况](https://www.miit.gov.cn/gxsj/tjfx/xfpgy/jd/art/2025/art_0053121a1a5c43d5a3adc1f166d0a301.html)
- [国家统计局：社会消费品零售总额发布入口](https://www.stats.gov.cn/szst/)
- [国家统计局：2024 年 12 月 CPI 原表](https://www.stats.gov.cn/xxgk/sjfb/zxfb2020/202501/t20250109_1958170.html)
- [海关总署：月度统计表](https://english.customs.gov.cn/statics/report/monthly.html)
- [海关总署：统计查询服务说明](https://online.customs.gov.cn/static/pages/guides/002029004002/002029004002.html)
- [发改委：2024 年以旧换新总结](https://www.ndrc.gov.cn/fggz/202502/t20250211_1396082.html)
- [商务部：2025 年以旧换新年度总结](https://www.mofcom.gov.cn/syxwfb/art/2026/art_74591d2d7e09478e8645c017fb747796.html)
- [商务部电商司：研究报告归档](https://dzswgf.mofcom.gov.cn/m_yjbg/page1.html)
- [国家统计局：房地产开发和销售情况发布入口](https://www.stats.gov.cn/szst/)

## 接纳条件

`REVIEWABLE` 的环境包必须有逐条原始发布物、可重读身份、精确的指标定义和不可推断边界。它即使通过，也始终是 `CONTEXT_ONLY_ZERO_SAMPLE`：不进入 `base_rate_case`、不创建 episode、不增加独立样本，也不允许替代正式的同行竞争证据包。
