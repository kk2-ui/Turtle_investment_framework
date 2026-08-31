# Turtle 专家纠偏蒸馏与报告自治训练 V1

> 状态：`IMPLEMENTED / FIRST_TEACHER_PACKAGE_TRAINING_READY / METHOD_NOT_VALIDATED`
>
> 日期：2026-08-31
>
> 首个教师样本：`HK:02669` 中海物业结果已知人工纠偏报告
>
> 权限：只形成 `TRAINING_MEMORY`；不构成当前公司证据、估值、行动价格、报告发布或投资授权

## 结论

本次把“高质量人工纠偏怎样变成下一份报告可复用的能力”接成了一条可运行的链：

```text
结果已知的高质量报告 + 被接受的人工/独立审阅纠偏
  -> ExpertCorrectionTeacherPackage
  -> 条件化原则与可迁移纠偏规则
  -> company-free TRAINING_MEMORY
  -> 现有 enterprise-underwriting-training-contract.v2
  -> 未见公司/未见 cutoff 的公平 Baseline / Enhanced
  -> 盲审首次成稿
  -> 现有 cutoff settlement 与 judgment-learning-note
  -> 再应用到不同公司
```

它解决的是此前缺失的一层：仓库已经能审阅报告、也能结算 cutoff 判断，但尚不能把“人具体纠正了哪一个经济错误、为什么错、何时不适用、下一家公司先查什么”稳定编译成训练记忆。现在这层已实现；尚未证明的是它在未见报告上必然更好。

## 1. 为什么多轮自我修改不够

同一 Agent 反复重写同一上下文，通常只会增加篇幅、结构和谨慎措辞。它没有得到新的误差信号，也没有被迫区分：

- 事实缺失与推理跳跃；
- 算术正确与经济身份正确；
- 公司执行与客户、单位经济、现金结果；
- 合并资产与普通股可实现价值；
- 公司存续与永久资本损失；
- 报告写得完整与投资处理真的改变。

因此 V1 不学习终稿文风，也不把整篇优秀文章直接塞给下一家公司。它学习的是每一项材料纠偏背后的**经济对象、责任边界、错误机制、投资后果、反向条件和下一证据**。

## 2. 新增对象的责任

### 2.1 `ExpertCorrectionTeacherPackage`

一个教师包包含四层：

1. **来源快照**：目标报告、材料审阅和作者纠偏交接，全部标记为结果已知教学出处；
2. **纠偏事件**：错误形状、根因类别、经济对象、责任边界、被接受的修复及投资后果；
3. **条件化原则**：从格雷厄姆到巴菲特的原则必须写明适用对象、传导机制、目标公司证据、常见误用、反向条件和下游用途；
4. **迁移合同**：同证据预算 A/B、fresh Agent 隔离、盲审首次成稿、cutoff 结算及能力声明边界。

`scripts/expert_correction_training.py` 验证教师包，并只把第三方公司可用的字段编译成 Markdown。编译器主动丢弃：

- 教师公司名称和代码；
- 教师公司的价格、币种和估值数值；
- 教师报告的公司事实和来源引用；
- 原来错误表述及最终报告全文。

这使输出可以作为现有训练合同中的 `TRAINING_MEMORY`，但不能进入目标 Episode 的 `evidence_trace` 或 `existing_object_refs`。现有 `enterprise_underwriting_training.py` 已对这条边界执行验证，无需第二套 Episode 或训练 runtime。

### 2.2 与现有 cutoff 反馈的关系

本次没有新建 outcome 控制面。教师包只预注册三类诊断时钟：

- 实施是否穿过客户采用和单位经济；
- 正常盈利是否穿过资本吸收和普通股 owner cash；
- 存续是否真正穿过每股价值、永久损失和价值实现路线。

结果到期后仍使用现有 outcome acquisition、append-only settlement、feedback card 和 `judgment-learning-note.v2`。只有独立接纳的 cutoff 反馈才能进入下一家公司的 learning application；股价、事后管理层叙事和“最终活下来”都不能代替冻结的经营判断。

## 3. 中海物业首个教师包学到了什么

首包将八项材料纠偏蒸馏成可迁移规则：

1. 投产、中标、面积和收入增长只证明实施，不证明成熟 cohort 回报；
2. 合并现金必须经过法律实体、限制、非控股权益和上游分配桥，才能变成普通股现金；
3. 母体既可提供客户、品牌和信用，也可形成关联应收、配置和现金约束，两条机制不能相互抵销；
4. 公司总量增量回报代理不能被重命名为某一项目的永久 ROIC；
5. 算得出的反解价不等于有经济实现证据的行动价，不同路线价格不得平均；
6. 项目或现金可达性的局部未知不能擦除独立成立的成熟业务判断，但若它控制存续或主路线则可约束全局；
7. 永久损失包括低回报留存、利润侵蚀和现金不可达造成的慢性每股价值损失，不只破产；
8. 关键事实必须就近绑定一手来源，而写作补引不得偷偷改变已接受的模型、路线或价格身份。

这些规则不是“物业行业参数”。它们是报告推理的责任边界。下一家公司仍须用自己的 cutoff 前证据证明适用性。

## 4. 格雷厄姆到巴菲特原则怎样进入训练

原则不以名言、人物风格或固定估值公式进入提示词，而以条件化问题进入：

| 原则 | 目标公司的必要证明 | 防止的误用 |
| --- | --- | --- |
| 资产、盈利能力、成长价值分开 | 正常盈利、资产归属与实现、增量回报、普通股兑现 | 把现金、EPV 与成长溢价混成一个数字 |
| 留存价值取决于增量回报 | 留存用途、匹配盈利、全部资本吸收、每股兑现 | 收入增长或项目完成即成长价值 |
| 现金价值取决于索取权 | 法律实体、限制、税费、非控股、分配记录 | 合并现金全额加回或因未知全部归零 |
| 价格身份取决于路线 | 经营现金、股东收款、终值/催化机制 | 条件价、压力价和行动价平均 |
| 永久损失不只破产 | 利润方向、留存回报、现金可达、稀释/分配 | “公司能活、还有分红，所以安全” |
| 行业结构约束管理层 | 客户、竞争、公司适应、单位经济与现金传导 | 用履历、奖项、母体声誉代替经济结果 |

这能让经典原则纠正推理，但不能把书中案例结果迁成目标公司的事实或参数。

## 5. 怎样判断以后是否达到“无需用户主动纠偏”

验收对象不是字段分数，而是**首次完整成稿**。在一个未见公司或未见时期上：

```text
Baseline = 当前统一合同 + 共同 cutoff 证据
Enhanced = 完全相同 + 编译后的专家纠偏 TRAINING_MEMORY
```

两个 arm 使用相同模型、工具、证据、时间和研究预算，由两个 `fork_turns=none` fresh Agent 独立生成完整 Episode 和报告。第三个 fresh reviewer 在不知道 arm 身份、也未读取 outcome 时，检查：

- 中心论点和行业—公司传导；
- 业务机器与正常盈利；
- owner cash 和资本责任；
- 永久损失；
- 价值路线与价格身份；
- 最强反方与翻转事实；
- 一手证据的就近绑定。

只有 Enhanced 避免至少一项会改变投资处理的材料错误，或在上述一项产生材料更优的处理，同时没有新增材料事实、推理、模型、价格身份或证据错误，才产生 `TRANSFER_CANDIDATE`。篇幅更长、字段更多、语气更稳、更加悲观或结论不变都不算提升。

报告自治的单次门槛是：现有 `golden-report-review-return.v2` 没有 `OPEN / MATERIAL` finding，人工只剩非材料写作润色并作为最终批准人。跨公司能力仍需多次不同原型与公司—时间 holdout；一个中海物业教师包或一个正样本都不能标记 `METHOD_VALIDATED`。

## 6. 运行入口

验证教师包：

```bash
.venv/bin/python scripts/expert_correction_training.py validate \
  docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/01_TEACHER_PACKAGE.json
```

编译训练记忆：

```bash
.venv/bin/python scripts/expert_correction_training.py compile-memory \
  docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/01_TEACHER_PACKAGE.json \
  --output docs/development/research/training_campaigns/EXPERT_CORRECTION_CN02669_20260831/02_COMPILED_TRAINING_MEMORY.md
```

下一次 Enhanced 合同只把 `02_COMPILED_TRAINING_MEMORY.md` 登记为 `time_role=TRAINING_MEMORY`；不能把 `source_snapshots/` 或 `01_TEACHER_PACKAGE.json` 发给未见公司 arm。

## 7. 当前真实状态与下一阶段

当前已经完成：

- 首个结果已知教师报告及六份审阅/纠偏出处的耐久快照；
- 八项材料纠偏事件；
- 七张带适用边界的投资原则；
- company-free 训练记忆编译器和验证器；
- cutoff 反馈与未见报告 A/B 的预注册规则。

当前尚未完成：

- 未见公司的首次公平 A/B；
- cutoff 后经营结果结算；
- 跨公司 learning application；
- 四至六份不同原型的高质量人工纠偏教师包；
- 两个真正公司/时间留出上的报告自治验收。

因此，准确表述是：**解决方案已经可运行，中海物业首个教师包已经训练就绪；效果尚待未见样本验证。**
