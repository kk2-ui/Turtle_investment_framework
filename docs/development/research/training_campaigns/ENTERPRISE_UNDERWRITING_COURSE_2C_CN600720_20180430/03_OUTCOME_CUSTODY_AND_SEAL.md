# Course 2C 结果封存与 Custodian 交接

> 状态：`PRE_OUTCOME_SEAL / CUSTODY_NOT_YET_OPEN_AUTHORIZED`

结果窗口固定为 FY2018—FY2022，且不得在训练阶段读取。Custodian 先只确认可取得的官方年报能覆盖下列结果字段及跨期边界；在两臂 Episode 冻结前，不向 coordinator、任一 arm 或 reviewer 透露任何数值、趋势、页内文字或公司结论。

## 可结算性字段

| 层级 | 必需字段 | 用途边界 |
| --- | --- | --- |
| 行业路径 | 全国水泥产量/需求代理、价格、收入、利润、销售利润率、有效供给/错峰/产能约束的官方后续观察 | 结算全国利润池与耐久性，不能替代公司区域事实 |
| 公司传导 | 产品销量或产能承载代理、产品/区域收入与毛利、OCF、长期资产现金支出、营运资本项目、现金/受限现金、债务、固定资产/CIP、合并范围变化 | 结算区域传导、成熟核心现金与融资/边界风险 |
| 资本 cohort | 陇南及已投产线的责任单元经营代理、已终止/未投产项目状态、酒钢宏达等 perimeter bridge | 只结算预注册的 conditional/excluded 处理；无项目 OCF、维护资本或独立投入资本时不得反推项目 ROIC |

## Custodian 开封条件

只有以下条件同时成立时才允许读取或汇总数字：

- Baseline 与 Enhanced 各有一次 `fork_turns=none` fresh Codex 正式 run；
- 两份 Episode 都由 `run --agent-response` 成功完成 v2 合同绑定并落盘；
- 两份 readout 都从冻结 Episode 单向生成；
- arm 映射由 Custodian 保管，Reviewer 第一阶段只看到匿名 `Arm A` 和 `Arm B`。

结果反馈必须分为行业路径和公司传导两份文件。每份说明预注册命题得到何种支持、哪些观察仍不能区分、其对正常盈利/owner cash/永久损失/价值路线的影响；不得评价写作风格或代替 Reviewer 选择胜者。
