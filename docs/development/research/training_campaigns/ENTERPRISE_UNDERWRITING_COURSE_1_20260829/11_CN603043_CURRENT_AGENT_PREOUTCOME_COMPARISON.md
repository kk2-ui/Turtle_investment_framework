# 广州酒家：Current-Agent 第二次 A/B 的结果前比较

> 状态：`PREOUTCOME_EPISODES_FROZEN / OUTCOME_NOT_READ`
>
> 运行身份：`CURRENT_AGENT_SELF_RUN`
>
> 结论权限：`RESEARCH_TRAINING_ONLY_NO_PRICE_VALUATION_OR_INVESTMENT_AUTHORITY`

## 本次运行是什么

两份完整 `EnterpriseUnderwritingEpisode` 都由当前会话中的训练 Agent 依据冻结合同、同一份
截止日前官方源包生成，并经过正式合同绑定、Episode 验证和价格分离投影编译后持久化：

| Arm | Episode | 额外输入 | 完成状态 |
| --- | --- | --- | --- |
| Baseline | `blind/05_CN603043_second_ab/baseline/enterprise_underwriting_episode.json` | 无 | `TRAINING_EPISODE_COMPLETED` |
| Enhanced | `blind/05_CN603043_second_ab/enhanced/enterprise_underwriting_episode.json` | 课程的负反馈研究议程与推理修订 | `TRAINING_EPISODE_COMPLETED` |

两份 Episode 都只引用同一份广州酒家 cutoff 前 source package；Enhanced 没有把
`TRAINING_MEMORY` 写入公司事实 `evidence_trace` 或 `existing_object_refs`。

## 必须保留的可比性限制

当前 Agent 在开始本轮前已经阅读过首轮顺丰的负反馈和课程推理修订。因此它可以按 Baseline
合同不引用那两份材料，也能保持广州酒家结果封存；但不能诚实地声称自己在认知上完全不知道
该推理规则。这不是数据或公司证据污染，也不使广州酒家 Episode 无效；它只限制这一次比较的
方法结论：

> 本轮是对当前 Agent 的受约束自我训练与反馈，不是独立外部 Baseline/Enhanced 效用证明。

因而，本文件不创建 `TRANSFER_CANDIDATE`、`TRANSFER_VALIDATED` 或
`METHOD_VALIDATED`。若要取得独立方法证据，后续仍须由未接触课程反馈的运行身份在同样封存
的公司上复做。

## 结果前已经发生的研究行为变化

Enhanced 并没有凭空降低广州酒家的利润或 owner cash，也没有把增长资本风险偷换成维护资本。
它的材料变化是将同一份公司事实重排为三个不可互换的问题：

1. **成熟业务维护后现金**：维护资本没有拆分，因而只能条件化处理；未知不等于零或负值。
2. **全部长期资产支出后的当期现金**：FY2018 经营现金约 4.76 亿元、全部长期资产支出约
   2.99 亿元，约正 1.78 亿元只说明当年没有机械现金缺口。
3. **增长资本后续回报**：梅州、湘潭、渠道和速冻扩张只有在客户、单位经济与资本后现金
   共同出现后才构成改善。

这使 Enhanced 的主路线从“成熟合并盈利能力 + 总体现金交叉检验”收紧为“成熟月饼、餐饮和
已证实品牌食品经济 + 三条资本证据线”。它没有以没有证据的数字压低合并历史盈利；它把速冻
和异地扩张保留为具名 product–channel–base cohort 情景，并把“经销收入增长但经销商净减少”
改写成需要分辨单经销商效率、渠道集中或支持成本的研究问题。

这是一项有经济内容的预先变化，而非多写了一条 `UNKNOWN`。是否真的更好，要由封存后的
客户吸收、毛利/利用率、现金和资本回报反馈决定。

## 已冻结的判别标准

反馈优先回答以下问题，而不是奖励更悲观的文字：

- 成熟高毛利品牌经济与速冻/异地扩张是否真的走出不同的利润和现金路径？
- 经销和省外增长是否穿过库存、渠道成本、利用率及新基地资本形成经济吸收？
- 成熟维护后的 owner cash、全部资本支出后的现金、增长资本回报是否需要不同处理？
- 如果扩张成功，Enhanced 是否过度排除了它；如果扩张没有成功，Baseline 是否错误地把合并
  增长视作成熟经济的延伸？

结果材料、市场价格、回报、正式 CJO、估值和黄金报告在这两份 Episode 之后才可被读取；它们
在本次结果前比较中均未使用。
