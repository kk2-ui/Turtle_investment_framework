# Turtle x Graham 迁移 - Claude 规划资料包

> **ARCHIVED / NON_CANONICAL：**迁移规划已完成并被现行估值路由与黄金报告契约吸收；本文不是当前Agent入口。

用途：给 Claude 做前期规划，不是直接改代码。这个包的目标是让 Claude 先理解整个 Turtle 框架、你的迁移目标、以及为什么这次改造不是“换一套说法”，而是“换一套判断引擎”。

## 先读什么

先读这份上下文包，再读后面的资料：

1. [turtle_graham_claude_context_pack.md](./turtle_graham_claude_context_pack.md)
2. [turtle_graham_project_brief.md](./turtle_graham_project_brief.md)
3. [turtle_graham_migration_blueprint.md](./turtle_graham_migration_blueprint.md)
4. [turtle_valuation_routing_and_investor_styles.md](./turtle_valuation_routing_and_investor_styles.md)
5. [Turtle_investment_framework/CLAUDE.md](/Users/xiami/workspace/analy/Turtle_investment_framework/CLAUDE.md:1)
6. [Turtle_investment_framework/strategies/turtle/references/factor_interface.md](/Users/xiami/workspace/analy/Turtle_investment_framework/strategies/turtle/references/factor_interface.md:1)
7. [Turtle_investment_framework/prompts/phase3_分析与报告.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/phase3_分析与报告.md:1)
8. [Turtle_investment_framework/prompts/references/factor1_资产质量与商业模式.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor1_资产质量与商业模式.md:1)
9. [Turtle_investment_framework/prompts/references/factor2_穿透回报率粗算.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor2_穿透回报率粗算.md:1)
10. [Turtle_investment_framework/prompts/references/factor3_穿透回报率精算.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor3_穿透回报率精算.md:1)
11. [Turtle_investment_framework/prompts/references/factor4_估值与安全边际.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor4_估值与安全边际.md:1)
12. [Turtle_investment_framework/templates/report_template_v12.md](/Users/xiami/workspace/analy/Turtle_investment_framework/templates/report_template_v12.md:1)
13. [Turtle_investment_framework/docs/value_investing_from_graham_to_buffett_notes.md](/Users/xiami/workspace/analy/Turtle_investment_framework/docs/value_investing_from_graham_to_buffett_notes.md:1)

## 目标

用《价值投资：从格雷厄姆到巴菲特》的方法重写 Turtle 的定性/定量/估值逻辑，但保留 GG 原版的计算严谨性。

更具体地说：

- 让框架先完成“生意分流”
- 让增长判断回到资本回报
- 让估值回到当前价格下的可计算回报
- 让风险回到永久损失与衰减
- 让报告输出继续保持工程化和可回溯
- 让 Claude 先理解“整体框架和目标”，再进入结构设计

## 你需要先看什么

按这个顺序读，别跳：

1. [turtle_graham_claude_context_pack.md](./turtle_graham_claude_context_pack.md)
2. [turtle_graham_project_brief.md](./turtle_graham_project_brief.md)
3. [turtle_graham_migration_blueprint.md](./turtle_graham_migration_blueprint.md)
4. [turtle_valuation_routing_and_investor_styles.md](./turtle_valuation_routing_and_investor_styles.md)
5. [Turtle_investment_framework/CLAUDE.md](/Users/xiami/workspace/analy/Turtle_investment_framework/CLAUDE.md:1)
6. [Turtle_investment_framework/strategies/turtle/references/factor_interface.md](/Users/xiami/workspace/analy/Turtle_investment_framework/strategies/turtle/references/factor_interface.md:1)
7. [Turtle_investment_framework/prompts/phase3_分析与报告.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/phase3_分析与报告.md:1)
8. [Turtle_investment_framework/prompts/references/factor1_资产质量与商业模式.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor1_资产质量与商业模式.md:1)
9. [Turtle_investment_framework/prompts/references/factor2_穿透回报率粗算.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor2_穿透回报率粗算.md:1)
10. [Turtle_investment_framework/prompts/references/factor3_穿透回报率精算.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor3_穿透回报率精算.md:1)
11. [Turtle_investment_framework/prompts/references/factor4_估值与安全边际.md](/Users/xiami/workspace/analy/Turtle_investment_framework/prompts/references/factor4_估值与安全边际.md:1)
12. [Turtle_investment_framework/templates/report_template_v12.md](/Users/xiami/workspace/analy/Turtle_investment_framework/templates/report_template_v12.md:1)
13. [Turtle_investment_framework/docs/value_investing_from_graham_to_buffett_notes.md](/Users/xiami/workspace/analy/Turtle_investment_framework/docs/value_investing_from_graham_to_buffett_notes.md:1)

## 书内迁移要点

- 先分流：资产价值 / EPV / 成长价值
- 再判断：增长是否创造价值
- 再识别：护城河是否真能长期保护回报
- 再折扣：衰减、治理、杠杆、价值陷阱
- 最后才是仓位

## 你应该先理解的框架现实

当前 Turtle 不是白纸，它已经有很强的工程结构：

- 数据采集和预处理已经比较完整
- 定性、定量、估值、报告是分层的
- GG 不是随便算出来的数字，而是一套有数据管线、有否决门、有校验规则的体系
- 现有问题不是“没有框架”，而是“框架的概念底座还不够书化、不够变量化”

所以这次迁移不是推倒重来，而是：

- 保留工程骨架
- 重写方法底座
- 重连变量关系
- 重新定义关键判断

## 严格约束

- 不要把书里的方法偷换回 Turtle 旧口径。
- 不要把概念写成口号，所有概念都必须落变量。
- 不要把变量写成模糊描述，所有变量都必须可计算。
- 不要把公式写成单点结论，必须包含输入、默认值、例外、否决门。
- 不要把资产价值和收益价值相加重复计算。
- 不要让 GPT 式“讲道理”替代 GG 式“算得清”。

## Claude 需要产出的东西

1. Turtle 改造总方案
2. 章节级/模块级映射表
3. 变量字典补全建议
4. 公式清单修订建议
5. prompt 重写顺序
6. 必须补的数据字段清单
7. 风险点清单
8. 最小可行改造版本（MVP）
9. 哪些地方不适合直接用书里的概念硬映射
10. 哪些内容应该先做成“规划建议”，不该立刻写成代码

## 优先关注的冲突

- 书里的“增长回报”与 Turtle 现有 `GG` 口径是否一致
- 书里的“经济特许权衰减”如何进入现有安全边际
- 书里的“价值创造因子”如何落到现有资本配置变量
- 书里的“好生意”如何映射到现有护城河评级
- 书里的“研究策略”如何压缩成可执行 prompt
- 书里的“资产价值 / EPV / 成长价值分流”如何嵌入现有因子1-4
- 中国市场的价值陷阱、治理风险、兑现能力如何进入框架而不变成空话
- 现有 `GG / DDM / 折价 / 仓位` 这些术语如何保留但重新定义

## 结果格式要求

Claude 最终输出时，必须按下面顺序写：

1. 迁移结论
2. 对我目标的理解
3. 结构设计
4. 变量与公式
5. 风险与缺口
6. 改造计划
7. 需要我确认的问题

## 额外要求

- 先给结论，再给结构
- 先讲你理解到的目标，再讲建议
- 如果有现有框架和书内思想冲突，直接指出，不要和稀泥
- 如果某个概念不能直接迁移，明确说“不能直接迁移”并解释原因
- 如果你认为应该先做 MVP，请明确 MVP 的边界
