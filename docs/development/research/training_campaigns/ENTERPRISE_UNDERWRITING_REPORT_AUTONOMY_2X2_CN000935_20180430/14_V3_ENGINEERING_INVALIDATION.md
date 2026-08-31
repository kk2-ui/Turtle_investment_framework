# V3 工程失效裁决

> 状态：`PAIRED_TEST_INVALID / OUTCOME_REMAINS_SEALED`

V3 在完整字段 Schema 和跨字段说明后启动。`A01_INDUSTRY_ONLY` 的 Episode 经正式 runner 绑定成功，并按冻结协议完成首份读者报告；`A00_BASELINE`、`A10_EXPERT_ONLY` 各完成一次原始 Episode，但正式绑定均为 `INVALID`；为了避免把已失效版本伪装为四臂试验，`A11_COMBINED` 未启动。V3 不进入匿名比较或 outcome 开封。

| Arm | Episode | 首份读者报告 | V3 状态 |
| --- | --- | --- | --- |
| `A00_BASELINE` | 原始响应存在，绑定 `INVALID` | 不生成 | 无效 |
| `A10_EXPERT_ONLY` | 原始响应存在，绑定 `INVALID` | 不生成 | 无效 |
| `A01_INDUSTRY_ONLY` | 绑定成功 | 已冻结 | 单格成功，不构成效用结论 |
| `A11_COMBINED` | 未启动 | 不生成 | 不执行 |

## 根因和经济影响

根因分类为 `MODEL`：task 已交付大多数语义规则，却仍把两项纯冗余的内部图关系交给 Agent 手工维护。其一，组件的 `UNRESOLVED`/`EXCLUDED` 等路线绑定只出现在 requirement 清单时，未被重复列入 `excluded_routes` 角色登记，导致 sensitivity 不能解析路线；其二，Agent 用 `DIRECT + UNKNOWN delta` 表达“机制存在但量级未知”，而 validator 对 `UNKNOWN delta` 的唯一语义是 `UNKNOWN transmission`。这两项不是四川双马的事实或经济判断，且不反映 E/I 的能力差异。

独立只读审阅在内存中仅作通用结构对齐（未改 raw 文件、未读 outcome）后，A00、A10、A01 均可经现有严格 validator 通过。这证明真正的经营判断未被该失败否定，但也证明 V3 不能用于比较训练效用。

## 修复边界

V4 仅把 compiler-owned summaries、未知量级状态和“排除当前价值输入”的路线登记纳入确定性 canonical materialization；它不改变任何 text、组件 treatment、normal earnings/owner cash/permanent-loss authority、route requirement 或资料来源。角色冲突、非零 PRESERVED delta、未授权 DIRECT、未知路线与所有经济连续性检查继续失败。四个新 fresh context 重新从一次 Episode 开始；V3 的 A01 输出不复用为 V4 任一臂。
