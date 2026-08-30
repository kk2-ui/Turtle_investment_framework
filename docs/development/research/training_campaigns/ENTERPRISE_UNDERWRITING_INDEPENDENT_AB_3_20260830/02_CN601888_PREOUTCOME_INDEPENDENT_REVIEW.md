# CN601888 结果前独立材料性审阅

> 审阅日：2026-08-30  
> 身份：独立 pre-outcome materiality reviewer  
> 结果边界：未读取 cutoff 后结果、价格、回报、其他 campaign、两臂 downstream bundle 或任何 outcome artifact  
> 权限边界：本审阅不授予方法、迁移、CJO、估值、BuyBand、报告或投资权限

## 一、裁决摘要

| 层次 | 裁决 | 是否可进入 outcome 结算 |
| --- | --- | --- |
| A. 标准 runtime paired test | **未完成；作为标准 runtime 配对试验无效**。两臂均在 Anthropic runtime 的四次尝试后因 `401 authentication_error: API key is invalid` 终止，没有生成标准 runtime Episode 或 `fresh_agent_response.json`。manual fallback 不能替代该生成条件。 | **否** |
| B. manual fresh diagnostic pair | 两份 draft 经当前 `validate_training_episode` 均为 `REVIEWABLE`，因此可作受限的内容诊断；但不是标准 runtime 配对，也不能作模型/方法的因果归因。内容裁决为 **`ENHANCED_WORSE`**，不是 `MATERIAL_PREOUTCOME_IMPROVEMENT_CANDIDATE`，也不只是无差异。 | **否；只保留结果前诊断结论** |

本轮应冻结的总判断是：标准 A/B 没有发生；手工对照中，Baseline 已经完成 treatment 所要求的核心经济处理，Enhanced 没有独有改善，却把证据不足的“成熟渠道”从条件性候选提升为基准中的 `UNDERWRITE`。不得读取 outcome 来给该变化补分，也不得用结果回写两份 Episode。

## 二、层 A：标准 runtime paired test

### 2.1 完成性与有效性

两份 `EXECUTION_BLOCKER.md` 记录了同一实质失败：Anthropic provider 无法通过认证，四次 LLM 尝试后返回 401。Baseline 和 Enhanced 都没有由 `run_training_agent` 返回 `TRAINING_EPISODE_COMPLETED`，也没有标准 runtime 生成的完整 Episode。因此不存在可比较的标准 runtime 输出。

两份 `MANUAL_FRESH_GENERATION_RECORD.md` 都明确说明 `manual_episode_draft.json` 未经过标准 provider runtime。Enhanced record 所述 `REVIEWABLE`，以及本审阅对两臂重新运行活动 validator 得到的两个 `REVIEWABLE / findings=[]`，仅证明 schema、公司/cutoff/sample identity、source allowlist、training-memory 禁止入证据、price/outcome 边界等静态绑定成立。

validator 不验证生成是否来自标准 runtime，也不验证两份 manual draft 的模型、token budget、上下文实现或独立生成过程是否可比；它也不判断经济材料性、组件是否重叠或条件是否被提前满足。故不能把静态 `REVIEWABLE` 改写为标准 runtime paired test 完成。

### 2.2 标准 runtime 接受条件

在不读取 outcome 的前提下，只有同时满足以下事实，层 A 才可改判完成：

1. 两臂各自通过 `run_training_agent` 从冻结合同和准确 allowlist 进行 fresh generation，并返回 `TRAINING_EPISODE_COMPLETED`；
2. 两臂使用同一 provider、同一明确模型版本、同一 runtime 参数和相近预算，唯一增量仍是 Enhanced 的 `TRAINING_MEMORY`；
3. 两个 runtime Episode 各自通过 `validate_training_episode`，且不存在 401、手工代写或复用本轮 manual draft；
4. 在读取任何 outcome 前，由独立 reviewer 重新冻结配对有效性和材料性裁决。

## 三、层 B：manual fresh diagnostic pair

### 3.1 共同经济处理：不能计为 Enhanced utility

两臂已经在相同经济口径上得出相同方向：

| 问题 | Baseline | Enhanced | 材料差异 |
| --- | --- | --- | --- |
| 正常盈利方向 | `MIXED` | `MIXED` | 无 |
| owner cash 方向 | `UNKNOWN` | `UNKNOWN` | 无 |
| 永久损失方向 | `MIXED` | `MIXED` | 无 |
| FY2018 高毛利/并表 | 不作为稳定状态，拆成熟、并表、新开渠道 | 不线性外推，拆成熟、并表、新开渠道 | 无 |
| 集团 OCF | 不等同普通股可分配现金 | 不等同 owner cash | 无 |
| 新渠道与在建项目 | 情景或排除基准 | 条件性/情景或排除基准 | 无 |
| 永久损失 | 经营权、租金、客流/政策、库存、商誉、建设资本、索取权 | 同一组主要路径 | 无 |
| 价值路线 | 分渠道正常化 owner cash + 经营权期限情景 | 成熟渠道期限现金 + 逐渠道 owner-cash bridge | 无实质差异 |

Baseline 并未落入预注册的两个风险：它没有把 FY2018 的 53.09% 免税毛利、机场经营权或日上上海并表直接永久化，也没有因为租金、存货和投资现金流为负而否定成熟底盘。Baseline 已明确区分成熟离岛、成熟机场、新渠道、旅游服务和开发项目，并把租赁、库存、维护投入、少数股东及融资索取权放回普通股现金边界。因此 Enhanced 的更多字段、更多 caveat、不同 horizon 和更长表述均不是独有材料性改善。

### 3.2 Enhanced 独有变化为何是负效用

Enhanced 的 `component_treatments.mature_existing_channels` 使用 `UNDERWRITE`，其 `normalization_case.treatment` 和最终 `investment_treatment` 又明确称成熟渠道“进入/可进入有界基准”。Baseline 对三亚成熟离岛及北京/上海机场均保持 `CONDITIONALLY_UNDERWRITE`，只有获得完整周期、租赁后单位经济和普通股现金证据后才进入核心。

这不是语气差异，而是基准正常盈利组成的变化。中性事实包只有 FY2018 的三亚规模与客流/购物人数，以及上海、首都机场收入；上海还是自 2018 年 3 月才并表。事实包明确缺少跨期同店、每客毛利、各渠道租金/保底、剩余期限、续约概率、库存周转、维护资本和资产组现金。`01` treatment 本身规定成熟渠道只有在“跨期吸收和现金证据”成立时才能进入有界基准。当前证据不满足该门槛。

Enhanced 一方面把整个 `mature_existing_channels` 设为 `UNDERWRITE`，另一方面又把日上上海及机场新经营权放入 `newly_consolidated_channels` 条件项，导致上海/机场组件可能同时属于已承保基准与待验证扩张。活动 validator 不检查这种经济重叠。其 `industry_future` 组件还称把续约和租金条件“置于基准边界之外”，而 owner cash 与其他段落又承认这些责任尚不可界定；后续 caveat 没有撤回先行纳入基准的决定。

Enhanced 没有明说经营权是永久特许权，也没有直接把 53.09% 毛利年金化；这一点不构成单独问题。但在缺少 treatment 要求的跨期吸收与责任后现金证据时，以单期渠道规模和客流把“成熟渠道”升级为 `UNDERWRITE`，实质上预支了渠道持续性和基准盈利资格。它材料性放宽了正常盈利和价值路线的纳入边界，故按预注册规则裁为 `ENHANCED_WORSE / REASONING`。

此外，Enhanced 的 `most_likely_regime` 直接采用“行业保持增长”，而中性包只证明公司 FY2018 的并表/扩张和免税业务对政策、客流的依赖，并没有提供未来行业增长率或持续增长证据。该假设不应支撑基准渠道吸收或价值路线；最多只能列为条件场景。

### 3.3 防御性写作检查

- **UNKNOWN 未扩散成全局停判。** 两臂都把 `UNKNOWN` 主要保留在 owner cash；Enhanced 对永久损失“幅度未知”属于局部边界，尚未把整个公司改写为不可判断。
- **保守措辞不是改善。** Enhanced 增加了合同、租金、库存和资本责任 caveat，但 Baseline 已经逐项处理。重复风险清单、降低信心或延长文字不产生 utility。
- **caveat 不能抵销提前纳入。** “有界”“条件范围”“待补数据”不能使 `UNDERWRITE` 与“进入基准”自动变回条件性候选；真正决定经济路线的是组件 treatment 和基准组成。
- **高毛利与渠道权没有被直接永久化，但存在部分预支。** Enhanced 拒绝峰值年金化和永久特许假设是正确的；错误在于未满足自身跨期/现金证据门槛就承保成熟渠道，而不是缺少风险用语。

## 四、审阅返回

### Finding 1 — 标准 runtime 没有产生配对样本

- **分类：`ACQUISITION_MODULE`**
- **经济影响：** 无法判断 treatment 在同一实际模型/runtime 下是否改变正常盈利、owner cash、永久损失或价值路线，也不能把任何后续 outcome 与两臂 Episode 配对。若把 manual fallback 冒充标准输出，会把生成方式差异误归因于方法。
- **缺失事实：** 两个成功的标准 runtime Episode、明确且相同的模型/runtime 配置、两个 `TRAINING_EPISODE_COMPLETED` receipt。
- **禁止假设：** 不得因两臂都遇到相同 401 就假设配对已发生；不得因 manual draft 通过 validator 就假设其来自或等价于标准 runtime；不得读取 outcome 后决定是否接受 fallback。
- **最小修复：** 修复 provider 凭证/运行配置后，从冻结输入 fresh rerun 两臂；不复用或改写本轮 manual draft。若无法恢复标准 runtime，则明确结束本轮标准 A/B，而不是降级命名为已完成。
- **接受标准：** 满足第 2.2 节四项条件，并在 outcome 仍 sealed 时由独立 reviewer 冻结有效性。

### Finding 2 — Enhanced 提前把证据不足的成熟渠道纳入基准

- **分类：`REASONING`**
- **经济影响：** 相对 Baseline，Enhanced 把成熟渠道从待完整周期与责任后现金验证的条件性候选提升为 `UNDERWRITE`/基准组成，会抬高同口径正常盈利承载范围，并把没有期限、租金和 owner-cash 证据的渠道带入价值路线；这能改变永久损失暴露和后续价值结果。
- **缺失事实：** 分渠道跨期客流到购物转化、同店/每客毛利、租金及保底、剩余期限和续约、库存周转、维护资本、税费及普通股现金；上海/机场成熟与新并表边界也未唯一化。
- **禁止假设：** 不得以 FY2018 单期规模、三亚顾客/购物人数、机场收入、高免税毛利、公司称为既有渠道或已取得经营权，替代跨期吸收与责任后现金；不得用“有界/保守”标签冒充门槛已满足；不得假设行业持续增长。
- **最小修复：** 对本轮不作 post-hoc Episode 修补，直接冻结 `ENHANCED_WORSE`。若未来重测，应在新的预注册/新 run identity 中把未满足跨期吸收和现金证据的成熟渠道统一保留为 `CONDITIONALLY_UNDERWRITE`，消除成熟/新并表组件重叠，并把行业增长降为条件场景。
- **接受标准：** 只有 Enhanced 独有地、基于同一 cutoff 事实纠正 Baseline 的错误，并材料性改善至少一条同口径经济路线，且不提前满足证据门槛，才可成为 `MATERIAL_PREOUTCOME_IMPROVEMENT_CANDIDATE`。当前 pair 不满足，不能靠改写或 outcome 补救。

### Finding 3 — pre-outcome 文档与正式合同的 cutoff 不一致

- **分类：`ACQUISITION_MODULE`**
- **经济影响：** `00` 写的是 `2019-04-27T00:00:00+08:00`，而两份正式合同和 Episode 使用 `2019-05-01T00:00:00+08:00`；中性源包的 `available_at` 为 `2019-04-27T23:59:59+08:00`。若按 `00` 的时点，核心年报源晚于 cutoff；若按 JSON 合同，则合法。该歧义会改变可用事实集合，因而不是纯格式问题。
- **缺失事实：** 一个被正式冻结、在 `00`、两份合同、两份 Episode 和源包可得性规则中一致的 cutoff 身份。
- **禁止假设：** 不得把“2019-04-27 当日”自动视为覆盖当天 23:59:59，也不得在不同文件间择有利 cutoff。
- **最小修复：** 在任何标准 rerun 前，以结果前 erratum 明确正式 cutoff，并使预注册头部、合同、Episode 与 `available_at <= cutoff` 一致；不得改变已经冻结的材料性分叉。若无法无歧义修订，则使用新 contract/run identity。
- **接受标准：** 所有控制文件只存在一个精确 cutoff，源包在该时点前可得，两份合同继续通过活动 contract validator。

## 五、最终 pre-outcome freeze

1. `STANDARD_RUNTIME_PAIRED_TEST = NOT_COMPLETED / INVALID_AS_STANDARD_RUNTIME_PAIR`
2. `MANUAL_FRESH_DIAGNOSTIC_PAIR = CONTENT_REVIEWABLE_BUT_NONCAUSAL`
3. `PREOUTCOME_MATERIALITY_SETTLEMENT = ENHANCED_WORSE`
4. `MATERIAL_PREOUTCOME_IMPROVEMENT_CANDIDATE = NO`
5. `OUTCOME_READ_AUTHORIZED = NO`
6. `METHOD_VALIDATED = NO`

若项目选择继续，下一步只能是先解决 runtime 与 cutoff 合同问题，再在 outcome sealed 状态下执行新的标准 fresh pair；若不重跑，则本轮应以“标准试验未完成、手工诊断 Enhanced Worse”结束。
