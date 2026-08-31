# 行业经验驱动前置取证 V1

## 目标

行业经验层的生产用途不是替公司下判断，也不是为报告补一段行业背景。它应在年报取证和正文写作**之前**回答一个更具体的问题：

> 为判断这家公司的利润池、正常化、永久损失与价值路线，下一步应优先取得哪类外部行业证据，以及怎样把它连接回本公司的一手证据？

V1 将既有 `IndustryUnderwritingContext` 变成一个小型、可审计的前置取证闭环。它以中海物业自动报告暴露的缺口为目标：年报链本身可以完整，却缺少受角色约束的行业外部事实，因而行业视角偏窄、估值只能把许多未验证的不确定性压成保守折扣。

这不是把行业经验直接变成更乐观的买入价。行业证据可能确认压力、确认机会、反证原有机制，或停在 `UNKNOWN`；四种结果都应保留。

## 生产链路

```text
IndustryLearningBlock / 机制卡 / 官方行业背景 / competitive arena
                         ↓
             IndustryUnderwritingContext
                         ↓
 industry_evidence_acquisition_plan.json
   ├─ DEMAND
   ├─ SUPPLY_COMPETITION
   ├─ PRICE_COST
   ├─ CUSTOMER_CHANNEL
   ├─ REGULATION
   └─ COMPANY_TRANSMISSION
                         ↓
  外部来源回读、原始来源包与可审计 receipt
                         ↓
 industry_evidence_acquisition_receipt.json
                         ↓
 EnterpriseUnderwritingEpisode 的候选 evidence_trace
                         ↓
 正式公司证据、判断账本、黄金报告
```

角色不是固定清单。编译器只为已有上下文实际触及的角色生成一项任务，避免把行业研究扩成无边界资料搜集。`COMPANY_TRANSMISSION` 在机制卡要求公司验证字段时加入，即使其行业侧引用尚为空；这保证“行业经验服务前置取证”最终仍回到目标公司的责任边界。

## 两个新工件

### `industry_evidence_acquisition_plan.json`

由 `scripts/industry_experience_acquisition.py:compile_industry_evidence_acquisition_plan` 编译。每项任务固定：

- 经济角色与决定性问题；
- 待验证的公司传导；
- 计量/责任边界；
- 可接受的来源角色；
- 可用于行业未来判断、公司传导测试、正常化条件或永久损失条件的范围；
- 停止规则；
- 对已存在行业上下文的证据指针。

计划不复制同业教师公司的姓名、事实或数值。它只保存通用问题和引用指针，因而不会把历史训练样本泄漏为新公司的“事实”。

### `industry_evidence_acquisition_receipt.json`

由 `build_industry_evidence_acquisition_receipt` 或 Agent 工具 `write_industry_evidence_acquisition_receipt` 写入。每个完成任务可以是：

- `VERIFIED`：发现符合来源角色、截止日和口径的外部观察；
- `CONTRADICTED`：发现了与候选机制相反的观察；
- `UNKNOWN`：已完成有界尝试但不能判定；
- `PUBLIC_INFO_UNAVAILABLE`：目标口径无法从公开资料取得。

`UNKNOWN` 和 `PUBLIC_INFO_UNAVAILABLE` 是合法的完成结果，不会阻断公司研究，也不会被伪装成正面证据。`VERIFIED`/`CONTRADICTED` 的每条观察必须记录：

- 稳定 `source_ref` 和 HTTPS 原始来源地址；
- 发布和可得时间（均须不晚于 cutoff）；
- 来源角色、来源类型、发布者、期间和定位点；
- 指标、单位和责任边界；
- 该外部观察如何**待由本公司一手披露继续验证**的传导。

同日但没有时刻的来源不能在同一 cutoff 日被默认为已可得；来源角色、来源类型、公司身份或 cutoff 不匹配同样会被拒绝。

## 三条硬边界

1. 行业经验、计划与外部行业观察都不是目标公司的直接事实。任何公司销量、份额、合同、成本、现金或资产主张仍须由目标公司的一手证据建立。
2. 该层不能产生 `owner_cash` 数值、估值参数、价格、回报或投资行动。它只能影响后来应验证的经济条件；是否改变正常化或永久损失，由完整 Episode 和现有账本决定。
3. `RESEARCH_AGENDA` 可以读取计划、回执摘要和 Episode 候选 trace；`JUDGMENT_SYNTHESIS` 与 `INVESTMENT_ENRICHMENT` 不读取该工件。这样报告在正式综合前不会把未配对的行业观察当作已完成公司判断。

## 接口与自动接线

- `scripts/turtle_agent/tools/phase_tools.py:build_industry_context` 在生成 `IndustryUnderwritingContext` 后自动编译计划。
- `write_industry_evidence_acquisition_plan` 支持在已有报告输出目录重编计划。
- `write_industry_evidence_acquisition_receipt` 只接受已固定任务的回执，不能临时换题。
- `read_industry_evidence_acquisition` 返回受控计划/回执投影。
- `scripts/judgment_generation_handoff.py` 只在 `RESEARCH_AGENDA` 投影 `industry_evidence_acquisition`；计划或回执身份不匹配时局部排除，并保留既有报告研究路径。
- `build_episode_industry_evidence_binding` 只生成现有 `EnterpriseUnderwritingEpisode` schema 可接受的 `existing_object_ref` 与 `evidence_trace` 候选字段。它不会创建或修改 Episode，更不会自动修改 component treatment、owner cash、估值或买点。

## 验证面

定向测试覆盖：

- 真实水泥上下文被压缩为角色任务，且不复制教师公司文本；
- cutoff 后来源、来源角色不匹配、来源类型不匹配都会被拒绝；
- `UNKNOWN` 不会生成 Episode trace 候选；
- 已接纳观察可按既有 Episode schema 作为候选 trace 接入；
- handoff 只在研究视图可见，错误公司身份局部排除且不阻塞研究；
- Phase 1.5 自动生成上下文后能生成计划。

本 V1 的产物验证面是黄金报告生成前的研究输入质量：外部行业事实覆盖、公司传导是否被明确提出、以及估值假设是否有待验证的经济条件。它不以报告变长、语言更像专家或买入价更高作为“有效”证据。
