# R-11 中国机制判断微演练：Baidu Q1 2023 变现结构分化

状态：`FROZEN_FOR_REVIEW / HISTORICAL_SELF_REPLAY / NO_PRIMARY / OUTCOME_UNREAD`

训练模板：[机制判断微演练](../../../../../templates/research_mechanism_micro_drill.md)。本卡使用 [P-60.2](../../TURTLE_RESEARCH_PREPARATION_ITERATION_LOG.md) 的事实切片纪律，并按照 [P-60.3](../../TURTLE_RESEARCH_PREPARATION_ITERATION_LOG.md) 在结果前锚定结果事件。它不形成百度的公司、估值、价格、回报或投资结论。

## 1｜训练边界

- drill ID：`R11-BIDU-2023Q1-MONETIZATION-MIX`。
- 核心训练域：`CHINA`；角色：`FOCAL / STANDALONE`；机制域为 `DEMAND_AND_MONETIZATION × online-ad / non-online revenue mix`。
- cutoff：`2023-08-20T23:59:59-04:00`。
- 第一遍原件：[Baidu Q1 2023 Form 6-K exhibit 99.1](https://www.sec.gov/Archives/edgar/data/1329099/000119312523145594/d472126dex991.htm)，2023-05-16 提交。
- 第一遍事实包 locator：该原件 `Baidu Core` 结果表与经营事实行中的 `Baidu Core revenues`、`online marketing revenue`、`non-online marketing revenue`、`Managed Page`。结构抽取不交付含 `primarily / mainly / due to / expect / guidance / believe / comment / said / announce / launch / because / attribute` 的说明文本。
- 事实包准备方式：`FROZEN_STRUCTURAL_EXTRACT / CONTEXT_SEPARATION_NOT_ASSURED`；本卡只能作 `HISTORICAL_SELF_REPLAY` 的流程练习。
- 结果事件合同（cutoff 前）：[Baidu 2023-08-02 board-meeting announcement](https://www.sec.gov/Archives/edgar/data/1329099/000119312523201108/d526118dex991.htm) 明示董事会于 2023-08-21 审议截至 2023-06-30 的季度及中期业绩，并将该 results announcement 上传至公司与 HKEX 网站。允许结果窗口为 `2023-08-21–2023-08-31`；发布者 `Baidu, Inc.`；结果事件 `Second Quarterly And Interim Results Announcement`；预期同口径标签 `Baidu Core online marketing revenue` 与 `Baidu Core non-online marketing revenue`。
- 已隔离、不得在冻结前读取：上述结果事件的正文、数字、解释、电话会、价格与回报。

## 2｜第一遍：事实层机制

**决定性问题**：Baidu Core 的 Q1 收入增长中，non-online marketing 的增速高于 online marketing；这是可持续的变现结构分化，还是小基数/单季组成波动而公司仍主要受广告周期决定？

**冻结事实**：Baidu Core 收入 RMB23.0bn、同比 +8%；其中 online marketing RMB16.6bn、同比 +6%，non-online marketing RMB6.4bn、同比 +11%；Managed Page 占 Baidu Core online-marketing 收入 49%。两机制均须解释“大头仍是广告、但非广告增长更快”的同一状态。

| 机制 | 状态 → driver → 中间变量 → 经营后果 | 最怕的观察 | 未来首先分叉的观察 |
|---|---|---|---|
| H-A：非广告变现扩张 | 产品/服务变现扩大 → non-online 增长持续快于广告 → Baidu Core 收入来源更分散。 | Q2 non-online 增速不高于 online marketing。 | Q2 `non-online marketing revenue YoY growth > online marketing revenue YoY growth`。 |
| H-B：广告周期仍主导 | non-online 的相对快增只是小基数/组合波动 → 广告周期重新决定增长 → 两者不再分化或广告更快。 | Q2 non-online 增速继续高于 online marketing。 | Q2 `non-online marketing revenue YoY growth <= online marketing revenue YoY growth`。 |

`NO_PRIMARY`：Q1 的相对增速与 Managed Page 渗透只显示当前结构，不足以让任一机制成为主路径；没有 cutoff 前、独立于公司解释的持续性证据。该保留不是弃权，而是防止“单季较快增长”被误写成业务结构已改变。

## 3｜冻结结果合同

- 主观察：Baidu Core Q2 2023 的 `online marketing revenue YoY growth` 与 `non-online marketing revenue YoY growth`，依同一结果表/同一口径的已报告数比较。
- H-A：`non-online growth > online-marketing growth`；H-B：`non-online growth <= online-marketing growth`。两区间非嵌套、无任意百分点阈值。
- 接受来源：第 1 节已登记 results event 的 Baidu/HKEX 官方结果公告；必须包含两个收入标签、当期/上年同期数或明示同比增速。
- 禁止替代：Baidu Core 总收入、整体收入、经营利润、AI 产品发布、Managed Page 后续渗透、搜索流量、价格、回报或电话会文字。
- 若标签定义/分部范围改变或两者任一未披露：`MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`；不得用总收入或第三方广告市场数据补算。

## 4｜第二遍待执行：解释攻击

冻结后才可读 Q1 原件中的管理层归因、AI/云产品叙事与展望。它们只能标为 H-A compatible、H-B compatible、共同或不具诊断性；不得改写第 2–3 节的机制、阈值、来源事件或 `NO_PRIMARY`。

## 5｜预先承诺的复盘动作

| 结果 | 本卡记录 | 下一张不同中国对象的改变 |
|---|---|---|
| `A_ONLY` | 只支持“相对增长分化延续”这个短窗箭头。 | 要求再找一个能区分增长质量/变现单位经济的前导信号，不能把收入份额当利润能力。 |
| `B_ONLY` | 只支持“相对分化没有延续”。 | 检查小基数、分部定义及广告周期是否应成为冻结前的明确 break。 |
| `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC` | 不裁决任一机制。 | 保留结果事件预告契约，改选披露连续性更高的对象。 |
