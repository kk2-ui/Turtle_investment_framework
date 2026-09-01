# Course 2B 简短学习说明

> 状态：`COMPANY_HOLDOUT_COMPLETE / NO_MATERIAL_UTILITY / PACK_TRAINING_READY / METHOD_NOT_VALIDATED`
>
> 冻结裁决：[13_FRESH_REVIEW_FINAL_MAPPING_ADJUDICATION.md](13_FRESH_REVIEW_FINAL_MAPPING_ADJUDICATION.md)

## 学到了什么

上峰水泥的未见公司公平 A/B 没有证明 Enhanced 更好。两臂都正确识别了价格主导且周期条件化的行业利润池、华东成熟核心、机械现金差额与正常 owner cash 的区别、增长/房地产资本边界，以及资本沉淀与区域恶化叠加的永久损失路径。Enhanced 的三笔资本账更整齐，但 Baseline 最终也作出相同经济处理，所以投资者没有得到材料性更好的正常盈利、owner cash、永久损失或价值路线判断。

## 材料性方法修订

根因是 `MODEL`，不是要求 Agent 再写更多文字。旧 Episode 允许组件只给 `UNDERWRITE / CONDITIONALLY_UNDERWRITE / SCENARIO_ONLY / EXCLUDE_FROM_BASE / CANNOT_BOUND` 标签；这些标签没有预先固定组件是否进入基础正常盈利、是否形成 owner-cash 范围、如何改变融资压力、如何进入永久损失和价值路线。不同结构因此可能收敛成同一最终处理，却仍在结果前看起来有差异。

面向未来合同，训练运行时现要求每个组件额外给出一条显式 `component_decisions` 记录，逐项固定：

- 可比较的经济责任范围；
- 正常盈利与 owner cash 的基础、条件、情景、排除或未决用途；
- 融资压力方向；
- 永久损失和估值路线用途；
- 分开的晋级测试与撤销测试。

验证器拒绝把 `SCENARIO_ONLY / EXCLUDE_FROM_BASE / CANNOT_BOUND` 组件静默提升为基础盈利或主价值输入，并从组件账确定性派生正常盈利、owner cash、融资压力、永久损失与估值五条权威经济路线。每条 primary、corroborative、stress 或 excluded 估值路线还必须用 `valuation_route_bindings` 绑定自己的组件及该路线专属用途，并用 `route_component_requirements` 声明必需和可选组件。必需组件被排除时，不能用另一个无关 primary 组件以同名 route 代替；真正可选的组件被排除则不使整条路线失效。CJO、valuation、report handoff 和 reader brief 现在实际消费这些派生路线；对没有获得基准/条件范围权限的正常盈利、owner cash 或永久损失，下游不再沿用可能矛盾的自由文本。

历史 v1 只允许按显式登记的仓库合同完整 JSON 原样回放；任意新建、改 ID 或由 v2 降级的 v1 都会失败，冻结 v1 也不能重新渲染任务或启动 Agent。本次 Baseline、Enhanced、Reviewer 及 00--13 冻结文件没有回填或重写。

## 尚未解决什么

本次同时暴露 `DATA_COVERAGE` 上限：经济维护资本、规范化营运资本、房地产 OCF、全部长期投入、逐 cohort 回报及区域量价/利用率没有完全闭合。按非正结果停止条件，本轮不追加公司、年份、字段或结果窗口，也不启动时间轴。未来若另行预注册新验证轮，应先改可复用 acquisition 与同责任边界资本桥，再把证据交给两臂；不能用机械 `OCF - 长期资产购建` 或更长解释填补。

## 状态边界

水泥 Pack 保持 `TRAINING_READY`；`TRANSFER_CANDIDATE`、`RELEASED`、方法迁移、Agent 行业前景判断能力、时间轴效用、CJO、估值、BuyBand、黄金报告和投资权限均未取得。接口修订只是对这次失败的可执行响应，必须由未来新的认知隔离实验验证，不能反向改变本轮 `NO_MATERIAL_UTILITY`。
