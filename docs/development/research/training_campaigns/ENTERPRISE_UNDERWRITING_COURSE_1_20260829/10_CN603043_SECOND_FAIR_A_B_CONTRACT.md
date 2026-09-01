# 广州酒家第二次公平 A/B 合同

> 状态：`FROZEN_BEFORE_AGENT_EXECUTION`
>
> 目标：检验顺丰负反馈后的推理修订，是否在一家具备不同经营结构的仓库零命中公司上，
> 产生有当前公司证据支撑的材料判断改善。

## 固定条件

| 条件 | Baseline | Enhanced |
| --- | --- | --- |
| 公司 / cutoff | `CN:603043` / `2019-05-01T00:00:00+08:00` | 相同 |
| 公司事实来源 | `sources/CN603043_20190501_PRE_CUTOFF_SOURCE_PACKAGE.md` | 相同 |
| Episode、反馈时钟、权力边界 | 各自合同中的同一内容 | 相同 |
| 运行方式 | `enterprise_underwriting_training.py run` 一次完整 Episode | 相同 |
| 运行模型与输出上限 | 执行时锁定后两边完全相同 | 相同 |
| 额外训练输入 | 无 | `07_POSTOUTCOME_RESEARCH_AGENDA.md` 与 `08_CAPITAL_AND_BOUNDARY_REASONING_REVISION.md` |

Enhanced 的两份额外资料登记为 `TRAINING_MEMORY`：它们可以重排问题、证据顺序、最强反方
和条件化处理，但不是广州酒家的事实，且被运行时绑定禁止出现在 `evidence_trace` 或
`existing_object_refs`。

## 预先声明的比较问题

广州餐饮品牌、月饼核心产品和食品制造扩张之间，Baseline 与 Enhanced 是否会对以下任一
**当前公司**命题形成不同且有资料支持的处理：

1. 高毛利月饼、餐饮与速冻/常态食品的正常盈利边界；
2. 经营现金、全部长期资产支出与维护资本未知下的 owner-cash 条件化处理；
3. 新基地、渠道和跨区域食品扩张是否构成可承保的增长、具名情景或永久损失路径；
4. 以成熟业务 earnings power、分业务路线或资本回报压力作为价值路线的主次；
5. 最早能够区分“品牌驱动的可复制食品经济”与“成熟高毛利业务补贴未证实扩张”的观察。

## 预先禁止的伪增量

以下均不算 Enhanced 改善：更多段落或 UNKNOWN；更低的盈利/现金范围却没有公司证据；
把全部资本开支或未证明增长回报等同维护资本；把餐饮品牌直接等同食品全国复制；把后续
结果写回结果前 Episode。若 Enhanced 没有以当前材料改变材料性企业处理，结论只能是
`NO_MATERIAL_UTILITY`；若它制造伪精确或违反边界，独立审阅应判 `ENHANCED_WORSE`。

## 结果隔离与后续

任何结果材料、市场价格、回报、CJO、正式估值或黄金报告都在两份正式训练 run 通过
完整 Episode 验证并冻结前保持封存。之后独立审阅分别检查行业路径、公司位置、生存、
适应、正常化、owner cash、永久损失和价值路线，而不是只比较字段或文风。

本合同本身不创建 `TRANSFER_CANDIDATE`、`TRANSFER_VALIDATED` 或 `METHOD_VALIDATED`，
也不授予 CJO、估值、报告或投资权限。
