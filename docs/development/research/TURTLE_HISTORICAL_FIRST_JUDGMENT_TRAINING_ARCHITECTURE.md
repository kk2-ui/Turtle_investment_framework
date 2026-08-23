# Turtle 历史优先的企业判断训练架构

> 状态：`CURRENT / IMPLEMENTED_CONTROL_LAYER / FIRST_PROGRAM_CONTRACT_READY`
>
> 日期：2026-08-23
>
> 目标：用历史 PIT 逐步回放训练企业判断，以冻结历史留出检验泛化，以少量真实前瞻 episode 校准部署纪律；外部披露等待不得阻断训练主线。

## 1. 产品定义

Turtle 的“训练”不是在本仓库中重新训练基础模型权重。它训练的是可持久、可复核并能改变下一份报告的研究系统：

```text
公司与行业状态表示
  -> 竞争机制和最强反方
  -> 决策—客户—单位经济—现金—资本回报判断
  -> 结果揭示与错误定位
  -> 方法约束和行业机制
  -> 下一家公司冻结前字段
  -> 黄金报告研究议程与判断前置物
```

一次案例只有在改变下一家不同公司的问题、证据门、H-A/H-B、信号、计量合同或停止规则，并由独立 reviewer 确认后，才形成系统学习。阅读更多材料、写出更好的事后故事或把案例导入数据库，都不是训练闭环。

## 2. 四条独立通道

| 通道 | 主要材料 | 是否改变当前方法 | 能证明什么 | 不能证明什么 |
|---|---|---:|---|---|
| `HISTORICAL_TRAINING` | cutoff 前事实与结果包严格隔离的历史 PIT episode | 是 | 历史条件下的刻意练习、错误诊断和跨公司迁移 | 实时预测优势、概率校准或投资收益 |
| `HISTORICAL_HOLDOUT` | 在方法版本冻结前预留的未揭盲公司和时期 | 否 | 冻结方法是否泛化到未参与规则形成的对象 | 见结果后继续修改同一版本仍算留出 |
| `HISTORICAL_TEACHING` | 研究者或模型已经知道结果的案例 | 只形成边界和禁止替代，不生成正式方法 learning | 反例、测量边界和常见因果错误 | 选对/选错、样本命中或方法优势 |
| `LIVE_SENTINEL` | 结果尚未发布的少量正式 episode | 结果到期后才允许 | 成熟系统在未知结果环境中的部署纪律和外部有效性 | 在等待期间阻断历史训练，或以单次结果证明完整能力 |

项目状态按通道投影。`LIVE_SENTINEL = WAITING_EXTERNAL` 与 `HISTORICAL_TRAINING = ACTIVE` 可以同时成立；此时系统总状态是 `ACTIVE`，不能标为 `blocked`。只有内部工件失效且没有其他可执行训练时，才进入 `NEEDS_REPAIR`。

## 3. 行业训练单元

### 3.1 不是只研究最后的幸存者

行业 cohort 必须按历史 cutoff 时可见的资格形成，后来是否存活不得参与选择。训练宇宙应保留当时符合条件的：

- 后来持续经营者；
- 长期平庸或资本回报恶化者；
- 被收购、私有化或退出上市者；
- 财务危机、业务收缩或消失者；
- cutoff 后进入行业的新竞争者，作为后续时期的新成员而非回填到早期宇宙。

“存活”只是最末端观察之一，不是正确答案。企业可能存活却持续毁灭资本，也可能退出上市但完成了合理的资本回收。终局仍按决策实施、客户/竞争反应、单位经济、营运资本与现金、资本回报五层分别结算。

### 3.2 公司 × 时点，而不是报告篇数

同一家公司可切成多个滚动时点，但这些时点属于同一 `company_cluster_id`，不得冒充多个独立公司样本。一个行业的建议首轮形态是理论抽样后的横纵面板，例如五至六家公司、三个结构时期；数量不是硬门，关键是同时包含：

- 一个 focal 公司；
- 至少一个只改变关键中介条件的 near miss；
- 至少一个改变行业状态或外部约束的 boundary；
- 相同交易点和可比较结果字段；
- 公司消失、披露中断和口径改变的保守处理。

每个时期只读取当时可得资料。下一时期可以看到上一时期已经结算的 learning，但不能看到本时期 cutoff 后的结果。

## 4. 历史逐步回放

这套运行方式属于 walk-forward historical simulation / rolling-origin backtesting，并结合过程追踪和案例迁移：

1. **形成 cohort。** 在 cutoff 时按行业、客户问题、责任单元和决策域建立完整候选框，禁止按后来结果挑样本。
2. **冻结输入。** curator 只交付 cutoff 前原件、精确指标切片和当时可得行业状态；管理层归因和结果包隔离。
3. **独立判断。** researcher 写企业系统图、H-A/H-B、最强反方、简单基线、关键假设及五层观察时钟。
4. **冻结方法对象。** 固定判断、阈值、允许结果来源、口径变化政策和停止规则；不能见结果后补写。
5. **分层揭示结果。** 结果 reader 只按预登记包读取下一窗口，分别结算五层时钟，允许 `UNKNOWN / NOT_DIAGNOSTIC / MEASUREMENT_MISMATCH`。
6. **双轴诊断。** 同时记录企业经济链错误位置与研究交付根因，说明经济影响、缺失事实、禁止假设、修复和接纳标准。
7. **方法迁移。** learning note 只能改变下一家不同公司的一个可定位冻结前字段，并形成 application receipt。
8. **留出揭盲。** 方法版本冻结后才打开预留公司/时期；留出结果只评价该版本，不反向修改它。

同一历史可以产生多个滚动 episode，但前一时点的结果只有在真实时间上已进入下一时点信息集后，才能成为下一时点输入。

## 5. 数据与权限模型

训练计划使用三个正交身份，禁止再用一个 `episode_class` 同时表达所有含义：

| 维度 | 字段 | 例子 |
|---|---|---|
| 程序职责 | `lane` | `HISTORICAL_TRAINING / HISTORICAL_HOLDOUT / HISTORICAL_TEACHING / LIVE_SENTINEL` |
| 来源与结果隔离 | `provenance_role + outcome_access` | `HISTORICAL_SELF_REPLAY + PIT_OUTCOME_SEALED` |
| 后续权限 | `learning_eligibility` | `SELECTION_METHOD_ELIGIBLE / EVALUATION_ONLY / TEACHING_ONLY / MECHANISM_SETTLEMENT_ONLY` |

硬边界如下：

- 历史训练只有在 PIT 结果被隔离、选择已准入且结果具诊断性时，才可生成正式 method learning；
- `NO_PRIMARY` 仍可结算机制和训练弃权纪律，但不能伪装为路径选择学习；
- 留出永远是 `EVALUATION_ONLY`，不得生成或应用同一方法版本的 learning note；
- 结果已知教学永远是 `TEACHING_ONLY`，不得进入选择成绩；
- 实时哨兵在结果未发布时只等待或执行到期采集，不提前解释，也不阻断其他通道。

## 6. 状态机与控制面

版本化计划契约为 `config/judgment_training_program_v1.json`，schema 为 `schemas/judgment_training_program.schema.json`。入口为：

```bash
.venv/bin/python scripts/judgment_training_program.py validate config/judgment_training_program_v1.json
.venv/bin/python scripts/judgment_training_program.py register config/judgment_training_program_v1.json --db stock_analysis.db
.venv/bin/python scripts/judgment_training_program.py status JTP:turtle-historical-primary-v1 --db stock_analysis.db --as-of 2026-08-23T18:00:00+08:00
```

方法训练完成且 application receipt 已由 reviewer 接纳后，使用一次性 `freeze-method` 锁定版本，之后才允许揭盲 holdout：

```bash
.venv/bin/python scripts/judgment_training_program.py freeze-method JTP:turtle-historical-primary-v1 --method-version enterprise-judgment-method-v1 --frozen-at <ISO-8601> --db stock_analysis.db
```

训练计划与 feedback claim 使用同一生产数据库，但职责不同：训练计划决定通道、抽样和是否允许学习；feedback control 保存每条冻结 claim 的到期、采集、结算、诊断和应用事件。现有 `historical_backtest`、`judgment_feedback`、`judgment_learning` 和报告 handoff 保持唯一语义实现，不另建平行结算器。

## 7. 如何进入黄金报告

历史训练不会把整篇旧报告或事后结论塞入新报告上下文。只有以下两类产物可进入生成：

1. 经 feedback、诊断、learning note、method review、跨公司 application receipt 和 cutoff replay 接纳的窄方法改变；
2. 满足跨公司、跨期、反例和独立审阅门的行业机制，按其可用时间进入行业知识快照。

新报告的 `RESEARCH_AGENDA` 接收这些问题、证据门、禁止替代和待验证机制；`JUDGMENT_SYNTHESIS` 仍只来自本公司、同 cutoff 的正式判断；`INVESTMENT_ENRICHMENT` 只能在公司判断完成后追加估值、价格和回报。历史结局不得直接成为当前公司事实或中心路径。

系统效果通过以下行为变化观察：

- 更早识别行业交易点和责任单元；
- 更少把收入、销量、投产、正 OCF 或存活当作机制成立；
- 更早保留材料性 `UNKNOWN`；
- 正常利润、owner cash、永久损失、价值和回报由同一经营驱动传播；
- 独立留出中仍能提出正确的分叉问题或正确弃权。

## 8. 当前计划与退出门

第一版计划契约已定义以下职责；只有在生产数据库执行 `register` 后，才可称为已登记：

- R-62 鹏鼎汽车／服务器 PCB 扩产：`HISTORICAL_TRAINING`，先完成 cutoff replay 和正式 control-plane 结算；
- R-61 沪硅少数股权收购：`HISTORICAL_HOLDOUT`，已预留 cutoff 冻结文件，方法冻结前保持 `WAITING_FOR_METHOD_FREEZE`；
- R-56 晶科与 R-58 美的—小天鹅：`HISTORICAL_TEACHING`，结果已知或曾参与规则形成，只训练边界，不能产生正式 method learning；
- R-25、R-21、R-78：`HISTORICAL_TEACHING`；
- R-54：`LIVE_SENTINEL`，只按原合同处理官方结果。

下一阶段不以案例数量或最新披露为出口，而以一条完整历史学习链为出口：

```text
R-62 PIT freeze
  -> 独立结果读取与五层结算
  -> 材料性诊断
  -> learning 改变不同公司冻结字段
  -> method version freeze
  -> R-61 holdout reveal
  -> 独立评价，不回写同一版本
```

完成这条链后，才扩展第二个决策域和更大的行业横纵面板。真实前瞻哨兵可提前冻结以启动时间钟，但它的正式能力验收位于历史训练、历史留出和黄金报告接线成熟之后。

## 9. 能力声明边界

| 已完成状态 | 允许声明 |
|---|---|
| 历史训练完成 | 方法在历史 PIT 条件下形成了可审计改变 |
| 历史留出完成 | 冻结方法在指定未见公司/时期表现出有限泛化或明确失败 |
| 黄金报告接线完成 | 历史学习确实改变了报告研究议程和经营—财务传播 |
| 多个真实哨兵结算 | 获得有限的部署外部有效性证据 |

以上任何单层都不能独自证明投资优势、准确率、经验概率、管理层普遍能力或组合收益。
