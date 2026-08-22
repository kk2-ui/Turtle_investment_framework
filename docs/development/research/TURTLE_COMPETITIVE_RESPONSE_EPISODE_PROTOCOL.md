# Turtle 竞争回应机制实验协议

状态：`METHOD_PROTOCOL / COMPANY_AND_INDUSTRY_FIRST / NO_PRICE_PROXY`

关联：[判断力飞轮](TURTLE_JUDGMENT_FLYWHEEL.md)、[研究操作流程](TURTLE_RESEARCH_OPERATING_PROTOCOL.md)、[判断验证与回测协议](TURTLE_JUDGMENT_VALIDATION_PROTOCOL.md)。

## 1. 要解决的问题

行业分析不能止于“行业竞争激烈”“公司推出了新产品”或“份额发生变化”。真正有判断价值的问题是：**在一个明确竞争 arena 中，一方已发生的行动会不会引出对手有针对性的回应；这种回应的对象、方式与时滞会如何改变后续的量、价、费用或现金传导？**

这是一种可选的机制实验，不是一张行业综述、竞争强度评分或市场份额预测。没有能观察对手回应的一手或持牌来源时，正确输出是 `NO_ELIGIBLE_ECONOMIC_FJ` 或 `UNKNOWN`。

## 2. 冻结单位：行动—回应—经营后果

每个实验仍复用现有 `rival_hypothesis_pair`、`causal_trace`、`EARLY_MECHANISM` 与 `TERMINAL_OPERATING` FJ；不新建平行 ledger。冻结前须写清以下对象：

| 对象 | 必填内容 | 不能替代它的东西 |
|---|---|---|
| 竞争 arena | 发起方、潜在回应方、产品/渠道/地区、客户群和时点。 | 宽泛的“行业”或全公司收入。 |
| 已发生行动 | 事项、行动类型、真实生效/实施状态、日期、范围和一手来源。 | 管理层意向、新闻标题或事后效果。 |
| H-A/H-B | 同一行动下，对手的 awareness、motivation、capability 各为何不同，并怎样传到回应。 | “竞争加剧/缓和”的形容词。 |
| 早期回应 FJ | 预定义的回应对象、类别、最大时滞、0/1 或明确数量口径、允许来源和 `A_ONLY/B_ONLY` 区域。 | 宏观变化、普遍行业降价、对手评论。 |
| 终局 FJ | 与 arena 相同边界下的价格实现、服务/促销让渡、组合、营运资本或 owner-cash 后果。 | 总收入、股价或单期毛利。 |

## 3. 两条机制必须如何分叉

两方都要解释共同的行动事实，但须对回应过程给出不同的、可被推翻的预期。例如：

```text
H-A：发起方在关键接口具备互补资产/切换成本
     → 对手即使察觉也缺少动机或能力做同 arena 的有针对性回应
     → 预定义窗口内无合格回应，或仅出现范围更窄/时滞更长的回应
     → 租金留在发起方：冻结的价格实现、费用让渡或现金路径改善

H-B：该接口并不受保护，对手有充分动机和可动用能力
     → 预定义窗口内出现同 arena、同客户对象的有针对性回应
     → 促销、服务、渠道投入或产品行动使租金转移
     → 冻结的价格实现、费用让渡或现金路径恶化
```

“未观察到回应”只有在结果期来源覆盖了事先定义的回应载体且没有口径缺口时，才可被作为一个 outcome；来源不足永远是 `MISSING_OBSERVATION`，不是 H-A 获胜。

## 4. 写入现有冻结对象的映射

| 既有对象 | 竞争回应实验中的用途 |
|---|---|
| `common_fact_evidence_ids` | 已发生的发起方行动及 arena 边界。 |
| `critical_assumptions` | 每一方对 awareness、motivation、capability 的必要前提；不可读时为 `UNKNOWN`，不能支持被选路径。 |
| `causal_trace` | `行动 → 对手观察/激励/能力 → 有针对性回应 → 租金落点 → 经营结果` 的逐箭头状态；早期回应箭头以本 pair 的 `RHPSIG` 标为 `TESTABLE`。 |
| `EARLY_MECHANISM` FJ | 对手回应的对象/类别/时滞。事件型观察须冻结一个可检查的 0/1 或数量化定义、窗口、官方/持牌 source policy 与禁止替代。 |
| `TERMINAL_OPERATING` FJ | 同一 arena 的量价、让渡、营运资本或现金后果；不得以全公司利润或投资结果替代。 |
| `industry_architecture` | 若使用，仅说明哪一接口/互补资产/价值攫取节点使上述回应过程不同；必须链接该 pair 的早期 `INDUSTRY_STRUCTURE` FJ 和可检验箭头。 |

## 5. 结算与失败归因

结算严格按顺序进行：

1. 先结算发起方行动是否真实实施；行动发生只确认共同事实，永远不支持任一机制。
2. 再结算对手回应是否落在已定义 arena、类别和窗口内；不合格来源、范围漂移或宏观共同冲击只能是 `NOT_DIAGNOSTIC`。
3. 最后才结算同边界的经营后果。早期回应与终局不同向时保留 `MIXED` 并重开传导箭头；不能把较晚利润结果倒灌为“当时已有回应”。

常见失败要明确归因，而非讲成故事：行动未真正发生（事实边界）、回应数据不可得（采集）、范围/分类变化（测量）、两方都能解释回应（机制非诊断）、或共同冲击改变 arena（环境）。

## 6. 准入与停止

实验准入必须同时满足：

- 行动与 arena 在 cutoff 前可由一手资料定位；
- 双方对回应对象、类别或时滞有真正不同预测；
- 早期回应与终局经营后果各有预注册的来源/指标合同；
- 没有把“对手沉默”作为无来源观察的正面证据。

任何一项不满足就不立项；可留为行业架构问题或 `QUESTION_ONLY`。一次回应的命中/未命中只能更新这一行动链，不能推出行业永久竞争格局、公司总判断、概率校准或投资结论。

## 7. 方法依据

- Chen, Su & Tsai (2007), [Competitive Tension: The Awareness-Motivation-Capability Perspective](https://doi.org/10.5465/amj.2007.24162081)：竞争行动是否引发回应取决于察觉、动机和能力，而非“竞争”标签。
- Chen & Miller (2012), [Competitive Dynamics: Themes, Trends, and a Prospective Research Platform](https://doi.org/10.5465/19416520.2012.660762)：行动与回应的对象、类型和时滞是竞争动态的核心分析单位。
- Teece (1986), [Profiting from Technological Innovation](https://doi.org/10.1016/0048-7333(86)90027-2)：价值攫取取决于可占有性与互补资产，不能由产品创新或份额本身推出。
- Langley (1999), [Strategies for Theorizing from Process Data](https://doi.org/10.2307/259349)：机制应按过程与顺序检验，而不是把同一期间的相关指标拼成因果。

这些文献提供机制设计原则；它们不提供某家公司的竞争参数，也不授权把公开缺口填成对手行为。
