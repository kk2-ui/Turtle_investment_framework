# 研究前瞻冻结附件

状态：`PREPARED / FROZEN / EARLY_PENDING / TERMINAL_PENDING / CLOSED`

用途：为一个有界的**方法实验**保存结果尚未知时的经营机制判断。它不替代完整公司研究，也不生成估值、价格、回报或交易动作。

## 冻结身份与材料边界

- experiment / freeze ID：
- 判断等级：`MECHANISM_SIGNAL_PROBE / JUDGMENT_SELECTION_EPISODE`。
- 若为 `JUDGMENT_SELECTION_EPISODE`，先冻结当时考虑的候选机制集合：被选的 `central_hypothesis_id`、仍保留的最强反方、其他实质候选为何被合并/排除；结果期不得补称一个未列出的旧机制“本来也是判断”。该集合必须先在机制实验卡的“假设空间筛选”表中完成：每个 material candidate 都要写明若为真会位移的本轮经济边界、FJ、来源任务或选择资格。凡是仍能解释共同事实、会作出这种位移、却没有可分叉观察的候选，均使本卡降为 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`。不解释共同事实或不位移本轮问题的事项只能为 `OUT_OF_SCOPE`，并另记其独立问题，不得被误写为已证伪。随后附上以下选择表；每行都必须是 cutoff 前已记录的、对 H-A/H-B 有不同方向含义的事实或传感器。共同事实、同一来源的重复转述、管理层语气、篇幅、已知结局、价格和投资回报不能填入。若没有合格行，显式写 `NO_PRIMARY`，不得强行选边。

  | selection evidence ID | 被解释的当前事实 | source lineage | 更符合 H-A / H-B 的方向原因 | 为什么另一方不能同样解释 | 它导出的未来顺序/阈值，以及为什么不是任意设定 | 若该观察失真会如何降级 |
  |---|---|---|---|---|---|---|
  |  |  |  |  |  |  |  |

- 若为 `JUDGMENT_SELECTION_EPISODE`，还须冻结一个简单、公平的 `baseline_rule`：规则、输入、同口径预测、与主路径不同的预测区域及其窗口；不同区域必须由上表的机制传导推出，不能只把当前数字改成一个更有利的阈值。主路径与基线同向时，后续结果只能记为 `BASELINE_NONDISCRIMINATING`，不计作方法增益；若无法在冻结前写出不同区域，应退回 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`。
- frozen at：
- cutoff：
- 决定性经营问题：
- 允许的截止日前 source package / source IDs：
- 明确未读的结果期材料：
- 冻结后的结果暴露边界：除各 future signal 在其 `DUE_FOR_ACQUISITION` 窗口内由结果期执行契约选中的 source body 外，所有 post-cutoff 公司结果（包括预先标作 `NONDIAGNOSTIC` 的中间“脉冲”）均为 `UNREAD`。若已读，记录 `OUTCOME_EXPOSURE_BREACH`；本实验不得再作为研究者判断或方法学习的前瞻证据，只可作为管线训练。
- 冻结后不可修改的字段：共同事实、H-A/H-B、指标定义、阈值、窗口、允许来源、结算规则。

## 共同事实与竞争机制

- 双方共同事实：
- H-A：
- H-B：
- 不能归因或仍为 `UNKNOWN` 的箭头：

### 适用环境与预注册的 regime break

| condition ID | cutoff 状态 / 来源 | 受约束的 H-A/H-B 箭头、FJ 或 critical assumption | break 观察、允许来源与窗口 | 触发后的动作 |
|---|---|---|---|---|
|  |  |  |  | `CONTINUE_AS_IN_SCOPE / CLOSE_AND_REFREEZE_NEW_EPISODE` |

只填写会改变 pair 因果顺序、指标含义或双方可比较性的条件；一般需求、价格、竞争、利率或周期变化仍须由 H-A/H-B 预测。`CLOSE_AND_REFREEZE_NEW_EPISODE` 只能由冻结前已定义、结果期可观察的 break 触发：保留原 source/extraction，但该结果不得作为原 regime 的主路径选择、迁移或 L3–L5 方法证据；随后以新 cutoff 建新 episode。未冻结的“环境变化”只能是之后的新问题，不得解释或重写原结算。

## 前瞻经营观察

| signal | 机制 A | 机制 B | 指标与定义 | 期间 | 结果来源与窗口 |
|---|---|---|---|---|---|
|  |  |  |  |  |  |

每一个 signal 必须有 A-only 与 B-only 区域；若定义变更、来源不合格或双方都可解释，结果为 `MEASUREMENT_MISMATCH`、`NOT_DIAGNOSTIC` 或 `MIXED`，而不是事后重写阈值。

### 结果期计量连续性合同（每一个 future signal 必填）

在冻结前，逐项写清结果期**如何**重建上表中的指标，而不只是写“将来读公司披露”：

| signal | 冻结谓词的指标/单位/调整 | 预期官方披露标签与文件范围 | 允许的转换 | 明确禁止的代理/替代 | 定义或口径变化时的停止动作 |
|---|---|---|---|---|---|
|  |  |  |  |  | `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC` |

没有逐项映射时，不能把未来总收入、利润、管理层解释或其他看似相近的 KPI 补作结果。这个合同不要求预知未来数字；它只要求在未知结果时决定什么才算同一个观察。已冻结的 legacy experiment 不得事后补写它；它们仍按原冻结定义和原有停止规则结算。

### 结果期执行契约（P-34 后的新实验必填）

冻结时还须基于 [结果期采集契约模板](research_outcome_acquisition_contract.json) 创建同目录的 `08_outcome_acquisition_contract.json`。它把已经冻结的 signal 变成机器可读的 `claim → metric / 期间 / 来源类型 / 发布者域名 / 窗口 / 初始或最新披露版本政策 / label / locator`；对于 `MECHANISM_SIGNAL_PROBE / NO_PRIMARY`，还必须逐字转写冻结卡已有的 H-A/H-B、阈值谓词、信号阶段和 locator，以供机械导出 `A_ONLY / B_ONLY`。它不能**新增或改写**当前事实、机制、预测、实际值、价格、回报、概率或 verdict。

结果到期后，先用它保存完整候选源 inventory（每个 source 指向可结算的 `claim_id`）、selected raw/reader、read attestation 和逐字 extraction；系统按冻结的 `INITIAL_DISCLOSURE / LATEST_OFFICIAL_AS_OF_EVALUATION` 从该 inventory 选择版本。对完整 CJO，只有 extraction 才能生成 settlement observation；对轻量 `NO_PRIMARY` 探针，先基于[结果暴露证明模板](research_outcome_exposure_attestation.json)写入 `11_outcome_exposure_attestation.json`，以 read audit 的 source IDs 绑定“无非 claim 结果暴露”或显式记录 breach，再以事件唯一的 `settlement_id` 调用 `live_forward_signal_settlement settle --event-root <experiment-output>`。生成物固定在 `outcome_events/<settlement_id>/09_signal_settlement.json`；同一事件的 feedback 在 `outcome_events/<settlement_id>/10_judgment_feedback.json`。不同信号/时钟必须使用不同 ID，CLI 拒绝覆盖已有事件。breach 仍保留机械结算，标为 `OUTCOME_EXPOSED_TRAINING_ONLY` 且不生成可学习 cards。`07_settlement.md` 只能按事件转录这些输出。候选源不足、原文未读、定义变化或指标未披露时，保持 `INCOMPLETE / MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC`，不能用手填值或代理 KPI 补足。

非 claim 的 post-cutoff 结果不得放入 inventory、source package、reader、红队或学习复盘；`NOT_YET_DUE` 的正确动作是等待，而非先读一份不会被机械结算的“背景脉冲”。这个边界不改变已冻结的 H-A/H-B 或阈值；它只防止无行动价值的结果提前进入研究者视野。

## 结算规则与边界

- 早期结果如何只更新一条机制箭头：
- 多次观察如何组成 `SUPPORTS_PRIMARY / SUPPORTS_RIVAL / MIXED / NOT_DIAGNOSTIC`：
- 何时关闭对象而不继续扩读：
- 禁止输出：公司总判断、正常盈利/现金总量、估值、价格、回报、交易动作，除非另有独立且范围匹配的研究。

## 预先承诺的学习动作

结果不只决定主/反方，也必须在冻结前决定下一次研究流程会如何改变：

| 到期结果 | 对本机制箭头的记录 | 对下一次方法的不可回写动作 |
|---|---|---|
| `A_ONLY`（早期） | 仅支持对应早期箭头，终局仍待结算。 | 保留该信号进入下一窗口；不得升级公司总判断。 |
| `B_ONLY`（早期） | 仅支持替代机制的对应箭头。 | 复盘主机制缺失的中间观察；下一对象必须补该缺失观察或缩小机制表述。 |
| `MIXED` | 当前信号不足以给出稳定方向。 | 将持续性拆成更窄的、先后有序的信号；不以更多同类材料修补。 |
| `MEASUREMENT_MISMATCH / NOT_DIAGNOSTIC` | 不裁决任一机制。 | 修复来源/定义契约或停用该信号；不得换成更有利的代理指标。 |
| 全部预注册信号完成 | 按冻结规则合成机制 verdict。 | 只对方法作 `RETAIN / MODIFY / REJECT / INSUFFICIENT_TEST` 裁决，并把实际变更定位到流程、模板或禁用项。 |

## 追加结算位置

- 结果只能追加至同目录的 `07_settlement.md`；本附件不因后来结果改写。
- 后续 source package：
- 方法复盘文件：
