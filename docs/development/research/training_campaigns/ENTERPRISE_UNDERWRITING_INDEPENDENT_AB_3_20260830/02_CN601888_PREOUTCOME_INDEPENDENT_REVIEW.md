# CN601888 结果前 fresh-context 独立材料性审阅

> 审阅日：2026-08-30
>
> 运行状态：`FRESH_CODEX_PAIR_COMPLETED`
>
> 材料性裁决：`ENHANCED_WORSE / REASONING`
>
> 结果边界：未读取 cutoff 后结果、价格、回报、其他 campaign 或任何 outcome artifact
>
> 权限边界：不授予方法、迁移、CJO、估值、BuyBand、报告或投资权限

## 一、裁决摘要

Baseline 与 Enhanced 分别由两个 `fork_turns=none` fresh Codex 子 Agent 生成。两臂只读取各自的
冻结合同和允许来源，未读取父会话、对方输出或结果；Enhanced 的唯一增量是预先冻结的
`TRAINING_MEMORY`。第三个 fresh-context reviewer 在结果仍封存时完成材料性比较。

两份原始响应随后均通过完整合同绑定校验，并由正式训练入口固化为：

```text
TRAINING_EPISODE_COMPLETED
execution_mode = CODEX_FRESH_SUBAGENT
completion_basis = FRESH_CODEX_SUBAGENT_GENERATED_COMPLETE_EPISODE_VALIDATED
```

因此本轮不是 manual fallback，也不因一次可选 Anthropic API 的 401 失败而无效。它是一轮已完成的
fresh Codex 公平配对；经济裁决为 **`ENHANCED_WORSE`**。

## 二、配对有效性

配对满足本轮实际要检验的隔离条件：

1. 两臂绑定同一公司、同一 `2019-05-01T00:00:00+08:00` cutoff、同一中性事实包和同一完整
   `EnterpriseUnderwritingEpisode` schema；
2. 两臂由互不共享上下文的 fresh Codex 子 Agent 生成，唯一输入差异是 Enhanced 的训练记忆；
3. 两份 Episode 均通过 `validate_training_episode` 的公司、cutoff、样本、source allowlist、
   outcome/price 隔离与完整 Episode 校验；
4. reviewer 不读取 outcome，不把结果反写 Episode，也不以篇幅、字段数、风险项或更低信心计分。

这里的“独立”准确指 fresh-context 认知隔离，不冒充不同模型家族或外部专家独立性。一次显式
Anthropic provider 尝试因凭据 401 失败，但外部 provider 不是正式默认路径，也没有改变两份已经
生成的 Codex 子 Agent 响应。

## 三、共同经济处理：不能计为 Enhanced utility

两臂已经在相同经济口径上得出相同方向：

| 问题 | Baseline | Enhanced | 材料差异 |
| --- | --- | --- | --- |
| 正常盈利方向 | `MIXED` | `MIXED` | 无 |
| owner cash 方向 | `UNKNOWN` | `UNKNOWN` | 无 |
| 永久损失方向 | `MIXED` | `MIXED` | 无 |
| FY2018 高毛利/并表 | 拆成熟、并表、新开渠道，不视为稳定状态 | 不线性外推，拆成熟、并表、新开渠道 | 无 |
| 集团 OCF | 不等同普通股可分配现金 | 不等同 owner cash | 无 |
| 新渠道与在建项目 | 情景或排除基准 | 条件性/情景或排除基准 | 无 |
| 永久损失 | 经营权、租金、客流/政策、库存、商誉、建设资本、索取权 | 同一组主要路径 | 无 |
| 价值路线 | 分渠道正常化 owner cash + 经营权期限情景 | 成熟渠道期限现金 + 逐渠道 owner-cash bridge | 无实质差异 |

Baseline 没有把 FY2018 的 53.09% 免税毛利、机场经营权或日上上海并表直接永久化，也没有因为
租金、存货和投资现金流为负而否定成熟底盘。它已经区分成熟离岛、成熟机场、新渠道、旅游服务
和开发项目，并把租赁、库存、维护投入、少数股东及融资索取权放回普通股现金边界。因此
Enhanced 的更多字段、caveat 和更长表述都不是独有材料性改善。

## 四、Enhanced 独有变化为何是负效用

Enhanced 把 `component_treatments.mature_existing_channels` 标为 `UNDERWRITE`，并在
`normalization_case.treatment` 和最终 `investment_treatment` 中把成熟渠道纳入有界基准。
Baseline 则保持 `CONDITIONALLY_UNDERWRITE`，等待完整周期、租赁后单位经济和普通股现金证据。

这不是语气差异，而是基准正常盈利组成的变化。中性事实包只有 FY2018 三亚规模、客流/购物人数
和上海、首都机场收入；日上上海还是自 2018 年 3 月才并表。它没有跨期同店、每客毛利、各渠道
租金/保底、剩余期限、续约概率、库存周转、维护资本和资产组现金。预注册 treatment 明确要求
跨期吸收和现金证据，当前事实没有满足。

Enhanced 又把日上上海及机场新经营权放入 `newly_consolidated_channels` 条件项，令上海/机场可能
同时属于已承保基准与待验证扩张。后文的“有界”“条件范围”和风险 caveat 没有撤回这项先行
纳入。两臂都提到行业增长，但中性包没有未来行业增长或持续增长证据；这个共享假设既不是
Enhanced utility，也最多只能作为条件场景，不能支持基准吸收。

因此本轮冻结 `ENHANCED_WORSE / REASONING`：显式渠道 memory 不但没有纠正 Baseline 的材料性
错误，反而预支了渠道持续性和责任后现金资格。

## 五、防御性写作检查

- 两臂都没有让局部 `UNKNOWN` 吞掉整家公司判断；这是实际改善，不因本轮 Enhanced 失败而抹掉。
- Enhanced 增加风险项、降低信心或延长文字不产生 utility；Baseline 已处理同一责任问题。
- “保守”“有界”不能把 `UNDERWRITE` 自动改回条件性候选；经济处理由基准组成决定。
- 本轮错误不是“不够悲观”，而是在目标公司证据不足时过早给予基准信用。

## 六、审阅返回

### Finding — Enhanced 提前把证据不足的成熟渠道纳入基准

- **分类：`REASONING`**
- **经济影响：** 相对 Baseline，Enhanced 会把缺少期限、租金和 owner-cash 证据的渠道带入正常
  盈利与价值路线，可能抬高同口径盈利承载范围并低估永久损失暴露。
- **缺失事实：** 分渠道跨期吸收、租金及保底、剩余期限和续约、库存周转、维护资本、税费及
  普通股现金，以及上海/机场成熟与新并表边界。
- **禁止假设：** 不得以 FY2018 单期规模、高免税毛利或已取得经营权替代责任后现金；不得用
  caveat 冒充证据门槛已经满足；不得假设行业持续增长。
- **可执行修复：** 不修改本轮 Episode，不读取 outcome 补理由；退休该显式渠道 memory。只有新
  Blind 反馈暴露 Baseline 的材料性错误时，才从真实错误生成新的对称推理练习。
- **接受标准：** 下一项训练干预必须在结果前、基于目标公司证据，独有地纠正 Baseline 的材料
错误并改善正常盈利、owner cash、永久损失或价值路线之一；更多文字或更保守不算改善。

## 七、最终 pre-outcome freeze

```text
FRESH_CODEX_PAIR = COMPLETED
PREOUTCOME_MATERIALITY = ENHANCED_WORSE
ROOT_CAUSE = REASONING
OUTCOME_READ_AUTHORIZED = NO
METHOD_VALIDATED = NO
TRANSFER_VALIDATED = NO
```
