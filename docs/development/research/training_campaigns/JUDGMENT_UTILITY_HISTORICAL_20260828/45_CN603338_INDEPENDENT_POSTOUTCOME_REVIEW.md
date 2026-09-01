# CN603338 独立结果后审阅

## 最终裁决

**ACCEPT_AFTER_SCOPE_CORRECTION。真实反馈 turn 已完成并关闭，修正后的企业反馈正式接纳。**

`settlement_merge_disposition = REJECTED_AS_OVERDEFENSIVE_SCOPE_FLATTENING`。44 中原机械 overall merge 保留为被结果后 reviewer correction 击穿的历史记录，不要求修改 41/44；其余底层事实、OC1/OC2/OC3 单元结算和轴向证据均接纳。

这不是字段数量退回。OC1 的臂式吸收为 `FAVORABLE`，OC2 的母公司现金为 `NEUTRAL_POSITIVE_CASH`，OC3 的信用载体为未达 adverse 门槛的 `MIXED_RESIDUAL`。真正的问题是 settlement 把 `POSITIVE + POSITIVE + scoped CONDITIONAL` 机械合并为企业整体 `CONDITIONAL_CREDIT`。预注册规则只说明不同载体出现 `POSITIVE` 与 `NEGATIVE` 时合并为 `CONDITIONAL_CREDIT`；本案没有任何 `NEGATIVE_CREDIT`。因此该合并缺乏经济依据，也让局部融资租赁/信用变化吞掉了已观察的产品吸收和仍为正的母公司现金。

修正后的企业总处理是：**已验证的臂式产品/商业渠道执行继续 `POSITIVE_CREDIT`；经营现金执行为 `POSITIVE_CREDIT_WITH_LOWER_NORMALIZED_LEVEL`；融资租赁与信用执行单列 `CONDITIONAL_CREDIT`；新增项目与 CMEC 的资本配置回报继续 `WITHHOLD_CREDIT`；企业整体为 `POSITIVE_CREDIT_WITH_CREDIT_AND_CAPITAL_ALLOCATION_CONSTRAINTS`，不是单一 overall `CONDITIONAL_CREDIT`。** 强产品结果不解除信用约束，信用 mixed 也不撤销产品事实。

本审阅只读取题定的六份材料：37、40、41、42、43、44。未读取其他仓库文件、packet 旧产物、网络、价格、回报、旧报告或其他公司 outcome。

## 六轴结果前—结果后比较

| 六轴 | 结果前 | settlement 结果 | 独立结果后处理 | 变化分类 |
|---|---|---|---|---|
| management execution | `POSITIVE_CREDIT` | overall `CONDITIONAL_CREDIT` | 企业整体维持正面；产品/渠道 `POSITIVE`，母公司现金执行 `POSITIVE`，信用/融资执行 `CONDITIONAL`，未验证项目资本配置 withheld | **局部材料 treatment change，整体机械降级被退回** |
| normal earnings | `RAISE`；约 13.08–15.107 亿元，中心约 14.09 亿元 | `RAISE` | 仍 `RAISE`；FY2024 同口径经常经营利润 19.242 亿元税前，同比增长 8.267%；按原 15% 税率惯例及更保守的 FY2024 总收入 2/4 个百分点回撤，方向性税后范围约 13.70–16.36 亿元、中心约 15.03 亿元 | **仅水平/范围与置信度变化，代码不变** |
| parent owner cash | `COUNT_IN_PARENT_OWNER_CASH`；约 13–17 亿元 | `COUNT_IN_PARENT_OWNER_CASH` | 继续计入，但正常化工作范围下修至约 10–14 亿元、中心锚定 FY2024 观察值 11.23 亿元；不再沿用 13–17 亿元而不作调整 | **仅水平/范围收窄，代码不变** |
| permanent loss | `MAINTAIN_CONSTRAINT` | `MAINTAIN_CONSTRAINT` | `MAINTAIN_CONSTRAINT`；信用监控更紧，但未达到 `TIGHTEN`，也不因现金缓冲而 `RELAX` | **treatment 完全不变** |
| valuation direction | `UP` | `UP` | `UP`，但仅是相对 FY2022 同责任边界经济的方向；没有价格、BuyBand 或预期回报 | **方向代码完全不变** |
| next research action | 广泛复核臂式吸收、集团利润、母公司现金、融资租赁与担保 | `PRESERVE_CURRENT` | 已完成的臂式吸收问题应退场；下一步集中在信用 cohort、实际回款/代偿、母公司现金回升，以及高位平台/CMEC 的增量资本回报 | **真正的材料 treatment change** |

这里没有把“更多字段”当作变化。材料变化只来自经济载体：已验证吸收、现金水平回落、信用准备率上升以及尚未闭合的资本回报。

## 三项最重要的结果后企业判断

### 1. 臂式产品及既有商业渠道的经济吸收得到强化

**判断：POSITIVE，且结果后证据强于结果前。** FY2024 臂式收入同比增长 20.84%，销量增长 18.65%，毛利额约 8.927 亿元、同比约增长 27.07%，毛利率 30.20%，库存下降 19.53%。集团同口径经常经营利润约 19.242 亿元、同比增长 8.267%。这不是单纯产量或产能投放。

**机制：** 产品销售增长同时带来单位毛利和毛利额增长，库存反向下降；销售、管理、研发、信用与资产减值后的集团经常经营利润仍增长，说明增量毛利没有被持续成本全部吞噬。渠道的具体地域归因没有单列闭合，但商业吸收本身已经由销量、库存和利润共同观察。

**最强反方：** settlement 没有单列高位平台利用率、海外地域渠道利润或产品级持续费用；销售与管理费用上升，当前毛利也可能包含产品组合或成本环境贡献。因此不能把这一结果扩展为所有新增产能和渠道投资都已获得高回报。

**投资含义：** 保留并强化已吸收产品/渠道的正面执行信用；不能用 OC3 的局部 mixed 撤回，也不能用 OC1 的强结果给高位平台或 CMEC 自动授信。

### 2. 母公司 owner cash 仍真实可计入，但高位不可永久化

**判断：COUNT_IN，水平下修。** FY2024 母公司 OCF 为 14.665 亿元，全部购建长期资产现金为 3.433 亿元，得到全资本开支后现金约 11.232 亿元；`OCF/母公司净利润` 为 0.8904。母公司货币资金约 45.445 亿元，约覆盖保守有息债务 1.103 亿元 41 倍。

**机制：** 现金直接存在于母公司责任边界，且扣除了全部资本开支；没有用合并现金、账面坏账准备或担保余额冒充母公司可接触现金。

**最强反方：** 全资本开支后现金由 FY2023 的 16.758 亿元下降至 11.232 亿元，现金转化率也由 1.0789 降至 0.8904；维持性与增长性资本开支没有拆分，母公司实际信用回款、子公司分配和担保代偿的组成金额仍为局部未知。因此 FY2023 的 13–17 亿元范围不能原样永久化。

**投资含义：** treatment code 不变，但正常化工作范围下修到约 10–14 亿元、中心约 11.2 亿元。若以后回到全资本开支后现金至少 15 亿元且现金转化率至少 0.9，才支持重新上修。

### 3. 信用载体温和恶化，但不是已发生的永久损失或企业失败

**判断：信用/融资执行 CONDITIONAL；永久损失仍 MAINTAIN_CONSTRAINT。** 综合应收减值率由 2.3895% 升至 3.0119%，融资租赁组合减值率由 0.57% 升至 1.91%，所以不能称为 favorable 或 stable。另一方面，融资租赁组合毛额由约 17.036 亿元降至 16.381 亿元，上海鼎策仍盈利约 0.453 亿元；FY2024 信用减值损失约 0.186 亿元，低于 FY2023 的约 0.251 亿元，且只占集团同口径经常经营利润约 0.97%。对子公司担保余额约 9.149 亿元，未观察到达到门槛的母公司实际代偿披露。

**机制：** 准备率上升表明信用 cohort 的预期损失或账龄压力在增加；但年度损失流量、融资子公司盈利和母公司现金尚未显示它已转化为材料本金损失。

**最强反方：** 融资租赁准备率一年内明显上升，实际母公司现金事件的分项金额未单独披露，不能把“未披露达到门槛的事件”写成零。若账龄继续迁移，当前盈利和现金缓冲可能滞后于损失确认。

**投资含义：** 信用载体必须继续单列追踪，不能被强产品结果忽略；但在综合减值率低于 4%、信用损失远低于 1.5 亿元、融资租赁减值率低于 3%且上海鼎策盈利的事实下，它没有经济依据把整家公司执行降为 conditional。

## 管理层：必须拆开的两种执行

- **产品/渠道执行：`POSITIVE_CREDIT`。** 臂式销售、毛利额、毛利率、库存和集团经常利润共同闭合。
- **经营现金执行：`POSITIVE_CREDIT_WITH_LOWER_NORMALIZED_LEVEL`。** 母公司现金仍为正且债务覆盖强，但低于上一高位。
- **信用/融资执行：`CONDITIONAL_CREDIT`。** 准备率恶化但未到 adverse；需要 cohort 和现金事件验证。
- **项目资本配置执行：`WITHHOLD_CREDIT`。** 允许材料仍未闭合高位平台和 CMEC 的利用率、单位利润、增量母公司现金或减值；不因企业其他部分成功而推定成功。

企业整体不是四项的最差值。合理汇总为 `POSITIVE_CREDIT_WITH_SCOPED_CREDIT_AND_CAPITAL_ALLOCATION_CONSTRAINTS`。

## Normal earnings、owner cash、永久损失与方向估值

FY2024 同口径经常经营利润为 19.242 亿元税前。沿用结果前 15% 税率规范化惯例，税后观察代理约 16.356 亿元。由于 FY2024 主营收入在 settlement 中未单独给出，使用更大的 FY2024 总营业收入 77.989 亿元做保守敏感性：回撤 2/4 个毛利率百分点后的税后代理约为 15.030/13.704 亿元。由此给出 **13.70–16.36 亿元、中心约 15.03 亿元** 的方向性 normal-earnings 工作范围；这不是正式预测，也不假设全部毛利改善永久化。

Parent owner cash 继续计入，但以 FY2024 观察值 11.232 亿元为中心，工作范围约 **10–14 亿元**。该范围不把担保余额当现金流，也不把未单列的实际代偿金额擅自填零。

Permanent loss 继续 `MAINTAIN_CONSTRAINT`。现金缓冲、盈利的融资子公司及较低年度信用损失阻止收紧；准备率上升、融资模式、担保、贸易壁垒以及尚未验证的新项目/并购回报阻止放松。当前不是 thesis-blocking。

方向估值仍为 **UP**，因为 normal earnings 载体较参考状态更强且 owner cash 仍为正；现金水平回落和信用 mixed 限制上调幅度。没有价格，不能形成安全边际、预期回报、BuyBand 或买卖动作。

## 三情景与翻转事实

### 乐观情景

臂式毛利率维持约 30% 或更高、毛利额继续增长，集团同口径经常经营利润不低于 FY2024 水平并继续增长；母公司全资本开支后现金回到至少 15 亿元且 `OCF/净利润 >= 0.9`；综合应收减值率回落到约 2.5% 以下、融资租赁减值率回到 1% 左右且无母公司代偿。Normal earnings 处于约 15–16.5 亿元，owner cash 约 13–16 亿元，方向仍 UP 且置信度增强。项目资本配置仍需独立现金回报才能获得信用。

### 基准情景

臂式毛利率约 28%–31%，集团同口径经常经营利润约 17–19.5 亿元税前；母公司全资本开支后现金 8–14 亿元且现金转化率至少 0.7；综合应收减值率约 2.8%–3.5%、融资租赁减值率低于 3%、上海鼎策保持盈利且无材料代偿。Normal earnings 约 13.5–15.5 亿元，owner cash 约 9–14 亿元，产品执行 positive、信用执行 conditional、永久损失维持约束、方向 UP。

### 悲观情景

臂式收入或销量下降超过 15%、毛利率低于 25%、库存增加超过 10%，同时集团同口径经常经营利润下降超过 15%；母公司全资本开支后现金转负且 `OCF/净利润 < 0.5`；或综合应收减值率达到 4%、信用损失至少 1.5 亿元并满足相对利润门槛，融资租赁减值率至少 3%且上海鼎策亏损，或发生达到 1 亿元与 FY2023 owner-cash 5% 双门槛的母公司代偿。届时 normal earnings LOWER、owner cash 条件计入或不计、永久损失 TIGHTEN，方向可转 DOWN。

关键翻转事实如下：

1. **产品正面翻转：** 臂式需求、毛利率、库存和集团经常利润同时命中 OC1 adverse，而不是某一字段单独变差。
2. **现金翻转：** 母公司全资本开支后现金转负、现金转化率低于 0.5，并伴随结构性营运资金占用或材料代偿。
3. **信用翻转：** 综合信用门槛或“融资租赁减值率至少 3%且上海鼎策亏损”被实际命中；账面准备率继续上升但未到门槛只收窄信用处理。
4. **进一步上修：** parent cash 恢复到至少 15 亿元且转化率至少 0.9，同时信用率回落；高位平台和 CMEC 只有出现可归属、可持续的增量利润与母公司现金才获得资本配置信用。

## 被击穿的 settlement merge：保留的 RETURN 历史

以下内容保留原独立审阅对 44 overall merge 的 RETURN 根因、修复与验收历史。该局部 RETURN 已由本文件给出的 scope correction 完整修复，不再悬置真实反馈或企业结论；最终状态为 `ACCEPT_AFTER_SCOPE_CORRECTION`。

**Root cause：`REASONING`, `WRITING`。**

**经济影响：** 把 scoped credit mixed 合并成 overall conditional，会低估已经验证的产品/渠道执行，并可能把方向估值、管理层判断和下一步研究资源错误地统一向下压；反向地，若只写强产品，又会漏掉可能滞后显现的信用损失。本修正同时避免两种错误。

**缺失事实：** 修复 overall merge 不需要新事实，现有数据已经足够。仍然缺失且必须局部保留的是高位平台/CMEC 的增量回报，以及母公司实际信用回款、子公司分配和代偿的分项金额。

**禁止假设：** 不得把 `MIXED_RESIDUAL` 当作 `NEGATIVE_CREDIT`；不得用最弱局部载体覆盖其他责任边界；不得把未披露的实际现金事件填成零；不得以强产品结果推定信用或新项目安全。

**最小修复：** 将 management merge 拆成产品/渠道、经营现金、信用/融资和项目资本配置四项；只有已观察到跨载体 `NEGATIVE` 或材料损失时才把企业整体降为 conditional/negative。将 next research action 从 `PRESERVE_CURRENT` 改为信用 cohort、母公司现金恢复和新增资本回报。

**验收标准：** 本案唯一企业处理必须同时显示产品/渠道 `POSITIVE`、信用/融资 `CONDITIONAL`、项目资本配置 withheld，整体不得低于 `POSITIVE_WITH_SCOPED_CONSTRAINTS`；OC3 仍须保留独立约束；已结算的广泛臂式吸收不再原样成为下一研究动作。

## 三项分开结算

### REAL_FEEDBACK_TURN

`COMPLETED_AND_CLOSED`。授权结果由独立 reviewer 消费，并产生了真实的企业反馈、范围修正和下一步研究行为。该结论不依赖价格、回报或其他公司 outcome。

### ENTERPRISE_INVESTMENT_TREATMENT

`ACCEPTED_AFTER_SCOPE_CORRECTION`。企业整体仍偏正面；normal earnings 维持 RAISE 并上移工作范围，owner cash 继续计入但下修范围，permanent loss 维持约束，valuation direction 仍 UP。产品与信用责任边界已经分开，原机械 overall merge 已明确拒绝。

### METHOD_LEARNING_UTILITY

`NOT_APPLICABLE_SINGLE_ARM_BLIND_EPISODE`，效用信用为 **0**。单臂 Blind 足以产生真实反馈和候选行为决定，但不能证明方法效用、`TRANSFER_VALIDATED` 或 `Method validated`。预测命中、字段更多、桥更清楚、reviewer 接受都不是方法效用。

公平的普通研究反事实会读取同一 FY2024 年报中的产品毛利、销量、库存、集团利润、母公司现金和信用风险，因此不能把它写成只看收入或净利润的稻草人：

- `SAME_BOUNDARY_RECURRING_ECONOMICS_FIRST`：候选决定 `RETAIN`，因为它保持了产品吸收与集团经常利润的责任匹配；但相对公平普通研究的材料 treatment delta **不可证明，记 0 / NOT_APPLICABLE**。
- `CONVERSION_TRIAD_RETAIN_AND_NARROW`：候选决定 `NARROW`，明确只暂停/保留增量项目和相应资本负担，不允许局部信用 mixed 撤回已验证产品信用；相对公平普通研究的材料 treatment delta **不可证明，记 0 / NOT_APPLICABLE**。

下一案行为修正是候选研究纪律，不是已验证方法：先按责任载体拆 management，再做企业汇总；`MIXED_RESIDUAL` 只有达到材料负面经济载体时才能外溢；已经结算的问题应从 next action 退场。

## 权限

本反馈不授予方法验证、迁移验证、CJO、正式估值、BuyBand、报告、投资动作或买卖权限。`method_validation = NONE`，`transfer_validation = NONE`，`training_utility_credit = NONE`。

## 关闭状态

`review_status = CLOSED_ACCEPTED`；`final_disposition = ACCEPT_AFTER_SCOPE_CORRECTION`；`enterprise_feedback = ACCEPTED`；`real_feedback_turn = COMPLETED_AND_CLOSED`。没有待补事实或待决修复。
