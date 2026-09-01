# Claude 规划提示词

> **ARCHIVED / DO NOT RUN：**该规划Prompt已经完成历史使命，不得作为当前Agent任务或生成入口。

你要做的是前期规划，不是直接改代码。目标不是回答“怎么写一版 prompt”，而是先把整个 Turtle 的方法底座重新规划清楚。

## 先读什么

先读这份上下文，再开始回答：

- `docs/turtle_graham_claude_context_pack.md`
- `docs/turtle_graham_project_brief.md`
- `docs/turtle_graham_migration_blueprint.md`
- `docs/turtle_valuation_routing_and_investor_styles.md`
- `strategies/turtle/references/factor_interface.md`
- `prompts/phase3_分析与报告.md`
- `prompts/references/factor1_资产质量与商业模式.md`
- `prompts/references/factor2_穿透回报率粗算.md`
- `prompts/references/factor3_穿透回报率精算.md`
- `prompts/references/factor4_估值与安全边际.md`
- `templates/report_template_v12.md`
- `docs/value_investing_from_graham_to_buffett_notes.md`

## 任务

请基于我提供的资料，规划如何把 Turtle Investment Framework 用《价值投资：从格雷厄姆到巴菲特》的方法重构，同时保留 GG 原版的计算严谨性。

你需要先理解三件事：

1. 这不是简单的“加一层书摘”
2. 这不是把 GG 改名成别的东西
3. 这不是把估值写得更文学，而是把判断链条变得更可靠

## 资料

先读：
- `docs/turtle_graham_project_brief.md`
- `docs/turtle_graham_claude_handoff.md`
- `docs/turtle_graham_migration_blueprint.md`
- `strategies/turtle/references/factor_interface.md`
- `prompts/phase3_分析与报告.md`
- `prompts/references/factor1_资产质量与商业模式.md`
- `prompts/references/factor2_穿透回报率粗算.md`
- `prompts/references/factor3_穿透回报率精算.md`
- `prompts/references/factor4_估值与安全边际.md`
- `templates/report_template_v12.md`
- `docs/value_investing_from_graham_to_buffett_notes.md`

## 你要遵守的原则

- 只做规划，不改代码。
- 先结构，后措辞。
- 先变量，后公式。
- 先公式，后 prompt。
- 所有结论都必须能落到可计算字段。
- 保持 GG 式严谨：每一步都可回溯、可复算、可保守化。
- 保持工程现实感：优先考虑可落地的最小改造，而不是一次性理想设计。
- 把“书里的概念”和“现有框架里的字段”分开看，避免概念硬拼接。
- 先理解整体框架和用户目标，再给结构建议。

## 你要输出什么

请按以下结构输出：

### 1. 总体判断
- 这次迁移的核心目标是什么
- 最大风险是什么
- 最小可行版本应该长什么样
- 你理解到的用户真正痛点是什么
- 你认为必须保留的 Turtle 核心是什么
- 你认为必须改掉的 Turtle 核心是什么
- 你对“先分流，再估值”的理解是什么
- 你对“中国市场要单独加折价”的理解是什么

### 2. 结构设计
- Turtle 现有模块哪些保留
- 哪些要改名
- 哪些要拆分
- 哪些要合并
- 你建议的目标架构图（文字版即可）
- 现有因子1-4 与书内概念的对应关系
- 哪些概念应该前置，哪些应该后置
- 哪些地方应该做成“路由层”，哪些地方应该做成“计算层”
- 哪些地方应该做成“否决门”，哪些地方应该做成“评分项”

### 3. 变量层
- 缺哪些关键变量
- 哪些变量需要重新定义
- 哪些变量要分成 reported / normalized / conservative / adjusted
- 哪些变量可以直接沿用
- 哪些变量必须新增
- 哪些变量其实应该删除或弱化
- 哪些变量应当作为路由输入，而不是估值输出

### 4. 公式层
- 哪些公式必须新增
- 哪些公式必须重写
- 哪些公式必须保留原样
- 哪些公式之间存在重复计算风险
- 哪些公式需要分场景（特许权 / 非特许权 / 价值陷阱）
- 哪些公式应该先做基准版再做修正版
- 哪些公式应先用于“粗分流”，哪些公式应先用于“精确认值”

### 5. Prompt 层
- prompt 重写顺序
- 每个 prompt 需要包含的硬字段
- 哪些地方不能再写成散文式描述
- 哪些 prompt 应该重写成“决策模板”
- 哪些 prompt 应该重写成“变量清单”
- 哪些 prompt 应该重写成“例外规则表”
- 哪些 prompt 应该变成“先分类后计算”的两段式模板

### 6. 风险与缺口
- 数据缺口
- 逻辑冲突
- 计算口径冲突
- 可能造成误判的地方
- 书内概念无法直接落地的地方
- 如果硬映射，会出现什么错误
- 哪些地方需要我先拍板
- 哪些地方最容易把“讲得通”误当成“算得通”

### 7. 建议的实施步骤
- 第一步做什么
- 第二步做什么
- 第三步做什么
- 每一步的验收标准是什么
- 每一步预估输出物是什么
- 哪一步最适合先做 MVP
- 哪一步最适合最后做
- 如果只做一轮 MVP，边界应该怎么切

### 8. 最后给我一个决策建议
- 你建议先改哪一块
- 你建议先不要改哪一块
- 你建议我先确认的 3 个问题
- 你建议我先让框架回答哪一个问题

## 额外要求

- 只给结论，不要长篇复述资料。
- 先给你对我目标的理解，再给结构建议。
- 如果有冲突，直接指出冲突，不要调和。
- 如果你认为某些书内概念不适合直接映射到 Turtle，请明确说“不适合”并说明原因。
- 如果你认为某些内容需要我先确认，请单列出来。
- 如果你认为现有框架已经有一部分设计是合理的，请保留，不要为了重构而重构。
- 如果你认为应该先定术语再定公式，请明确说出来。
