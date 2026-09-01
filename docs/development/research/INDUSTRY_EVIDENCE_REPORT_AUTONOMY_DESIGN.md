# 行业证据到报告自主性的实现设计

## 目标

行业经验不替代公司研究，也不直接产生估值、买入价或行动。它的产品职责是：在公司首稿
之前，把行业判断转成可核验的外部取证任务；把实际取得的静态来源绑定到该任务；再要求
任何进入报告的行业观察都同时带有目标公司的一手传导证据。

这解决的是自动报告当前的两处窄点：行业判断只停留在年报内部，和过度保守的行动结论
没有可追问的外部经营证据链。它不预设行业材料一定会提高结论，也不把行业总量升级为
公司销量、利润、现金或价值。

## 已有底座与复用边界

| 需要 | 复用的既有模块 | 本次新增的最小接口 |
| --- | --- | --- |
| 政府统计、政策和监管原文 | `industry_context_acquisition.py` | 将已物化的 `CONTEXT_ONLY` 来源绑定到某个 agenda 观察；仍不能成为公司事实。 |
| 竞争者、客户、供应商的官方披露 | `phase10_acquisition.py` | 复用完整 inventory、PIT admission、原始文件和 reader copy；不从当前网页补历史材料。 |
| 行业学习转成研究动作 | `industry_experience_acquisition.py` | 保持原来的 role-bound plan 和 `UNKNOWN` 回执。 |
| 进入报告 | 新的 source binding，后续的 report admission | 只有冻结来源、观察和目标公司一手传导证据三者闭合，才给报告消费者。 |

`daily_stock_analysis` 是有价值的产品参考：它把多个数据 provider 和定时任务放在一个
可替换的框架中。但其动态行情/新闻搜索/外部模型运行方式不是历史静态、截止日可重放的
研究证据链。本项目不引入该项目代码或其 API 依赖，只借鉴“provider adapter、失败可见、
定时刷新不改变已冻结报告”的接口原则。

## 证据流

```text
IndustryUnderwritingContext
       │
       ▼
role-bound acquisition plan ──► existing static source packages
       │                              │
       └──── receipt observation ◄────┘
                       │
                       ▼
      IndustryEvidenceSourceBinding (new, report-local)
                       │
                       ├── target-company primary evidence + Episode
                       ▼
          report-admitted industry observation (later step)
```

一个来源无法物化、角色不匹配或发布时间晚于 cutoff 时，不能由另一个当前网页替换；它留在
`PUBLIC_INFO_UNAVAILABLE` 或 `UNKNOWN`，且不生成 Episode/报告候选。来源绑定只验证来源
身份、时间、任务角色和本地 reader/raw 存在；不判断其经济解释正确与否。

## 非目标

- 不建立第三套下载器、行情库或新闻抓取器；
- 不接入 Anthropic、OpenAI、DeepSeek 或其他外部模型 API；
- 不从行业证据直接输出 owner cash、估值参数、价格或投资动作；
- 不以样本替换或事后结果制造训练正效用。

## 已冻结的效用验证与本阶段使用方式

本阶段不重跑或事后改写已经完成的 blind experiment，而是把其可迁移的边界变成报告运行时
可执行的证据门：

- Course 2C 的祁连山未见公司 holdout 已完成公平双臂、匿名结果前审阅和官方结果反馈。它的
  正效用来自把持续经营、控制/并表边界、项目生命周期和资本责任分别接入下游处理；行业主
  路径本身为 `NO_MATERIAL_DIFFERENCE`。因此这里不把行业 pack 当作自动行业预测器。
- 四川双马报告自治 2×2 已完成同 cutoff 的 baseline / industry-only / expert-only / combined
  对照与封存结果结算。行业输入的独立增量为 `INCONCLUSIVE_DATA`；它在专家错误放宽现金边界
  的条件下帮助保留了 `UNRESOLVED`，但这仍不是普适的行业洞见证明。

二者共同决定本实现的评估原则：行业层应提高“主动找到并闭合哪条传导链”的能力；只有未来
多个未见公司、连续可结算的 pre-outcome 差异，才可把它升级为行业判断的可迁移效用。

## 验收标准

1. 每个已接受的外部观察精确映射到已物化的官方静态来源，且 URL、发布日期和 cutoff
   边界一致。
2. 同一来源可服务多个任务，但每一个观察必须有独立 task 绑定；来源不能跨角色伪装。
3. 缺少 raw/reader、来源 package 不完整、观察来源 URL 不一致、或缺少绑定均使报告准入
   不可用，而不是默认为已验证。
4. 历史的 HK02669 pilot 保留为“receipt 可复审、但 source package 未绑定”的诊断样本；
   不倒改成已可写入报告。
