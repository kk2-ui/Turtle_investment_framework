# 报告自主性五阶段：已实现接缝与盲测设计

## 当前设计结论

训练系统不应试图把“行业判断”或“优秀文章风格”直接塞进报告。可验证的产品链应当是：

```text
行业经验（问题、反例、取证顺序）
  -> 角色化外部取证计划
  -> 静态来源回执与来源包绑定
  -> 目标公司一手传导任务
  -> 已准入行业观察
  -> 同一 JUDGMENT_SYNTHESIS writer handoff

Enterprise Underwriting Episode
  -> component decisions + normal-earnings derivation
  -> component reader bridge（只读、逐项锚点）
  -> 同一 JUDGMENT_SYNTHESIS writer handoff
  -> 既有章节 writer / reader surface
  -> completion anchor gate
```

这两条流在报告前汇合，但不互相越权：行业材料只能改变公司取证和已验证的行业—公司传导解释；组件账本才决定正常盈利、普通股现金、永久损失和价值路线的经济去向。估值数值、价格和投资动作不在此设计的权限范围内。

## 阶段 1：行业经验变为公司取证与必验问题

现有 `industry_experience_acquisition.py` 保留每个行业角色的边界、来源角色和停止规则。新增的报告准入收紧为：

- 每个配对必须写明计划的 `task_id` 与确定性 `transmission_requirement_id`；
- 行业观察必须确实属于该任务，而非任意 receipt；
- 目标公司一手 `evidence_trace` 必须把自身用途显式绑定到同一 `task_id`；
- 因而“有一条公司来源”不再足够，必须能回答“它在验证哪条行业—公司传导”。

`UNKNOWN` 与 `PUBLIC_INFO_UNAVAILABLE` 仍是合格的取证收口；它们不能升级为正面公司事实或报告行业结论。

## 阶段 2：组件经济账本

不重建第二本账。`EnterpriseUnderwritingEpisode` 现有的 `component_decisions` 与 `economic_derivation` 是唯一经济真源。新增的 `report_autonomy_bridge.py` 只从该 Episode 进行精确、price-free 派生，输出：

- 每个组件的读者安全经济去向锚点；
- 正常盈利组件桥的段落锚点；
- 材料敏感性和翻转条件的段落锚点；
- Episode、公司、cutoff 和 underwriting thesis 的完整身份绑定。

桥禁止补写公司事实、估值参数、价格或行动；它也不把条件、情景、排除或未解决的经济处理提升成基准处理。

## 阶段 3：完整读者报告强制消费账本

`write_enterprise_underwriting_component_reader_bridge` 将同公司、同 cutoff 的 Episode bridge 写入当前 `analysis_contract`。随后：

1. `JUDGMENT_SYNTHESIS` 同时投影 `report_admitted_industry_evidence` 和已绑定的 `enterprise_underwriting_component_reader_bridge`；
2. Episode-bound投资报告在首次 `read_report_contract_pack` 时即收到两者，而非等到最终组装前；
3. 仍由既有章节 writer 写完整报告，`assemble_report` 不追加平行的组件报告、不重算账本；
4. 技术稿每次使用 `IEA:` 外部行业观察，必须在既有 `claim_evidence` 的对应原子事实中同时声明该 identity、原始取证 `task_id` 与 `transmission_requirement_id`；完成门逐项核对该结构化记录、正文 identity 与公司一手证据已闭合的准入记录。省略显示标记不能绕过此门，读者版则无需显示内部 identity；
5. `report_completion` 检查技术稿及 reader surface 对每个桥锚点各保留一次。少一个组件、正常盈利桥或敏感性/翻转段落即阻断。

因此，新的工作不是强迫模型模仿中海物业的措辞，而是让读者可以在正文中追问组件如何进入正常盈利、现金、永久损失和价值路线。

## 阶段 4：人工纠偏与经典原则的正确权限

`expert_correction_training.py` 和 02669 教师包已经满足这一阶段的实现要求：它把接受的人工纠偏编译为 company-free `TRAINING_MEMORY`，保留适用条件、错误机制、禁止假设、反向条件与下一取证动作，并隔离教师公司的事实、来源、结果、价格与报告全文。

经典投资原则只可作为条件化的纠偏问题，例如：现金索取权、留存资本回报、资产/盈利/成长分层、永久损失和价值路线身份。它们必须由新公司自己的 cutoff 前证据决定是否适用；不成为参数表或结论模板。

## 阶段 5：8 家未见公司 2×2 盲测预注册

本阶段的最小可识别设计是 **8 家**（不是以一家公司凑结果）。每家公司固定一份共同 cutoff 源包和同一报告合同，运行四个 fresh `fork_turns=none` arm：

| Arm | 行业经验 | 专家纠偏原则 |
| --- | --- | --- |
| A00 | 无 | 无 |
| A01 | 有 | 无 |
| A10 | 无 | 有 |
| A11 | 有 | 有 |

冻结前的样本资格：至少三个连续年度的官方披露、可明确公司身份与 cutoff、可构造核心业务组件与一项材料性现金/资本责任问题、未出现在任何既有 teacher/pack/holdout/campaign 中。样本按事先写明的 cutoff-only 名单排序进入，禁止因预测效果或事后结果替换。

每个 arm 只能读取其 rendered task packet；共同源逐字相同，Enhanced 仅多出对应的 company-free `TRAINING_MEMORY`。每臂保存完整 Episode、组件桥、首份完整读者报告和原始响应。第三个 fresh Agent 先匿名审阅首稿，逐项判断：

- 行业—公司传导是否由同一公司一手证据闭合；
- 组件、正常盈利、普通股现金、永久损失、价值路线和反方是否可挑战；
- 条件性或未知项目是否被错误提升；
- 是否仍需材料性人工纠偏。

四臂全部冻结、匿名审阅完成后，隔离 custodian 才能读取 cutoff 后经营结果，按预注册的经营时钟结算；不得以市场价格、收益率或后见公司叙述替代。单家公司只说明 case-local difference；只有跨 8 家的方向一致、无新增材料错误、并经独立工程复审，才可以主张任何可复现的报告自主性增益。

## 当前状态

- 阶段 1–3 的生产接缝和定向回归已实现；
- 阶段 4 的蒸馏器与教师包已经存在并保持训练记忆边界；
- 阶段 5 尚未冻结新 8 家名单、未运行任何 arm、未读取任何未来结果。

所以当前不能声称“训练已经让报告自主达到中海物业水准”。能够声称的是：下一轮试验终于会测量一条真实生产链，而不是比较两份提示词更像不像好报告。
