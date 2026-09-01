# Stage‑5 分阶段判断账本架构审阅

## 结论

**Stage‑5 execution snapshot：PASS（仅限执行与闸门，不代表方法效果）。**
快照所载 32 个 cell、9 个 `FROZEN`、23 个 `EPISODE_INVALID`、每格一次尝试及
`BLOCKED_UNTIL_ALL_ANONYMOUS_PREOUTCOME_REVIEWS_FROZEN` 与冻结回执一致。四个
case 均缺至少一臂，故处理效应不可识别；不得开 outcome、不得重跑或修写本 cohort。

**分阶段 judgment-ledger follow-up：RETURN（架构尚未达到可冻结验收）。**
快照正确指出需要 price‑free judgment ledger 与 deterministic compiler，但尚未给出
可执行的最小字段契约、诊断协议、编译器不越权边界及公平性收据。下列标准是重新预注册
之前的硬出口。

## 23/32 失败说明（按回执，不读 outcome/web/API）

23 个失败不是单一模型质量结论，而是一次性 Episode 合同把“判断”和“合同完成”耦合后的
系统性拒绝。失败回执中出现：

- normal‑earnings bridge：基准收益权威缺失、组件行 `component_id` 未知、未覆盖每个
  normal‑earnings 组件、条件区间没有条件基准（覆盖 19/23 个失败 cell，计数有重叠）；
- driver sensitivity：`LOW/BASE/HIGH` 或 range 形状无效、传导未绑定组件、route role
  不兼容（9/23）；
- value‑route / component 决策：route 组件资格、active/excluded 冲突、条件处理没有
  下游条件用途（7/23 与 1/23）；
- schema/JSON/证据完整性：schema 版本或必填字段错误、JSON 截断/分隔符错误、
  `evidence_trace.used_for` 缺失（多项重叠，至少 6 个 cell）。

这些数量按“出现过该诊断的 cell”统计，不能相加为 23。其经济影响是完成率和 arm 分布
受序列化/结构门影响，导致每家公司都缺四臂，进而无法估计 industry、expert 或交互效应；
不能把 invalid 当作零分，也不能据此声称某记忆层无效。缺失事实是“哪些字段可由共同 source
package 直接回答、哪些字段只是下游派生”；禁止假设是 Agent 能安全猜测 route/component
ID、基准收益权威或敏感性数值。

## 责任边界：Agent 判断 vs compiler 派生

### Agent 必须提交的判断（price‑free）

1. 公司/行业处境、核心与非核心 component 列表及每项 economic scope；
2. 每项 component 的 `UNDERWRITE / CONDITIONAL / SCENARIO / EXCLUDE / CANNOT_BOUND`、
   base/conditional normal earnings 用途、owner‑cash 用途、融资压力、永久损失路径、
   promotion/invalidation 条件；
3. 主/协同/压力 value route 选择及理由，最强反方、reversal observations、关键 UNKNOWN
   （含原因与下一验证）；
4. 对共同 source package 的 evidence IDs、locator、责任边界；只有证据支持时才提交
   bounded sensitivity magnitude，否则提交 `UNKNOWN`（不得以 0 代替）；
5. 一条叙事性的 underwriting thesis。以上内容由 Agent 负责经济含义，不能由 schema
   默认值或记忆文本代填。

### Compiler 可以且应该自动派生的内容

- 身份复制与一致性（company、cutoff、sample identity、schema/version）；
- component decision summary 及从 component decision 计算的 `normal_earnings_use`；
- 每条 route 的 required/optional component 集合、binding role compatibility、active
  与 excluded 互斥检查；
- 唯一 `REFERENCE_EARNINGS` 及 bridge 行覆盖、重复键、证据引用闭合检查；
- sensitivity 的 shape、组件/route 存在性、role 兼容性、UNKNOWN/BOUNDED/PRESERVED
  传导规则及 reversal 引用解析；
- price‑free reader bridge、确定性排序和报告字段投影；
- 结构化 diagnostics（`field_path`, `code`, `severity`, `owner=AGENT|COMPILER`,
  `blocking`, `remediation`）。

Compiler **不得** 选择组件、补写收益基准、估计敏感性幅度、把 UNKNOWN 变成 0、升级
scenario/excluded 为 base、改变 route 经济角色，或生成价格/回报/行动。任何经济缺口应
返回 `JUDGMENT_INCOMPLETE`/`EVIDENCE_INSUFFICIENT`，而非静默修复。

## 分阶段账本最小接口

建议冻结三个只读对象，而非要求 Agent 一次生成完整 Episode：

| 阶段 | Agent 输出 | Compiler 输出/闸门 |
|---|---|---|
| J0 context | 身份、组件、行业—公司问题、证据引用 | source/cutoff/allowlist 绑定；字段可回答性检查 |
| J1 economics | component treatments、normal earnings/owner cash/permanent loss 方向、route 选择、UNKNOWN 与 reversal | decision summary、route requirements、bridge/sensitivity 结构和诊断 |
| J2 thesis | strongest rival、中心路径、监测与反方叙事 | price‑free reader bridge；仅在 J0/J1 accepted 后可消费 |

每阶段都保存输入、输出、compiler version、diagnostics 和 `PENDING/READY/ACCEPTED` 状态。
J1 不应要求尚未由 source package 支持的精确收益范围；允许“方向 + UNKNOWN + 验证条件”，
由后续 evidence stage 再升级。只有 compiler 通过且独立 reviewer 接受，才投影为严格
`EnterpriseUnderwritingEpisode`；失败原因必须可定位到 Agent 判断或 compiler 合同。

## 2×2 公平性硬标准

1. A00/A01/A10/A11 使用同一 cutoff、byte‑identical common source、同一 J0/J1/J2 schema、
   compiler 版本、超时、调用次数、模型/reasoning、工具权限和 evidence/token budget；
2. industry memory 与 expert memory 只能作为各自 arm 的 company‑free 提示，不能携带
   target facts、答案、额外字段模板或 compiler 特权；四臂编译阶段完全相同；
3. 每臂一次 fresh run、无 retry/rewrite。compiler 失败不得触发该臂重跑；可在独立
   validation fixture 上测试 compiler，但不能回写 cohort；
4. 预先登记 completion、diagnostic 类别和 substantive judgment 质量三类终点，分别报告
   结构成功率与内容差异；不得将 invalid 直接记为最差质量；
5. 至少一个 company‑local 四臂全冻结、匿名 review PASS 后，才有资格进入 outcome gate；
   不足时保持 outcome sealed，效应标记 `UNIDENTIFIABLE`；
6. reviewer 只看匿名 compiled outputs 与统一评分表，不能看到 memory 映射、失败臂的
   后验修复或 compiler 内部提示。预算差异（额外字段、额外验证轮次、隐藏重试）均属
   `REASONING`/`MODEL` confound，必须 fail closed。

## 风险分类与整改验收

### DATA_COVERAGE — RETURN（材料性）

**问题/影响：** 一次性 strict Episode 要求基准收益权威、逐组件 bridge 和敏感性幅度，
而共同 source package 未必直接提供；造成 19/23 bridge 类拒绝和选择性 arm attrition，
使 treatment effect 不可识别。**禁止假设：** 不得从 OCF、单年利润或 prose 推出授权基准。
**整改：** 将 J1 最小包改为“有证据的区间或 UNKNOWN+reason+promotion test”；把定量幅度
证据作为可选升级阶段。**接受条件：** 在冻结 source package 上，四臂均可提交合法 UNKNOWN
并通过 compiler；缺证据只产生可审计 diagnostic，不产生伪精确值。

### ACQUISITION_MODULE — PASS（当前非阻塞，需守住边界）

快照回执没有 provider/API 或 outcome 污染证据。后续 compiler 必须只消费 source manifest
中的 evidence IDs/locator，并在 source 缺口时返回 `EVIDENCE_INSUFFICIENT`；不得让 industry
memory 变成 target evidence。**接受条件：** source/cutoff/allowlist 绑定在 J0 通过，且
匿名审阅可复核每个引用。

### REASONING — RETURN（材料性）

**问题/影响：** Agent 同时承担经济判断和严格 route/sensitivity 连接，导致 route role
错配、条件处理无下游用途（7+1 个 cell），失败率与 memory arm 纠缠。**禁止假设：**
不能把 route ID 记忆或模板当作公司判断。**整改：** Agent 只声明经济语义与证据；compiler
负责键存在性、覆盖和 role 兼容诊断，并允许 UNKNOWN。**接受条件：** 独立 fixtures 覆盖
base/conditional/scenario/excluded 四类路径，错误均归因到明确 owner，且不改经济含义。

### MODEL — RETURN（材料性）

**问题/影响：** strict v2 把 valuation route eligibility、normal earnings authority 和
component binding 作为同一提交契约；Agent 任意 route 选择即触发 fail，可能将真实经济
判断误判为无效。**禁止假设：** compiler 不得替 Agent 选主模型或升级 route。**整改：**
建立只读 route-role registry；J1 记录“为何适用/不适用”，compiler 仅验证一致性并输出
route diagnostics。**接受条件：** route 选择在同一输入下可重放；不支持的 route 明确
`UNRESOLVED`，不会被静默排除或平均。

### WRITING — RETURN（非经济但阻断完成）

**问题/影响：** 至少两个 cell 出现 JSON 分隔符/截断，另有 schema completeness 错误；
这不是投资判断错误，却阻断四臂冻结。**禁止假设：** 不得通过手改、重试或把截断 JSON
拼接为成功。**整改：** 使用结构化 staged packet、长度/JSON preflight 和 deterministic
serialization；一次失败留下原始响应及诊断。**接受条件：** 合法最小 J0/J1/J2 包在统一
序列化器下 100% 可解析；任何超长或截断均为 terminal invalid 并可定位。

## 最终闸门

在上述 DATA_COVERAGE、REASONING、MODEL、WRITING 的 RETURN 项关闭前，分阶段架构不得
标记 `READY_FOR_PREREGISTRATION`，不得重用 23/32 cohort，也不得解封 outcome。关闭后需
独立工程审阅确认：同一 compiler 在四臂及 synthetic fixtures 上可重放、诊断 owner 正确、
预算公平收据完整，并至少产生一个四臂 company case，才可进入匿名 review 与后续 outcome
结算。
